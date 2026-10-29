"""Run from ShellyOTA/: python -m unittest discover tests"""

import hashlib
import json
import shutil
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from needs_fw import needs_fw  # noqa: E402
from shelly_ota import builder, devicegen, firmware, profile  # noqa: E402
from test_builder import fake_app  # noqa: E402

PARTITIONS_DIR = Path(__file__).resolve().parent.parent / "partitions"


def zip_with_app_slot(src: Path, dst: Path, ptn: str, new_size: int, pt_addr: int | None = None) -> None:
    """Copy of an official ZIP whose partition table gives `ptn` another size (manifest hash and size kept consistent)."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        manifest = json.loads(zin.read("manifest.json"))
        pt = manifest["parts"]["pt"]
        table = bytearray(zin.read(pt["src"]))
        for pos in range(0, len(table), devicegen.ENTRY.size):
            magic, *_, name, _flags = devicegen.ENTRY.unpack_from(table, pos)
            if magic == devicegen.MAGIC and name.rstrip(b"\0") == ptn.encode():
                struct.pack_into("<I", table, pos + 8, new_size)
        pt["cs_sha256"] = hashlib.sha256(table).hexdigest()
        if pt_addr is not None:
            pt["addr"] = pt_addr
        for name in zin.namelist():
            zout.writestr(name, json.dumps(manifest) if name == "manifest.json" else
                          bytes(table) if name == pt["src"] else zin.read(name))


class LayoutCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.profile = profile.load_profile("PlugMG3")
        self.official = firmware.cached_zip("PlugMG3")
        self.assertIsNotNone(self.official, "seed ZIP missing in fw/shelly")
        self.app = self.tmp / "app.bin"
        self.app.write_bytes(fake_app(100_000))

    def _problems(self, path):
        with zipfile.ZipFile(path) as zf:
            return builder.package_layout_problems(self.profile, zf, builder.read_official_manifest(zf))

    @needs_fw
    def test_matching_package_has_no_problem(self):
        self.assertEqual(self._problems(self.official), [])

    @needs_fw
    def test_build_refuses_a_bigger_app_slot(self):
        other = self.tmp / "beta.zip"
        zip_with_app_slot(self.official, other, "app_0", 0x300000)  # the layout of PlugMG3 2.2.0-beta2
        with self.assertRaises(builder.OtaError) as cm:
            builder.build(self.profile, self.app, other, self.tmp / "out.zip")
        self.assertIn("app_0 is 0x300000", str(cm.exception))
        self.assertIn("Nothing was built", str(cm.exception))
        self.assertFalse((self.tmp / "out.zip").exists())

    @needs_fw
    def test_build_refuses_it_also_when_pt_is_dropped(self):
        other = self.tmp / "beta.zip"
        zip_with_app_slot(self.official, other, "app_0", 0x300000)
        with self.assertRaises(builder.OtaError):
            builder.build(self.profile, self.app, other, self.tmp / "out.zip", drop=("pt",))

    @needs_fw
    def test_other_table_address_is_a_problem(self):
        other = self.tmp / "moved.zip"
        zip_with_app_slot(self.official, other, "app_0", self.profile.app_slot_size, pt_addr=0x8000)
        self.assertIn("0x8000", self._problems(other)[0])

    @needs_fw
    def test_inspect_warns(self):
        other = self.tmp / "beta.zip"
        zip_with_app_slot(self.official, other, "app_0", 0x300000)
        self.assertIn("WARNING: another layout", builder.inspect_zip(other, self.profile))
        self.assertNotIn("WARNING", builder.inspect_zip(self.official, self.profile))


class CachedPackagesMatchStockCsvTests(unittest.TestCase):
    """A new official package with another table shows up here, before it reaches anyone."""

    @staticmethod
    def _rows(text):
        return [l.strip() for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")]

    @needs_fw
    def test_every_cached_package_matches_its_profile_and_csv(self):
        checked = 0
        for name in profile.list_devices():
            prof = profile.load_profile(name)
            zip_path = firmware.cached_zip(prof.package_name, prerelease=prof.channel == "beta")
            if zip_path is None:
                continue
            checked += 1
            with zipfile.ZipFile(zip_path) as zf:
                manifest = builder.read_official_manifest(zf)
                with self.subTest(device=name, check="profile"):
                    self.assertEqual(builder.package_layout_problems(prof, zf, manifest), [])
            csv = PARTITIONS_DIR / f"{name}-stock.csv"
            if csv.is_file():
                with self.subTest(device=name, check="stock csv"):
                    self.assertEqual(self._rows(csv.read_text(encoding="utf-8")),
                                     self._rows(devicegen.partition_csv(zip_path)))
        self.assertGreater(checked, 0, "no cached package found in fw/shelly")


if __name__ == "__main__":
    unittest.main()
