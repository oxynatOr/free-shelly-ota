"""Run from ShellyOTA/: python -m unittest discover tests"""

import http.server
import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelly_ota import builder, firmware, profile, sender  # noqa: E402


class FakeShelly:
    """Minimal Shelly: answers GetDeviceInfo and downloads the url given to Shelly.Update."""

    def __init__(self, app="DuoBulbG3", auth_en=False):
        self.app, self.auth_en = app, auth_en
        self.updates = []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                u = urllib.parse.urlparse(self.path)
                if u.path == "/rpc/Shelly.GetDeviceInfo":
                    body = json.dumps({"app": outer.app, "model": "X", "ver": "2.0.1", "id": "fake",
                                       "auth_en": outer.auth_en}).encode()
                elif u.path == "/rpc/Shelly.Update":
                    url = urllib.parse.parse_qs(u.query)["url"][0]
                    outer.updates.append(url)
                    threading.Thread(target=lambda: urllib.request.urlopen(url).read()).start()
                    body = b"{}"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.addr = f"127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup = lambda: (self.httpd.shutdown(), self.httpd.server_close())


class SenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile = profile.load_profile("DuoBulbG3")
        self.zip = self.tmp / "t.zip"
        shutil.copy(firmware.cached_zip("DuoBulbG3"), self.zip)

    def _shelly(self, **kw):
        s = FakeShelly(**kw)
        self.addCleanup(s.addCleanup)
        return s

    def test_send_delivers_zip(self):
        s = self._shelly()
        log = []
        ok = sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, timeout=10, out=log.append)
        self.assertTrue(ok)
        self.assertEqual(len(s.updates), 1)

    def test_dry_run_sends_nothing(self):
        s = self._shelly()
        sender.send(self.profile, self.zip, s.addr, port=0, dry_run=True, out=lambda m: None)
        self.assertEqual(s.updates, [])

    def test_wrong_model_is_refused(self):
        s = self._shelly(app="PlugMG3")
        with self.assertRaises(builder.OtaError):
            sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, out=lambda m: None)
        self.assertEqual(s.updates, [])

    def test_password_protected_is_refused(self):
        s = self._shelly(auth_en=True)
        with self.assertRaises(builder.OtaError):
            sender.send(self.profile, self.zip, s.addr, port=0, assume_yes=True, out=lambda m: None)

    def test_declined_confirmation_sends_nothing(self):
        s = self._shelly()
        with self.assertRaises(builder.OtaError):
            sender.send(self.profile, self.zip, s.addr, port=0, ask=lambda p: "no", out=lambda m: None)
        self.assertEqual(s.updates, [])

    def test_unreachable_device(self):
        with self.assertRaises(builder.OtaError):
            sender.device_info("127.0.0.1:1", timeout=2)


if __name__ == "__main__":
    unittest.main()
