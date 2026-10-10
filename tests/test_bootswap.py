"""Run from ShellyOTA/: python -m unittest discover tests"""

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelly_ota import bootswap, builder, firmware, profile, sender  # noqa: E402
from shelly_ota.devicegen import parse_partitions  # noqa: E402
from test_extras import FakeRpcShelly, free_udp_port  # noqa: E402
from test_builder import fake_app  # noqa: E402


def make_esphome_bootloader(shelly_boot: bytes, tweak=None) -> bytes:
    """A valid bootloader image (checksum + SHA-256) that differs from Shelly's, with the same header."""
    n = bootswap.image_length(shelly_boot) - 32
    img = bytearray(shelly_boot[:n])
    img[100] ^= 0x55                      # change one data byte inside the first segment
    chk, pos = 0xEF, 24
    for _ in range(img[1]):
        size = int.from_bytes(img[pos + 4:pos + 8], "little")
        for x in img[pos + 8:pos + 8 + size]:
            chk ^= x
        pos += 8 + size
    img[n - 1] = chk
    if tweak:
        tweak(img)
    return bytes(img) + hashlib.sha256(bytes(img)).digest()


def make_factory(official: Path, app: bytes, *, boot_tweak=None, otadata=b"\xff" * 8192, pt_mod=None) -> bytes:
    """A merged ESPHome-style image whose addresses come from the official package (bootloader, table, otadata, app_0)."""
    with zipfile.ZipFile(official) as z:
        manifest = json.loads(z.read("manifest.json"))
        shelly_boot, pt = z.read("bootloader.bin"), bytearray(z.read("partition-table.bin"))
    boot_addr = manifest["parts"]["boot"].get("addr", 0)
    pt_addr = manifest["parts"]["pt"].get("addr", 0x10000)
    entries = {e["name"]: e for e in parse_partitions(bytes(pt))}
    if pt_mod:
        pt_mod(pt)
    boot = make_esphome_bootloader(shelly_boot, boot_tweak)
    ota_off, app_off = entries["otadata"]["offset"], entries["app_0"]["offset"]
    f = bytearray(b"\xff" * app_off)
    f[boot_addr:boot_addr + len(boot)] = boot
    f[pt_addr:pt_addr + len(pt)] = pt
    f[ota_off:ota_off + len(otadata)] = otadata
    return bytes(f) + app


class BootswapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile = profile.load_profile("PlugMG3")
        self.official = firmware.cached_zip("PlugMG3")
        self.app = fake_app(100_000)
        (self.tmp / "app.bin").write_bytes(self.app)

    def _build(self, factory_bytes, **kw):
        (self.tmp / "factory.bin").write_bytes(factory_bytes)
        return builder.build(self.profile, self.tmp / "app.bin", self.official, self.tmp / "out.zip",
                             factory=self.tmp / "factory.bin", **kw)

    def test_bootloader_and_otadata_replaced_everything_else_untouched(self):
        res = self._build(make_factory(self.official, self.app))
        self.assertEqual(res.replaced, ["boot", "otadata"])
        with zipfile.ZipFile(res.output) as out, zipfile.ZipFile(self.official) as off:
            self.assertNotEqual(out.read("bootloader.bin"), off.read("bootloader.bin"))
            self.assertEqual(set(out.read("boot_state.bin")), {0xFF})
            self.assertEqual(out.read("partition-table.bin"), off.read("partition-table.bin"))
            self.assertEqual(out.read("fs.img"), off.read("fs.img"))
            m = json.loads(out.read("manifest.json"))
            self.assertEqual(m["parts"]["boot"]["addr"], 0)
            self.assertEqual(m["parts"]["boot"]["size"], len(out.read("bootloader.bin")))
            builder.read_official_manifest(out, "PlugMG3")  # all hashes consistent
        self.assertTrue(any("BOOTLOADER REPLACED" in w for w in res.warnings))

    def test_flash_mode_mismatch_is_refused(self):
        with self.assertRaises(builder.OtaError) as cm:
            self._build(make_factory(self.official, self.app, boot_tweak=lambda b: b.__setitem__(2, 0)))
        self.assertIn("flash mode", str(cm.exception))

    def test_corrupt_bootloader_is_refused(self):
        f = bytearray(make_factory(self.official, self.app))
        f[200] ^= 0xFF                      # damage the body, digest no longer matches
        with self.assertRaises(builder.OtaError):
            self._build(bytes(f))

    def test_non_erased_otadata_is_refused(self):
        with self.assertRaises(builder.OtaError):
            self._build(make_factory(self.official, self.app, otadata=b"SH0S" + b"\xff" * 8188))

    def test_other_app_than_packed_is_refused(self):
        with self.assertRaises(builder.OtaError) as cm:
            self._build(make_factory(self.official, fake_app(100_000)[:-1] + b"\x01"))
        self.assertIn("same build", str(cm.exception))

    def test_critical_partition_mismatch_is_refused_but_scratch_only_warns(self):
        def move_app0(pt):
            pt[2 * 32 + 8:2 * 32 + 12] = (0x30000).to_bytes(4, "little")   # app_0 offset
        with self.assertRaises(builder.OtaError):
            self._build(make_factory(self.official, self.app, pt_mod=move_app0))

        def move_scratch(pt):
            pt[6 * 32 + 8:6 * 32 + 12] = (0x720000).to_bytes(4, "little")  # scratch offset
        res = self._build(make_factory(self.official, self.app, pt_mod=move_scratch))
        self.assertTrue(any("scratch" in w for w in res.warnings))

    def _min_version(self, **kw):
        res = self._build(make_factory(self.official, self.app), **kw)
        with zipfile.ZipFile(res.output) as z:
            return json.loads(z.read("manifest.json"))["parts"]["boot"]["min_version"], res

    def test_boot_min_version_is_raised_by_default_and_overridable(self):
        import dataclasses
        self.profile = dataclasses.replace(self.profile, boot_min_version=None)   # profile sets nothing: official + one patch
        v, res = self._min_version()
        self.assertEqual(v, "1.0.3")                       # official 1.0.2 + one patch level
        self.assertTrue(any("min_version raised" in w for w in res.warnings))
        self.assertEqual(self._min_version(boot_min_version="keep")[0], "1.0.2")
        self.assertEqual(self._min_version(boot_min_version="2.0.0")[0], "2.0.0")

    def test_profile_boot_min_version_is_the_default_and_the_option_still_wins(self):
        import dataclasses
        self.profile = dataclasses.replace(self.profile, boot_min_version="1.0.9")
        self.assertEqual(self._min_version()[0], "1.0.9")
        self.assertEqual(self._min_version(boot_min_version="2.0.0")[0], "2.0.0")
        self.assertEqual(profile.load_profile("HTG3").boot_min_version, "1.0.9")
        self.assertEqual(profile.load_profile("PlugMG3").boot_min_version, "1.0.9")   # restored Plug M runs loader 1.0.3

    def _error_for(self, **factory_kw) -> str:
        with self.assertRaises(builder.OtaError) as cm:
            self._build(make_factory(self.official, self.app, **factory_kw))
        return str(cm.exception)

    def test_header_errors_say_what_differs_and_how_to_fix_it(self):
        def set_byte(i, v):
            return lambda img: img.__setitem__(i, v)

        msg = self._error_for(boot_tweak=set_byte(3, 0x20))                  # 4 MB / 40 MHz instead of Shelly's value
        self.assertIn("flash size/frequency", msg)
        self.assertIn("40 MHz", msg)
        self.assertIn("board_build.f_flash", msg)
        self.assertIn("Fix:", msg)

        msg = self._error_for(boot_tweak=set_byte(14, 1))                    # Shelly's Plug M loader has 3 here
        self.assertIn("minimum chip revision", msg)
        self.assertIn("minimum_chip_revision", msg)
        self.assertIn("sram1_as_iram", msg)

        msg = self._error_for(boot_tweak=set_byte(2, 3))                     # DOUT
        self.assertIn("DOUT", msg)
        self.assertIn("flash_mode", msg)

        def other_chip(img):
            img[12:14] = (0x000D).to_bytes(2, "little")
        msg = self._error_for(boot_tweak=other_chip)
        self.assertIn("ESP32-C6", msg)
        self.assertIn("variant", msg)

    def test_esp32_frequency_hint_names_the_sdkconfig_option(self):
        prof = profile.load_profile("PlusPlugS")
        official = firmware.cached_zip("PlusPlugS")
        app = bytearray(fake_app(100_000))
        app[12:14] = (0).to_bytes(2, "little")
        (self.tmp / "app.bin").write_bytes(bytes(app))
        (self.tmp / "factory.bin").write_bytes(make_factory(official, bytes(app), boot_tweak=lambda img: img.__setitem__(3, 0x20)))
        with self.assertRaises(builder.OtaError) as cm:
            builder.build(prof, self.tmp / "app.bin", official, self.tmp / "o.zip", factory=self.tmp / "factory.bin")
        msg = str(cm.exception)
        self.assertIn("4 MB, 40 MHz", msg)
        self.assertIn("4 MB, 80 MHz", msg)
        self.assertIn("CONFIG_ESPTOOLPY_FLASHFREQ_80M", msg)

    def test_partition_layout_and_other_build_errors_come_with_a_fix(self):
        def move_app0(pt):
            pt[2 * 32 + 8:2 * 32 + 12] = (0x30000).to_bytes(4, "little")
        msg = self._error_for(pt_mod=move_app0)
        self.assertIn("partitions: PlugMG3-stock.csv", msg)
        self.assertIn("partition-csv", msg)
        with self.assertRaises(builder.OtaError) as cm:
            self._build(make_factory(self.official, fake_app(100_000)[:-1] + b"\x01"))
        self.assertIn("same build", str(cm.exception))
        self.assertIn("Fix:", str(cm.exception))

    def test_app_checks_name_the_fix(self):
        with self.assertRaises(builder.OtaError) as cm:
            builder.check_app_image(fake_app(100_000), "esp32c6", 1 << 20, "app_0")   # fake_app has the C3 chip id
        self.assertIn("variant", str(cm.exception))
        self.assertIn("ESP32C6", str(cm.exception))
        with self.assertRaises(builder.OtaError) as cm:
            builder.check_app_image(fake_app(100_000), "esp32c3", 50_000, "app_0")
        self.assertIn("COMPILER_OPTIMIZATION_SIZE", str(cm.exception))

    def _send_dry(self, target_slot, **kw):
        res = self._build(make_factory(self.official, self.app))        # a package that replaces the bootloader
        shelly = FakeRpcShelly(app="PlugMG3", target_slot=target_slot)
        self.addCleanup(shelly.close)
        lines = []
        try:
            sender.send(self.profile, res.output, shelly.addr, port=0, dry_run=True, log_port=free_udp_port(),
                        probe_wait=1.5, out=lines.append, **kw)
            error = None
        except builder.OtaError as e:
            error = str(e)
        return lines, error, shelly

    def test_send_refuses_when_the_installer_would_write_to_slot_1(self):
        lines, error, shelly = self._send_dry(target_slot=1)
        self.assertIsNotNone(error)
        self.assertIn("slot 1", error)
        self.assertIn("restore", error)
        self.assertEqual(shelly.updates, [])
        self.assertIsNone(shelly.udp_addr)                  # the debug log setting was put back

    def test_send_accepts_slot_0_and_reports_it(self):
        lines, error, _ = self._send_dry(target_slot=0)
        self.assertIsNone(error)
        self.assertTrue(any("Update target slot: 0" in l for l in lines), lines)

    def test_ignore_slot_sends_with_a_warning(self):
        lines, error, _ = self._send_dry(target_slot=1, ignore_slot=True)
        self.assertIsNone(error)
        self.assertTrue(any("--ignore-slot" in l and "WARNING" in l for l in lines), lines)

    def test_unreadable_target_slot_only_warns(self):
        lines, error, _ = self._send_dry(target_slot=None)
        self.assertIsNone(error)
        self.assertTrue(any("could not be read" in l for l in lines), lines)

    def test_classic_esp32_bootloader_at_0x1000_is_swapped(self):
        """Gen2 (ESP32): bootloader at 0x1000, partition table at 0x8000, otadata at 0xd000, chip id 0."""
        prof = profile.load_profile("PlusPlugS")
        official = firmware.cached_zip("PlusPlugS")
        self.assertEqual(prof.platform, "esp32")
        app = bytearray(fake_app(100_000))
        app[12:14] = (0).to_bytes(2, "little")          # chip id of the classic ESP32
        app = bytes(app)
        (self.tmp / "app.bin").write_bytes(app)
        (self.tmp / "factory.bin").write_bytes(make_factory(official, app))
        res = builder.build(prof, self.tmp / "app.bin", official, self.tmp / "esp32.zip",
                            factory=self.tmp / "factory.bin")
        self.assertIn("boot", res.replaced)
        with zipfile.ZipFile(res.output) as z:
            m = json.loads(z.read("manifest.json"))
            self.assertEqual(m["parts"]["boot"]["addr"], 0x1000)
            self.assertNotEqual(z.read(m["parts"]["boot"]["src"]), zipfile.ZipFile(official).read("bootloader.bin"))
        with self.assertRaises(builder.OtaError):         # a C3 chip id must be refused for an ESP32 profile
            (self.tmp / "bad.bin").write_bytes(fake_app(100_000))
            builder.build(prof, self.tmp / "bad.bin", official, self.tmp / "bad.zip")

    def test_boot_min_version_needs_factory_and_valid_format(self):
        with self.assertRaises(builder.OtaError):
            builder.build(self.profile, self.tmp / "app.bin", self.official, self.tmp / "o.zip",
                          boot_min_version="1.0.3")
        with self.assertRaises(builder.OtaError):
            self._build(make_factory(self.official, self.app), boot_min_version="abc")

    def test_cannot_drop_boot_with_factory(self):
        with self.assertRaises(builder.OtaError):
            self._build(make_factory(self.official, self.app), drop=("boot",))

    def test_send_warns_about_replaced_bootloader(self):
        from test_extras import FakeRpcShelly
        res = self._build(make_factory(self.official, self.app))
        s = FakeRpcShelly(app="PlugMG3")
        self.addCleanup(s.close)
        lines = []
        sender.send(self.profile, res.output, s.addr, port=0, dry_run=True, out=lines.append)
        self.assertTrue(any("replaces Shelly's bootloader" in l for l in lines), lines)

    def test_send_after_replaced_bootloader_needs_no_update_note(self):
        from test_extras import FakeRpcShelly
        res = self._build(make_factory(self.official, self.app))
        s = FakeRpcShelly(app="PlugMG3")
        self.addCleanup(s.close)
        lines = []
        sender.send(self.profile, res.output, s.addr, port=0, assume_yes=True, timeout=10, out=lines.append)
        self.assertTrue(any("no separate bootloader update is needed" in l for l in lines), lines)
        self.assertFalse(any("update the bootloader (see README" in l for l in lines), lines)


if __name__ == "__main__":
    unittest.main()
