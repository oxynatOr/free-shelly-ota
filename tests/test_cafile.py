"""fetch / build --download with --cafile (#110). Run from ShellyOTA/: python -m unittest discover tests

The certificates in tests/fixtures are made for these tests only (openssl, valid until 2126):
- tls-ca.pem: a self-signed X.509 v1 CA, like Shelly's root. It has no extensions, so no CA:TRUE, and
  VERIFY_X509_STRICT (on by default from Python 3.13) refuses it as an "invalid CA certificate".
- tls-server.pem: certificate and key for 127.0.0.1, signed by tls-ca.pem. Its authority key identifier carries a key
  id, so the strict check has nothing else to refuse.
- tls-other-ca.pem: an ordinary CA that signed nothing here.
"""

import contextlib
import hashlib
import http.server
import io
import json
import shutil
import socket
import ssl
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ota  # noqa: E402
from shelly_ota import builder, firmware, profile  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CA = FIXTURES / "tls-ca.pem"
OTHER_CA = FIXTURES / "tls-other-ca.pem"
SERVER = FIXTURES / "tls-server.pem"


def fake_package(name: str = "Fake", version: str = "1.0.0") -> bytes:
    """The smallest ZIP that store_zip takes as an official package."""
    app = b"\xe9" + bytes(255)
    manifest = {"name": name, "version": version,
                "parts": {"app": {"src": "app.bin", "size": len(app), "cs_sha256": hashlib.sha256(app).hexdigest()}}}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("app.bin", app)
    return buf.getvalue()


class FakeUpdateServer:
    """HTTPS on 127.0.0.1 with the test certificate: /update/<id> answers like the update API, /fw/<sha256> the ZIP."""

    def __init__(self):
        self.package = fake_package()
        sha = hashlib.sha256(self.package).hexdigest()
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith("/update/"):
                    body = json.dumps({"stable": {"version": "1.0.0", "url": f"{outer.base}/fw/{sha}"}}).encode()
                elif self.path == f"/fw/{sha}":
                    body = outer.package
                else:
                    return self.send_error(404)
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(str(SERVER))
        self.httpd.socket = ctx.wrap_socket(self.httpd.socket, server_side=True)  # a refused handshake is dropped
        self.port = self.httpd.server_address[1]
        self.base = f"https://127.0.0.1:{self.port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class CafileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = FakeUpdateServer()
        cls.addClassCleanup(cls.server.close)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        patcher = mock.patch.object(firmware, "UPDATE_API", self.server.base + "/update/{update_id}")
        patcher.start()
        self.addCleanup(patcher.stop)

    def fetch(self, **kw) -> Path:
        with contextlib.redirect_stdout(io.StringIO()):
            return firmware.fetch("Fake", "Fake", fw_dir=self.tmp, **kw)

    def handshake(self, ctx: ssl.SSLContext, hostname: str = "127.0.0.1") -> None:
        with socket.create_connection(("127.0.0.1", self.server.port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname):
                pass

    def test_the_right_ca_is_accepted(self):
        path = self.fetch(cafile=CA)
        self.assertEqual(path.read_bytes(), self.server.package)
        self.assertEqual(firmware.list_versions("Fake", self.tmp), ["1.0.0"])

    def test_another_ca_is_refused(self):
        with self.assertRaises(builder.OtaError) as cm:
            self.fetch(cafile=OTHER_CA)
        self.assertIn("CERTIFICATE_VERIFY_FAILED", str(cm.exception))
        self.assertIn(f"--cafile {OTHER_CA}", str(cm.exception))
        self.assertEqual(firmware.list_versions("Fake", self.tmp), [])

    def test_without_cafile_nothing_changes(self):
        with self.assertRaises(builder.OtaError) as cm:     # the test CA is in no system store
            self.fetch()
        self.assertIn("--cafile PEM or --insecure", str(cm.exception))
        self.assertEqual(self.fetch(insecure=True).read_bytes(), self.server.package)

    def test_the_strict_check_refuses_this_ca_and_cafile_clears_it(self):
        real = ssl.create_default_context

        def strict_default(*args, **kw):    # what Python 3.13 and newer do, on every version
            ctx = real(*args, **kw)
            ctx.verify_flags |= ssl.VERIFY_X509_STRICT
            return ctx

        with mock.patch.object(ssl, "create_default_context", strict_default):
            with self.assertRaisesRegex(ssl.SSLCertVerificationError, "invalid CA certificate"):
                self.handshake(ssl.create_default_context(cafile=str(CA)))
            self.handshake(firmware._ssl_context(cafile=CA))
            self.assertTrue(firmware._ssl_context().verify_flags & ssl.VERIFY_X509_STRICT)   # only that context

    def test_strict_is_cleared_for_this_context_only(self):
        default = ssl.create_default_context().verify_flags
        if sys.version_info >= (3, 13):
            self.assertTrue(default & ssl.VERIFY_X509_STRICT)
        ctx = firmware._ssl_context(cafile=CA)
        self.assertEqual(ctx.verify_flags, default & ~ssl.VERIFY_X509_STRICT)   # that flag, nothing else
        self.assertEqual(ssl.create_default_context().verify_flags, default)   # no global change
        self.assertEqual(firmware._ssl_context().verify_flags, default)        # a fetch without --cafile keeps it

    def test_host_name_and_chain_are_still_checked(self):
        ctx = firmware._ssl_context(cafile=CA)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)
        with self.assertRaisesRegex(ssl.SSLCertVerificationError, "(?i)hostname mismatch"):
            self.handshake(ctx, hostname="updates.shelly.invalid")

    def test_only_the_given_file_is_trusted(self):
        subjects = [dict(rdn[0] for rdn in c["subject"]) for c in firmware._ssl_context(cafile=CA).get_ca_certs()]
        self.assertEqual(subjects, [{"organizationName": "free-shelly-ota test CA"}])

    def test_a_missing_or_wrong_ca_file_is_an_error(self):
        not_pem = self.tmp / "not.pem"
        not_pem.write_text("no certificate here", encoding="utf-8")
        for path in (self.tmp / "missing.pem", not_pem):
            with self.assertRaisesRegex(builder.OtaError, "Cannot use --cafile"):
                firmware._ssl_context(cafile=path)


