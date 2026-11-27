"""Run from ShellyOTA/: python -m unittest discover tests

Beta firmware and flash layouts: version order in send, layouts of compiled configs, CSV sizes, missing packages.
"""

import argparse
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ota  # noqa: E402
from shelly_ota import builder, compile as compile_, firmware, lint, profile, sender  # noqa: E402


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


class ChannelTests(unittest.TestCase):
    def setUp(self):
        self.p = profile.load_profile("PlugSG3").variants()[-1]

    def test_beta_only_on_request(self):
        with mock.patch.object(firmware, "zip_for_layout", return_value=None) as pick:
            self.assertIsNone(ota._cached_official(self.p, self.p, None, "beta"))
        self.assertTrue(pick.call_args.kwargs["prerelease"])
        with mock.patch.object(firmware, "cached_zip", return_value=None) as cached:
            ota._cached_official(self.p, None, None, "stable")
        self.assertFalse(cached.call_args.kwargs["prerelease"])

    def test_a_layout_only_a_beta_has_is_named_not_taken(self):
        found = lambda v, version=None, prerelease=False: Path("b.zip") if prerelease else None
        with mock.patch.object(firmware, "zip_for_layout", side_effect=found):
            with self.assertRaises(builder.OtaError) as cm:
                ota._cached_official(self.p, self.p, None, "stable")
            self.assertIn("--channel beta", str(cm.exception))
            self.assertEqual(ota._cached_official(self.p, self.p, None, "beta"), Path("b.zip"))


class TableTests(unittest.TestCase):
    def test_a_wrong_row_beside_the_app_slot_is_a_warning(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        p = profile.load_profile("PlugSG3").variants()[-1]
        good = lint.shipped_table(p)
        (tmp / "t.csv").write_text(good, encoding="utf-8")
        config = ["esp32:", "  partitions: t.csv", "ota:", "  - platform: esphome", "    allow_partition_access: true"]
        (tmp / "my.yaml").write_text(chr(10).join(config), encoding="utf-8")
        self.assertEqual(lint.lint_warnings(tmp / "my.yaml", profile=p), [])
        (tmp / "t.csv").write_text(good.replace("0x700000", "0x6f0000"), encoding="utf-8")
        warnings = lint.lint_warnings(tmp / "my.yaml", profile=p)
        self.assertEqual(len(warnings), 1)
        self.assertIn("fs_1", warnings[0])

    def test_every_shipped_csv_agrees_with_itself_and_suffixes_compare_equal(self):
        self.assertEqual(lint.table_differences("app_0, app, ota_0, , 3M,", "app_0, app, ota_0, 0x20000, 0x300000,"), [])

    def test_a_moved_table_is_read_for_the_layout(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        for name in ("PlugSG3", "S1G3"):       # table at 0x10000 and at 0xf000
            for variant in profile.load_profile(name).variants():
                entry = struct.pack("<2sBBII16sI", bytes((0xAA, 0x50)), 0, 0x10, 0x20000, variant.app_slot_size, b"app_0", 0)
                factory = bytearray(bytes((0xFF,)) * 0x12000)
                factory[builder.RELOCATED_PT_ADDR:builder.RELOCATED_PT_ADDR + 32] = entry
                (tmp / "factory.bin").write_bytes(bytes(factory))
                with self.subTest(name=name, size=variant.app_slot_size):
                    self.assertEqual(ota._table_app_size(variant, None, tmp / "factory.bin"), variant.app_slot_size)


if __name__ == "__main__":
    unittest.main()
