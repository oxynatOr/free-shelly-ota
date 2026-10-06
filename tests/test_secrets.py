"""Run from ShellyOTA/: python -m unittest discover tests"""

import base64
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shelly_ota import __version__, builder, firmware, profile, secrets_check  # noqa: E402
from test_builder import fake_app  # noqa: E402

PW = "hunter2-test-pw"
SSID = "TestNet-42"
KEY = base64.b64encode(bytes(range(32))).decode()


def image_with(*texts: bytes) -> bytes:
    app = bytearray(fake_app(100_000))
    pos = 200
    for t in texts:
        app[pos:pos + len(t)] = t
        pos += len(t) + 8
    return bytes(app)


class SecretsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "secrets.yaml").write_text(
            f'wifi_ssid: "{SSID}"\nwifi_password: "{PW}"\napi_key: "{KEY}"\nshort: "ab"\nunused_thing: "never-in-image"\n',
            encoding="utf-8")
        self.yaml = self.tmp / "dev.yaml"
        self.yaml.write_text(
            "wifi:\n  ssid: !secret wifi_ssid\n  password: !secret wifi_password\n"
            "  ap:\n    password: literal-ap-pass\n"
            "api:\n  encryption:\n    key: !secret api_key\n"
            "ota:\n  - platform: esphome\n    password: ota-secret-1\n", encoding="utf-8")

    def test_collect_resolves_secrets_and_reads_literals(self):
        found, problem = secrets_check.collect(self.yaml)
        self.assertIsNone(problem)
        for name in ("wifi.ssid", "wifi.password", "wifi.ap.password", "api.encryption.key", "ota[0].password"):
            self.assertIn(name, found)
        self.assertNotIn("secrets.yaml:short", found)          # too short to compare
        self.assertIn(bytes(range(32)), found["api.encryption.key"])  # base64 key as raw bytes

    def test_scan_reports_names_only(self):
        found, _ = secrets_check.collect(self.yaml)
        hits = secrets_check.scan(image_with(SSID.encode(), PW.encode(), bytes(range(32))), found)
        self.assertEqual(hits, ["api.encryption.key", "wifi.password", "wifi.ssid"])
        self.assertFalse(any(PW in h or SSID in h for h in hits))

    def test_clean_image_has_no_hits(self):
        found, _ = secrets_check.collect(self.yaml)
        self.assertEqual(secrets_check.scan(image_with(b"nothing special"), found), [])

    def test_build_warns_and_reports_names_never_values(self):
        found, _ = secrets_check.collect(self.yaml)
        app = self.tmp / "app.bin"
        app.write_bytes(image_with(PW.encode()))
        p = profile.load_profile("PlugMG3")
        res = builder.build(p, app, firmware.cached_zip("PlugMG3"), self.tmp / "o.zip", secrets=found)
        self.assertEqual(res.secrets_found, ["wifi.password"])
        self.assertTrue(any("CREDENTIALS IN THE IMAGE" in w for w in res.warnings))
        self.assertFalse(any(PW in w for w in res.warnings))
        builder.write_report(res)
        text = (self.tmp / "o.zip.report.json").read_text(encoding="utf-8")
        self.assertNotIn(PW, text)
        data = json.loads(text)
        self.assertEqual(data["contains_secrets"], ["wifi.password"])
        self.assertEqual(data["tool_version"], __version__)

    def test_fail_on_secrets_writes_nothing(self):
        found, _ = secrets_check.collect(self.yaml)
        app = self.tmp / "app.bin"
        app.write_bytes(image_with(PW.encode()))
        out = self.tmp / "o.zip"
        with self.assertRaises(builder.OtaError) as ctx:
            builder.build(profile.load_profile("PlugMG3"), app, firmware.cached_zip("PlugMG3"), out,
                          secrets=found, fail_on_secrets=True)
        self.assertNotIn(PW, str(ctx.exception))
        self.assertFalse(out.exists())

    def test_unchecked_build_says_so(self):
        app = self.tmp / "app.bin"
        app.write_bytes(fake_app(100_000))
        res = builder.build(profile.load_profile("PlugMG3"), app, firmware.cached_zip("PlugMG3"), self.tmp / "o.zip")
        self.assertIsNone(res.secrets_found)
        self.assertTrue(any("not checked" in w for w in res.warnings))
        builder.write_report(res)
        data = json.loads((self.tmp / "o.zip.report.json").read_text(encoding="utf-8"))
        self.assertIsNone(data["contains_secrets"])

    def test_report_note(self):
        z = self.tmp / "x.zip"
        z.write_bytes(b"")
        self.assertIsNone(secrets_check.report_note(z))  # no report
        rep = Path(str(z) + ".report.json")
        rep.write_text(json.dumps({"contains_secrets": ["wifi.password"]}), encoding="utf-8")
        self.assertEqual(secrets_check.report_note(z)[0], "WARNING")
        rep.write_text(json.dumps({"contains_secrets": None}), encoding="utf-8")
        self.assertEqual(secrets_check.report_note(z)[0], "NOTE")
        rep.write_text(json.dumps({"contains_secrets": []}), encoding="utf-8")
        self.assertIsNone(secrets_check.report_note(z))

    def test_version_flag(self):
        import subprocess
        out = subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent / "ota.py"), "--version"],
                             capture_output=True, text=True)
        self.assertTrue(out.stdout.strip().startswith(f"ota.py {__version__}"), out.stdout)   # plus branch/commit in a checkout


if __name__ == "__main__":
    unittest.main()