class CafileOptionTests(unittest.TestCase):
    def parse(self, *argv):
        return ota.build_parser().parse_args(list(argv))

    def test_fetch_and_build_take_it(self):
        self.assertEqual(self.parse("fetch", "PlugMG3", "--cafile", "ca.pem").cafile, Path("ca.pem"))
        self.assertIsNone(self.parse("fetch", "PlugMG3").cafile)
        args = self.parse("build", "PlugMG3", "app.bin", "--download", "--cafile", "ca.pem")
        self.assertEqual(args.cafile, Path("ca.pem"))
        self.assertFalse(args.insecure)

    def test_cafile_and_insecure_exclude_each_other(self):
        for argv in (["fetch", "PlugMG3"], ["build", "PlugMG3", "app.bin", "--download"]):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
                self.parse(*argv, "--insecure", "--cafile", "ca.pem")
            self.assertIn("not allowed with argument", err.getvalue())

    def test_fetch_and_build_download_pass_it_on(self):
        for argv in (["fetch", "PlugMG3"], ["build", "PlugMG3", "app.bin", "--download"]):
            args = self.parse(*argv, "--cafile", str(CA))
            with mock.patch.object(firmware, "cached_zip", return_value=None), \
                    mock.patch.object(ota, "_fetch_official", side_effect=builder.OtaError("stop")) as fetch, \
                    self.assertRaises(builder.OtaError):
                args.func(args)
            self.assertEqual(fetch.call_args.kwargs["cafile"], CA, argv[0])

    def test_a_variant_passes_it_on_too(self):
        for name in ("PlugMG3", "PowerStripZB"):    # PowerStripZB is looked up in the reply of PowerStrip
            with mock.patch.object(firmware, "fetch", return_value=Path("x.zip")) as fetch:
                ota._fetch_official(profile.load_profile(name), cafile=CA)
            self.assertEqual(fetch.call_args.kwargs["cafile"], CA, name)


if __name__ == "__main__":
    unittest.main()
