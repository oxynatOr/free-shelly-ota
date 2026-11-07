"""send --slot-swap (#111, experimental): the partition table with the app subtypes swapped. Run from ShellyOTA/:
python -m unittest discover tests

Nothing here needs the official ZIPs in fw/: the tables are made from the stock CSVs in partitions/ (which were read from
those packages), and the packages are small stand-ins with the same layout.
"""

import contextlib
import dataclasses
import hashlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ota  # noqa: E402
from shelly_ota import bootswap, builder, devicegen, firmware, lint, logview, profile, sender, slotswap  # noqa: E402
from shelly_ota.devicegen import parse_partitions  # noqa: E402
from test_builder import fake_app  # noqa: E402
from test_extras import FakeRpcShelly, free_udp_port  # noqa: E402

PARTITIONS = profile.MODULE_DIR / "partitions"
_TYPES = {"app": 0, "data": 1}
_SUBTYPES = {name: sub for (_, sub), name in devicegen._SUBTYPES.items()}   # "ota_0" -> 0x10, ...


def stock_table(device: str, md5: bool = True) -> bytes:
    """The binary partition table of partitions/<device>-stock.csv, as ESP-IDF's gen_esp32part writes it (0xC00 bytes)."""
    table = b""
    for line in (PARTITIONS / f"{device}-stock.csv").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, kind, sub, offset, size = [c.strip() for c in line.split(",")[:5]]
        ptype = _TYPES[kind] if kind in _TYPES else int(kind, 16)     # the Pro devices have a type 0x55 partition
        subtype = _SUBTYPES[sub] if sub in _SUBTYPES else int(sub, 16)
        table += devicegen.ENTRY.pack(devicegen.MAGIC, ptype, subtype, int(offset, 16), int(size, 16), name.encode(), 0)
    if md5:
        table += b"\xeb\xeb" + b"\xff" * 14 + hashlib.md5(table).digest()
    return table + b"\xff" * (0xC00 - len(table))


def stock_devices() -> list[str]:
    return sorted(p.name[:-len("-stock.csv")] for p in PARTITIONS.glob("*-stock.csv"))


def changed_bytes(a: bytes, b: bytes) -> list[int]:
    return [i for i, (x, y) in enumerate(zip(a, b)) if x != y]


def by_name(table: bytes) -> dict:
    return {e["name"]: e for e in parse_partitions(table)}


