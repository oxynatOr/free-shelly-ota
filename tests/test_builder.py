"""Run from ShellyOTA/: python -m unittest discover tests"""

import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelly_ota import builder, firmware, profile  # noqa: E402


def fake_app(size: int, chip_id: int = 5) -> bytes:
    hdr = bytearray(24)
    hdr[0], hdr[1] = 0xE9, 2
    hdr[12:14] = chip_id.to_bytes(2, "little")
    body = bytearray(size - 24)
    body[8:12] = builder.APP_DESC_MAGIC  # app descriptor magic at image offset 32
    return bytes(hdr) + bytes(body)


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _build(self, device, app_bytes, **kw):
        p = profile.load_profile(device)
        official = firmware.cached_zip(device)
        self.assertIsNotNone(official, "seed ZIP missing in fw/shelly")
        app = self.tmp / "app.bin"
        app.write_bytes(app_bytes)
        return p, official, builder.build(p, app, official, self.tmp / "out.zip", **kw)

    def test_golden_official_app_reproduces_manifest(self):
        for device in profile.list_devices():
            official = firmware.cached_zip(device)
            with zipfile.ZipFile(official) as z:
                manifest = json.loads(z.read("manifest.json"))
                app = z.read(manifest["parts"]["app"]["src"])
            _, _, res = self._build(device, app)
            with zipfile.ZipFile(res.output) as z:
                self.assertEqual(json.loads(z.read("manifest.json")), manifest)
            res.output.unlink()

    def test_drop_fs_removes_part_and_file(self):
        _, _, res = self._build("PlugMG3", fake_app(100_000), drop=("fs",))
        with zipfile.ZipFile(res.output) as z:
            self.assertNotIn("fs.img", z.namelist())
            self.assertNotIn("fs", json.loads(z.read("manifest.json"))["parts"])

    def test_rejects_bad_magic(self):
        bad = bytearray(fake_app(100_000)); bad[0] = 0x00
        with self.assertRaises(builder.OtaError):
            self._build("PlugMG3", bytes(bad))

    def test_rejects_bootloader_and_factory_images(self):
        boot = zipfile.ZipFile(firmware.cached_zip("PlugMG3")).read("bootloader.bin")
        with self.assertRaises(builder.OtaError) as cm:
            self._build("PlugMG3", boot)
        self.assertIn("factory", str(cm.exception))

    def test_rejects_wrong_chip(self):
        with self.assertRaises(builder.OtaError):
            self._build("PlugMG3", fake_app(100_000, chip_id=0))

    def test_slot_sizes_differ_per_device(self):
        size = 0x2A0000  # fits PlugMG3 exactly, too big for DuoBulbG3
        self._build("PlugMG3", fake_app(size))
        with self.assertRaises(builder.OtaError):
            self._build("DuoBulbG3", fake_app(size))

    def test_rejects_unknown_drop_part(self):
        with self.assertRaises(builder.OtaError):
            self._build("PlugMG3", fake_app(100_000), drop=("app",))


if __name__ == "__main__":
    unittest.main()
