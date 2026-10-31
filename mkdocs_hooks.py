"""MkDocs hooks for the documentation site.

The pages are written for GitHub: they link to files outside docs/ (README, CHANGELOG, device profiles) and the device pages
carry the generation as a badge. The site keeps the pages as they are; this module only
  - builds the nav (top pages in reading order, device pages grouped by generation),
  - points links that leave docs/ at the file on GitHub.
"""

import re
from pathlib import Path, PurePosixPath

REPO_URL = "https://github.com/oxynatOr/free-shelly-ota"
BRANCH = "main"

TOP_PAGES = [
    ("Overview", "README.md"),
    ("Step-by-step guide", "guide.md"),
    ("Commands", "commands.md"),
    ("Troubleshooting", "troubleshooting.md"),
    ("Bootloader and slots", "bootloader-and-slots.md"),
    ("Recovery over UART", "recovery-uart.md"),
    ("Test on a dev board", "devkit.md"),
    ("Credential check", "credential-check.md"),
    ("Versions", "versions.md"),
    ("Developer guide", "guide-developers.md"),
    ("Gen1 research", "research/gen1.md"),
]

_LINK = re.compile(r"(\]\()([^)\s#]+)((?:#[^)\s]*)?\))")
_GEN = re.compile(r"badge/gen-(\d)")
_TITLE = re.compile(r"^# (.+)$", re.MULTILINE)


def _title(path: Path) -> str:
    match = _TITLE.search(path.read_text(encoding="utf-8"))
    return match.group(1).strip() if match else path.stem


def on_config(config):
    docs = Path(config["docs_dir"])
    groups = {}
    for page in sorted((docs / "devices").glob("*.md")):
        if page.name == "README.md":
            continue
        gen = _GEN.search(page.read_text(encoding="utf-8"))
        groups.setdefault(f"Gen{gen.group(1)}" if gen else "Other", []).append(
            {_title(page): f"devices/{page.name}"}
        )
    devices = [{"All devices": "devices/README.md"}]
    devices += [{name: pages} for name, pages in sorted(groups.items())]
    config["nav"] = [{title: path} for title, path in TOP_PAGES[:1]] + [
        {"Devices": devices},
        *({title: path} for title, path in TOP_PAGES[1:]),
    ]
    return config


def on_page_markdown(markdown, page, config, files):
    """Links that resolve outside docs/ go to the file on GitHub, the rest stays relative."""
    page_dir = PurePosixPath(page.file.src_uri).parent

    def rewrite(match):
        target = match.group(2)
        if re.match(r"[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) or target.startswith("/"):
            return match.group(0)
        resolved = PurePosixPath(*_normalise(page_dir / target))
        if not resolved.parts or resolved.parts[0] != "..":
            return match.group(0)
        repo_path = PurePosixPath(*resolved.parts[1:])
        kind = "tree" if not repo_path.suffix else "blob"
        return f"{match.group(1)}{REPO_URL}/{kind}/{BRANCH}/{repo_path}{match.group(3)}"

    return _LINK.sub(rewrite, markdown)


def _normalise(path: PurePosixPath):
    parts = []
    for part in path.parts:
        if part == "..":
            if parts and parts[-1] != "..":
                parts.pop()
            else:
                parts.append("..")
        elif part != ".":
            parts.append(part)
    return parts
