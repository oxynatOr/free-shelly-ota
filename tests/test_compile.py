"""Compile step: runner choice, the command line per OS and finding the binaries, with a fake process (no Docker or ESPHome needed).

Run from ShellyOTA/: python -m unittest discover tests
"""

import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelly_ota import builder, compile as comp  # noqa: E402


def only(*names):
    return lambda n: f"/usr/bin/{n}" if n in names else None


class Runner(unittest.TestCase):
    def test_auto_prefers_esphome(self):
        self.assertEqual(comp.pick_runner("auto", only("esphome", "docker")), "esphome")

    def test_auto_falls_back_to_docker(self):
        self.assertEqual(comp.pick_runner("auto", only("docker")), "docker")

    def test_explicit_runner_does_not_fall_back(self):
        with self.assertRaises(comp.CompileError):
            comp.pick_runner("esphome", only("docker"))
        self.assertEqual(comp.pick_runner("docker", only("esphome", "docker")), "docker")

    def test_nothing_installed_gives_a_hint(self):
        with self.assertRaises(comp.CompileError) as ctx:
            comp.pick_runner("auto", only())
        self.assertIn("Neither", str(ctx.exception))
        self.assertIn("install", str(ctx.exception).lower())

    def test_hint_names_the_runner_that_was_asked_for(self):
        with self.assertRaises(comp.CompileError) as ctx:
            comp.pick_runner("docker", only("esphome"))
        self.assertIn("Docker", str(ctx.exception))
        self.assertNotIn("pipx", str(ctx.exception))
        with self.assertRaises(comp.CompileError) as ctx:
            comp.pick_runner("esphome", only("docker"))
        self.assertIn("ESPHome", str(ctx.exception))
        self.assertNotIn("Docker", str(ctx.exception))

    def test_unknown_runner(self):
        with self.assertRaises(comp.CompileError):
            comp.pick_runner("podman", only("docker"))

    def test_error_is_an_ota_error(self):
        self.assertTrue(issubclass(comp.CompileError, builder.OtaError))