class SwapTableTests(unittest.TestCase):
    def test_every_stock_layout_swaps_for_slot_1_and_only_the_subtypes_and_md5_change(self):
        devices = stock_devices()
        self.assertGreaterEqual(len(devices), 60)
        for device in devices:
            with self.subTest(device):
                old = stock_table(device)
                new = slotswap.swap_table(old, 1)
                before, after = by_name(old), by_name(new)
                self.assertEqual((after["app_1"]["subtype"], after["app_0"]["subtype"]), (0x10, 0x11))
                self.assertEqual(list(before), list(after))                  # same labels, same order
                for name in before:                                          # labels, types, addresses, sizes unchanged
                    keep = ("name", "type", "offset", "size") + (() if name in slotswap.APP_SLOTS else ("subtype",))
                    self.assertEqual({k: after[name][k] for k in keep}, {k: before[name][k] for k in keep}, name)
                n = len(before)
                app_rows = [i for i, e in enumerate(parse_partitions(old)) if e["name"] in slotswap.APP_SLOTS]
                expected = {i * 32 + 3 for i in app_rows} | set(range(n * 32 + 16, n * 32 + 32))
                self.assertTrue(set(changed_bytes(old, new)) <= expected)
                self.assertEqual(new[n * 32 + 16:n * 32 + 32], hashlib.md5(new[:n * 32]).digest())   # MD5 fits the new table

    def test_esp_idf_would_pick_the_written_slot(self):
        """ESP-IDF's bootloader indexes the app slots by subtype (bs->ota[subtype & 0x0F]) and, with otadata it cannot
        read and no factory app, tries ota_0 first. After the swap for slot N that is the address of app_N."""
        for device in ("S1PMG3", "S2PMG3", "PlusPlugS", "PowerStrip"):
            old = stock_table(device)
            for target in (0, 1):
                entries = parse_partitions(slotswap.swap_table(old, target))
                ota_0 = next(e for e in entries if e["type"] == 0 and e["subtype"] == 0x10)
                self.assertEqual(ota_0["offset"], by_name(old)[f"app_{target}"]["offset"], (device, target))

    def test_slot_0_keeps_shellys_table_byte_for_byte(self):
        for device in stock_devices():
            old = stock_table(device)
            self.assertEqual(slotswap.swap_table(old, 0), old, device)

    def test_swapping_back_gives_shellys_table(self):
        old = stock_table("S1PMG3")
        self.assertEqual(slotswap.swap_table(slotswap.swap_table(old, 1), 0), old)
        self.assertEqual(slotswap.swap_table(slotswap.swap_table(old, 1), 1), slotswap.swap_table(old, 1))

    def test_critical_partitions_keep_label_type_address_and_size(self):
        """What bootswap.CRITICAL_PARTITIONS stands for: everything but the app subtypes is as in Shelly's table."""
        old = stock_table("S1PMG3")
        new = slotswap.swap_table(old, 1)
        before, after = by_name(old), by_name(new)
        self.assertTrue(bootswap.CRITICAL_PARTITIONS <= set(after))
        for name in bootswap.CRITICAL_PARTITIONS:
            key = lambda e: (e["name"], e["type"], e["offset"], e["size"])   # noqa: E731
            self.assertEqual(key(after[name]), key(before[name]), name)
            if name not in slotswap.APP_SLOTS:
                self.assertEqual(bootswap._entry_key(after[name]), bootswap._entry_key(before[name]), name)

    def test_table_without_md5_entry(self):
        old = stock_table("S1PMG3", md5=False)
        new = slotswap.swap_table(old, 1)
        self.assertEqual(len(changed_bytes(old, new)), 2)        # the two subtype bytes, no MD5 added
        self.assertEqual(by_name(new)["app_1"]["subtype"], 0x10)

    def test_a_table_with_a_wrong_md5_is_left_alone(self):
        old = bytearray(stock_table("S1PMG3"))
        n = len(parse_partitions(bytes(old)))
        old[n * 32 + 20] ^= 0xFF
        with self.assertRaises(builder.OtaError) as cm:
            slotswap.swap_table(bytes(old), 1)
        self.assertIn("MD5", str(cm.exception))

    def test_tables_that_cannot_be_swapped_are_refused(self):
        old = stock_table("S1PMG3")
        rows = parse_partitions(old)
        app1 = next(i for i, e in enumerate(rows) if e["name"] == "app_1")

        def edited(fn):
            t = bytearray(old)
            fn(t)
            n = len(parse_partitions(bytes(t)))
            t[n * 32 + 16:n * 32 + 32] = hashlib.md5(bytes(t[:n * 32])).digest()   # keep the MD5 valid: only the content is wrong
            return bytes(t)

        renamed = edited(lambda t: t.__setitem__(slice(app1 * 32 + 12, app1 * 32 + 28), b"app_9".ljust(16, b"\0")))
        as_data = edited(lambda t: t.__setitem__(app1 * 32 + 2, 1))
        as_ota_2 = edited(lambda t: t.__setitem__(app1 * 32 + 3, 0x12))
        for table, words in ((renamed, "no app_1"), (as_data, "not the app partitions"), (as_ota_2, "not the app partitions")):
            with self.assertRaises(builder.OtaError) as cm:
                slotswap.swap_table(table, 1)
            self.assertIn(words, str(cm.exception))
        with self.assertRaises(builder.OtaError):
            slotswap.swap_table(old, 2)

    def test_another_ota_app_partition_is_refused(self):
        old = bytearray(stock_table("S1PMG3"))
        n = len(parse_partitions(bytes(old)))
        extra = devicegen.ENTRY.pack(devicegen.MAGIC, 0, 0x12, 0x700000, 0x10000, b"app_2", 0)
        table = bytes(old[:n * 32]) + extra
        table += b"\xeb\xeb" + b"\xff" * 14 + hashlib.md5(table).digest()
        with self.assertRaises(builder.OtaError) as cm:
            slotswap.swap_table(table + b"\xff" * (0xC00 - len(table)), 1)
        self.assertIn("app_2", str(cm.exception))

    def test_check_swapped_refuses_anything_beyond_the_subtypes(self):
        old = stock_table("S1PMG3")
        new = slotswap.swap_table(old, 1)
        slotswap.check_swapped(old, new, 1)
        with self.assertRaises(builder.OtaError):
            slotswap.check_swapped(old, new, 0)                       # app_0 is not ota_0 in it
        rows = parse_partitions(old)
        for i, e in enumerate(rows):
            if e["name"] in ("app_1", "fs_0", "otadata"):
                moved = bytearray(new)
                moved[i * 32 + 4] ^= 0x01                             # the address
                with self.assertRaises(builder.OtaError, msg=e["name"]):
                    slotswap.check_swapped(old, bytes(moved), 1)
                relabelled = bytearray(new)
                relabelled[i * 32 + 12] ^= 0x20                       # first letter of the label
                with self.assertRaises(builder.OtaError, msg=e["name"]):
                    slotswap.check_swapped(old, bytes(relabelled), 1)
        nvs = next(i for i, e in enumerate(rows) if e["name"] == "nvs")
        other = bytearray(new)
        other[nvs * 32 + 3] = 0x81                                    # another partition's subtype
        with self.assertRaises(builder.OtaError):
            slotswap.check_swapped(old, bytes(other), 1)


