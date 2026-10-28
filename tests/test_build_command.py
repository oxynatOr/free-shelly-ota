"""The build command's handling of existing output files. Run from ShellyOTA/: python -m unittest discover tests"""

import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ota  # noqa: E402
from shelly_ota import firmware  # noqa: E402
from test_builder import fake_app  # noqa: E402


class BuildOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.app = self.tmp / "firmware.ota.bin"      # ESPHome's name, so every build gets the same automatic one
        self.app.write_bytes(fake_app(100_000))
        self.other = self.tmp / "other"
        self.other.mkdir()
        (self.other / "firmware.ota.bin").write_bytes(fake_app(100_000) + b"\0" * 16)
        patcher = mock.patch.object(ota, "MODULE_DIR", self.tmp)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.out_dir = self.tmp / "out"

    def run_ota(self, *argv) -> tuple[int, str]:
        buf = io.StringIO()
        code = 0
        with mock.patch.object(sys, "argv", ["ota.py", "--color", "never", *argv]), contextlib.redirect_stdout(buf), \
                contextlib.redirect_stderr(buf):
            try:
                ota.main()
            except SystemExit as e:      # sys.exit("Error: ...") carries the message instead of printing it
                code = e.code if isinstance(e.code, int) else 1
                if isinstance(e.code, str):
                    buf.write(e.code)
        return code, buf.getvalue()

    def build(self, *extra, app=None):
        official = firmware.cached_zip("PlugMG3")
        return self.run_ota("build", "PlugMG3", str(app or self.app), "--official", str(official), *extra)

    def packages(self) -> dict[str, bytes]:
        return {p.name: p.read_bytes() for p in sorted(self.out_dir.glob("*"))} if self.out_dir.exists() else {}

    def test_dry_run_writes_nothing(self):
        code, text = self.build("--dry-run")
        self.assertEqual(code, 0, text)
        self.assertIn("DRY RUN", text)
        self.assertEqual(self.packages(), {})

    def test_dry_run_leaves_an_existing_package_and_its_files_alone(self):
        code, text = self.build()
        self.assertEqual(code, 0, text)
        before = self.packages()
        self.assertEqual(len(before), 3, sorted(before))         # zip, .sha256, .report.json

        code, text = self.build("--dry-run", app=self.other / "firmware.ota.bin")
        self.assertEqual(code, 0, text)
        self.assertIn("DRY RUN", text)
        self.assertIn("already exists", text)                   # a real build would stop: say so
        self.assertEqual(self.packages(), before)

    def test_dry_run_with_an_explicit_output_leaves_it_alone(self):
        target = self.tmp / "mine.zip"
        target.write_bytes(b"precious")
        code, text = self.build("--dry-run", "-o", str(target))
        self.assertEqual(code, 0, text)
        self.assertEqual(target.read_bytes(), b"precious")

    def test_dry_run_still_refuses_an_output_that_is_an_input(self):
        code, text = self.build("--dry-run", "-o", str(self.app))
        self.assertNotEqual(code, 0)
        self.assertIn("must not overwrite an input", text)

    def test_second_build_with_the_same_automatic_name_stops(self):
        self.assertEqual(self.build()[0], 0)
        before = self.packages()
        code, text = self.build(app=self.other / "firmware.ota.bin")
        self.assertNotEqual(code, 0)
        self.assertIn("already exists", text)
        self.assertIn("--force", text)
        self.assertEqual(self.packages(), before)

    def test_force_replaces_the_automatic_name(self):
        self.assertEqual(self.build()[0], 0)
        first = self.packages()
        code, text = self.build("--force", app=self.other / "firmware.ota.bin")
        self.assertEqual(code, 0, text)
        after = self.packages()
        self.assertEqual(sorted(after), sorted(first))
        zip_name = next(n for n in after if n.endswith(".zip"))
        self.assertNotEqual(after[zip_name], first[zip_name])

    def test_tag_gives_a_second_package_next_to_the_first(self):
        self.assertEqual(self.build()[0], 0)
        code, text = self.build("--tag", "b", app=self.other / "firmware.ota.bin")
        self.assertEqual(code, 0, text)
        self.assertEqual(len([n for n in self.packages() if n.endswith(".zip")]), 2)

    def test_explicit_output_is_replaced_without_force(self):
        target = self.tmp / "mine.zip"
        self.assertEqual(self.build("-o", str(target))[0], 0)
        first = target.read_bytes()
        self.assertEqual(self.build("-o", str(target), app=self.other / "firmware.ota.bin")[0], 0)
        self.assertNotEqual(target.read_bytes(), first)

    # --compile: the binaries come from compile_yaml (faked here), everything after that is the normal build.
    def test_neither_app_nor_compile(self):
        code, text = self.run_ota("build", "PlugMG3")
        self.assertNotEqual(code, 0)
        self.assertIn("--compile", text)

    def test_app_and_compile_together(self):
        code, text = self.run_ota("build", "PlugMG3", str(self.app), "--compile", str(self.tmp / "x.yaml"))
        self.assertNotEqual(code, 0)
        self.assertIn("not both", text)

    def test_runner_without_compile(self):
        code, text = self.build("--runner", "docker")
        self.assertNotEqual(code, 0)
        self.assertIn("--compile", text)

    def test_compile_feeds_the_build(self):
        yaml = self.tmp / "plug.yaml"
        yaml.write_text("esp32: {}\n")
        factory = self.tmp / "firmware.factory.bin"
        compiled = ota.compile_.Compiled(self.app, factory)
        seen = {}

        def fake_build(p, app, official, target, **kw):
            seen.update(app=app, factory=kw["factory"])
            raise ota.builder.OtaError("stop here")

        with mock.patch.object(ota.lint, "lint_esphome", return_value=[]), \
                mock.patch.object(ota.lint, "lint_warnings", return_value=[]), \
                mock.patch.object(ota.compile_, "pick_runner"), \
                mock.patch.object(ota.compile_, "compile_yaml", return_value=compiled) as comp, \
                mock.patch.object(ota.builder, "build", fake_build):
            code, text = self.run_ota("build", "PlugMG3", "--compile", str(yaml), "--runner", "docker",
                                      "--official", str(firmware.cached_zip("PlugMG3")))
        comp.assert_called_once_with(yaml, "docker", ota.compile_.DEFAULT_IMAGE)
        self.assertEqual(seen, {"app": self.app, "factory": factory})
        self.assertIn("stop here", text)

    def test_existing_package_stops_before_the_compile(self):
        self.assertEqual(self.build()[0], 0)                       # firmware.ota.bin gives the automatic name
        with mock.patch.object(ota.lint, "lint_esphome", return_value=[]), \
                mock.patch.object(ota.compile_, "compile_yaml") as comp:
            code, text = self.run_ota("build", "PlugMG3", "--compile", str(self.tmp / "x.yaml"))
        self.assertNotEqual(code, 0)
        self.assertIn("already exists", text)
        comp.assert_not_called()

    def test_a_config_with_packages_is_resolved_by_esphome_and_checked_like_any_other(self):
        yaml = self.tmp / "p.yaml"
        yaml.write_text("packages:\n  base: github://x/y/z.yaml@v1\n")
        resolved = ("esp32:\n  partitions: PlugMG3-stock.csv\n  framework:\n    type: esp-idf\n    sdkconfig_options:\n"
                    "      CONFIG_PARTITION_TABLE_OFFSET: \"0x10000\"\nota:\n  - platform: esphome\n    allow_partition_access: true\n")
        (self.tmp / "PlugMG3-stock.csv").write_text("app_0, app, ota_0, 0x20000, 0x2a0000,\n")
        compiled = ota.compile_.Compiled(self.app, self.tmp / "firmware.factory.bin")
        with mock.patch.object(ota.compile_, "pick_runner"), \
                mock.patch.object(ota.compile_, "resolve_config", return_value=resolved) as res, \
                mock.patch.object(ota.compile_, "compile_yaml", return_value=compiled) as comp, \
                mock.patch.object(ota.builder, "build", side_effect=ota.builder.OtaError("stop here")):
            code, text = self.run_ota("build", "PlugMG3", "--compile", str(yaml),
                                      "--official", str(firmware.cached_zip("PlugMG3")))
        res.assert_called_once()
        comp.assert_called_once()                                  # the check passed on the resolved config
        self.assertIn("asking ESPHome for the full config", text)
        self.assertIn("config check OK", text)
        self.assertIn("stop here", text)

    def test_a_resolved_config_without_the_partition_table_is_refused_before_the_compile(self):
        yaml = self.tmp / "p.yaml"
        yaml.write_text("packages:\n  base: github://x/y/z.yaml@v1\n")
        with mock.patch.object(ota.compile_, "pick_runner"), \
                mock.patch.object(ota.compile_, "resolve_config", return_value="esp32:\n  board: x\n"), \
                mock.patch.object(ota.compile_, "compile_yaml") as comp:
            code, text = self.run_ota("build", "PlugMG3", "--compile", str(yaml))
        self.assertNotEqual(code, 0)
        self.assertIn("config check failed", text)
        comp.assert_not_called()

    def test_esphome_yaml_with_packages_only_says_what_to_do(self):
        yaml = self.tmp / "p.yaml"
        yaml.write_text("packages:\n  base: !include other.yaml\n")
        code, text = self.build("--esphome-yaml", str(yaml), "--dry-run")
        self.assertNotEqual(code, 0)
        self.assertIn("packages", text)
        self.assertIn("--compile", text)

    def test_config_problem_stops_before_the_compile(self):
        (self.tmp / "x.yaml").write_text("esp32: {}\n")
        with mock.patch.object(ota.lint, "lint_esphome", return_value=["bad partition"]), \
                mock.patch.object(ota.compile_, "compile_yaml") as comp:
            code, text = self.run_ota("build", "PlugMG3", "--compile", str(self.tmp / "x.yaml"))
        self.assertNotEqual(code, 0)
        self.assertIn("bad partition", text)
        comp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