class Command(unittest.TestCase):
    def setUp(self):
        self.yaml = Path(tempfile.mkdtemp()) / "plug.yaml"
        self.yaml.write_text("esphome:\n  name: plug\n")

    def test_esphome(self):
        cmd = comp.build_command("esphome", self.yaml)
        self.assertEqual(cmd[:2], ["esphome", "compile"])
        self.assertEqual(Path(cmd[2]), self.yaml.resolve())

    def test_docker_linux_runs_as_the_user(self):
        cmd = comp.build_command("docker", self.yaml, "img:1", posix=True, uid_gid=(1000, 1001))
        self.assertEqual(cmd[:3], ["docker", "run", "--rm"])
        self.assertIn("1000:1001", cmd)
        self.assertEqual(cmd[-3:], ["img:1", "compile", "/config/plug.yaml"])

    def test_docker_windows_has_no_user_option(self):
        cmd = comp.build_command("docker", self.yaml, "img:1", posix=False)
        self.assertNotIn("--user", cmd)
        self.assertEqual(cmd[cmd.index("-v") + 1], f"{self.yaml.resolve().parent}:/config")

    def test_docker_keeps_the_toolchain_in_a_named_volume(self):
        cmd = comp.build_command("docker", self.yaml, "img:1", posix=False)
        self.assertIn(f"{comp.CACHE_VOLUME}:/cache", cmd)
        self.assertIn("ESPHOME_DATA_DIR=/cache/data", cmd)
        self.assertIn("ESPHOME_ESP_IDF_PREFIX=/cache/idf", cmd)
        self.assertIn("HOME=/cache/home", cmd)     # the user's home is not writable in the container on Linux
        self.assertEqual(cmd[cmd.index("-v") + 1], f"{self.yaml.resolve().parent}:/config")

    def test_prepare_volume_hands_it_to_the_linux_user(self):
        cmd = comp.prepare_volume_command("img:1", uid_gid=(1000, 1001))
        self.assertIn(f"{comp.CACHE_VOLUME}:/cache", cmd)
        self.assertEqual(cmd[cmd.index("--entrypoint") + 1], "sh")
        self.assertNotIn("--user", cmd)            # it runs as root: only root may chown
        self.assertIn("mkdir -p /cache/data /cache/idf /cache/home", cmd[-1])
        self.assertIn("chown -R 1000:1001 /cache", cmd[-1])
        self.assertIn('= "1000"', cmd[-1])         # only when the volume does not belong to the user yet

    def test_prepare_volume_on_windows_or_as_root_does_not_chown(self):
        for ids in (None, (0, 0)):
            self.assertNotIn("chown", comp.prepare_volume_command("img:1", uid_gid=ids)[-1])

    def test_copy_back_command(self):
        cmd = comp.copy_back_command(self.yaml, "img:1", posix=True, uid_gid=(1000, 1001))
        self.assertEqual(cmd[:3], ["docker", "run", "--rm"])
        self.assertIn("1000:1001", cmd)
        self.assertIn(f"{comp.CACHE_VOLUME}:/cache", cmd)
        self.assertEqual(cmd[cmd.index("--entrypoint") + 1], "sh")
        script = cmd[-3]
        self.assertEqual(cmd[-2:], ["sh", "/config"])      # the YAML's folder in the container: $1 of the script
        self.assertIn("firmware.ota.bin", script)
        self.assertIn("firmware.factory.bin", script)
        self.assertIn("$1/.esphome/build/", script)

    def test_a_git_repository_is_mounted_whole_so_includes_next_to_it_are_found(self):
        repo = Path(tempfile.mkdtemp())
        (repo / ".git").mkdir()
        (repo / "examples").mkdir()
        (repo / "projects").mkdir()
        yaml = repo / "examples" / "full.yaml"
        yaml.write_text("packages:\n  base: !include ../projects/p.yaml\n")
        self.assertEqual(comp.mount_root(yaml), repo.resolve())
        cmd = comp.build_command("docker", yaml, "img:1", posix=False)
        self.assertEqual(cmd[cmd.index("-v") + 1], f"{repo.resolve()}:/config")
        self.assertEqual(cmd[-3:], ["img:1", "compile", "/config/examples/full.yaml"])
        back = comp.copy_back_command(yaml, "img:1", posix=False)
        self.assertEqual(back[-1], "/config/examples")       # the binaries land next to the YAML, not in the repo root

    def test_without_a_repository_only_the_yaml_folder_is_mounted(self):
        self.assertEqual(comp.mount_root(self.yaml), self.yaml.resolve().parent)

    def test_the_action_can_be_config(self):
        self.assertEqual(comp.build_command("esphome", self.yaml, action="config")[:2], ["esphome", "config"])
        self.assertEqual(comp.build_command("docker", self.yaml, "img:1", posix=False, action="config")[-2], "config")

    def test_default_image_is_pinned(self):
        self.assertRegex(comp.DEFAULT_IMAGE, r":\d{4}\.\d+\.\d+$")

        self.assertNotIn(":latest", comp.DEFAULT_IMAGE)
        self.assertIn(":", comp.DEFAULT_IMAGE)


