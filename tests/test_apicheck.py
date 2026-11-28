"""Run from ShellyOTA/: python -m unittest discover tests

`profiles --check-api` and `partition-csv` with a package that is not cached. No network.
"""

import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ota  # noqa: E402
from needs_fw import base_zip, needs_fw  # noqa: E402
from shelly_ota import apicheck, builder, firmware, profile  # noqa: E402


def run(reply, cached=("2.2.0",), name="PlugMG3", **kw):
    lines = []
    fetch = kw.pop("fetch", mock.Mock())
    query = kw.pop("query", lambda *a, **k: reply)
    with mock.patch.object(firmware, "list_versions", return_value=list(cached)):
        attention = apicheck.check_api([name], out=lines.append, query=query, fetch=fetch, sleep=lambda s: None, **kw)
    return lines, attention, fetch


class CheckApiTests(unittest.TestCase):
    def test_cached_older_and_new_versions(self):
        self.assertEqual(run({"stable": {"version": "2.2.0"}})[0], ["PlugMG3: stable 2.2.0 cached"])
        self.assertEqual(run({"stable": {"version": "2.0.3"}})[0],
                         ["PlugMG3: stable 2.0.3 offered, older than the cached 2.2.0"])
        lines, attention, fetch = run({"stable": {"version": "2.3.0"}})
        self.assertEqual((lines, attention), (["PlugMG3: stable 2.3.0 NEW (not cached)"], []))
        fetch.assert_not_called()

    def test_an_offered_beta_gets_its_own_line(self):
        lines = run({"stable": {"version": "2.2.0"}, "beta": {"version": "2.3.0-beta1"}})[0]
        self.assertEqual(lines, ["PlugMG3: stable 2.2.0 cached", "PlugMG3: beta 2.3.0-beta1 NEW (not cached)"])

    def test_no_release(self):
        self.assertEqual(run({"time": 1})[0], ["PlugMG3: no stable release listed"])

    def test_a_flaky_server_is_asked_again(self):
        query = mock.Mock(side_effect=[builder.OtaError("HTTP Error 502"), {"stable": {"version": "2.2.0"}}])
        self.assertEqual(run(None, query=query)[0], ["PlugMG3: stable 2.2.0 cached"])

    def test_an_unanswered_profile_needs_attention(self):
        lines, attention, _ = run(None, query=mock.Mock(side_effect=builder.OtaError("down")))
        self.assertEqual(attention, ["PlugMG3"])
        self.assertIn("not answered", lines[0])

    def test_a_certificate_error_stops_at_once(self):
        query = mock.Mock(side_effect=builder.OtaError("CERTIFICATE_VERIFY_FAILED"))
        with self.assertRaises(builder.OtaError):
            run(None, query=query)
        self.assertEqual(query.call_count, 1)

    def test_the_download_asks_as_the_check_did(self):
        listed = {"stable": {"version": "9.0.0"}}
        only_for_old = lambda *a, **k: listed if k["from_version"] else {"time": 1}
        for query, expected in ((only_for_old, apicheck.OLD_DEVICE), (lambda *a, **k: listed, None)):
            fetch = mock.Mock(side_effect=builder.OtaError("stop here"))
            run(None, query=query, download=True, fetch=fetch)
            self.assertEqual(fetch.call_args.kwargs["from_version"], expected)

    @needs_fw
    def test_download_says_which_layout_fits(self):
        later = profile.load_profile("PlugMG3").variants()[-1]
        for path, text in ((base_zip("PlugMG3"), "the first one"), (firmware.zip_for_layout(later), "since 2.2.0")):
            if path is None:
                continue
            lines, attention, fetch = run({"stable": {"version": "9.0.0"}}, download=True, fetch=mock.Mock(return_value=path))
            self.assertIn(f"layout fits: {text}", lines[0])
            self.assertEqual(attention, [])


class PartitionCsvDownloadTests(unittest.TestCase):
    def setUp(self):
        self.fw = Path(tempfile.mkdtemp())
        self.p = profile.load_profile("PlugMG3")

    def args(self, **kw):
        base = dict(layout="2.2.0", official=None, version=None, download=False, insecure=False, cafile=None, channel="stable",
                    esphome_yaml=None, compile=None, esphome_factory=None)
        return argparse.Namespace(**{**base, **kw})

    def test_without_a_terminal_it_names_the_missing_file_and_the_way(self):
        with mock.patch.object(firmware, "zip_for_layout", return_value=None), \
                mock.patch.object(ota, "_fetch_official") as fetch, \
                mock.patch("sys.stdin.isatty", return_value=False):
            with self.assertRaises(builder.OtaError) as cm:
                ota._partition_csv_package(self.p, self.args())
        fetch.assert_not_called()
        for text in ("is cached in", "PlugMG3-stock-2.2.0.csv", "--download", "--insecure", "--cafile"):
            self.assertIn(text, str(cm.exception))

    def test_the_answers_set_how_tls_is_checked(self):
        for answers, expected, insecure, cafile in ((["i"], True, True, None), (["c", "ca.pem"], True, False, Path("ca.pem")),
                                                    ([""], False, False, None), (["c", ""], False, False, None)):
            args = self.args()
            with mock.patch.object(ota, "_ask", side_effect=answers), mock.patch("sys.stdin.isatty", return_value=True), \
                    mock.patch("sys.stderr.isatty", return_value=True):
                self.assertEqual(ota._ask_download_tls(args, "missing"), expected, answers)
            self.assertEqual((args.insecure, args.cafile), (insecure, cafile), answers)

    def test_download_flag_fetches_without_asking(self):
        with mock.patch.object(firmware, "zip_for_layout", return_value=None), \
                mock.patch.object(ota, "_fetch_official", return_value=Path("x/2.2.0/PlugMG3.zip")) as fetch, \
                mock.patch.object(builder, "zip_layout_problems", return_value=[]):
            found = ota._partition_csv_package(self.p, self.args(download=True, insecure=True))
        self.assertEqual(found, Path("x/2.2.0/PlugMG3.zip"))
        self.assertTrue(fetch.call_args.kwargs["insecure"])


if __name__ == "__main__":
    unittest.main()
