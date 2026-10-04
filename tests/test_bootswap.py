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
    with zipfile.ZipFile(official) as z:
        shelly_boot, pt = z.read("bootloader.bin"), bytearray(z.read("partition-table.bin"))
    if pt_mod:
        pt_mod(pt)
    boot = make_esphome_bootloader(shelly_boot, boot_tweak)
    f = bytearray(b"\xff" * 0x20000)
    f[0:len(boot)] = boot
    f[0x10000:0x10000 + len(pt)] = pt
    f[0x11000:0x11000 + len(otadata)] = otadata
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
        v, res = self._min_version()
        self.assertEqual(v, "1.0.3")                       # official 1.0.2 + one patch level
        self.assertTrue(any("min_version raised" in w for w in res.warnings))
        self.assertEqual(self._min_version(boot_min_version="keep")[0], "1.0.2")
        self.assertEqual(self._min_version(boot_min_version="2.0.0")[0], "2.0.0")

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
