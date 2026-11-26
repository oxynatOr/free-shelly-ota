"""Run from ShellyOTA/: python -m unittest discover tests

A profile with several flash layouts (`layouts:`): loading, choosing by package and by the user's table, build and send.
Most tests write their own profile; the shipped ones are checked too.
"""

import argparse
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ota  # noqa: E402
from needs_fw import needs_fw  # noqa: E402
from shelly_ota import builder, firmware, profile, sender  # noqa: E402
from test_builder import fake_app  # noqa: E402
from test_layout_check import zip_with_app_slot  # noqa: E402

YAML = """display_name: "Test plug"
platform: esp32c3
update_id: PlugMG3
package: PlugMG3
app_ptn: app_0
app_slot_size: 0x2a0000
layouts:
  - since: "2.2.0"
    app_slot_size: 0x300000
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "Plug.yaml").write_text(YAML, encoding="utf-8")
        self.p = profile.load_profile("Plug", self.tmp)

    def zips(self):
        """An official package of each layout, made from whatever PlugMG3 package is cached."""
        source = firmware.cached_zip("PlugMG3")
        out = {}
        for key, size in (("old", 0x2A0000), ("new", 0x300000)):
            out[key] = self.tmp / f"{key}.zip"
            zip_with_app_slot(source, out[key], "app_0", size)
        return out

    def args(self, **kw):
        values = {"layout": None, "esphome_yaml": None, "compile": None, "esphome_factory": None}
        values.update(kw)
        return argparse.Namespace(**values)

    def config(self, size):
        (self.tmp / "table.csv").write_text(f"app_0, app, ota_0, 0x20000, {size},\n", encoding="utf-8")
        path = self.tmp / "app.yaml"
        path.write_text("esp32:\n  partitions: table.csv\n", encoding="utf-8")
        return path


class LoadingTests(Base):
    def test_each_layout_is_an_ordinary_profile(self):
        old, new = self.p.variants()
        self.assertIs(old, self.p)
        self.assertEqual((old.app_slot_size, old.layout_since, old.csv_name), (0x2A0000, None, "Plug-stock.csv"))
        self.assertEqual((new.app_slot_size, new.layout_since, new.csv_name), (0x300000, "2.2.0", "Plug-stock-2.2.0.csv"))
        self.assertEqual(new.variants(), [old, new])   # a variant knows the others
        self.assertEqual(new.package_name, "PlugMG3")

    def test_shipped_profiles_with_one_layout_are_unchanged_by_this(self):
        for name in profile.list_devices():
            p = profile.load_profile(name)
            if p.layouts:
                continue
            self.assertEqual(len(p.variants()), 1, name)
            self.assertIs(p.variants()[0], p)
            self.assertEqual(p.csv_name, f"{name}-stock.csv")

    def test_every_shipped_layout_has_its_csv_with_that_slot_size(self):
        partitions = Path(__file__).resolve().parent.parent / "partitions"
        names = [n for n in profile.list_devices() if profile.load_profile(n).layouts]
        self.assertEqual(len(names), 24, names)
        for name in names:
            for variant in profile.load_profile(name).variants():
                text = (partitions / variant.csv_name).read_text(encoding="utf-8")
                row = next(l for l in text.splitlines() if l.startswith(variant.app_ptn + ","))
                self.assertEqual(int(row.split(",")[4], 0), variant.app_slot_size, variant.csv_name)

    def test_the_old_v2_names_are_aliases_of_one_layout(self):
        for name, since in (("PlugSG3", "2.2.0"), ("S2PMG3", "2.2.0"), ("Mini1PMG3", "2.2.1"), ("RGBCCTBulbG3", "2.2.1")):
            alias = profile.load_profile(f"{name}-v2")
            self.assertEqual((alias.name, alias.package_name, alias.app_slot_size, alias.layout_since),
                             (f"{name}-v2", name, 0x300000, since))
            self.assertEqual(alias.variants(), [alias])
            self.assertEqual(alias.csv_name, f"{name}-stock-{since}.csv")
            self.assertNotIn(f"{name}-v2", profile.list_devices())

    def test_bad_layout_lists_are_refused(self):
        for layouts in ('  - since: "2.2.0"\n', '  - app_slot_size: 0x300000\n',
                        '  - since: "2.2.0"\n    app_slot_size: 0x2a0000\n',
                        '  - since: "2.2.0"\n    app_slot_size: 0x300000\n  - since: "2.1.0"\n    app_slot_size: 0x310000\n'):
            (self.tmp / "Bad.yaml").write_text(YAML.split("layouts:")[0] + "layouts:\n" + layouts, encoding="utf-8")
            with self.assertRaises(profile.ProfileError, msg=layouts):
                profile.load_profile("Bad", self.tmp)


class ChoiceTests(Base):
    def test_the_users_csv_decides(self):
        for size, since in (("0x2a0000", None), ("0x300000", "2.2.0")):
            self.assertEqual(ota._layout_for_build(self.p, self.args(esphome_yaml=self.config(size))).layout_since, since)

    def test_layout_option_and_unknown_values(self):
        self.assertIs(ota._layout_for_build(self.p, self.args(layout="base")), self.p)
        self.assertEqual(ota._layout_for_build(self.p, self.args(layout="2.2.0")).app_slot_size, 0x300000)
        with self.assertRaises(builder.OtaError):
            ota._layout_for_build(self.p, self.args(layout="9.9.9"))
        with self.assertRaises(builder.OtaError):
            ota._layout_for_build(self.p, self.args(esphome_yaml=self.config("0x123000")))

    def test_without_a_table_the_package_decides(self):
        self.assertIsNone(ota._layout_for_build(self.p, self.args()))

    def test_a_profile_with_one_layout_is_left_alone(self):
        p = profile.load_profile("HTG3")
        self.assertIsNone(ota._layout_for_build(p, self.args(esphome_yaml=self.config("0x123000"))))
        with self.assertRaises(builder.OtaError):
            ota._layout_for_build(p, self.args(layout="2.2.0"))


class PackageTests(Base):
    @needs_fw
    def test_the_package_selects_its_layout_and_build_takes_it(self):
        zips = self.zips()
        app = self.tmp / "app.bin"
        app.write_bytes(fake_app(0x2B0000))   # fits only the new slot
        for key, since in (("old", None), ("new", "2.2.0")):
            self.assertEqual(builder.resolve_layout(self.p, zips[key]).layout_since, since)
        builder.build(self.p, app, zips["new"], self.tmp / "out.zip")
        with self.assertRaises(builder.OtaError):
            builder.build(self.p, app, zips["old"], self.tmp / "out2.zip")

    @needs_fw
    def test_a_package_of_no_known_layout_is_refused(self):
        other = self.tmp / "other.zip"
        zip_with_app_slot(firmware.cached_zip("PlugMG3"), other, "app_0", 0x340000)
        app = self.tmp / "app.bin"
        app.write_bytes(fake_app(100_000))
        with self.assertRaises(builder.OtaError) as cm:
            builder.build(self.p, app, other, self.tmp / "out.zip")
        self.assertIn("another flash layout", str(cm.exception))

    @needs_fw
    def test_cached_zip_per_layout_and_inspect(self):
        zips = self.zips()
        fw = self.tmp / "fw"
        for version, key in (("2.1.1", "old"), ("2.2.0", "new")):
            target = fw / "PlugMG3" / version / "PlugMG3.zip"
            target.parent.mkdir(parents=True)
            shutil.copy(zips[key], target)
        old, new = self.p.variants()
        self.assertEqual(firmware.zip_for_layout(old, fw_dir=fw).parent.name, "2.1.1")
        self.assertEqual(firmware.zip_for_layout(new, fw_dir=fw).parent.name, "2.2.0")
        self.assertIsNone(firmware.zip_for_layout(old, "2.2.0", fw_dir=fw))
        self.assertIn("the layout since 2.2.0 (Plug-stock-2.2.0.csv)", builder.inspect_zip(zips["new"], self.p))
        self.assertIn("the first layout", builder.inspect_zip(zips["old"], self.p))


class SendTextTests(Base):
    def test_old_firmware_refuses_the_new_layout_only(self):
        old, new = self.p.variants()
        self.assertIn("old flash layout", sender.old_layout_text(new, "2.1.1"))
        self.assertIsNone(sender.old_layout_text(new, "2.2.0"))
        self.assertIsNone(sender.old_layout_text(old, "1.4.4"))

    def test_an_old_package_on_new_firmware_gets_a_warning_not_a_refusal(self):
        old, new = self.p.variants()
        self.assertIn("Plug-stock-2.2.0.csv", sender.newer_layout_text(old, "2.2.0"))
        self.assertIsNone(sender.old_layout_text(old, "2.2.0"))
        self.assertIsNone(sender.newer_layout_text(old, "2.1.1"))
        self.assertIsNone(sender.newer_layout_text(new, "2.2.1"))
        self.assertIsNone(sender.newer_layout_text(profile.load_profile("HTG3"), "2.2.0"))


if __name__ == "__main__":
    unittest.main()