class ResolveConfig(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.yaml = self.dir / "plug.yaml"
        self.yaml.write_text("packages:\n  a: github://x/y/z.yaml@v1\n")

    def test_returns_the_text_ESPHome_prints(self):
        seen = []

        def run(cmd, **kw):
            seen.append((cmd, kw))
            return SimpleNamespace(returncode=0, stdout="esp32:\n  board: x\n", stderr="INFO Reading\n")
        text = comp.resolve_config(self.yaml, "esphome", run=run, which=only("esphome"))
        self.assertEqual(text, "esp32:\n  board: x\n")
        self.assertEqual(seen[0][0][:2], ["esphome", "config"])
        self.assertTrue(seen[0][1]["capture_output"])      # kept in memory: it can hold secrets

    def test_docker_gets_the_daemon_check_and_the_volume_first(self):
        seen = []

        def run(cmd, **kw):
            seen.append(cmd)
            return SimpleNamespace(returncode=0, stdout="esp32: {}\n", stderr="")
        comp.resolve_config(self.yaml, "docker", run=run, which=only("docker"))
        self.assertEqual([c[1] for c in seen], ["info", "run", "run"])
        self.assertEqual(seen[2][-2], "config")

    def test_a_config_ESPHome_rejects_says_why(self):
        def run(cmd, **kw):
            return SimpleNamespace(returncode=2, stdout="", stderr="INFO Reading\nFailed config\n  Error including file 'x'\n")
        with self.assertRaises(comp.CompileError) as ctx:
            comp.resolve_config(self.yaml, "esphome", run=run, which=only("esphome"))
        self.assertIn("Error including file 'x'", str(ctx.exception))
        self.assertNotIn("INFO Reading", str(ctx.exception))

    def test_the_message_on_stdout_is_found_too(self):
        # the esphome command prints "Failed config" on stdout and only INFO lines on stderr
        out = "Failed config\n\npackages: [source x.yaml:3]\n  \n  git is not installed. See https://git-scm.com\n  base: IncludeFile(a.yaml)\n"
        for _ in range(3):
            out += "  a: 1\n"

        def run(cmd, **kw):
            return SimpleNamespace(returncode=2, stdout=out, stderr="INFO ESPHome 2026.10.0\nINFO Cloning https://x\n")
        with self.assertRaises(comp.CompileError) as ctx:
            comp.resolve_config(self.yaml, "esphome", run=run, which=only("esphome"))
        self.assertIn("git is not installed", str(ctx.exception))
        self.assertNotIn("INFO", str(ctx.exception))

    def test_a_failure_without_any_text_still_says_something(self):
        def run(cmd, **kw):
            return SimpleNamespace(returncode=1, stdout="", stderr="INFO only\n")
        with self.assertRaises(comp.CompileError) as ctx:
            comp.resolve_config(self.yaml, "esphome", run=run, which=only("esphome"))
        self.assertIn("esphome config", str(ctx.exception))

    def test_yaml_not_found(self):
        with self.assertRaises(comp.CompileError):
            comp.resolve_config(self.dir / "nope.yaml", "esphome", which=only("esphome"))


class Compile(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.yaml = self.dir / "plug.yaml"
        self.yaml.write_text("esphome:\n  name: plug\n")
        self.out = self.dir / ".esphome" / "build" / "plug" / ".pioenvs" / "plug"

    def fake_run(self, code=0, files=(comp.OTA_BIN, comp.FACTORY_BIN)):
        def run(cmd, **kw):
            self.cmd = cmd
            if code == 0:
                self.out.mkdir(parents=True, exist_ok=True)
                for f in files:
                    (self.out / f).write_bytes(b"x")
            return SimpleNamespace(returncode=code)
        return run

    def test_returns_the_binaries(self):
        got = comp.compile_yaml(self.yaml, "esphome", run=self.fake_run(), which=only("esphome"))
        self.assertEqual(got.ota, self.out / comp.OTA_BIN)
        self.assertEqual(got.factory, self.out / comp.FACTORY_BIN)
        self.assertEqual(self.cmd[0], "esphome")

    def test_failed_compile(self):
        with self.assertRaises(comp.CompileError) as ctx:
            comp.compile_yaml(self.yaml, "esphome", run=self.fake_run(code=2), which=only("esphome"))
        self.assertIn("exit code 2", str(ctx.exception))

    def test_binary_missing(self):
        with self.assertRaises(comp.CompileError) as ctx:
            comp.compile_yaml(self.yaml, "esphome", run=self.fake_run(files=()), which=only("esphome"))
        self.assertIn(comp.OTA_BIN, str(ctx.exception))

    def test_factory_missing(self):
        with self.assertRaises(comp.CompileError) as ctx:
            comp.compile_yaml(self.yaml, "esphome", run=self.fake_run(files=(comp.OTA_BIN,)), which=only("esphome"))
        self.assertIn(comp.FACTORY_BIN, str(ctx.exception))

    def test_old_binaries_from_an_earlier_build_do_not_count(self):
        self.out.mkdir(parents=True)
        for f in (comp.OTA_BIN, comp.FACTORY_BIN):
            p = self.out / f
            p.write_bytes(b"old")
            old = time.time() - 3600
            import os
            os.utime(p, (old, old))
        with self.assertRaises(comp.CompileError):
            comp.compile_yaml(self.yaml, "esphome", run=lambda cmd, **kw: SimpleNamespace(returncode=0),
                              which=only("esphome"))

    def test_yaml_not_found(self):
        with self.assertRaises(comp.CompileError):
            comp.compile_yaml(self.dir / "nope.yaml", "esphome", run=self.fake_run(), which=only("esphome"))

    def test_process_cannot_start(self):
        def boom(cmd, **kw):
            raise OSError("no such file")
        with self.assertRaises(comp.CompileError):
            comp.compile_yaml(self.yaml, "esphome", run=boom, which=only("esphome"))

    def test_docker_not_running_stops_before_the_compile(self):
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            return SimpleNamespace(returncode=1)
        with self.assertRaises(comp.CompileError) as ctx:
            comp.compile_yaml(self.yaml, "docker", run=run, which=only("docker"))
        self.assertIn("not running", str(ctx.exception))
        self.assertEqual(calls, [["docker", "info"]])

    def test_docker_running_compiles(self):
        inner = self.fake_run()
        seen = []

        def run(cmd, **kw):
            seen.append(cmd)
            return SimpleNamespace(returncode=0) if cmd[:2] == ["docker", "info"] else inner(cmd, **kw)
        got = comp.compile_yaml(self.yaml, "docker", run=run, which=only("docker"))
        self.assertEqual([c[1] for c in seen], ["info", "run", "run", "run"])   # daemon, volume, compile, copy back
        self.assertIn("--entrypoint", seen[1])
        self.assertEqual(seen[2][-2], "compile")
        self.assertIn("--entrypoint", seen[3])
        self.assertEqual(got.ota, self.out / comp.OTA_BIN)

    def test_volume_cannot_be_prepared(self):
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            return SimpleNamespace(returncode=1 if "--entrypoint" in cmd else 0)
        with self.assertRaises(comp.CompileError) as ctx:
            comp.compile_yaml(self.yaml, "docker", run=run, which=only("docker"))
        self.assertIn("prepare", str(ctx.exception))
        self.assertEqual(len(calls), 2)            # daemon check and the volume step, no compile

    def test_copy_back_failure(self):
        inner = self.fake_run()

        def run(cmd, **kw):
            if "--entrypoint" in cmd and "compile" not in cmd and "chown" not in cmd[-1] and "mkdir -p /cache/data /" not in cmd[-1]:
                return SimpleNamespace(returncode=1)      # the copy-back step
            if cmd[:2] == ["docker", "info"] or "mkdir -p /cache/data /" in cmd[-1]:
                return SimpleNamespace(returncode=0)
            return inner(cmd, **kw)
        with self.assertRaises(comp.CompileError) as ctx:
            comp.compile_yaml(self.yaml, "docker", run=run, which=only("docker"))
        self.assertIn("copying", str(ctx.exception))

    def test_esp_idf_layout_is_found(self):
        native = self.dir / ".esphome" / "build" / "plug" / "build"
        native.mkdir(parents=True)
        for f in (comp.OTA_BIN, comp.FACTORY_BIN):
            (native / f).write_bytes(b"x")
        got = comp.find_binaries(self.dir)
        self.assertEqual(got.ota, native / comp.OTA_BIN)
        self.assertEqual(got.factory, native / comp.FACTORY_BIN)

    def test_esphome_runner_does_not_ask_docker(self):
        inner = self.fake_run()
        comp.compile_yaml(self.yaml, "esphome", run=inner, which=only("esphome", "docker"))
        self.assertEqual(self.cmd[0], "esphome")


if __name__ == "__main__":
    unittest.main()
