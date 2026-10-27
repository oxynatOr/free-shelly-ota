"""Run from ShellyOTA/: python -m unittest discover tests"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelly_ota import firmware, profile  # noqa: E402


class BetaProfileTests(unittest.TestCase):
    def test_the_beta_profile_points_at_the_beta_package(self):
        beta, stable = profile.load_profile("PlugMG3-beta"), profile.load_profile("PlugMG3")
        self.assertEqual((beta.package_name, beta.channel, beta.update_id), ("PlugMG3", "beta", stable.update_id))
        self.assertEqual((stable.package_name, stable.channel), ("PlugMG3", "stable"))
        self.assertEqual(beta.app_slot_size, 0x300000)

    def test_prerelease_picks_the_newest_beta_and_the_default_stays_stable(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        for version in ("2.0.1", "2.1.0", "2.2.0-beta1", "2.2.0-beta2"):
            (tmp / "Dev" / version).mkdir(parents=True)
            (tmp / "Dev" / version / "Dev.zip").write_bytes(b"PK")
        self.assertEqual(firmware.cached_zip("Dev", fw_dir=tmp).parent.name, "2.1.0")
        self.assertEqual(firmware.cached_zip("Dev", fw_dir=tmp, prerelease=True).parent.name, "2.2.0-beta2")
        shutil.rmtree(tmp / "Dev" / "2.2.0-beta1"), shutil.rmtree(tmp / "Dev" / "2.2.0-beta2")
        self.assertIsNone(firmware.cached_zip("Dev", fw_dir=tmp, prerelease=True))


if __name__ == "__main__":
    unittest.main()
