"""A package that keeps Shelly's bootloader (built without --esphome-factory) is not sent without --force."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from needs_fw import needs_fw  # noqa: E402
from shelly_ota import builder, firmware, profile, sender  # noqa: E402
from test_builder import fake_app  # noqa: E402
from test_extras import FakeRpcShelly  # noqa: E402


class PlainPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile = profile.load_profile("DuoBulbG3")
        self.official = firmware.cached_zip("DuoBulbG3")
        app = self.tmp / "app.bin"
        app.write_bytes(fake_app(100_000))
        self.plain = self.tmp / "plain.zip"
        builder.build(self.profile, app, self.official, self.plain)   # no factory image: Shelly's bootloader stays
        self.shelly = FakeRpcShelly()
        self.addCleanup(self.shelly.close)
        self.lines = []

    def _send(self, zip_path, **kw):
        return sender.send(self.profile, zip_path, self.shelly.addr, port=0, assume_yes=True, timeout=10,
                           out=self.lines.append, **kw)

    @needs_fw
    def test_refused_without_force(self):
        with self.assertRaises(builder.OtaError) as cm:
            self._send(self.plain)
        text = str(cm.exception)
        self.assertIn("KEEPS SHELLY'S BOOTLOADER", text)
        self.assertIn("--esphome-factory", text)
        self.assertIn("--force", text)
        self.assertEqual(self.shelly.updates, [])   # nothing was sent

    @needs_fw
    def test_dry_run_is_refused_too(self):
        with self.assertRaises(builder.OtaError):
            self._send(self.plain, dry_run=True)

    @needs_fw
    def test_force_sends_and_repeats_the_text_as_a_warning(self):
        self._send(self.plain, force=True)
        self.assertEqual(len(self.shelly.updates), 1)
        warn = [l for l in self.lines if l.startswith("WARNING: THIS PACKAGE KEEPS SHELLY'S BOOTLOADER")]
        self.assertEqual(len(warn), 1, self.lines)
        self.assertIn("sending anyway", warn[0])
        self.assertTrue(any("three starts" in l for l in self.lines), self.lines)   # the note after the update

    @needs_fw
    def test_official_package_is_not_refused(self):
        for kw in ({}, {"restoring": True}):
            self.shelly.updates.clear()
            self.lines.clear()
            self._send(self.official, **kw)
            self.assertEqual(len(self.shelly.updates), 1)
            self.assertFalse(any("KEEPS SHELLY'S BOOTLOADER" in l or "three starts" in l for l in self.lines), self.lines)


if __name__ == "__main__":
    unittest.main()
