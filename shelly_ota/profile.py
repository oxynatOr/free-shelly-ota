"""Device profiles: one small YAML file per device in devices/."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from pathlib import Path

import yaml

from . import MODULE_DIR

DEVICES_DIR = MODULE_DIR / "devices"


class ProfileError(Exception):
    pass


LOCK_FILE = "profiles.lock"


@dataclass(frozen=True)
class Layout:
    """A later flash layout of the same device, from the Shelly firmware version `since` on."""
    since: str
    app_slot_size: int
    csv: str


@dataclass(frozen=True)
class Profile:
    name: str
    display_name: str
    platform: str
    update_id: str
    app_ptn: str
    app_slot_size: int
    parent: str | None = None  # base device whose update API lists this variant under "alt"
    pt_offset: int = 0x10000  # where the device keeps its partition table (HTG3: 0xf000)
    boot_min_version: str | None = None  # default for --boot-min-version with --esphome-factory (HTG3: 1.0.9)
    revision: int = 1  # counts changes of this profile; bump it when anything else in the file changes
    package: str | None = None  # name of the official package and of its folder in fw/ when it is not the profile's name (-beta profiles)
    channel: str = "stable"  # "beta": the profile is for pre-releases, so the newest pre-release is the default package
    layout_since: str | None = None  # firmware version from which the device has this profile's flash layout; `send` refuses older ones
    layouts: tuple[Layout, ...] = ()  # later layouts, oldest first; empty: the profile has exactly one layout
    csv: str | None = None  # the stock CSV of this layout (None: <name>-stock.csv)
    base: "Profile | None" = None  # set on a variant for a later layout: the profile it was made from

    @property
    def csv_name(self) -> str:
        return self.csv or f"{self.name}-stock.csv"

    def variants(self) -> list["Profile"]:
        """One profile per flash layout, oldest first. Each is an ordinary Profile with that layout's slot size, CSV and
        `layout_since`, so the code that builds and sends does not need to know about layouts."""
        root = self.base or self
        return [root] + [replace(root, app_slot_size=l.app_slot_size, layout_since=l.since, csv=l.csv, base=root)
                         for l in root.layouts]

    @property
    def package_name(self) -> str:
        return self.package or self.name


def _to_int(value, key: str) -> int:
    try:
        return int(value, 0) if isinstance(value, str) else int(value)
    except (TypeError, ValueError):
        raise ProfileError(f"'{key}' is not a valid integer: {value!r}") from None


def _version_numbers(version: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in version.split("."))


def _read_layouts(file: str, name: str, raw: dict) -> tuple[Layout, ...]:
    entries = raw.get("layouts") or []
    if not isinstance(entries, list):
        raise ProfileError(f"{file}: 'layouts' must be a list")
    layouts = []
    sizes = {_to_int(raw["app_slot_size"], "app_slot_size")}
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("since") or "app_slot_size" not in entry:
            raise ProfileError(f"{file}: every entry of 'layouts' needs 'since' and 'app_slot_size'")
        since = str(entry["since"])
        size = _to_int(entry["app_slot_size"], "app_slot_size")
        if size in sizes:   # the slot size is how a package or a CSV is told apart from the other layouts
            raise ProfileError(f"{file}: two layouts with app_slot_size 0x{size:x}; they cannot be told apart")
        if layouts and _version_numbers(since) <= _version_numbers(layouts[-1].since):
            raise ProfileError(f"{file}: 'layouts' must be listed oldest first (since)")
        sizes.add(size)
        layouts.append(Layout(since, size, str(entry.get("csv") or f"{name}-stock-{since}.csv")))
    return tuple(layouts)


def list_devices(devices_dir: Path = DEVICES_DIR) -> list[str]:
    return sorted(p.stem for p in devices_dir.glob("*.yaml"))


def load_profile(name: str, devices_dir: Path = DEVICES_DIR) -> Profile:
    path = devices_dir / f"{name}.yaml"
    if not path.is_file():
        raise ProfileError(f"Unknown device '{name}'. Available: {', '.join(list_devices(devices_dir)) or 'none'}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "app_slot_size" not in raw:
        raise ProfileError(f"{path.name}: missing required key 'app_slot_size'")
    layouts = _read_layouts(path.name, name, raw)
    return Profile(
        layouts=layouts,
        name=name,
        display_name=raw.get("display_name", name),
        platform=raw.get("platform", "esp32c3"),
        update_id=raw.get("update_id", name),
        app_ptn=raw.get("app_ptn", "app_0"),
        app_slot_size=_to_int(raw["app_slot_size"], "app_slot_size"),
        parent=raw.get("parent"),
        pt_offset=_to_int(raw.get("pt_offset", 0x10000), "pt_offset"),
        boot_min_version=str(raw["boot_min_version"]) if raw.get("boot_min_version") else None,
        revision=_to_int(raw.get("revision", 1), "revision"),
        package=str(raw["package"]) if raw.get("package") else None,
        channel=str(raw.get("channel", "stable")),
        layout_since=str(raw["layout_since"]) if raw.get("layout_since") else None,
    )


def content_hash(name: str, devices_dir: Path = DEVICES_DIR) -> str:
    """Short hash of a profile file without its `revision:` line, so a change is visible even if the revision was not bumped."""
    text = (devices_dir / f"{name}.yaml").read_text(encoding="utf-8").replace("\r\n", "\n")
    body = "\n".join(l.rstrip() for l in text.split("\n") if not l.startswith("revision:")).strip()
    return hashlib.sha256(body.encode()).hexdigest()[:12]


def read_lock(devices_dir: Path = DEVICES_DIR) -> dict:
    path = devices_dir / LOCK_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def write_lock(devices_dir: Path = DEVICES_DIR) -> dict:
    """Record the current revision and content hash of every profile (done after bumping a revision)."""
    lock = {n: {"revision": load_profile(n, devices_dir).revision, "hash": content_hash(n, devices_dir)}
            for n in list_devices(devices_dir)}
    (devices_dir / LOCK_FILE).write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return lock


def check_lock(devices_dir: Path = DEVICES_DIR) -> list[str]:
    """Problems between the profiles and devices/profiles.lock: a changed profile needs a higher revision and a new lock."""
    lock, problems = read_lock(devices_dir), []
    for n in list_devices(devices_dir):
        cur_rev, cur_hash = load_profile(n, devices_dir).revision, content_hash(n, devices_dir)
        entry = lock.get(n)
        if entry is None:
            problems.append(f"{n}: not in {LOCK_FILE} (run: python ota.py profiles --update-lock)")
        elif entry["hash"] != cur_hash and cur_rev <= entry["revision"]:
            problems.append(f"{n}: the profile changed, but revision is still {cur_rev}. Raise `revision:` in "
                            f"devices/{n}.yaml, then run: python ota.py profiles --update-lock")
        elif entry["hash"] != cur_hash or entry["revision"] != cur_rev:
            problems.append(f"{n}: {LOCK_FILE} is out of date (run: python ota.py profiles --update-lock)")
    for n in lock:
        if n not in list_devices(devices_dir):
            problems.append(f"{n}: in {LOCK_FILE} but the profile is gone (run: python ota.py profiles --update-lock)")
    return problems