def fake_bootloader(seed: int) -> bytes:
    """A small but valid ESP image (one segment, checksum, appended SHA-256) with the header of an ESP32-C3 loader."""
    data = bytes((seed * 7 + i) & 0xFF for i in range(64))
    hdr = bytearray(24)
    hdr[0], hdr[1], hdr[2], hdr[3] = 0xE9, 1, 2, 0x4F            # magic, 1 segment, DIO, 8 MB / 80 MHz
    hdr[12:14] = (0x0005).to_bytes(2, "little")
    hdr[23] = 1                                                    # SHA-256 appended
    img = bytearray(hdr + (0x403C0000).to_bytes(4, "little") + len(data).to_bytes(4, "little") + data)
    end = (len(img) + 1 + 15) // 16 * 16
    img += bytes(end - len(img))
    chk = 0xEF
    for x in data:
        chk ^= x
    img[end - 1] = chk
    return bytes(img) + hashlib.sha256(bytes(img)).digest()


def write_package(path: Path, name: str, files: dict, parts: dict) -> Path:
    """A package: parts {key: (file name or None, extra manifest values)}; size and hash come from `files`."""
    manifest = {"name": name, "version": "2.1.0", "build_id": "test", "platform": "esp32c3", "parts": {}}
    for key, (src, extra) in parts.items():
        part = dict(extra)
        if src:
            part.update(src=src, size=len(files[src]), cs_sha256=hashlib.sha256(files[src]).hexdigest())
        manifest["parts"][key] = part
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        for src, data in files.items():
            zf.writestr(src, data)
    return path


def official_package(path: Path, device: str = "S1PMG3", table: bytes | None = None) -> Path:
    """A stand-in for Shelly's package: Shelly's loader, the stock table, Shelly's boot state in otadata, an app, a file system."""
    p = profile.load_profile(device)
    files = {"bootloader.bin": fake_bootloader(1), "partition-table.bin": table or stock_table(device),
             "boot_state.bin": b"SH0S" + b"\xff" * 8188, "app.bin": fake_app(50_000), "fs.img": b"fs" * 1000}
    return write_package(path, p.package_name, files, {
        "boot": ("bootloader.bin", {"addr": 0, "min_version": "1.0.2"}),
        "pt": ("partition-table.bin", {"addr": p.pt_offset}),
        "otadata": ("boot_state.bin", {"ptn": "otadata"}),
        "nvs": (None, {"ptn": "nvs", "fill": 0xFF, "size": 0xC000}),
        "app": ("app.bin", {"ptn": "app_0"}),
        "fs": ("fs.img", {"ptn": "fs_0"}),
    })


