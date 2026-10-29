"""Run from ShellyOTA/: python -m unittest discover tests"""

import http.server
import json
import shutil
import socket
import sys
import tempfile
import _thread
import threading
import time
import unittest
from unittest import mock
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelly_ota import builder, firmware, profile, sender  # noqa: E402


class FakeShelly:
    """Minimal Shelly: answers GetDeviceInfo and downloads the url given to Shelly.Update.

    reach: what HTTP.GET does. None: the method does not exist (404). "ok": fetches the url and reports its status.
    "blocked": cannot connect; the reply text is modelled on a device report, its HTTP status is a guess."""

    def _fetch(self, url):
        with urllib.request.urlopen(url) as r:
            while chunk := r.read(self.rate // 10 if self.rate else 65536):
                if self.rate:
                    time.sleep(0.1)

    def __init__(self, app="DuoBulbG3", auth_en=False, reach=None, download=True, update_error=None, rate=None, ver="2.0.1"):
        self.app, self.auth_en, self.reach, self.ver = app, auth_en, reach, ver
        self.download, self.update_error, self.rate = download, update_error, rate
        self.updates = []
        self.fetched = []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                u = urllib.parse.urlparse(self.path)
                if u.path == "/rpc/Shelly.GetDeviceInfo":
                    body = json.dumps({"app": outer.app, "model": "X", "ver": outer.ver, "id": "fake",
                                       "auth_en": outer.auth_en}).encode()
                elif u.path == "/rpc/Shelly.Update" and outer.update_error:
                    body = json.dumps({"code": -109, "message": outer.update_error}).encode()
                    self.send_response(500)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                elif u.path == "/rpc/Shelly.Update":
                    url = urllib.parse.parse_qs(u.query)["url"][0]
                    outer.updates.append(url)
                    if outer.download:
                        threading.Thread(target=lambda: outer._fetch(url)).start()
                    body = b"{}"
                elif u.path == "/rpc/HTTP.GET" and outer.reach == "ok":
                    url = urllib.parse.parse_qs(u.query)["url"][0]
                    outer.fetched.append(url)
                    try:
                        code = urllib.request.urlopen(url).status
                    except urllib.error.HTTPError as e:
                        code = e.code
                    body = json.dumps({"code": code}).encode()
                elif u.path == "/rpc/HTTP.GET" and outer.reach == "blocked":
                    body = json.dumps({"code": -103, "message": "Connection error: -13"}).encode()
                    self.send_response(500)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.addr = f"127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup = lambda: (self.httpd.shutdown(), self.httpd.server_close())


class SenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile = profile.load_profile("DuoBulbG3")
        self.zip = self.tmp / "t.zip"
        shutil.copy(firmware.cached_zip("DuoBulbG3"), self.zip)

    def _shelly(self, **kw):
        s = FakeShelly(**kw)
        self.addCleanup(s.addCleanup)
        return s

    def test_send_delivers_zip(self):
        s = self._shelly()
        log = []
        ok = sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, timeout=10, out=log.append)
        self.assertTrue(ok)
        self.assertEqual(len(s.updates), 1)

    def test_ctrl_c_ends_the_wait_for_the_download_quickly(self):
        # On Windows one long Event.wait() ignores Ctrl+C until it times out: the wait must be sliced.
        s = self._shelly(download=False)
        timer = threading.Timer(1.0, _thread.interrupt_main)
        timer.start()
        self.addCleanup(timer.cancel)
        start = time.monotonic()
        with self.assertRaises(KeyboardInterrupt):
            sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, timeout=300, out=lambda m: None)
        self.assertLess(time.monotonic() - start, 10)

    def test_not_committed_gets_an_explanation(self):
        s = self._shelly(update_error="Not committed")
        with self.assertRaises(builder.OtaError) as cm:
            sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, out=lambda m: None)
        self.assertIn("couple of minutes", str(cm.exception))      # the wording of explain_update_refusal

    def test_dry_run_sends_nothing(self):
        s = self._shelly()
        sender.send(self.profile, self.zip, s.addr, port=0, dry_run=True, out=lambda m: None)
        self.assertEqual(s.updates, [])

    def test_wrong_model_is_refused(self):
        s = self._shelly(app="PlugMG3")
        with self.assertRaises(builder.OtaError):
            sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, out=lambda m: None)
        self.assertEqual(s.updates, [])

    def test_password_protected_is_refused(self):
        s = self._shelly(auth_en=True)
        with self.assertRaises(builder.OtaError):
            sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, out=lambda m: None)

    def test_declined_confirmation_sends_nothing(self):
        s = self._shelly()
        with self.assertRaises(builder.OtaError):
            sender.send(self.profile, self.zip, s.addr, port=0, ask=lambda p: "no", out=lambda m: None)
        self.assertEqual(s.updates, [])

    def test_dry_run_checks_that_the_device_reaches_this_pc(self):
        s = self._shelly(reach="ok")
        log = []
        self.assertTrue(sender.send(self.profile, self.zip, s.addr, port=0, dry_run=True, out=log.append))
        self.assertTrue(any("can reach this PC" in m and "HTTP 404" in m for m in log), log)
        self.assertEqual(len(s.fetched), 1)
        self.assertTrue(s.fetched[0].endswith("/"), s.fetched)  # the root, never the ZIP itself
        self.assertEqual(s.updates, [])

    def _dry(self, level):
        s = self._shelly(reach="ok")
        log = []
        sender.send(self.profile, self.zip, s.addr, port=0, dry_run=True, out=log.append, level=level)
        return log

    def test_normal_says_the_steps_but_not_the_details(self):
        log = self._dry(sender.Level.normal)
        self.assertTrue(any(l.startswith("Device ") and ", fw " in l for l in log), log)
        self.assertTrue(any(l.startswith("ZIP: ") for l in log), log)
        self.assertTrue(any(l.startswith("Dry run: nothing sent") for l in log), log)
        self.assertFalse(any(l.startswith(("Download URL", "  parts:", "  model")) or "can reach this PC" in l for l in log), log)

    def test_verbose_adds_the_details(self):
        log = self._dry(sender.Level.verbose)
        self.assertTrue(any(l.startswith("Download URL") for l in log), log)
        self.assertTrue(any(l.startswith("  parts:") for l in log), log)
        self.assertTrue(any("can reach this PC" in l for l in log), log)

    def test_quiet_says_nothing_when_all_is_well(self):
        self.assertEqual(self._dry(sender.Level.quiet), [])

    def test_dry_run_fails_when_the_device_cannot_reach_this_pc(self):
        s = self._shelly(reach="blocked")
        with self.assertRaises(builder.OtaError) as cm:
            sender.send(self.profile, self.zip, s.addr, port=0, dry_run=True, out=lambda m: None)
        self.assertIn("Connection error: -13", str(cm.exception))
        self.assertEqual(s.updates, [])

    def test_dry_run_without_http_get_is_only_a_note(self):
        s = self._shelly()  # no HTTP.GET on this fake
        log = []
        self.assertTrue(sender.send(self.profile, self.zip, s.addr, port=0, dry_run=True, out=log.append))
        self.assertTrue(any(m.startswith("NOTE: could not check whether the device can reach") for m in log), log)

    def test_send_warns_but_still_sends_when_the_check_fails(self):
        s = self._shelly(reach="blocked")
        log = []
        self.assertTrue(sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, timeout=10, out=log.append))
        self.assertTrue(any(m.startswith("WARNING: The device cannot reach this PC") for m in log), log)
        self.assertEqual(len(s.updates), 1)

    def test_check_reach_answers(self):
        ok, blocked, none = self._shelly(reach="ok"), self._shelly(reach="blocked"), self._shelly()
        server = sender.FileServer(self.zip, 0)
        server.start()
        self.addCleanup(server.stop)
        self.assertEqual(sender.check_reach(ok.addr, "127.0.0.1", server.port), (True, "HTTP 404"))
        self.assertEqual(sender.check_reach(blocked.addr, "127.0.0.1", server.port), (False, "Connection error: -13"))
        state, detail = sender.check_reach(none.addr, "127.0.0.1", server.port)
        self.assertIsNone(state)
        self.assertIn("404", detail)

    def test_unreachable_device(self):
        with self.assertRaises(builder.OtaError):
            sender.device_info("127.0.0.1:1", timeout=2)


