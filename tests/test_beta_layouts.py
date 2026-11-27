"""Run from ShellyOTA/: python -m unittest discover tests

Beta firmware and flash layouts: version order in send, layouts of compiled configs, CSV sizes, missing packages.
"""

import argparse
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ota  # noqa: E402
from shelly_ota import builder, compile as compile_, devicegen, lint, profile, sender  # noqa: E402


class VersionTests(unittest.TestCase):
    def test_a_beta_before_the_layout_is_refused_and_the_one_with_it_is_not(self):
        for name in ("PlugMG3", "Mini1PMG3", "RGBCCTBulbG3"):
            later = profile.load_profile(name).variants()[-1]
            with self.subTest(name):
                self.assertIn("2.2.0-beta2 and later", sender.old_layout_text(later, "2.2.0-beta1"))
                self.assertIsNone(sender.old_layout_text(later, "2.2.0-beta2"))
                self.assertIsNone(sender.old_layout_text(later, "2.2.1"))
                self.assertIsNotNone(sender.old_layout_text(later, "2.1.1"))
                self.assertIsNotNone(sender.old_layout_text(later, "unknown"))

    def test_an_old_layout_package_on_that_beta_gets_the_warning(self):
        p = profile.load_profile("Mini1PMG3")
        self.assertIsNotNone(sender.newer_layout_text(p, "2.2.0-beta2"))
        self.assertIsNone(sender.newer_layout_text(p, "2.2.0-beta1"))
        self.assertIsNone(sender.newer_layout_text(p, "2.1.1"))
        self.assertIsNone(sender.newer_layout_text(p.variants()[-1], "2.2.1"))

    def test_without_from_the_release_counts(self):
        later = profile.load_profile("Pro1").variants()[-1]
        self.assertIsNotNone(sender.old_layout_text(later, "2.2.0-beta2"))
        self.assertIsNone(sender.old_layout_text(later, "2.2.0"))

    def test_the_beta_profile_accepts_its_beta(self):
        p = profile.load_profile("PlugMG3-beta")
        self.assertIsNone(sender.old_layout_text(p, "2.2.0-beta2"))
        self.assertIsNotNone(sender.old_layout_text(p, "1.8.99-plugmg3prod0"))


class CsvSizeTests(unittest.TestCase):
    def test_suffixes(self):
        for text, value in (("0x300000", 0x300000), ("3M", 0x300000), ("3072K", 0x300000), (" 16k ", 0x4000), ("x", None), ("", None)):
            self.assertEqual(lint._parse_size(text), value, text)


class CompileLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.p = profile.load_profile("PlugSG3")
        (self.tmp / "my.yaml").write_text("packages:\n  base: !include base.yaml\n", encoding="utf-8")
        (self.tmp / "t.csv").write_text("app_0, app, ota_0, 0x20000, 3M,\n", encoding="utf-8")
        self.resolved = "esp32:\n  partitions: t.csv\n  framework:\n    type: esp-idf\n"

    def args(self, **kw):
        base = dict(app=None, image=None, runner="auto", compile=self.tmp / "my.yaml", layout=None, pt_addr=None,
                    esphome_factory=None, esphome_yaml=None)
        return argparse.Namespace(**{**base, **kw})

    def test_the_layout_comes_from_the_resolved_config(self):
        seen = []
        with mock.patch.object(compile_, "pick_runner"), mock.patch.object(compile_, "resolve_config", return_value=self.resolved), \
                mock.patch.object(lint, "lint_esphome", side_effect=lambda path, p, **kw: seen.append(p) or []), \
                mock.patch.object(compile_, "compile_yaml",
                                  return_value=argparse.Namespace(ota=self.tmp / "a.bin", factory=self.tmp / "no.bin")):
            found = ota._compile_for_build(self.args(), self.p)
        self.assertEqual(found.layout_since, "2.2.0")
        self.assertEqual(seen[0].app_slot_size, 0x300000)      # the config check uses that layout too

    def test_a_table_no_layout_has_stops_before_the_compile(self):
        (self.tmp / "t.csv").write_text("app_0, app, ota_0, 0x20000, 0x123000,\n", encoding="utf-8")
        with mock.patch.object(compile_, "pick_runner"), mock.patch.object(compile_, "resolve_config", return_value=self.resolved), \
                mock.patch.object(compile_, "compile_yaml") as compiled:
            with self.assertRaises(builder.OtaError):
                ota._compile_for_build(self.args(), self.p)
        compiled.assert_not_called()


if __name__ == "__main__":
    unittest.main()
