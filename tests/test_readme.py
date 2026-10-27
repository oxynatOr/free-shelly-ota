"""Run from ShellyOTA/: python -m unittest discover tests

Keeps the README (and the device overview next to the device pages) in step with the profiles.
"""

import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelly_ota import profile  # noqa: E402

ROOT = profile.MODULE_DIR
README = ROOT / "README.md"
DEVICE_OVERVIEW = ROOT / "docs" / "devices" / "README.md"
STATES = ("✅", "🟡", "🔬", "🧪")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}


def _slug(heading: str) -> str:
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def _anchors(path: Path) -> set:
    found = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"#{1,6}\s+(.*)", line)
        if m:
            found.add(_slug(m.group(1)))
    return found


def _table_states(path: Path, state_cell: str) -> dict:
    """{profile: state symbol} from the rows that link a profile as [`Name`](...)."""
    states = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|[^|]*\|\s*\[`([\w-]+)`\]\([^)]*\)\s*\|", line) \
            or re.match(r"\|\s*\[[^\]]+\]\([^)]*\)\s*\|\s*`([\w-]+)`\s*\|", line)    # the profile linked, or the device linked
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) <= state_cell:
            continue                      # another table with a profile column (the dev board runs)
        symbol = cells[state_cell].split(" ")[0]
        states[m.group(1)] = symbol
    return states


class ReadmeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = README.read_text(encoding="utf-8")
        cls.states = _table_states(README, state_cell=3)  # Device | Profile | Chip | State | Note: the confirmed devices
        cls.overview = _table_states(DEVICE_OVERVIEW, state_cell=5)  # Device | Profile | Chip | Table | Slot | State: all of them

    def test_the_overview_has_every_profile_and_nothing_else(self):
        self.assertEqual(sorted(self.overview), profile.list_devices())

    def test_the_readme_table_has_exactly_the_confirmed_devices(self):
        confirmed = {name: symbol for name, symbol in self.overview.items() if symbol in ("✅", "🟡")}
        self.assertEqual(self.states, confirmed)

    def test_states_are_known_symbols(self):
        for name, symbol in self.overview.items():
            self.assertIn(symbol, STATES, name)

    def test_summary_line_matches_the_table(self):
        m = re.search(r"\*\*(\d+) profiles:\*\* ✅ (\d+) confirmed · 🟡 (\d+) partly checked · 🔬 (\d+) DevKit-tested · 🧪 (\d+) untested", self.text)
        self.assertIsNotNone(m, "summary line above the device table is missing or changed its form")
        symbols = list(self.overview.values())
        expected = (len(symbols), symbols.count("✅"), symbols.count("🟡"), symbols.count("🔬"), symbols.count("🧪"))
        self.assertEqual(tuple(int(g) for g in m.groups()), expected)

    def test_the_dev_board_section_lists_exactly_the_devkit_tested_devices(self):
        text = DEVICE_OVERVIEW.read_text(encoding="utf-8")
        section = text.split("## Tested on a dev board", 1)[1].split("\n## ", 1)[0]
        listed = set(re.findall(r"(?m)^\| \[[^\]]+\]\([^)]*\) \| `(\w+)` \|", section))
        self.assertEqual(listed, {name for name, symbol in self.overview.items() if symbol == "🔬"})

    def test_relative_links_and_images_exist(self):
        for m in re.finditer(r"\]\(([^)\s]+)\)", self.text):
            url = m.group(1)
            if re.match(r"[a-z]+://", url):
                continue
            path, _, frag = url.partition("#")
            target = ROOT / path if path else README
            self.assertTrue(target.exists(), url)
            if frag and target.suffix == ".md":
                self.assertIn(frag, _anchors(target), url)
        for m in re.finditer(r'<img [^>]*src="([^"]+)"', self.text):
            if not re.match(r"[a-z]+://", m.group(1)):
                self.assertTrue((ROOT / m.group(1)).is_file(), m.group(1))


SECTIONS = ("Before you start", "ESPHome config", "Pins", "Flash it", "What to expect", "Notes for this device", "Way back")
BADGE = {"✅": "state-confirmed-", "🟡": "state-partly%20checked-", "🔬": "state-devkit%20tested-", "🧪": "state-untested-"}


class DevicePageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = sorted(p for p in (ROOT / "docs" / "devices").glob("*.md") if p.name != "README.md")
        cls.states = _table_states(DEVICE_OVERVIEW, state_cell=5)

    def _profiles(self, text):
        m = re.search(r"(?m)^\| Profile \| (.+) \|$", text)
        self.assertIsNotNone(m, "no Profile row")
        return re.findall(r"`([\w-]+)`", m.group(1))

    def test_every_profile_has_a_page(self):
        named = set()
        for page in self.pages:
            named.update(self._profiles(page.read_text(encoding="utf-8")))
        self.assertEqual(sorted(named), profile.list_devices())

    def test_pages_have_the_standard_sections_in_order(self):
        for page in self.pages:
            heads = re.findall(r"(?m)^## (.+)$", page.read_text(encoding="utf-8"))
            core = [h for h in heads if h in SECTIONS]
            self.assertEqual(core, [s for s in SECTIONS if s in heads], page.name)
            for needed in ("Before you start", "Flash it", "What to expect", "Notes for this device", "Way back"):
                self.assertIn(needed, heads, page.name)

    # The safety sentences stand on every device page, word for word: someone who lands on a page from a search must read them there.
    # The pages repeat them on purpose; this test keeps the copies from drifting apart.
    SAFETY_WIPES = ("> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, "
                    "power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).")
    SAFETY_BACK = ("> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back "
                   "([Recovery over UART](../recovery-uart.md)). Take a flash backup first")
    SAFETY_REPORT = ("> - **Flashed it? Tell us,** also when it worked: "
                     "[open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).")
    FLASHED_WITHOUT_UART = {"Pill.md", "PlusPlugIT.md", "PlusPlugS.md"}      # no bootloader swap needed there, their Way back says what applies

    def test_every_page_ends_with_the_same_safety_box(self):
        for page in self.pages:
            text = page.read_text(encoding="utf-8")
            box = text[text.rindex("---"):]
            self.assertIn("> [!WARNING]\n", box, page.name)
            self.assertIn(self.SAFETY_WIPES, box, page.name)
            self.assertIn(self.SAFETY_REPORT, box, page.name)
            if page.name in self.FLASHED_WITHOUT_UART:
                self.assertNotIn("No way back over the network", box, page.name)
            else:
                self.assertIn(self.SAFETY_BACK, box, page.name)

    def test_the_checklist_is_a_task_list_with_the_four_standard_checks(self):
        for page in self.pages:
            text = page.read_text(encoding="utf-8")
            section = text.split("## Before you start\n\n", 1)[1].split("\n## ", 1)[0]
            lines = section.splitlines()
            self.assertEqual(lines[:2], ["Check first:", ""], page.name)
            items = []
            for line in lines[2:]:
                if not line.startswith("- [ ] "):
                    break
                items.append(line)
            self.assertGreaterEqual(len(items), 4, page.name)
            checks = "\n".join(items)
            for part in ("Shelly's own firmware", "you know its IP address", "port 8000", "partition table below"):
                self.assertIn(part, checks, page.name)
            if "Recovery over UART" not in checks:         # a page with its own UART item says it under "Also:"
                self.assertIn("UART", section, page.name)

    def test_state_badge_matches_the_readme(self):
        for page in self.pages:
            text = page.read_text(encoding="utf-8")
            for name in self._profiles(text):
                self.assertIn(BADGE[self.states[name]], text, f"{page.name}: {name}")

    def test_a_page_that_links_the_esphome_device_page_has_it_as_a_row_of_the_table(self):
        """The link is in the Fact table once, as https://devices.esphome.io/devices/<slug>/, and every other link on the page goes to the same page."""
        for page in self.pages:
            text = page.read_text(encoding="utf-8")
            linked = set(re.findall(r"https://devices\.esphome\.io/devices/([^/)\s]+)/", text))
            if not linked:
                continue
            rows = re.findall(r"(?m)^\| ESPHome device page \| \[[^\]]+\]\(https://devices\.esphome\.io/devices/([a-z0-9-]+)/\)", text)
            self.assertEqual(len(rows), 1, f"{page.name}: one ESPHome device page row")
            self.assertEqual(linked, {rows[0]}, f"{page.name}: all links go to the page of the row")

    def test_flash_commands_use_the_profile_of_the_page(self):
        for page in self.pages:
            text = page.read_text(encoding="utf-8")
            first = self._profiles(text)[0]
            self.assertIn(f"python ota.py fetch {first} --insecure", text, page.name)
            self.assertIn(f"python ota.py restore {first}", text, page.name)

    def test_config_snippets_allow_partition_access(self):
        """The ota block of every config snippet lets ESPHome update the bootloader later."""
        block = "ota:\n  - platform: esphome\n    allow_partition_access: true"
        for page in self.pages + [README]:
            text = page.read_text(encoding="utf-8").replace("\r\n", "\n")
            if "platform: esphome" in text:
                self.assertIn(block, text, page.name)

    def test_relative_links_exist(self):
        for page in self.pages + [DEVICE_OVERVIEW]:
            text = page.read_text(encoding="utf-8")
            for m in re.finditer(r"\]\(([^)\s]+)\)", text):
                url = m.group(1)
                if re.match(r"[a-z]+://", url):
                    continue
                path, _, frag = url.partition("#")
                target = (page.parent / path) if path else page
                self.assertTrue(target.exists(), f"{page.name}: {url}")
                if frag and target.suffix == ".md":
                    self.assertIn(frag, _anchors(target), f"{page.name}: {url}")


