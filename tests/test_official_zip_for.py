"""sender.official_zip_for: a package is compared with the official ZIP of its own base version (#142)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelly_ota import sender  # noqa: E402


class OfficialZipForTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        for v in ("2.1.0", "2.1.1", "2.2.0-beta2"):
            d = self.tmp / "S1PMG4" / v
            d.mkdir(parents=True)
            (d / "S1PMG4.zip").write_bytes(b"")
        self.stable = SimpleNamespace(package_name="S1PMG4", channel="stable")
        self.beta = SimpleNamespace(package_name="S1PMG4", channel="beta")

    def _version(self, profile, version):
        path = sender.official_zip_for(profile, version, fw_dir=self.tmp)
        return path.parent.name if path else None

    def test_a_beta_package_on_a_stable_profile_is_compared_with_the_beta_zip(self):
        self.assertEqual(self._version(self.stable, "2.2.0-beta2"), "2.2.0-beta2")

    def test_a_stable_package_is_compared_with_its_own_version(self):
        self.assertEqual(self._version(self.stable, "2.1.0"), "2.1.0")
        self.assertEqual(self._version(self.beta, "2.1.1"), "2.1.1")

    def test_an_unknown_or_missing_version_falls_back_to_the_channel(self):
        self.assertEqual(self._version(self.stable, "9.9.9"), "2.1.1")
        self.assertEqual(self._version(self.stable, None), "2.1.1")
        self.assertEqual(self._version(self.beta, "9.9.9"), "2.2.0-beta2")

    def test_nothing_cached(self):
        self.assertIsNone(sender.official_zip_for(self.stable, "2.1.1", fw_dir=self.tmp / "none"))


if __name__ == "__main__":
    unittest.main()
