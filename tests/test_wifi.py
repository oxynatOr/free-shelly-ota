"""The Wi-Fi signal check of send(): a weak signal is said and offered a longer wait; the questions are 'seconds / s / c'.

Run from ShellyOTA/: python -m unittest discover tests
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from needs_fw import needs_fw  # noqa: E402
from shelly_ota import builder, firmware, profile, sender  # noqa: E402
from test_errors import FLASH, Script, never_ask  # noqa: E402
from test_extras import FakeRpcShelly  # noqa: E402


class WifiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile = profile.load_profile("DuoBulbG3")
        self.zip = self.tmp / "t.zip"
        shutil.copy(firmware.cached_zip("DuoBulbG3"), self.zip)

    def _shelly(self, **kw):
        s = FakeRpcShelly(**kw)
        self.addCleanup(s.close)
        return s

    def _send(self, s, ask, **kw):
        lines = []
        kw.setdefault("sleep", lambda seconds: None)
        try:
            ok = sender.send(self.profile, self.zip, s.addr, port=0, out=lines.append, ask=ask, probe_wait=0.3, **kw)
        except builder.OtaError as e:
            return e, lines
        return ok, lines

    @needs_fw
    def test_rssi_is_read_and_a_missing_answer_is_none(self):
        self.assertEqual(sender.device_wifi_rssi(self._shelly(rssi=-55).addr), -55)
        self.assertIsNone(sender.device_wifi_rssi(self._shelly().addr))           # the device does not answer Wifi.GetStatus

    @needs_fw
    def test_a_good_signal_asks_nothing_and_is_only_shown_when_verbose(self):
        s = self._shelly(rssi=-55)
        ok, lines = self._send(s, Script(), dry_run=True)
        self.assertIs(ok, True)
        self.assertTrue(any("-55 dBm" in l for l in lines), lines)
        self.assertFalse(any("weak" in l.lower() for l in lines), lines)

    @needs_fw
    def test_a_weak_signal_is_said_and_asked_about(self):
        for answer, wait in (("", 1200), ("s", 300), ("skip", 300), ("600", 600)):
            with self.subTest(answer=answer):
                s = self._shelly(rssi=-72)
                script = Script(answer, "yes")
                ok, lines = self._send(s, lambda q, script=script: "yes" if q == FLASH else script(q), timeout=300)
                self.assertIs(ok, True, lines)
                self.assertTrue(any("weak Wi-Fi signal" in l and "-72 dBm" in l for l in lines), lines)
                self.assertTrue(any(f"Waiting up to {wait} s" in l for l in lines), lines)
                self.assertTrue(any("seconds, s = skip, c = cancel" in p for p in script.prompts), script.prompts)

    @needs_fw
    def test_cancel_ends_before_anything_is_sent(self):
        s = self._shelly(rssi=-80)
        ok, lines = self._send(s, Script("c"))
        self.assertIsInstance(ok, builder.OtaError)
        self.assertIn("Cancelled", str(ok))
        self.assertEqual(s.updates, [])

    @needs_fw
    def test_cancel_can_be_spelled_out(self):
        ok, lines = self._send(self._shelly(rssi=-80), Script("Cancel"))
        self.assertIn("Cancelled", str(ok))

    @needs_fw
    def test_an_answer_that_is_not_understood_is_asked_again(self):
        s = self._shelly(rssi=-80)
        script = Script("what", "-5", "0", "c")
        ok, lines = self._send(s, script)
        self.assertIn("Cancelled", str(ok))
        self.assertEqual(len(script.prompts), 4)

    @needs_fw
    def test_dry_run_and_yes_say_it_but_never_ask(self):
        for kw in ({"dry_run": True}, {"assume_yes": True}):
            with self.subTest(kw=kw):
                s = self._shelly(rssi=-72)
                ok, lines = self._send(s, never_ask, timeout=300, **kw)
                self.assertIs(ok, True, lines)
                self.assertTrue(any("weak Wi-Fi signal" in l and "--timeout" in l for l in lines), lines)
                if "assume_yes" in kw:
                    self.assertTrue(any("Waiting up to 300 s" in l for l in lines), lines)


class SlowDownloadTests(unittest.TestCase):
    """A device that takes the ZIP in small bites: the wait is not given up behind the user's back."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile = profile.load_profile("DuoBulbG3")
        self.zip = self.tmp / "t.zip"
        shutil.copy(firmware.cached_zip("DuoBulbG3"), self.zip)

    def _run(self, ask, **kw):
        s = FakeRpcShelly(slow=(256 * 1024, 0.4))
        self.addCleanup(s.close)
        lines = []
        try:
            ok = sender.send(self.profile, self.zip, s.addr, port=0, out=lines.append, ask=ask, probe_wait=0.3,
                             sleep=lambda seconds: None, timeout=1.5, **kw)
        except builder.OtaError as e:
            return e, lines
        return ok, lines

    @needs_fw
    def test_the_user_can_wait_on_while_the_device_is_still_downloading(self):
        script = Script("", "", "", "", "", "", "", "", "")      # Enter = wait as long again
        ask = lambda q: "yes" if q == FLASH else script(q)
        ok, lines = self._run(ask)
        self.assertIs(ok, True, lines)
        self.assertTrue(any("still downloading" in l for l in lines), lines)
        self.assertTrue(script.prompts and "Wait longer for" in script.prompts[0], script.prompts)

    @needs_fw
    def test_cancel_at_the_question_ends_the_wait(self):
        script = Script("c")
        ok, lines = self._run(lambda q: "yes" if q == FLASH else script(q))
        self.assertIsInstance(ok, builder.OtaError)
        self.assertIn("Cancelled", str(ok))

    @needs_fw
    def test_with_yes_it_never_waits_on_its_own(self):
        ok, lines = self._run(never_ask, assume_yes=True)
        self.assertIsInstance(ok, builder.OtaError)
        self.assertIn("did not finish the download", str(ok))
        self.assertIn("--timeout", str(ok))


if __name__ == "__main__":
    unittest.main()