def esphome_package(tmp: Path, official: Path, device: str = "S1PMG3", pt_addr: int | None = builder.RELOCATED_PT_ADDR) -> Path:
    """What `build --esphome-factory --pt-addr` makes of the stand-in: through the real build and bootswap.prepare.
    pt_addr=None: the table stays where Shelly's is (plain `build --esphome-factory`)."""
    p = profile.load_profile(device)
    app = fake_app(100_000)
    with zipfile.ZipFile(official) as z:
        pt = z.read("partition-table.bin")
    rows = by_name(pt)
    factory = bytearray(b"\xff" * rows["app_0"]["offset"])
    boot = fake_bootloader(2)
    factory[0:len(boot)] = boot
    factory[pt_addr or p.pt_offset:(pt_addr or p.pt_offset) + len(pt)] = pt
    (tmp / "app.bin").write_bytes(app)
    (tmp / "factory.bin").write_bytes(bytes(factory) + app)
    out = tmp / "esphome.zip"
    builder.build(p, tmp / "app.bin", official, out, factory=tmp / "factory.bin", pt_addr=pt_addr)
    return out


class SwapPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.official = official_package(self.tmp / "official.zip")
        self.package = esphome_package(self.tmp, self.official)

    def test_slot_1_package_differs_only_in_the_table_and_its_hash(self):
        res = slotswap.swap_package(self.package, self.tmp / "swapped.zip", 1)
        self.assertTrue(res.changed)
        self.assertEqual(res.output, self.tmp / "swapped.zip")
        with zipfile.ZipFile(self.package) as old, zipfile.ZipFile(res.output) as new:
            self.assertEqual(new.namelist(), old.namelist())
            builder.read_official_manifest(new, "S1PMG3")             # every hash fits
            for name in old.namelist():
                if name not in ("manifest.json", "partition-table.bin"):
                    self.assertEqual(new.read(name), old.read(name), name)
            m_old, m_new = json.loads(old.read("manifest.json")), json.loads(new.read("manifest.json"))
            self.assertEqual(m_new["parts"]["pt"].pop("cs_sha256"), hashlib.sha256(new.read("partition-table.bin")).hexdigest())
            m_old["parts"]["pt"].pop("cs_sha256")
            self.assertEqual(m_new, m_old)                            # boot min_version, app, addresses: all as built
            self.assertEqual(by_name(new.read("partition-table.bin"))["app_1"]["subtype"], 0x10)
            # the check `build` and `send` already do on a package's table still passes
            self.assertEqual(builder.package_layout_problems(profile.load_profile("S1PMG3"), new, m_new, allow_relocated=True), [])
            self.assertEqual(m_new["parts"]["pt"]["addr"], builder.RELOCATED_PT_ADDR)       # the move stays
        self.assertEqual(slotswap.describe(res), "app_1 (0x3a0000) is ota_0, app_0 (0x20000) is ota_1")

    def test_slot_0_writes_nothing(self):
        res = slotswap.swap_package(self.package, self.tmp / "swapped.zip", 0)
        self.assertFalse(res.changed)
        self.assertEqual(res.output, self.package)
        self.assertFalse((self.tmp / "swapped.zip").exists())

    def test_package_needs_a_table_and_a_clean_otadata(self):
        with zipfile.ZipFile(self.official) as z:      # Shelly's own: its otadata carries Shelly's boot state
            with self.assertRaises(builder.OtaError) as cm:
                slotswap.check_package(z, builder.read_official_manifest(z))
        self.assertIn("clean", str(cm.exception))
        no_pt = self.tmp / "no-pt.zip"         # `build` cannot make this with --esphome-factory; a hand-made one
        with zipfile.ZipFile(self.package) as z, zipfile.ZipFile(no_pt, "w") as out:
            m = json.loads(z.read("manifest.json"))
            del m["parts"]["pt"]
            out.writestr("manifest.json", json.dumps(m))
            for name in z.namelist():
                if name not in ("manifest.json", "partition-table.bin"):
                    out.writestr(name, z.read(name))
        with self.assertRaises(builder.OtaError) as cm:
            slotswap.swap_package(no_pt, self.tmp / "x.zip", 1)
        self.assertIn("'pt'", str(cm.exception))


