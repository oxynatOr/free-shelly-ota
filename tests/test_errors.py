"""Error handling of the OTA sender: what the device refuses, what the user is told, and when the tool waits.

Run from ShellyOTA/: python -m unittest discover tests
"""

import contextlib
import io
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ota  # noqa: E402
from needs_fw import needs_fw  # noqa: E402
from shelly_ota import builder, firmware, logwatch, profile, rpc, sender  # noqa: E402
from test_extras import FakeRpcShelly, free_udp_port  # noqa: E402

NOT_COMMITTED = {"code": -109, "message": "Not committed"}
BATTERY = {"code": -109, "message": "OTA not allowed (Battery below 30 percent. )"}
FLASH = "Type 'yes' to flash this device: "
FLASH_AGAIN = "Type 'yes' to flash this device again: "


class Script:
    """Answers the questions of send() in order and remembers them. A question that was not expected fails the test."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if not self.answers:
            raise AssertionError(f"unexpected question: {prompt!r}")
        return self.answers.pop(0)


def never_ask(prompt):
    raise AssertionError(f"unexpected question: {prompt!r}")


class RpcErrorTests(unittest.TestCase):
    def _shelly(self, **kw):
        s = FakeRpcShelly(**kw)
        self.addCleanup(s.close)
        return s

    def test_refusal_body_is_parsed_and_the_url_is_not_repeated(self):
        s = self._shelly(update_refusals=[NOT_COMMITTED])
        with self.assertRaises(rpc.RpcError) as cm:
            rpc.request(f"http://{s.addr}/rpc/Shelly.Update?url=http%3A%2F%2F10.1.2.3%3A8000%2Fx.zip")
        e = cm.exception
        self.assertEqual((e.status, e.code, e.device_message, e.method), (500, -109, "Not committed", "Shelly.Update"))
        self.assertIn("Not committed", str(e))
        self.assertNotIn("10.1.2.3", str(e))
        self.assertNotIn("url=", str(e))

    def test_a_body_that_is_not_json_is_shown_as_text(self):
        s = self._shelly(update_refusals=["something broke"])
        with self.assertRaises(rpc.RpcError) as cm:
            rpc.request(f"http://{s.addr}/rpc/Shelly.Update?url=x")
        self.assertIsNone(cm.exception.code)
        self.assertEqual(cm.exception.device_message, "something broke")
        self.assertIn("something broke", str(cm.exception))

    def test_an_rpc_error_object_becomes_an_rpc_error(self):
        s = self._shelly()
        with self.assertRaises(rpc.RpcError) as cm:
            rpc.call(s.addr, "No.Such.Method")
        self.assertEqual((cm.exception.code, cm.exception.device_message), (-105, "unknown"))

    def test_no_answer_is_device_unreachable(self):
        with self.assertRaises(rpc.DeviceUnreachable):
            rpc.request("http://127.0.0.1:1/rpc/Shelly.GetDeviceInfo", timeout=2)
        with self.assertRaises(rpc.DeviceUnreachable):
            sender.device_info("127.0.0.1:1", timeout=2)

    def test_garbage_from_the_device_is_an_ota_error_not_a_traceback(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        self.addCleanup(srv.close)

        def answer_with_garbage():
            conn, _ = srv.accept()
            conn.recv(4096)
            conn.sendall(b"this is not http\r\n\r\n")
            conn.close()

        threading.Thread(target=answer_with_garbage, daemon=True).start()
        with self.assertRaises(builder.OtaError) as cm:
            rpc.request(f"http://127.0.0.1:{srv.getsockname()[1]}/rpc/Shelly.GetDeviceInfo", timeout=3)
        self.assertNotIsInstance(cm.exception, rpc.DeviceUnreachable)
        self.assertIn("Unexpected answer", str(cm.exception))


class ExplainTests(unittest.TestCase):
    @staticmethod
    def _error(refusal):
        return rpc.RpcError("x", status=500, code=refusal["code"], device_message=refusal["message"], method="Shelly.Update")

    def test_not_committed_can_be_retried(self):
        r = sender.explain_update_refusal(self._error(NOT_COMMITTED))
        self.assertTrue(r.retryable)
        self.assertIn("Not committed", r.text)
        self.assertIn("send again", r.text)

    def test_battery_is_not_retried(self):
        r = sender.explain_update_refusal(self._error(BATTERY))
        self.assertFalse(r.retryable)
        self.assertIn("Charge the battery", r.text)

    def test_other_refusals_show_the_device_message_and_code(self):
        r = sender.explain_update_refusal(self._error({"code": -114, "message": "No space left"}))
        self.assertFalse(r.retryable)
        self.assertIn("No space left", r.text)
        self.assertIn("-114", r.text)


class SendFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile = profile.load_profile("DuoBulbG3")
        self.zip = self.tmp / "t.zip"
        shutil.copy(firmware.cached_zip("DuoBulbG3"), self.zip)
        self.sleeps = []
        self.lines = []

    def _shelly(self, **kw):
        s = FakeRpcShelly(**kw)
        self.addCleanup(s.close)
        return s

    def _send(self, shelly, ask=never_ask, **kw):
        kw.setdefault("sleep", self.sleeps.append)
        return sender.send(self.profile, self.zip, shelly.addr, port=0, timeout=10, ask=ask, out=self.lines.append, **kw)

    # --- uptime check before sending

    @needs_fw
    def test_device_uptime_is_read_and_a_missing_answer_is_not_an_error(self):
        self.assertEqual(sender.device_uptime(self._shelly(uptime=42).addr), 42)
        self.assertIsNone(sender.device_uptime(self._shelly().addr))          # Sys.GetStatus answers with an error
        self.assertIsNone(sender.device_uptime("127.0.0.1:1"))

    @needs_fw
    def test_a_device_that_just_started_gets_a_note_and_an_offer_to_wait(self):
        s = self._shelly(uptime=30)
        ask = Script("yes", "yes")
        self.assertTrue(self._send(s, ask))
        self.assertEqual(ask.prompts, ["Wait about 95 s before sending? Type 'yes' to wait: ", FLASH])
        self.assertTrue(any("running for only 30 s" in l for l in self.lines), self.lines)
        self.assertEqual(self.sleeps.count(0.5), 190)                         # 95 s in half-second steps
        self.assertEqual(len(s.updates), 1)

    @needs_fw
    def test_the_offer_can_be_declined_and_sending_goes_on(self):
        s = self._shelly(uptime=30)
        ask = Script("no", "yes")
        self.assertTrue(self._send(s, ask))
        self.assertEqual(self.sleeps.count(0.5), 0)
        self.assertTrue(any("Not waiting" in l for l in self.lines), self.lines)

    @needs_fw
    def test_a_settled_device_gets_no_question_about_waiting(self):
        ask = Script("yes")
        self.assertTrue(self._send(self._shelly(uptime=500), ask))
        self.assertEqual(ask.prompts, [FLASH])
        self.assertFalse(any("running for only" in l for l in self.lines), self.lines)

    @needs_fw
    def test_an_unknown_uptime_stays_quiet(self):
        ask = Script("yes")
        self.assertTrue(self._send(self._shelly(), ask))
        self.assertEqual(ask.prompts, [FLASH])

    @needs_fw
    def test_dry_run_and_yes_only_say_so_and_never_wait(self):
        s = self._shelly(uptime=30)
        self._send(s, dry_run=True)
        self._send(s, assume_yes=True)
        self.assertEqual(sum("running for only 30 s" in l for l in self.lines), 2)
        self.assertEqual(self.sleeps.count(0.5), 0)

    @needs_fw
    def test_ctrl_c_while_waiting_stops_cleanly(self):
        def interrupt(seconds):
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            self._send(self._shelly(uptime=30), Script("yes"), sleep=interrupt)

    # --- the device refuses anyway

    @needs_fw
    def test_not_committed_waits_and_asks_again_before_the_next_pass(self):
        s = self._shelly(uptime=500, update_refusals=[NOT_COMMITTED])
        ask = Script("yes", "yes", "yes")
        self.assertTrue(self._send(s, ask))
        self.assertEqual(ask.prompts, [FLASH, "Wait about 120 s and try again? Type 'yes' to wait: ", FLASH_AGAIN])
        self.assertEqual(self.sleeps.count(0.5), 240)
        self.assertEqual(len(s.updates), 1)
        self.assertTrue(any("Not committed" in l and l.startswith("WARNING") for l in self.lines), self.lines)

    @needs_fw
    def test_wait_option_sets_the_pause(self):
        s = self._shelly(uptime=500, update_refusals=[NOT_COMMITTED])
        self.assertTrue(self._send(s, Script("yes", "yes", "yes"), wait=30))
        self.assertEqual(self.sleeps.count(0.5), 60)

    @needs_fw
    def test_declining_to_wait_ends_with_the_explanation(self):
        s = self._shelly(uptime=500, update_refusals=[NOT_COMMITTED])
        with self.assertRaises(builder.OtaError) as cm:
            self._send(s, Script("yes", "no"))
        self.assertIn("Not committed", str(cm.exception))
        self.assertIn("send again", str(cm.exception))
        self.assertNotIn("url=", str(cm.exception))
        self.assertEqual(s.updates, [])

    @needs_fw
    def test_the_next_pass_needs_its_own_confirmation(self):
        s = self._shelly(uptime=500, update_refusals=[NOT_COMMITTED])
        with self.assertRaises(builder.OtaError) as cm:
            self._send(s, Script("yes", "yes", "no"))
        self.assertEqual(str(cm.exception), "Cancelled.")
        self.assertEqual(s.updates, [])

    @needs_fw
    def test_yes_never_retries_by_itself(self):
        s = self._shelly(uptime=500, update_refusals=[NOT_COMMITTED])
        with self.assertRaises(builder.OtaError) as cm:
            self._send(s, assume_yes=True)
        self.assertIn("Not committed", str(cm.exception))
        self.assertEqual(self.sleeps.count(0.5), 0)

    @needs_fw
    def test_it_gives_up_after_three_passes(self):
        s = self._shelly(uptime=500, update_refusals=[NOT_COMMITTED] * 3)
        ask = Script(*["yes"] * 5)
        with self.assertRaises(builder.OtaError) as cm:
            self._send(s, ask)
        self.assertIn("Stopped after 3 attempts", str(cm.exception))
        self.assertEqual(len(ask.prompts), 5)           # flash, then twice: wait? + flash again
        self.assertEqual(s.updates, [])

    @needs_fw
    def test_a_battery_refusal_is_not_retried(self):
        s = self._shelly(uptime=500, update_refusals=[BATTERY])
        with self.assertRaises(builder.OtaError) as cm:
            self._send(s, Script("yes"))
        self.assertIn("Charge the battery", str(cm.exception))

    @needs_fw
    def test_ctrl_c_in_the_wait_after_a_refusal_leaves_no_server_behind(self):
        s = self._shelly(uptime=500, update_refusals=[NOT_COMMITTED])

        def interrupt(seconds):
            raise KeyboardInterrupt

        with mock.patch.object(sender.FileServer, "stop", autospec=True, side_effect=sender.FileServer.stop) as stop:
            with self.assertRaises(KeyboardInterrupt):
                self._send(s, Script("yes", "yes"), sleep=interrupt)
        self.assertEqual(stop.call_count, 1)             # the web server of the refused pass was closed before waiting


class LogSettingTests(unittest.TestCase):
    def _shelly(self, **kw):
        s = FakeRpcShelly(**kw)
        self.addCleanup(s.close)
        return s

    def test_a_setting_that_could_not_be_read_is_not_overwritten(self):
        s = self._shelly(getconfig_fails=True)
        with self.assertRaises(rpc.RpcError):
            with logwatch.udp_log(s.addr, "127.0.0.1", free_udp_port(), lambda m: None):
                pass
        self.assertEqual(s.setconfig_calls, [])

    def test_failing_to_put_the_setting_back_is_reported(self):
        s = self._shelly(restore_fails=True)
        lines = []
        with logwatch.udp_log(s.addr, "127.0.0.1", free_udp_port(), lines.append):
            pass
        self.assertTrue(any("could not put the device's log setting back" in l for l in lines), lines)

    def test_a_device_that_is_gone_after_the_update_is_not_reported(self):
        s = self._shelly()
        lines = []
        with logwatch.udp_log(s.addr, "127.0.0.1", free_udp_port(), lines.append):
            s.close()                                    # the device reboots into the new firmware
        self.assertFalse(any("could not put" in l for l in lines), lines)


class MainErrorTests(unittest.TestCase):
    def _run(self, *argv, func=None):
        out, err = io.StringIO(), io.StringIO()
        patches = [mock.patch.object(sys, "argv", ["ota.py", *argv])]
        if func is not None:
            patches.append(mock.patch.object(ota, "cmd_inspect", side_effect=func))
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            with self.assertRaises(SystemExit) as cm:
                ota.main()
        return cm.exception.code, err.getvalue()

    def test_ctrl_c_exits_quietly_with_130(self):
        code, err = self._run("inspect", "x.zip", func=KeyboardInterrupt)
        self.assertEqual(code, 130)
        self.assertIn("Interrupted", err)

    def test_closed_input_is_a_message_not_a_traceback(self):
        code, _ = self._run("inspect", "x.zip", func=EOFError)
        self.assertIn("input was closed", code)

    def test_a_file_that_is_not_a_zip_is_a_message_not_a_traceback(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        bad = tmp / "bad.zip"
        bad.write_text("this is not a zip file")
        code, _ = self._run("inspect", str(bad))
        self.assertTrue(str(code).startswith("Error:"), code)


if __name__ == "__main__":
    unittest.main()
