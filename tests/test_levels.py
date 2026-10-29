"""send() at every level: what is shown, the progress, the device's own confirmation, and what happens on a failure.

Run from ShellyOTA/: python -m unittest discover tests
"""

import contextlib
import io
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from needs_fw import needs_fw  # noqa: E402
from shelly_ota import builder, firmware, logview, profile, sender, ui  # noqa: E402
from shelly_ota.logview import Level  # noqa: E402
from test_extras import FakeRpcShelly, free_udp_port  # noqa: E402

DONE_CONFIRMED = "Done: update installed, the device confirmed it."
DONE_DOWNLOADED = "Done: the device downloaded the ZIP."


class SendLevelTests(unittest.TestCase):
    def setUp(self):
        ui._progress_step.clear()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile = profile.load_profile("DuoBulbG3")
        self.zip = self.tmp / "t.zip"
        shutil.copy(firmware.cached_zip("DuoBulbG3"), self.zip)
        self.lines = []

    def _shelly(self, **kw):
        kw.setdefault("uptime", 500)
        s = FakeRpcShelly(**kw)
        self.addCleanup(s.close)
        return s

    def _send(self, shelly, level, **kw):
        return sender.send(self.profile, self.zip, shelly.addr, port=0, assume_yes=True, timeout=10,
                           log_port=free_udp_port(), sleep=lambda s: None, out=self.lines.append, level=level, **kw)

    def _starting_with(self, text):
        return [l for l in self.lines if l.startswith(text)]

    # --- a successful update that the device confirms

    @needs_fw
    def test_normal_shows_the_progress_and_the_confirmation_and_not_the_details(self):
        self.assertTrue(self._send(self._shelly(ota_events="success"), Level.normal))
        self.assertEqual(self._starting_with("Update:"), ["Update: 0 %", "Update: 50 %", "Update: 100 %"])
        self.assertTrue(self._starting_with(DONE_CONFIRMED), self.lines)
        self.assertTrue(self._starting_with("Device 127.0.0.1"))
        self.assertFalse(self._starting_with(DONE_DOWNLOADED))
        for hidden in ("Download URL", "Device accepted", "After the first ESPHome boot", "NOTE: the build"):
            self.assertFalse(self._starting_with(hidden), (hidden, self.lines))
        self.assertTrue(self.lines[-1].startswith("Device log: ") and "hidden" in self.lines[-1], self.lines[-1])

    @needs_fw
    def test_quiet_shows_only_the_result(self):
        self.assertTrue(self._send(self._shelly(ota_events="success"), Level.quiet))
        self.assertEqual(len(self.lines), 1, self.lines)
        self.assertTrue(self.lines[0].startswith(DONE_CONFIRMED))

    @needs_fw
    def test_verbose_adds_the_explanations_and_the_steps_of_the_device(self):
        self.assertTrue(self._send(self._shelly(ota_events="success"), Level.verbose))
        for shown in ("ZIP:", "Download URL", "Device accepted", "After the first ESPHome boot", "Device: The update started"):
            self.assertTrue(self._starting_with(shown), (shown, self.lines))
        self.assertFalse(self._starting_with("  log|"))

    @needs_fw
    def test_debug_shows_every_entry_of_the_device_log_on_its_own_line(self):
        self.assertTrue(self._send(self._shelly(ota_events="success"), Level.debug))
        entries = self._starting_with("  log|")
        self.assertEqual(len(entries), 6)             # begin, 0 %, 50 %, 100 %, success: five events and the log setup ...
        self.assertTrue(any("ota_success" in e or "Event ota_success" in e for e in entries), entries)

    @needs_fw
    def test_raw_shows_the_log_as_it_arrives(self):
        self.assertTrue(self._send(self._shelly(ota_events="success"), Level.raw))
        glued = [l for l in self._starting_with("  log|") if l.count("fakeshelly-aabbccddeeff ") > 1]
        self.assertTrue(glued, "the first datagram holds two entries")
        self.assertTrue(self._starting_with(DONE_CONFIRMED))

    # --- without a confirmation

    @needs_fw
    def test_a_log_that_never_arrives_falls_back_to_the_download(self):
        """No datagram reaches the PC (a firewall): no waiting, the old message."""
        self.assertTrue(self._send(self._shelly(send_log=False, ota_events="success"), Level.normal))
        self.assertTrue(self._starting_with(DONE_DOWNLOADED), self.lines)
        self.assertFalse(self._starting_with("Update:"))

    @needs_fw
    def test_a_device_log_that_cannot_be_switched_on_is_a_note_not_a_failure(self):
        self.assertTrue(self._send(self._shelly(getconfig_fails=True), Level.normal))
        self.assertTrue(any(l.startswith("NOTE: the device log is not available") for l in self.lines), self.lines)
        self.assertTrue(self._starting_with(DONE_DOWNLOADED))

    @needs_fw
    def test_a_device_without_update_events_is_not_waited_for(self):
        self.assertTrue(self._send(self._shelly(), Level.normal))      # the fake logs, but reports no update
        self.assertTrue(self._starting_with(DONE_DOWNLOADED))
        self.assertFalse(self._starting_with("NOTE: the device did not confirm"))

    # --- a failure

    @needs_fw
    def test_an_error_of_the_device_ends_the_run_and_shows_the_last_lines_even_when_quiet(self):
        with self.assertRaises(builder.OtaError) as cm:
            self._send(self._shelly(ota_events="error"), Level.quiet)
        self.assertIn("flash write failed", str(cm.exception))
        self.assertIn("Last lines of the device log:", self.lines)
        self.assertTrue(any("flash write failed" in l for l in self.lines), self.lines)
        self.assertFalse(self._starting_with("Done:"))

    @needs_fw
    def test_a_refusal_of_the_update_does_not_print_log_lines(self):
        s = self._shelly(update_refusals=[{"code": -109, "message": "Not committed"}])
        with self.assertRaises(builder.OtaError):
            self._send(s, Level.normal)
        self.assertNotIn("Last lines of the device log:", self.lines)

    # --- the log file

    @needs_fw
    def test_the_log_file_holds_everything_whatever_the_level(self):
        path = self.tmp / "logs" / "t.send.log"
        logfile = logview.LogFile(path)
        self.assertTrue(self._send(self._shelly(ota_events="success"), Level.quiet, logfile=logfile))
        logfile.close()
        text = path.read_text(encoding="utf-8")
        self.assertEqual(len(self.lines), 1)                      # the console stayed quiet
        for expected in ("tool| Device 127.0.0.1", "tool| ZIP: t.zip", "tool| Download URL", f"tool| {DONE_CONFIRMED}",
                         "dev | fakeshelly-aabbccddeeff 101 10.100 2 2|y_notifications.cpp:213 Event from sys:"):
            self.assertIn(expected, text)
        self.assertEqual(len(re.findall(r" dev \| ", text)), 6)       # one line for each entry, not for each datagram

    # --- the python API keeps working

    @needs_fw
    def test_the_default_level_is_verbose_so_existing_callers_see_what_they_saw(self):
        lines = []
        s = self._shelly()
        sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, timeout=10, log_port=free_udp_port(),
                    sleep=lambda t: None, out=lines.append)
        self.assertTrue(any(l.startswith("ZIP:") for l in lines))
        self.assertTrue(any(l.startswith("Download URL") for l in lines))


