"""Colored messages: when colors are used, and which line gets which color."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelly_ota import ui  # noqa: E402


class ShouldColorTests(unittest.TestCase):
    def test_auto_colors_only_on_a_terminal(self):
        self.assertTrue(ui.should_color("auto", True, {}))
        self.assertFalse(ui.should_color("auto", False, {}))

    def test_no_color_and_dumb_terminal_switch_it_off(self):
        self.assertFalse(ui.should_color("auto", True, {"NO_COLOR": "1"}))
        self.assertFalse(ui.should_color("auto", True, {"TERM": "dumb"}))

    def test_always_and_never_are_forced(self):
        self.assertTrue(ui.should_color("always", False, {"NO_COLOR": "1"}))
        self.assertFalse(ui.should_color("never", True, {}))


class ColorForTests(unittest.TestCase):
    def test_levels(self):
        cases = {
            "Error: something broke": ui.RED,
            "WARNING: the update target slot could not be read": ui.YELLOW,
            "  WARNING: Credentials were not checked (give --esphome-yaml ...)": ui.YELLOW,
            "WARNING: this package replaces Shelly's bootloader. If it does not suit the device": ui.ORANGE,
            "WARNING: this wipes NVS (Wi-Fi credentials and settings) and replaces the firmware.": ui.ORANGE,
            "  WARNING: BOOTLOADER REPLACED: the package carries ESPHome's bootloader": ui.ORANGE,
            "WARNING: the installer will write to slot 1, but ESPHome's bootloader starts app_0": ui.ORANGE,
            "WARNING: TLS certificate verification is OFF for this download.": ui.ORANGE,
            "NOTE: ESPHome's bootloader starts app_0": ui.CYAN,
            "OK: I:\\x\\y.zip": ui.GREEN,
            "Update target slot: 0 (the slot ESPHome's bootloader starts).": ui.GREEN,
            "ESPHome config check OK (x.yaml)": ui.GREEN,
            "  Credential check OK: none of 2 known values found in the image": ui.GREEN,
            "  all part hashes OK": ui.GREEN,
            "  log| shellyplugx 0 41.093 2 2|shos_rpc_inst.c:243 Sys.SetConfig": ui.DIM,
            "Device 192.168.33.1: app=PlugMG3": None,
            "Waiting for the device to download the ZIP ...": None,
        }
        for line, code in cases.items():
            self.assertEqual(ui.color_for(line), code, line)


class PaintTests(unittest.TestCase):
    def test_disabled_returns_the_text_unchanged(self):
        text = "WARNING: x\nplain"
        self.assertEqual(ui.paint(text, enabled=False), text)

    def test_enabled_wraps_colored_lines_and_keeps_the_words(self):
        out = ui.paint("OK: done", enabled=True)
        self.assertEqual(out, f"{ui.GREEN}OK: done{ui.RESET}")
        self.assertIn("WARNING:", ui.paint("WARNING: careful", enabled=True))

    def test_indented_continuation_lines_keep_the_color_of_the_message(self):
        text = "NOTE: first line\n      continued here\nplain again"
        lines = ui.paint(text, enabled=True).split("\n")
        self.assertTrue(lines[0].startswith(ui.CYAN))
        self.assertTrue(lines[1].startswith(ui.CYAN))     # continuation of the NOTE
        self.assertEqual(lines[2], "plain again")         # not indented: a new message

    def test_blank_lines_are_not_wrapped(self):
        self.assertEqual(ui.paint("NOTE: a\n\nb", enabled=True).split("\n")[1], "")

    def test_error_text_is_plain_without_a_terminal(self):
        self.assertEqual(ui.error("boom"), "Error: boom")   # stderr is not a terminal under the test runner


class ColorsCommandTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parent.parent

    def _run(self, *args):
        import os
        import subprocess
        env = {k: v for k, v in os.environ.items() if k not in ("NO_COLOR", "TERM")}   # do not depend on the caller's setup
        return subprocess.run([sys.executable, str(self.ROOT / "ota.py"), *args], capture_output=True, text=True,
                              encoding="utf-8", cwd=self.ROOT, env=env)

    def test_forced_colors_show_every_level(self):
        done = self._run("--color", "always", "colors")
        self.assertEqual(done.returncode, 0, done.stderr)
        for code in (ui.GREEN, ui.CYAN, ui.YELLOW, ui.ORANGE, ui.RED, ui.DIM):
            self.assertIn(code, done.stdout)
        self.assertIn("Colors are ON", done.stdout)

    def test_piped_output_has_no_codes_and_says_why(self):
        done = self._run("colors")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("\x1b", done.stdout)
        self.assertIn("Colors are OFF: the output is not a terminal", done.stdout)

    def test_why_off_names_the_reason(self):
        self.assertEqual(ui.why_off("never", True, {}), "--color never")
        self.assertIn("NO_COLOR", ui.why_off("auto", True, {"NO_COLOR": "1"}))
        self.assertIn("TERM=dumb", ui.why_off("auto", True, {"TERM": "dumb"}))
        self.assertIn("not a terminal", ui.why_off("auto", False, {}))

    def test_the_sources_are_plain_ascii(self):
        """A Windows console (cp1252) cannot print characters like arrows; a message with one would crash the command."""
        for path in [self.ROOT / "ota.py", *sorted((self.ROOT / "shelly_ota").glob("*.py"))]:
            try:
                path.read_bytes().decode("ascii")
            except UnicodeDecodeError as e:
                self.fail(f"{path.name} contains a non-ASCII character at byte {e.start}")


if __name__ == "__main__":
    unittest.main()