if __name__ == "__main__":
    unittest.main()


class FileServerStartTests(unittest.TestCase):
    def test_start_does_not_wait_for_a_reverse_lookup(self):
        # socket.getfqdn() can take many seconds on a slow resolver; the server has no use for the name
        path = Path(tempfile.mkdtemp()) / "f.zip"
        path.write_bytes(b"x")
        self.addCleanup(shutil.rmtree, path.parent, ignore_errors=True)
        with mock.patch.object(socket, "getfqdn", side_effect=AssertionError("getfqdn called")):
            server = sender.FileServer(path, port=0, bind="127.0.0.1")
        self.addCleanup(server.httpd.server_close)
        self.assertEqual(server.httpd.server_name, "127.0.0.1")
        self.assertEqual(server.httpd.server_port, server.port)

    def test_it_still_serves_the_file(self):
        path = Path(tempfile.mkdtemp()) / "f.zip"
        path.write_bytes(b"payload")
        self.addCleanup(shutil.rmtree, path.parent, ignore_errors=True)
        server = sender.FileServer(path, port=0, bind="127.0.0.1")
        server.start()
        self.addCleanup(server.stop)
        with urllib.request.urlopen(server.url("127.0.0.1")) as r:
            self.assertEqual(r.read(), b"payload")
        self.assertTrue(server.served.wait(5))


