"""Run from ShellyOTA/: python -m unittest discover tests"""

import hashlib
import http.server
import json
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelly_ota import builder, devicegen, firmware, lint, logwatch, profile, rpc, sender  # noqa: E402


class FakeRpcShelly:
    """Shelly simulator with RPC, optional digest auth (SHA-256) and UDP debug log."""

    def __init__(self, password=None, slot=1, app="DuoBulbG3", target_slot=None):
        self.app = app
        self.password = password
        self.slot = slot
        self.target_slot = target_slot  # if set, the debug log announces "Storing core dumps to app_<n>" like a real updater
        self.udp_addr = None
        self.updates = []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def _authorized(self, method):
                if not outer.password:
                    return True
                header = self.headers.get("Authorization", "")
                if header.startswith("Digest"):
                    f = dict(p.strip().split("=", 1) for p in header[7:].split(","))
                    f = {k: v.strip('"') for k, v in f.items()}
                    h = lambda t: hashlib.sha256(t.encode()).hexdigest()
                    ha1 = h(f"admin:fake:{outer.password}")
                    ha2 = h(f"{method}:{f['uri']}")
                    if f["response"] == h(f"{ha1}:n0nce:{f['nc']}:{f['cnonce']}:auth:{ha2}") and f["uri"] == self.path:
                        return True
                self.send_response(401)
                self.send_header("WWW-Authenticate", 'Digest qop="auth", realm="fake", nonce="n0nce", algorithm=SHA-256')
                self.send_header("Content-Length", "0")
                self.end_headers()
                return False

            def _reply(self, obj):
                body = json.dumps(obj).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                u = urllib.parse.urlparse(self.path)
                if u.path == "/rpc/Shelly.GetDeviceInfo":
                    return self._reply({"app": outer.app, "ver": "2.0.1", "slot": outer.slot,
                                             "auth_en": bool(outer.password)})
                if u.path == "/rpc/Shelly.Update":
                    if not self._authorized("GET"):
                        return
                    url = urllib.parse.parse_qs(u.query)["url"][0]
                    outer.updates.append(url)
                    threading.Thread(target=lambda: urllib.request.urlopen(url).read()).start()
                    return self._reply({})
                self.send_error(404)

            def do_POST(self):
                if not self._authorized("POST"):
                    return
                req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if req["method"] == "Sys.GetConfig":
                    return self._reply({"id": 1, "result": {"debug": {"udp": {"addr": outer.udp_addr}}}})
                if req["method"] == "Sys.SetConfig":
                    outer.udp_addr = req["params"]["config"]["debug"]["udp"]["addr"]
                    if outer.udp_addr:
                        host, port = outer.udp_addr.rsplit(":", 1)
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.sendto(b"OTA: hello from fake shelly\n", (host, int(port)))
                        if outer.target_slot is not None:
                            sock.sendto(f"shos_ota_esp32_back:949 Storing core dumps to app_{outer.target_slot} "
                                        f"(0x200000)\n".encode(), (host, int(port)))
                        sock.close()
                    return self._reply({"id": 1, "result": {"restart_required": False}})
                self._reply({"id": 1, "error": {"code": -105, "message": "unknown"}})

            def log_message(self, *a):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.addr = f"127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class SlotAndChipTests(unittest.TestCase):
    def test_c6_image_accepted_and_wrong_chip_rejected(self):
        hdr = bytearray(24)
        hdr[0], hdr[1] = 0xE9, 2
        hdr[12:14] = (0x000D).to_bytes(2, "little")
        body = bytearray(100)
        body[8:12] = builder.APP_DESC_MAGIC
        img = bytes(hdr) + bytes(body)
        self.assertEqual(builder.check_app_image(img, "esp32c6", 1 << 20, "app_0"), [])
        with self.assertRaises(builder.OtaError):
            builder.check_app_image(img, "esp32c3", 1 << 20, "app_0")

    def test_send_warns_on_slot_0(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        z = tmp / "t.zip"
        shutil.copy(firmware.cached_zip("DuoBulbG3"), z)
        s = FakeRpcShelly(slot=0)
        self.addCleanup(s.close)
        lines = []
        sender.send(profile.load_profile("DuoBulbG3"), z, s.addr, port=0, dry_run=True, out=lines.append)
        self.assertTrue(any("slot 0" in l and "WARNING" in l for l in lines), lines)
        s.slot = 1
        lines.clear()
        sender.send(profile.load_profile("DuoBulbG3"), z, s.addr, port=0, dry_run=True, out=lines.append)
        self.assertFalse(any("WARNING" in l for l in lines), lines)


class VariantTests(unittest.TestCase):
    def test_zigbee_profile_has_parent_and_own_firmware(self):
        zb = profile.load_profile("PowerStripZB")
        self.assertEqual(zb.parent, "PowerStrip")
        self.assertIsNone(profile.load_profile("PowerStrip").parent)
        self.assertNotEqual(firmware.cached_zip("PowerStripZB"), firmware.cached_zip("PowerStrip"))

    def _send_dry(self, app, profile_name, **kw):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        z = tmp / "t.zip"
        shutil.copy(firmware.cached_zip(profile_name), z)
        s = FakeRpcShelly(app=app)
        self.addCleanup(s.close)
        lines = []
        sender.send(profile.load_profile(profile_name), z, s.addr, port=0, dry_run=True, out=lines.append, **kw)
        return lines

    def test_zigbee_device_accepted_by_base_package_via_compatible_pattern(self):
        lines = self._send_dry("PowerStripZB", "PowerStrip")
        self.assertTrue(any("compatible pattern" in l for l in lines), lines)

    def test_exact_match_has_no_note(self):
        lines = self._send_dry("PowerStripZB", "PowerStripZB")
        self.assertFalse(any("compatible pattern" in l for l in lines), lines)

    def test_unrelated_device_still_refused(self):
        with self.assertRaises(builder.OtaError):
            self._send_dry("PlugMG3", "PowerStrip")

    def test_alt_missing_in_reply_is_an_error(self):
        orig = firmware.query_update_api
        firmware.query_update_api = lambda uid, insecure=False: {"stable": {"url": "https://x/y"}, "alt": {}}
        self.addCleanup(setattr, firmware, "query_update_api", orig)
        with self.assertRaises(builder.OtaError):
            firmware.fetch("NoSuchDevice", "Base", alt="Variant", fw_dir=Path(tempfile.mkdtemp()))


class RestoreNoteTests(unittest.TestCase):
    def test_restore_prints_note_and_hints_when_device_is_silent(self):
        import argparse, contextlib, io
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        import ota
        args = argparse.Namespace(device="PlugMG3", version=None, ip="127.0.0.1:1", host=None, port=0, timeout=2,
                                  yes=True, dry_run=False, force=False, user="admin", password=None, watch=0,
                                  log_port=0, ignore_slot=False)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            with self.assertRaises(builder.OtaError) as cm:
                ota.cmd_restore(args)
        self.assertIn("only works while the Shelly firmware is still running", buf.getvalue())
        self.assertIn("UART", str(cm.exception))


def free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.zip = self.tmp / "t.zip"
        shutil.copy(firmware.cached_zip("DuoBulbG3"), self.zip)
        self.profile = profile.load_profile("DuoBulbG3")

    def _shelly(self, **kw):
        s = FakeRpcShelly(**kw)
        self.addCleanup(s.close)
        return s

    def test_log_is_captured_and_setting_restored(self):
        s = self._shelly()
        lines = []
        logwatch.watch(s.addr, "127.0.0.1", free_udp_port(), 1.5, out=lines.append)
        self.assertTrue(any("hello from fake shelly" in l for l in lines), lines)
        self.assertIsNone(s.udp_addr)

    def test_send_with_watch(self):
        s = self._shelly()
        lines = []
        sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, timeout=10, watch=1,
                    log_port=free_udp_port(), out=lines.append)
        self.assertEqual(len(s.updates), 1)
        self.assertTrue(any("log|" in l for l in lines), lines)

    def test_send_with_password(self):
        s = self._shelly(password="secret")
        sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, timeout=10,
                    user="admin", password="secret", out=lambda m: None)
        self.assertEqual(len(s.updates), 1)

    def test_password_missing_or_wrong(self):
        s = self._shelly(password="secret")
        with self.assertRaises(builder.OtaError):
            sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, out=lambda m: None)
        with self.assertRaises(builder.OtaError):
            sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, user="admin",
                        password="wrong", out=lambda m: None)
        self.assertEqual(s.updates, [])


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_add_device_reads_slot_size_from_partition_table(self):
        for name in ("PlugMG3", "DuoBulbG3"):
            path, info = devicegen.create_profile(firmware.cached_zip(name), devices_dir=self.tmp)
            written = profile.load_profile(name, self.tmp)
            self.assertEqual(written.app_slot_size, profile.load_profile(name).app_slot_size)
            self.assertEqual(info["ptn"], "app_0")

    def test_lint_accepts_the_esp_idf_default_offset_for_the_classic_esp32(self):
        prof = profile.load_profile("PlusPlugS")
        self.assertEqual(prof.pt_offset, 0x8000)
        csv = "app_0, app, ota_0, 0x10000, 0x190000\n"
        unset = self._yaml("esp32:\n  partitions: p.csv\n  framework:\n    type: esp-idf\n", csv)
        self.assertEqual(lint.lint_esphome(unset, prof), [])      # option not set = ESP-IDF default 0x8000
        # Gen3 still needs the option: offset unset (0x8000) is wrong there, and the slot size differs as well
        self.assertEqual(len(lint.lint_esphome(unset, profile.load_profile("PlugMG3"))), 2)
        wrong = self._yaml(self.GOOD, csv)                        # 0x10000 would be wrong on this device
        self.assertEqual(len(lint.lint_esphome(wrong, prof)), 1)

    def test_partition_csv_matches_the_files_in_partitions_dir(self):
        for name in profile.list_devices():
            committed = profile.MODULE_DIR / "partitions" / f"{name}-stock.csv"
            zip_path = firmware.cached_zip(name)
            if not zip_path:
                continue
            self.assertEqual(devicegen.partition_csv(zip_path), committed.read_text(encoding="utf-8"), name)

    def test_partition_csv_rows_pass_the_lint_slot_check(self):
        text = devicegen.partition_csv(firmware.cached_zip("HTG3"))
        self.assertIn("app_0, app, ota_0, 0x20000, 0x280000,", text)
        self.assertIn('"0xf000"', text)
        y = self._yaml(self.GOOD.replace("0x10000", "0xf000"), text)
        self.assertEqual(lint.lint_esphome(y, profile.load_profile("HTG3")), [])

    def test_add_device_refuses_overwrite(self):
        devicegen.create_profile(firmware.cached_zip("PlugMG3"), devices_dir=self.tmp)
        with self.assertRaises(builder.OtaError):
            devicegen.create_profile(firmware.cached_zip("PlugMG3"), devices_dir=self.tmp)

    def _yaml(self, text, csv=None):
        y = self.tmp / "app.yaml"
        y.write_text(text, encoding="utf-8")
        if csv:
            (self.tmp / "p.csv").write_text(csv, encoding="utf-8")
        return y

    GOOD = ("esp32:\n  partitions: p.csv\n  framework:\n    type: esp-idf\n    sdkconfig_options:\n"
            "      CONFIG_PARTITION_TABLE_OFFSET: \"0x10000\"\nwifi:\n  password: !secret pw\n")

    def test_lint_accepts_good_config(self):
        y = self._yaml(self.GOOD, "app_0, app, ota_0, 0x20000, 0x2a0000\n")
        self.assertEqual(lint.lint_esphome(y, profile.load_profile("PlugMG3")), [])

    def test_lint_uses_profile_pt_offset(self):
        htg3 = profile.load_profile("HTG3")
        self.assertEqual(htg3.pt_offset, 0xf000)
        self.assertEqual(profile.load_profile("PlugMG3").pt_offset, 0x10000)
        csv = "app_0, app, ota_0, 0x20000, 0x280000\n"
        good = self._yaml(self.GOOD.replace("0x10000", "0xf000"), csv)
        self.assertEqual(lint.lint_esphome(good, htg3), [])
        bad = self._yaml(self.GOOD, csv)  # Plug M's offset on the H&T
        self.assertEqual(len(lint.lint_esphome(bad, htg3)), 1)

    def test_add_device_writes_pt_offset_only_when_not_default(self):
        path, _ = devicegen.create_profile(firmware.cached_zip("HTG3"), devices_dir=self.tmp)
        self.assertEqual(profile.load_profile("HTG3", self.tmp).pt_offset, 0xf000)
        path, _ = devicegen.create_profile(firmware.cached_zip("PlugMG3"), devices_dir=self.tmp)
        self.assertNotIn("pt_offset", path.read_text(encoding="utf-8"))

    def test_lint_flags_missing_offset_and_wrong_slot(self):
        y = self._yaml("esp32:\n  partitions: p.csv\n  framework:\n    type: esp-idf\n",
                       "app_0, app, ota_0, 0x20000, 0x100000\n")
        problems = lint.lint_esphome(y, profile.load_profile("PlugMG3"))
        self.assertEqual(len(problems), 2, problems)

    def test_lint_warns_without_allow_partition_access(self):
        y = self._yaml(self.GOOD + "ota:\n  - platform: esphome\n")
        self.assertEqual(len(lint.lint_warnings(y)), 1)
        y = self._yaml(self.GOOD + "ota:\n  - platform: esphome\n    allow_partition_access: true\n")
        self.assertEqual(lint.lint_warnings(y), [])
        y = self._yaml(self.GOOD)  # no ota block at all
        self.assertEqual(len(lint.lint_warnings(y)), 1)
        self.assertEqual(lint.lint_warnings(y, bootloader_shipped=True), [])  # --esphome-factory: nothing to update later

    def test_send_prints_bootloader_follow_up_note(self):
        zip_path = self.tmp / "t.zip"
        shutil.copy(firmware.cached_zip("DuoBulbG3"), zip_path)
        s = FakeRpcShelly()
        self.addCleanup(s.close)
        lines = []
        sender.send(profile.load_profile("DuoBulbG3"), zip_path, s.addr, port=0, assume_yes=True, timeout=10,
                    out=lines.append)
        self.assertTrue(any("update the bootloader" in l for l in lines), lines)


if __name__ == "__main__":
    unittest.main()
