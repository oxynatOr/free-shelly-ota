"""Version information: tool build info, profile revisions and their lock, report fields, the line in send."""

import dataclasses
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelly_ota import MODULE_DIR, __version__, buildinfo, builder, firmware, profile, sender  # noqa: E402
from test_builder import fake_app  # noqa: E402
from test_extras import FakeRpcShelly  # noqa: E402


def fake_git(answers: dict, toplevel=None):
    """A stand-in for subprocess.run that answers `git ...` from a table."""
    def run(cmd, **kw):
        args = tuple(cmd[1:])
        if args == ("rev-parse", "--show-toplevel"):
            out = toplevel if toplevel is not None else str(MODULE_DIR)
            return SimpleNamespace(returncode=0 if out else 1, stdout=out or "")
        out = answers.get(args)
        return SimpleNamespace(returncode=0 if out is not None else 1, stdout=out or "")
    return run


FULL = {
    ("describe", "--tags", "--always", "--dirty"): "v0.2.0-3-gb225e1f-dirty",
    ("rev-parse", "--short", "HEAD"): "b225e1f",
    ("rev-parse", "--abbrev-ref", "HEAD"): "feature/x",
    ("log", "-1", "--format=%cs"): "2026-10-06",
}


class BuildInfoTests(unittest.TestCase):
    def test_full_info_in_a_git_checkout(self):
        info = buildinfo.get(run=fake_git(FULL))
        self.assertEqual(info.short(), f"{__version__} (feature/x, v0.2.0-3-gb225e1f-dirty, 2026-10-06)")
        self.assertTrue(info.dirty)
        self.assertEqual(info.commit, "b225e1f")
        self.assertEqual(info.as_dict()["branch"], "feature/x")

    def test_clean_release_checkout_shows_the_tag(self):
        answers = {**FULL, ("describe", "--tags", "--always", "--dirty"): "v0.2.0"}
        info = buildinfo.get(run=fake_git(answers))
        self.assertFalse(info.dirty)
        self.assertIn("v0.2.0,", info.short())

    def test_detached_head_is_named(self):
        answers = {**FULL, ("rev-parse", "--abbrev-ref", "HEAD"): "HEAD"}
        self.assertIn("detached", buildinfo.get(run=fake_git(answers)).short())

    def test_without_git_or_outside_the_own_repo_only_the_version(self):
        def no_git(cmd, **kw):
            raise FileNotFoundError("git")
        self.assertEqual(buildinfo.get(run=no_git).short(), __version__)
        self.assertEqual(buildinfo.get(run=fake_git(FULL, toplevel="")).short(), __version__)
        other_repo = str(MODULE_DIR.parent)           # the tool unpacked inside someone else's repository
        self.assertEqual(buildinfo.get(run=fake_git(FULL, toplevel=other_repo)).short(), __version__)


class ProfileRevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_every_shipped_profile_has_an_explicit_revision_and_the_lock_is_current(self):
        for name in profile.list_devices():
            text = (profile.DEVICES_DIR / f"{name}.yaml").read_text(encoding="utf-8")
            self.assertIn("\nrevision:", text, f"{name} has no revision")
            self.assertGreaterEqual(profile.load_profile(name).revision, 1)
        # If this fails: you changed a profile. Raise its `revision:` and run `python ota.py profiles --update-lock`.
        self.assertEqual(profile.check_lock(), [])

    def test_hash_ignores_the_revision_line_and_line_endings(self):
        (self.tmp / "A.yaml").write_text("platform: esp32\napp_slot_size: 0x1000\nrevision: 1\n", encoding="utf-8")
        h1 = profile.content_hash("A", self.tmp)
        (self.tmp / "A.yaml").write_bytes(b"platform: esp32\r\napp_slot_size: 0x1000\r\nrevision: 9\r\n")
        self.assertEqual(profile.content_hash("A", self.tmp), h1)
        (self.tmp / "A.yaml").write_text("platform: esp32\napp_slot_size: 0x2000\nrevision: 1\n", encoding="utf-8")
        self.assertNotEqual(profile.content_hash("A", self.tmp), h1)

    def test_a_change_needs_a_higher_revision_and_a_new_lock(self):
        path = self.tmp / "A.yaml"
        path.write_text("platform: esp32\napp_slot_size: 0x1000\nrevision: 1\n", encoding="utf-8")
        profile.write_lock(self.tmp)
        self.assertEqual(profile.check_lock(self.tmp), [])
        path.write_text("platform: esp32\napp_slot_size: 0x2000\nrevision: 1\n", encoding="utf-8")
        problems = profile.check_lock(self.tmp)
        self.assertEqual(len(problems), 1)
        self.assertIn("still 1", problems[0])
        path.write_text("platform: esp32\napp_slot_size: 0x2000\nrevision: 2\n", encoding="utf-8")
        self.assertIn("out of date", profile.check_lock(self.tmp)[0])      # revision raised, lock not yet written
        profile.write_lock(self.tmp)
        self.assertEqual(profile.check_lock(self.tmp), [])

    def test_missing_and_stale_lock_entries_are_reported(self):
        (self.tmp / "A.yaml").write_text("app_slot_size: 0x1000\nrevision: 1\n", encoding="utf-8")
        self.assertIn("not in profiles.lock", profile.check_lock(self.tmp)[0])
        profile.write_lock(self.tmp)
        (self.tmp / "A.yaml").unlink()
        self.assertIn("profile is gone", profile.check_lock(self.tmp)[0])


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile = profile.load_profile("PlugMG3")
        (self.tmp / "app.bin").write_bytes(fake_app(100_000))

    def _built(self):
        out = self.tmp / "o.zip"
        res = builder.build(self.profile, self.tmp / "app.bin", firmware.cached_zip("PlugMG3"), out, tag="t1")
        builder.write_report(res)
        return out, json.loads(Path(str(out) + ".report.json").read_text(encoding="utf-8"))

    def test_report_says_which_tool_state_profile_and_options_made_the_package(self):
        _, data = self._built()
        self.assertEqual(data["tool_version"], __version__)
        self.assertEqual(data["tool_build"]["version"], __version__)
        self.assertEqual(data["profile"], {"name": "PlugMG3", "revision": self.profile.revision})
        self.assertEqual(data["options"], {"esphome_factory": False, "boot_min_version": None, "dropped": [], "tag": "t1"})
        self.assertNotIn(str(self.tmp), json.dumps(data))             # flags only, no local paths

    def test_send_prints_the_origin_of_the_package_and_notes_a_changed_profile(self):
        out, _ = self._built()
        shelly = FakeRpcShelly(app="PlugMG3")
        self.addCleanup(shelly.close)
        lines = []
        sender.send(self.profile, out, shelly.addr, port=0, dry_run=True, out=lines.append)
        package = [l for l in lines if l.startswith("Package: built")]
        self.assertEqual(len(package), 1, lines)
        self.assertIn(f"by free-shelly-ota {__version__}", package[0])
        self.assertIn(f"profile PlugMG3 revision {self.profile.revision}", package[0])
        self.assertFalse(any("has changed since this package" in l for l in lines), lines)
        newer = dataclasses.replace(self.profile, revision=self.profile.revision + 1)
        lines.clear()
        sender.send(newer, out, shelly.addr, port=0, dry_run=True, out=lines.append)
        self.assertTrue(any("has changed since this package was built" in l for l in lines), lines)

    def test_a_package_without_report_just_has_no_origin_line(self):
        out, _ = self._built()
        Path(str(out) + ".report.json").unlink()
        self.assertEqual(sender.package_info(out, self.profile), [])


class CommandLineTests(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, str(MODULE_DIR / "ota.py"), *args], capture_output=True, text=True,
                              encoding="utf-8", cwd=MODULE_DIR)

    def test_version_option_shows_the_build_info(self):
        out = self._run("--version").stdout.strip()
        self.assertTrue(out.startswith(f"ota.py {__version__}"), out)

    def test_commands_start_with_the_tool_line_except_data_output(self):
        first = self._run("list").stdout.splitlines()[0]
        self.assertTrue(first.startswith(f"free-shelly-ota {__version__}"), first)
        csv_first = self._run("partition-csv", "PlugMG3").stdout.splitlines()[0]
        self.assertTrue(csv_first.startswith("#"), csv_first)         # nothing before the CSV, so it can be piped

    def test_profiles_command_checks_the_lock(self):
        done = self._run("profiles")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("PlugMG3", done.stdout)


if __name__ == "__main__":
    unittest.main()