class OldLayoutTests(unittest.TestCase):
    """The PlugMG3-beta package must not go to a plug with the old flash layout (seen on a real plug, 2026-10-28)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile = profile.load_profile("PlugMG3-beta")
        self.zip = self.tmp / "beta.zip"
        shutil.copy(firmware.cached_zip("PlugMG3", prerelease=True), self.zip)

    def _shelly(self, ver):
        s = FakeShelly(app="PlugMG3", ver=ver)
        self.addCleanup(s.addCleanup)
        return s

    def test_text_for_old_firmware_only(self):
        for ver in ("1.8.99-plugmg3prod0", "2.0.1", "2.1.0", "", "garbage"):
            self.assertIn("old flash layout", sender.old_layout_text(self.profile, ver), ver)
        for ver in ("2.2.0-beta2", "2.2.0", "2.3.1", "3.0.0-beta1"):
            self.assertIsNone(sender.old_layout_text(self.profile, ver), ver)
        self.assertIsNone(sender.old_layout_text(profile.load_profile("PlugMG3"), "1.8.99"))   # a profile without the key is not affected

    def test_send_refuses_old_firmware_before_anything_is_sent(self):
        s = self._shelly("1.8.99-plugmg3prod0")
        with self.assertRaises(builder.OtaError) as cm:
            sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, out=lambda m: None)
        self.assertIn("restore PlugMG3-beta", str(cm.exception))
        self.assertEqual(s.updates, [])

    def test_dry_run_refuses_too(self):
        s = self._shelly("2.1.0")
        with self.assertRaises(builder.OtaError):
            sender.send(self.profile, self.zip, s.addr, port=0, dry_run=True, out=lambda m: None)

    def test_force_and_restore_go_through(self):
        for kw in ({"force": True}, {"restoring": True}):
            s = self._shelly("1.8.99-plugmg3prod0")
            self.assertTrue(sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, timeout=10, probe_wait=0.2,
                                        out=lambda m: None, **kw), kw)
            self.assertEqual(len(s.updates), 1, kw)

    def test_a_device_with_the_beta_layout_is_fine(self):
        s = self._shelly("2.2.0-beta2")
        sender.send(self.profile, self.zip, s.addr, port=0, dry_run=True, probe_wait=0.2, out=lambda m: None)


class DownloadWatchTests(unittest.TestCase):
    def test_eta_follows_the_speed_of_the_window(self):
        w = sender.DownloadWatch(1000, window=60)
        self.assertIsNone(w.eta())                       # nothing yet
        w.add(0, 0)
        w.add(5, 50)
        self.assertIsNone(w.eta())                       # too short a span to tell
        w.add(20, 200)                                    # 10 bytes/s
        self.assertAlmostEqual(w.eta(), 80.0)
        self.assertEqual(w.percent(), 20)

    def test_a_stall_gives_no_estimate_and_old_samples_fall_out(self):
        w = sender.DownloadWatch(1000, window=60)
        for t in range(0, 200, 10):
            w.add(t, min(t, 100))                         # fast, then standing still at 100 bytes
        self.assertIsNone(w.eta())

    def test_duration_for_people(self):
        from shelly_ota import ui
        self.assertEqual([ui.duration(x) for x in (5, 89, 600, 3600, 3900, 7200)],
                         ["5 s", "89 s", "10 min", "1 h", "1 h 5 min", "2 h"])


class SlowDownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.zip = self.tmp / "t.zip"
        shutil.copy(firmware.cached_zip("DuoBulbG3"), self.zip)
        self.profile = profile.load_profile("DuoBulbG3")
        self.size = self.zip.stat().st_size

    def _send(self, seconds, **kw):
        s = FakeShelly(rate=self.size // seconds)
        self.addCleanup(s.addCleanup)
        log = []
        with mock.patch.object(sender, "ETA_MIN_SPAN", 1.0):
            try:
                ok = sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, out=log.append,
                                 level=sender.Level.normal, **kw)
            except sender.OtaError as e:
                ok = e
        return ok, log

    def test_a_slow_but_steady_download_extends_the_wait(self):
        ok, log = self._send(9, timeout=4, max_wait=60)
        self.assertIs(ok, True, (ok, log))
        self.assertTrue(any("extended" in l for l in log), log)

    def test_the_cap_is_kept(self):
        ok, log = self._send(30, timeout=3, max_wait=5)
        self.assertIsInstance(ok, sender.OtaError)
        self.assertTrue(any("--max-wait" in l for l in log), log)