class SlotSwapSendTests(unittest.TestCase):
    """send with and without slot_swap, against the fake Shelly that names its target slot in the log."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.work = self.tmp / "work"
        self.work.mkdir()
        self.profile = profile.load_profile("S1PMG3")
        self.official = official_package(self.tmp / "official.zip")
        self.package = esphome_package(self.tmp, self.official)
        patcher = mock.patch.object(firmware, "cached_zip", return_value=self.official)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _send(self, zip_path=None, target_slot=None, core_dump_target=None, **kw):
        shelly = FakeRpcShelly(app="S1PMG3", target_slot=target_slot, core_dump_target=core_dump_target)
        self.addCleanup(shelly.close)
        lines = []
        kw.setdefault("dry_run", True)
        try:
            sender.send(self.profile, zip_path or self.package, shelly.addr, port=0, log_port=free_udp_port(),
                        probe_wait=1.5, out=lines.append, timeout=10, **kw)
            error = None
        except builder.OtaError as e:
            error = str(e)
        return lines, error, shelly

    def test_without_the_option_slot_1_is_still_refused(self):
        lines, error, shelly = self._send(target_slot=1)
        self.assertIn("restore", error)
        self.assertNotIn("slot-swap", error)
        self.assertFalse(any("slot-swap" in l or "EXPERIMENTAL" in l for l in lines), lines)
        self.assertEqual(list(self.work.iterdir()), [])

    def test_dry_run_with_slot_1_swaps_and_sends_nothing(self):
        lines, error, shelly = self._send(target_slot=1, slot_swap=self.work)
        self.assertIsNone(error, lines)
        self.assertEqual(shelly.updates, [])
        self.assertTrue(any(l.startswith("WARNING: --slot-swap is EXPERIMENTAL") for l in lines), lines)
        self.assertTrue(any("app_1 (0x3a0000) is ota_0" in l for l in lines), lines)
        self.assertTrue(any("Dry run: nothing sent" in l for l in lines), lines)

    def test_send_with_slot_1_serves_the_swapped_package(self):
        lines, error, shelly = self._send(target_slot=1, slot_swap=self.work, dry_run=False, assume_yes=True)
        self.assertIsNone(error, lines)
        self.assertEqual(len(shelly.updates), 1)
        self.assertIn("esphome.slot-swap-1.zip", shelly.updates[0])
        with zipfile.ZipFile(self.work / "esphome.slot-swap-1.zip") as z:
            self.assertEqual(by_name(z.read("partition-table.bin"))["app_1"]["subtype"], 0x10)
        with zipfile.ZipFile(self.package) as z:                      # the package itself is untouched
            self.assertEqual(by_name(z.read("partition-table.bin"))["app_0"]["subtype"], 0x10)
        self.assertTrue(any("now has app_1 as ota_0" in l for l in lines), lines)

    def test_send_with_slot_0_sends_the_package_as_built(self):
        lines, error, shelly = self._send(target_slot=0, slot_swap=self.work, dry_run=False, assume_yes=True)
        self.assertIsNone(error, lines)
        self.assertTrue(shelly.updates[0].endswith("/esphome.zip"), shelly.updates)
        self.assertEqual(list(self.work.iterdir()), [])
        self.assertTrue(any("nothing to swap" in l for l in lines), lines)
        self.assertFalse(any("now has app_" in l for l in lines), lines)

    def test_unknown_target_slot_is_refused(self):
        for kw, words in (({}, "could not be read"), ({"core_dump_target": "scratch"}, "Storing core dumps to scratch")):
            lines, error, shelly = self._send(slot_swap=self.work, dry_run=False, assume_yes=True, **kw)
            self.assertIsNotNone(error, kw)
            self.assertIn("--slot-swap needs the update target slot", error)
            self.assertIn(words, error)
            self.assertEqual(shelly.updates, [])

    def test_package_without_esphomes_bootloader_is_refused_even_with_force(self):
        plain = self.tmp / "plain.zip"
        builder.build(self.profile, self.tmp / "app.bin", self.official, plain)
        lines, error, shelly = self._send(plain, target_slot=1, slot_swap=self.work, force=True)
        self.assertIsNotNone(error)
        self.assertIn("clean", error)                                 # its otadata is Shelly's, refused before the device is asked
        self.assertEqual(shelly.updates, [])

    def test_boot_not_replaced_is_refused(self):
        """A package with a clean otadata but Shelly's bootloader (made by hand): the swap needs ESPHome's loader."""
        hand = self.tmp / "hand.zip"
        with zipfile.ZipFile(self.package) as z, zipfile.ZipFile(self.official) as o:
            m = json.loads(z.read("manifest.json"))
            m["parts"]["boot"] = json.loads(o.read("manifest.json"))["parts"]["boot"]
            files = {n: z.read(n) for n in z.namelist() if n != "manifest.json"}
            files["bootloader.bin"] = o.read("bootloader.bin")
        with zipfile.ZipFile(hand, "w") as zf:
            zf.writestr("manifest.json", json.dumps(m))
            for n, data in files.items():
                zf.writestr(n, data)
        lines, error, shelly = self._send(hand, target_slot=1, slot_swap=self.work, force=True)
        self.assertIn("ESPHome's bootloader", error)
        self.assertEqual(shelly.updates, [])

    def test_no_cached_official_zip_is_refused(self):
        with mock.patch.object(firmware, "cached_zip", return_value=None):
            lines, error, shelly = self._send(target_slot=1, slot_swap=self.work)
        self.assertIn("fetch", error)

    def test_does_not_go_with_ignore_slot_or_restore(self):
        _, error, _ = self._send(target_slot=1, slot_swap=self.work, ignore_slot=True)
        self.assertIn("--ignore-slot", error)
        _, error, _ = self._send(target_slot=1, slot_swap=self.work, restoring=True)
        self.assertIn("restore", error)


class InstallerSlotWatchTests(unittest.TestCase):
    def _session(self, target):
        lines = []
        session = logview.Session(level=logview.Level.normal, out=lines.append, device_id="shelly1pmg3-aabbcc")
        session.slot_swap_target = target
        return session, lines

    def _feed(self, session, slot):
        session.device(f"shelly1pmg3-aabbcc 12 34.567 2 2|a_esp32_backend.cpp:422 Will write to slot {slot}")

    def test_another_slot_than_the_swapped_one_is_a_warning_once(self):
        session, lines = self._session(1)
        self._feed(session, 0)
        self._feed(session, 0)
        warn = [l for l in lines if l.startswith("WARNING: the installer writes to slot 0")]
        self.assertEqual(len(warn), 1, lines)
        self.assertIn("serial", warn[0])

    def test_same_slot_or_no_swap_says_nothing_extra(self):
        for target, slot in ((1, 1), (None, 0), (None, 1)):
            session, lines = self._session(target)
            self._feed(session, slot)
            self.assertFalse(any("--slot-swap" in l for l in lines), (target, slot, lines))


class RelocatedTableTests(unittest.TestCase):
    """build --pt-addr: Shelly's table is shipped at 0x8000 and the bootloader comes from a build that reads it there."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.official = official_package(self.tmp / "official.zip")

    def test_build_moves_the_table_and_keeps_it_shellys(self):
        package = esphome_package(self.tmp, self.official)
        with zipfile.ZipFile(package) as new, zipfile.ZipFile(self.official) as old:
            m_new = builder.read_official_manifest(new, "S1PMG3")
            self.assertEqual(m_new["parts"]["pt"]["addr"], 0x8000)
            self.assertEqual(new.read("partition-table.bin"), old.read("partition-table.bin"))   # not swapped at build time
            self.assertEqual(new.read("bootloader.bin"), fake_bootloader(2))                      # from the factory image's 0x0..0x8000
            self.assertEqual(m_new["parts"]["boot"]["addr"], 0)
            p = profile.load_profile("S1PMG3")
            self.assertEqual(builder.package_layout_problems(p, new, m_new), [
                f"the partition table is at 0x8000, the profile says 0x{p.pt_offset:x}"])
            self.assertEqual(builder.package_layout_problems(profile.load_profile("S1PMG3"), new, m_new, allow_relocated=True), [])

    def test_without_the_option_the_table_stays_where_it_was(self):
        package = esphome_package(self.tmp, self.official, pt_addr=None)
        with zipfile.ZipFile(package) as z:
            self.assertEqual(json.loads(z.read("manifest.json"))["parts"]["pt"]["addr"],
                             profile.load_profile("S1PMG3").pt_offset)

    def test_build_refusals(self):
        p = profile.load_profile("S1PMG3")
        app = self.tmp / "app.bin"
        app.write_bytes(fake_app(100_000))
        out = self.tmp / "x.zip"
        with self.assertRaises(builder.OtaError) as cm:
            builder.build(p, app, self.official, out, pt_addr=0x8000)                   # no factory image
        self.assertIn("--esphome-factory", str(cm.exception))
        with self.assertRaises(builder.OtaError) as cm:
            builder.build(p, app, self.official, out, factory=app, pt_addr=0x9000)
        self.assertIn("only 0x8000", str(cm.exception))
        with self.assertRaises(builder.OtaError) as cm:
            builder.build(p, app, self.official, out, factory=app, pt_addr=0x8000, drop=("pt",))
        self.assertIn("drop 'pt'", str(cm.exception))
        at_8000 = dataclasses.replace(p, pt_offset=0x8000)
        with self.assertRaises(builder.OtaError) as cm:
            builder.build(at_8000, app, self.official, out, factory=app, pt_addr=0x8000)
        self.assertIn("nothing to move", str(cm.exception))

    def test_a_partition_on_the_new_address_is_refused(self):
        rows = parse_partitions(stock_table("S1PMG3"))
        table = b"".join(devicegen.ENTRY.pack(devicegen.MAGIC, e["type"], e["subtype"], e["offset"], e["size"],
                                               e["name"].encode(), 0) for e in rows)
        table += devicegen.ENTRY.pack(devicegen.MAGIC, 1, 0x82, 0x8800, 0x1000, b"in_the_way", 0)
        table += b"\xeb\xeb" + b"\xff" * 14 + hashlib.md5(table).digest()
        official = official_package(self.tmp / "other.zip", table=table + b"\xff" * (0xC00 - len(table)))
        with self.assertRaises(builder.OtaError) as cm:
            esphome_package(self.tmp, official)
        self.assertIn("overlap", str(cm.exception))
        self.assertIn("in_the_way", str(cm.exception))

    def test_slot_swap_refuses_a_package_whose_table_was_not_moved(self):
        plain = esphome_package(self.tmp, self.official, pt_addr=None)
        with self.assertRaises(builder.OtaError) as cm:
            slotswap.swap_package(plain, self.tmp / "x.zip", 1)
        text = str(cm.exception)
        self.assertIn("PT1", text)
        self.assertIn("--pt-addr 0x8000", text)
        self.assertFalse((self.tmp / "x.zip").exists())

    def test_lint_expects_the_default_offset_when_the_table_moves(self):
        p = profile.load_profile("S1PMG3")
        y = self.tmp / "app.yaml"
        base = "esp32:\n  partitions: p.csv\n  framework:\n    type: esp-idf\n"
        (self.tmp / "p.csv").write_text("app_0, app, ota_0, 0x20000, 0x%x\n" % p.app_slot_size, encoding="utf-8")
        unset, at_own = base, base + '    sdkconfig_options:\n      CONFIG_PARTITION_TABLE_OFFSET: "0x%x"\n' % p.pt_offset
        for text, relocated, ok in ((unset, True, True), (at_own, True, False), (unset, False, False), (at_own, False, True)):
            y.write_text(text, encoding="utf-8")
            problems = [x for x in lint.lint_esphome(y, p, relocated=relocated) if "CONFIG_PARTITION_TABLE_OFFSET" in x]
            self.assertEqual(problems == [], ok, (relocated, text, problems))


