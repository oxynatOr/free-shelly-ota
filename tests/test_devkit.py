"""ota.py devkit: a flash image for a dev board, made from a package."""

import hashlib
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ota  # noqa: E402
from needs_fw import needs_fw  # noqa: E402
from shelly_ota import builder, devkit, firmware, profile  # noqa: E402
from shelly_ota.devicegen import parse_partitions  # noqa: E402
from test_bootswap import make_factory  # noqa: E402
from test_builder import fake_app  # noqa: E402

DOC = Path(__file__).resolve().parent.parent / "docs" / "devkit.md"


def rewrite(src: Path, dst: Path, files: dict | None = None, edit=None) -> Path:
    """Copy a package, optionally replacing files and editing the manifest (the hashes are the caller's business)."""
    with zipfile.ZipFile(src) as zin:
        manifest = json.loads(zin.read("manifest.json"))
        data = {n: zin.read(n) for n in zin.namelist() if n != "manifest.json"}
    data.update(files or {})
    if edit:
        edit(manifest, data)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_STORED) as zout:
        zout.writestr("manifest.json", json.dumps(manifest))
        for name, blob in data.items():
            zout.writestr(name, blob)
    return dst


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    @needs_fw
    def test_every_profile_gives_a_consistent_image(self):
        seen = 0
        for name in profile.list_devices():
            official = firmware.cached_zip(name)
            if official is None:
                continue
            seen += 1
            prof = profile.load_profile(name)
            image = devkit.build_image(official, prof)
            with zipfile.ZipFile(official) as z:
                manifest = json.loads(z.read("manifest.json"))
                table = parse_partitions(z.read("partition-table.bin"))
                covered = bytearray(len(image.data))
                for p in image.parts:
                    part = manifest["parts"][p.key]
                    want = z.read(part["src"]) if "src" in part else bytes([part["fill"]]) * p.size
                    self.assertEqual(image.data[p.offset:p.offset + p.size], want, f"{name} {p.key}")
                    covered[p.offset:p.offset + p.size] = b"\x01" * p.size
            gaps = [i for i, c in enumerate(covered) if not c]
            self.assertTrue(all(image.data[i] == 0xFF for i in gaps), f"{name}: gaps are not 0xFF")
            self.assertEqual(len(image.data) % devkit.SECTOR, 0, name)
            self.assertGreaterEqual(len(image.data), max(p.offset + p.size for p in image.parts), name)
            self.assertEqual(image.table_end, max(e["offset"] + e["size"] for e in table), name)
            self.assertIn(image.needed_mib, (4, 8, 16), name)
            self.assertEqual(image.chip, prof.platform, name)
            pt = next(p for p in image.parts if p.key == "pt")
            self.assertEqual(pt.offset, prof.pt_offset, name)
        self.assertGreater(seen, 5, "the firmware cache is missing")

    @needs_fw
    def test_a_board_with_too_little_flash_is_refused_with_the_need(self):
        plug = profile.load_profile("PlugMG3")
        with self.assertRaises(builder.OtaError) as cm:
            devkit.build_image(firmware.cached_zip("PlugMG3"), plug, flash_size="4MB")
        self.assertIn("8 MiB", str(cm.exception))
        self.assertEqual(devkit.build_image(firmware.cached_zip("PlugMG3"), plug, flash_size="8MB").needed_mib, 8)
        uni = profile.load_profile("PlusUni")
        self.assertEqual(devkit.build_image(firmware.cached_zip("PlusUni"), uni, flash_size="4MB").needed_mib, 4)
        with self.assertRaises(builder.OtaError) as cm:
            devkit.build_image(firmware.cached_zip("Pro3EM"), profile.load_profile("Pro3EM"), flash_size="8MB")
        self.assertIn("16 MiB", str(cm.exception))
        with self.assertRaises(builder.OtaError):
            devkit.build_image(firmware.cached_zip("PlusUni"), uni, flash_size="3MB")

    @needs_fw
    def test_a_built_package_gives_the_state_after_the_install(self):
        prof = profile.load_profile("PlugMG3")
        official = firmware.cached_zip("PlugMG3")
        app = fake_app(100_000)
        (self.tmp / "app.bin").write_bytes(app)
        with zipfile.ZipFile(official) as z:
            table = {e["name"]: e for e in parse_partitions(z.read("partition-table.bin"))}
            official_boot = z.read("bootloader.bin")
        slot = table["app_0"]["offset"]

        plain = self.tmp / "plain.zip"
        builder.build(prof, self.tmp / "app.bin", official, plain)
        image = devkit.build_image(plain, prof)
        self.assertEqual(image.data[slot:slot + len(app)], app)
        self.assertEqual(image.data[0:len(official_boot)], official_boot)     # Shelly's bootloader stays

        (self.tmp / "factory.bin").write_bytes(make_factory(official, app))
        swapped = self.tmp / "swapped.zip"
        builder.build(prof, self.tmp / "app.bin", official, swapped, factory=self.tmp / "factory.bin")
        image = devkit.build_image(swapped, prof)
        self.assertEqual(image.data[slot:slot + len(app)], app)
        self.assertNotEqual(image.data[0:len(official_boot)], official_boot)  # ESPHome's bootloader
        ota_off = table["otadata"]["offset"]
        self.assertEqual(set(image.data[ota_off:ota_off + 8192]), {0xFF})      # clean otadata

    @needs_fw
    def test_a_part_that_does_not_fit_its_partition_is_refused(self):
        prof = profile.load_profile("PlugMG3")

        def too_big(manifest, data):
            data["PlugMG3.bin"] = data["PlugMG3.bin"] + bytes(prof.app_slot_size)
            manifest["parts"]["app"]["size"] = len(data["PlugMG3.bin"])
            manifest["parts"]["app"]["cs_sha256"] = hashlib.sha256(data["PlugMG3.bin"]).hexdigest()

        bad = rewrite(firmware.cached_zip("PlugMG3"), self.tmp / "big.zip", edit=too_big)
        with self.assertRaises(builder.OtaError) as cm:
            devkit.build_image(bad, prof)
        self.assertIn("does not fit", str(cm.exception))

    @needs_fw
    def test_overlapping_parts_are_refused(self):
        prof = profile.load_profile("PlugMG3")

        def overlap(manifest, data):
            manifest["parts"]["pt"]["addr"] = 0x1000     # inside the bootloader

        bad = rewrite(firmware.cached_zip("PlugMG3"), self.tmp / "overlap.zip", edit=overlap)
        with self.assertRaises(builder.OtaError) as cm:
            devkit.build_image(bad, prof)
        self.assertIn("overlap", str(cm.exception))

    @needs_fw
    def test_a_package_with_a_wrong_hash_is_refused(self):
        prof = profile.load_profile("PlugMG3")
        bad = rewrite(firmware.cached_zip("PlugMG3"), self.tmp / "hash.zip", files={"fs.img": b"\x00" * 917504})
        with self.assertRaises(builder.OtaError):
            devkit.build_image(bad, prof)


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def _run(self, *argv):
        args = ota.build_parser().parse_args(["devkit", *argv])
        buf = io.StringIO()
        with redirect_stdout(buf):
            args.func(args)
        return buf.getvalue()

    @needs_fw
    def test_writes_the_image_and_prints_the_esptool_commands(self):
        out = self.tmp / "uni.bin"
        text = self._run("PlusUni", "-o", str(out), "--port", "COM7")
        self.assertTrue(out.is_file())
        self.assertEqual(len(out.read_bytes()), 2 * 1024 * 1024)
        self.assertIn("--chip esp32 --port COM7 erase-flash", text)
        self.assertRegex(text, r"--chip esp32 --port COM7 --baud 460800 write-flash .* 0x0 .*uni\.bin")
        self.assertIn("0x001000", text)          # the bootloader of the classic ESP32
        self.assertIn(hashlib.sha256(out.read_bytes()).hexdigest(), text)
        self.assertIn("BURN BLOCK3", text)
        self.assertIn("WARNING:", text)

    @needs_fw
    def test_the_c3_image_starts_with_the_bootloader_at_zero(self):
        out = self.tmp / "plug.bin"
        text = self._run("PlugMG3", "-o", str(out))
        self.assertIn("--chip esp32c3", text)
        self.assertIn("0x000000", text)
        with zipfile.ZipFile(firmware.cached_zip("PlugMG3")) as z:
            boot = z.read("bootloader.bin")
        self.assertEqual(out.read_bytes()[:len(boot)], boot)

    @needs_fw
    def test_an_existing_output_needs_force(self):
        out = self.tmp / "uni.bin"
        out.write_bytes(b"old")
        with self.assertRaises(builder.OtaError):
            self._run("PlusUni", "-o", str(out))
        self._run("PlusUni", "-o", str(out), "--force")
        self.assertGreater(len(out.read_bytes()), 3)

    def test_flash_size_stops_before_anything_is_written(self):
        out = self.tmp / "plug.bin"
        with self.assertRaises(builder.OtaError):
            self._run("PlugMG3", "-o", str(out), "--flash-size", "4MB")
        self.assertFalse(out.exists())


class DocTests(unittest.TestCase):
    def test_the_board_table_matches_the_profiles(self):
        rows = {}
        for line in DOC.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\|\s*`(\w+)`\s*\|[^|]*\|\s*([\w-]+)\s*\|\s*(\d+) MiB\s*\|", line)
            if m:
                rows[m.group(1)] = (m.group(2).lower().replace("-", ""), int(m.group(3)))
        for name in profile.list_devices():
            official = firmware.cached_zip(name)
            if official is None:
                continue
            image = devkit.build_image(official, profile.load_profile(name))
            self.assertIn(name, rows, f"{name} is not in the board table of docs/devkit.md")
            self.assertEqual(rows[name], (image.chip, image.needed_mib), name)
        self.assertEqual(sorted(set(rows) - set(profile.list_devices())), [], "the table lists a profile that does not exist")


if __name__ == "__main__":
    unittest.main()
