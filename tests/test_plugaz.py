"""Checks against a locally cached official AZ package; no firmware is shipped."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from shelly_ota import builder, devicegen, firmware, profile


class PlugAZPackageTests(unittest.TestCase):
    def test_official_layout_and_default_package_parts(self):
        device = profile.load_profile('PlugAZ')
        stock = firmware.zip_for_layout(device)   # the first layout; the newest package can be of the later one
        if stock is None:
            self.skipTest('no official PlugAZ ZIP of the first layout cached')
        with zipfile.ZipFile(stock) as z:
            manifest = builder.read_official_manifest(z, 'PlugAZ')
            self.assertEqual(builder.package_layout_problems(device, z, manifest), [])
            app = z.read(manifest['parts']['app']['src'])
            original_pt = z.read(manifest['parts']['pt']['src'])
            original_fs = z.read(manifest['parts']['fs']['src'])
        csv = profile.MODULE_DIR / 'partitions/PlugAZ-stock.csv'
        self.assertEqual(csv.read_text(), devicegen.partition_csv(stock))
        with tempfile.TemporaryDirectory() as folder:
            app_path = Path(folder) / 'app.bin'
            app_path.write_bytes(app)
            result = builder.build(device, app_path, stock, Path(folder) / 'out.zip')
            with zipfile.ZipFile(result.output) as z:
                packed = json.loads(z.read('manifest.json'))
                self.assertEqual(packed, manifest)
                self.assertEqual(z.read('partition-table.bin'), original_pt)
                self.assertEqual(z.read('fs.img'), original_fs)