class TopicPageTests(unittest.TestCase):
    """The pages that are not device pages share one frame: title, a navigation row that starts with the way back, then the text."""

    PAGES = (
        "docs/README.md", "docs/commands.md", "docs/bootloader-and-slots.md", "docs/troubleshooting.md", "docs/recovery-uart.md",
        "docs/credential-check.md", "docs/versions.md", "docs/devkit.md", "docs/devices/README.md", "devices/README.md", "ROADMAP.md", "CREDITS.md",
    )
    CALLOUTS = {"NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION"}

    @staticmethod
    def _lines_outside_code(text: str) -> list:
        lines, in_code = [], False
        for line in text.splitlines():
            if line.startswith("```"):
                in_code = not in_code
            elif not in_code:
                lines.append(line)
        return lines

    def _pages(self):
        for rel in self.PAGES:
            yield rel, ROOT / rel, (ROOT / rel).read_text(encoding="utf-8")

    def test_title_then_navigation_row_with_the_way_back(self):
        for rel, _, text in self._pages():
            lines = text.splitlines()
            self.assertTrue(lines[0].startswith("# "), rel)
            self.assertEqual(lines[1], "", rel)
            self.assertTrue(lines[2].startswith("[← README]("), f"{rel}: line 3 must be the navigation row starting with [← README](...)")

    def test_headings_carry_no_emoji(self):
        """Emoji only in links: in a heading they end up in the anchor."""
        emoji = re.compile("[\U0001F300-\U0001FAFF☀-➿️]")
        for rel, _, text in self._pages():
            for line in self._lines_outside_code(text):
                if re.match(r"#{1,6}\s", line):
                    self.assertIsNone(emoji.search(line), f"{rel}: {line}")

    def test_callouts_are_of_a_kind_github_renders(self):
        for rel, _, text in self._pages():
            for line in self._lines_outside_code(text):
                m = re.match(r">\s*\[!(\w+)\]", line)
                if m:
                    self.assertIn(m.group(1), self.CALLOUTS, f"{rel}: {line}")

    def test_relative_links_and_anchors_exist(self):
        for rel, path, text in self._pages():
            for m in re.finditer(r"\]\(([^)\s]+)\)", "\n".join(self._lines_outside_code(text))):
                url = m.group(1)
                if re.match(r"[a-z]+://|mailto:", url):
                    continue
                target_part, _, frag = url.partition("#")
                target = (path.parent / target_part) if target_part else path
                self.assertTrue(target.exists(), f"{rel}: {url}")
                if frag and target.suffix == ".md":
                    self.assertIn(frag, _anchors(target), f"{rel}: {url}")


class RepositoryTests(unittest.TestCase):
    def test_images_only_in_docs_assets(self):
        """The logo and the social preview live in docs/assets. Device photos belong on the ESPHome device pages."""
        if not shutil.which("git") or not (ROOT / ".git").exists():
            self.skipTest("needs a git checkout")
        files = subprocess.run(["git", "-C", str(ROOT), "ls-files"], capture_output=True, text=True, check=True).stdout.splitlines()
        stray = [f for f in files if Path(f).suffix.lower() in IMAGE_SUFFIXES and not f.startswith("docs/assets/")]
        self.assertEqual(stray, [], "pictures of devices do not belong in this repository: put them on the ESPHome device page")


if __name__ == "__main__":
    unittest.main()