class TableMovedLogTests(unittest.TestCase):
    def _session(self):
        lines = []
        session = logview.Session(level=logview.Level.normal, out=lines.append, device_id="shelly1pmg3-aabbcc")
        session.slot_swap_target = 1
        return session

    def _feed(self, session, text):
        session.device(f"shelly1pmg3-aabbcc 12 34.567 2 2|2xx_ota_backend.cpp:171 {text}")

    def test_the_move_is_recognised(self):
        for text in ("Installing PT 4096@fs_1(0x700000) -> pt(0x8000)...", "PT is being moved from 0x10000 to 0x8000"):
            session = self._session()
            self._feed(session, text)
            self.assertTrue(session.table_moved, text)

    def test_the_journal_is_not_a_move(self):
        session = self._session()
        self._feed(session, "Installing new PT1 (6e4c9cb1) ")
        self.assertFalse(session.table_moved)

    def test_texts(self):
        self.assertIn("did not show", sender.table_not_moved_text())
        self.assertIn("Shelly's table", sender.slot_swap_after_text(0, swapped=False))
        self.assertIn("app_1 as ota_0", sender.slot_swap_after_text(1))


class CommandLineTests(unittest.TestCase):
    def test_option_is_off_by_default_and_only_on_send(self):
        parser = ota.build_parser()
        self.assertFalse(parser.parse_args(["send", "S1PMG3", "x.zip"]).slot_swap)
        self.assertTrue(parser.parse_args(["send", "S1PMG3", "x.zip", "--slot-swap"]).slot_swap)
        self.assertIsNone(parser.parse_args(["build", "S1PMG3", "app.bin"]).pt_addr)
        self.assertEqual(parser.parse_args(["build", "S1PMG3", "app.bin", "--pt-addr", "0x8000"]).pt_addr, 0x8000)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["restore", "S1PMG3", "--slot-swap"])

    def _run_send(self, *extra):
        args = ota.build_parser().parse_args(["send", "S1PMG3", "x.zip", *extra])
        with mock.patch.object(sender, "send") as send:
            ota._send(args, Path("x.zip"))
        return send.call_args.kwargs["slot_swap"]

    def test_send_gets_a_work_directory_only_with_the_option(self):
        self.assertIsNone(self._run_send())
        work = self._run_send("--slot-swap")
        self.assertIsInstance(work, Path)
        self.assertFalse(work.exists())                               # removed after the send

    def test_help_marks_it_experimental_and_names_serial_and_flash_dump(self):
        from test_help import help_of
        _, text = help_of("send")
        self.assertIn("experimental:", text)
        flat = " ".join(text.split())
        self.assertIn("--slot-swap EXPERIMENTAL", flat)
        self.assertIn("serial connection and a flash dump", flat)

    def test_no_rollback_claim_anywhere(self):
        """#111: no 'rollback' wording for this until the way back has been tried on a dev board."""
        from test_help import help_of
        root = profile.MODULE_DIR
        slots = (root / "docs" / "bootloader-and-slots.md").read_text(encoding="utf-8")
        section = re.search(r"(?ms)^## Experimental: slot swap in the package$.*?(?=^## |\Z)", slots)
        self.assertIsNotNone(section)
        mentions = [line for path in (root / "docs" / "commands.md", root / "CHANGELOG.md", root / "README.md")
                    for line in path.read_text(encoding="utf-8").splitlines() if "slot-swap" in line or "slot swap" in line]
        self.assertTrue(mentions)
        texts = [help_of("send")[1], sender.SLOT_SWAP_WARNING, sender.slot_swap_after_text(1), slotswap.__doc__,
                 section.group(0), *mentions]
        for text in texts:
            self.assertIsNone(re.search(r"(?i)roll[ -]?back", text), text)


if __name__ == "__main__":
    unittest.main()
