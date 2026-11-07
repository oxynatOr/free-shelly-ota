"""ota.py ca: Shelly's root CA out of a package, checked against a fingerprint. Run from ShellyOTA/: python -m unittest discover tests

The tests use a made-up "certificate" (a DER-shaped blob) and its own fingerprint, so they need neither fw/ nor Shelly's file.
One test at the end takes the real root out of the real packages, if there are any.
"""

import hashlib
import io
import ssl
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ota  # noqa: E402
from needs_fw import needs_fw  # noqa: E402
from shelly_ota import builder, cacert, firmware  # noqa: E402

# 30 82 <length> <body>: shaped like a DER certificate, 304 bytes long (the check is the hash, not the content)
BODY = bytes(range(256)) + bytes(44)
DER = b"\x30\x82" + len(BODY).to_bytes(2, "big") + BODY
SHA = hashlib.sha256(DER).hexdigest()
NOISE = b"\xff" * 300 + b"\x30\x82\x00\x10short" + b"\x00" * 50    # a 30 82 header whose length is too small to count


def pem_of(der: bytes) -> bytes:
    return ssl.DER_cert_to_PEM_cert(der).encode("ascii")


def package(directory: Path, fs: bytes | None, name: str = "Fake.zip") -> Path:
    path = directory / name
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", "{}")
        if fs is not None:
            zf.writestr("fs.img", fs)
    return path


class FindRootTests(unittest.TestCase):
    def test_der_between_other_bytes(self):
        self.assertEqual(cacert.find_root(NOISE + DER + NOISE, SHA), DER)

    def test_pem_between_text_that_is_not_utf8(self):
        fs = b"\xd4\xff Subject: O = Allterco\n" + pem_of(DER) + b"\x00\xfe more\n"
        self.assertEqual(cacert.find_root(fs, SHA), DER)

    def test_pem_with_windows_line_ends(self):
        self.assertEqual(cacert.find_root(pem_of(DER).replace(b"\n", b"\r\n"), SHA), DER)

    def test_another_certificate_is_not_taken(self):
        other = b"\x30\x82" + len(BODY).to_bytes(2, "big") + bytes(reversed(BODY))
        self.assertIsNone(cacert.find_root(NOISE + other + pem_of(other), SHA))

    def test_a_cut_off_certificate_is_not_taken(self):
        self.assertIsNone(cacert.find_root(DER[:-1], SHA))

    def test_a_block_that_is_not_base64_is_skipped(self):
        fs = b"-----BEGIN CERTIFICATE-----\n!!not base64!!\n-----END CERTIFICATE-----\n" + pem_of(DER)
        self.assertEqual(cacert.find_root(fs, SHA), DER)

    def test_nothing_in_empty_or_blank_data(self):
        self.assertIsNone(cacert.find_root(b"", SHA))
        self.assertIsNone(cacert.find_root(b"\xff" * 4096, SHA))

    def test_the_default_is_the_pinned_fingerprint(self):
        self.assertEqual(len(cacert.SHELLY_ROOT_SHA256), 64)
        self.assertEqual(cacert.SHELLY_ROOT_SHA256, cacert.SHELLY_ROOT_SHA256.lower())
        self.assertIsNone(cacert.find_root(DER))    # the made-up certificate is not Shelly's

    def test_colon_hex_is_what_openssl_prints(self):
        self.assertEqual(cacert.colon_hex("5a7ee2fa"), "5A:7E:E2:FA")

    def test_expiry(self):
        self.assertFalse(cacert.expired(date(2030, 8, 2)))
        self.assertTrue(cacert.expired(date(2030, 8, 3)))


class ExtractFromZipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_der_package(self):
        self.assertEqual(cacert.extract_from_zip(package(self.dir, NOISE + DER), SHA), DER)

    def test_pem_package(self):
        self.assertEqual(cacert.extract_from_zip(package(self.dir, b"\x00" * 64 + pem_of(DER)), SHA), DER)

    def test_other_certificate_is_refused_and_the_message_names_the_fingerprint(self):
        with self.assertRaises(builder.OtaError) as cm:
            cacert.extract_from_zip(package(self.dir, NOISE), SHA)
        self.assertIn(cacert.colon_hex(SHA), str(cm.exception))

    def test_package_without_fs_img(self):
        with self.assertRaisesRegex(builder.OtaError, "no fs.img"):
            cacert.extract_from_zip(package(self.dir, None), SHA)

    def test_a_file_that_is_not_a_zip(self):
        bad = self.dir / "image.bin"
        bad.write_bytes(b"\x00" * 16)
        with self.assertRaises(builder.OtaError):
            cacert.extract_from_zip(bad, SHA)


class CaCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.zip = package(self.dir, NOISE + DER)
        patcher = mock.patch.object(cacert, "SHELLY_ROOT_SHA256", SHA)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_ca(self, *argv) -> str:
        args = ota.build_parser().parse_args(["ca", *map(str, argv)])
        out = io.StringIO()
        with redirect_stdout(out):
            args.func(args)
        return out.getvalue()

    def test_writes_a_pem_that_is_the_certificate(self):
        out = self.dir / "ca.pem"
        text = self.run_ca("--zip", self.zip, "-o", out)
        self.assertEqual(ssl.PEM_cert_to_DER_cert(out.read_text(encoding="ascii")), DER)
        self.assertNotIn(b"\r", out.read_bytes())
        self.assertIn(cacert.colon_hex(SHA), text)
        self.assertIn("2030-08-02", text)
        self.assertIn("NOTE:", text)

    def test_existing_output_is_kept_without_force(self):
        out = self.dir / "ca.pem"
        out.write_text("mine", encoding="utf-8")
        with self.assertRaisesRegex(builder.OtaError, "already exists"):
            self.run_ca("--zip", self.zip, "-o", out)
        self.assertEqual(out.read_text(encoding="utf-8"), "mine")
        self.run_ca("--zip", self.zip, "-o", out, "--force")
        self.assertEqual(ssl.PEM_cert_to_DER_cert(out.read_text(encoding="ascii")), DER)

    def test_nothing_is_written_when_the_certificate_is_missing(self):
        out = self.dir / "sub" / "ca.pem"
        with self.assertRaises(builder.OtaError):
            self.run_ca("--zip", package(self.dir, NOISE, "Blank.zip"), "-o", out)
        self.assertFalse(out.exists())
        self.assertFalse(out.parent.exists())

    def test_default_output_is_fw_shelly_ca_pem_beside_not_inside_fw_shelly(self):
        with mock.patch.object(ota, "MODULE_DIR", self.dir):
            self.run_ca("--zip", self.zip)
        self.assertTrue((self.dir / "fw" / "shelly-ca.pem").is_file())

    def test_expired_root_warns(self):
        with mock.patch.object(cacert, "expired", return_value=True):
            self.assertIn("WARNING:", self.run_ca("--zip", self.zip, "-o", self.dir / "ca.pem"))

    def test_without_arguments_it_takes_a_cached_package(self):
        fw = self.dir / "fw" / "shelly"
        for device, fs in (("A", NOISE), ("B", NOISE + DER)):
            (fw / device / "1.0.0").mkdir(parents=True)
            package(fw / device / "1.0.0", fs, f"{device}.zip")
        with mock.patch.object(firmware, "FW_DIR", fw):
            newest = ota._newest_cached_package()
            self.assertEqual(newest.parent.parent.name, "B")    # written last
            self.run_ca("-o", self.dir / "ca.pem")
        self.assertTrue((self.dir / "ca.pem").is_file())

    def test_without_arguments_and_nothing_cached(self):
        with mock.patch.object(firmware, "FW_DIR", self.dir / "none"):
            with self.assertRaisesRegex(builder.OtaError, "No official ZIP cached"):
                self.run_ca()

    def test_unknown_device_is_an_error(self):
        with self.assertRaises(Exception):
            self.run_ca("NoSuchDevice")


class RealPackagesTests(unittest.TestCase):
    @needs_fw
    def test_every_cached_package_holds_the_pinned_root(self):
        zips = sorted(firmware.FW_DIR.glob("*/*/*.zip"))
        missing = []
        for z in zips:
            try:
                cacert.extract_from_zip(z)
            except builder.OtaError:
                missing.append(z.relative_to(firmware.FW_DIR).as_posix())
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