class CliTests(unittest.TestCase):
    """The options of ota.py: levels, --log-file, and replaying a saved log."""

    FIXTURE = Path(__file__).parent / "fixtures" / "rgbcct_update.devlog.txt"

    def setUp(self):
        ui._progress_step.clear()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _parse(self, *argv):
        """The arguments the real parser gives to cmd_send."""
        import ota
        seen = []
        with mock.patch.object(sys, "argv", ["ota.py", "send", "DuoBulbG3", "x.zip", *argv]), \
                mock.patch.object(ota, "cmd_send", side_effect=seen.append), \
                contextlib.redirect_stdout(io.StringIO()):
            ota.main()
        return seen[0]

    def _run(self, *argv):
        import ota
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["ota.py", "--color", "never", *argv]), contextlib.redirect_stdout(out):
            ota.main()
        return out.getvalue()

    def test_levels_from_the_options(self):
        import ota
        for argv, expected in (([], Level.normal), (["-q"], Level.quiet), (["-v"], Level.verbose), (["-vv"], Level.debug),
                               (["--log-level", "raw"], Level.raw), (["-q", "-vv"], Level.quiet),
                               (["--log-level", "debug", "-q"], Level.debug)):
            self.assertEqual(ota._level(self._parse(*argv), Level.normal), expected, argv)

    def test_log_file_without_a_path_or_with_one(self):
        import ota
        self.assertIsNone(self._parse().log_file)
        self.assertEqual(self._parse("--log-file").log_file, ota.LOG_FILE_AUTO)
        self.assertEqual(self._parse("--log-file=out/mine.log").log_file, "out/mine.log")
        self.assertEqual(self._parse("-v", "--log-file", "out/mine.log").log_file, "out/mine.log")

    def test_the_default_log_file_is_below_logs_and_named_after_the_zip(self):
        import ota
        with mock.patch.object(ota, "MODULE_DIR", self.tmp), contextlib.redirect_stdout(io.StringIO()):
            args = self._parse("--log-file")
            logfile = ota._open_logfile(args, Level.normal, "RGBCCTBulbG3-firmware.ota-20261015.send.log")
            logfile.close()
        self.assertEqual(logfile.path, self.tmp / "logs" / "RGBCCTBulbG3-firmware.ota-20261015.send.log")
        self.assertIn("free-shelly-ota", logfile.path.read_text(encoding="utf-8"))

    def test_an_explicit_path_is_used_as_it_is(self):
        import ota
        target = self.tmp / "somewhere" / "mine.log"
        args = self._parse(f"--log-file={target}")
        with contextlib.redirect_stdout(io.StringIO()):
            logfile = ota._open_logfile(args, Level.quiet, "ignored.log")
        logfile.close()
        self.assertEqual(logfile.path, target)
        self.assertTrue(target.exists())

    def test_no_log_file_unless_asked(self):
        import ota
        self.assertIsNone(ota._open_logfile(self._parse(), Level.normal, "x.log"))

    def test_replay_shows_a_saved_log_at_the_chosen_level(self):
        normal = self._run("log", "--replay", str(self.FIXTURE), "--log-level", "normal")
        self.assertIn("Device: The installer writes to slot 0", normal)
        self.assertIn("Update: 100 %", normal)
        self.assertNotIn("  log|", normal)
        debug = self._run("log", "--replay", str(self.FIXTURE), "-vv")
        self.assertIn("RPC Shelly.GetStatus <- 192.0.2.30:47470", debug)

    def test_quiet_also_drops_the_version_line(self):
        self.assertEqual(self._run("log", "--replay", str(self.FIXTURE), "-q"), "")

    def test_replay_of_a_missing_file_is_a_message(self):
        import ota
        with mock.patch.object(sys, "argv", ["ota.py", "log", "--replay", str(self.tmp / "nope.log")]), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as cm:
            ota.main()
        self.assertTrue(str(cm.exception.code).startswith("Error:"), cm.exception.code)


if __name__ == "__main__":
    unittest.main()
