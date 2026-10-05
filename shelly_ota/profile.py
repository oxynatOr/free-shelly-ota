"""Device profiles: one small YAML file per device in devices/."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from . import MODULE_DIR

DEVICES_DIR = MODULE_DIR / "devices"


class ProfileError(Exception):
    pass


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


def _to_int(value, key: str) -> int:
    try:
        return int(value, 0) if isinstance(value, str) else int(value)
    except (TypeError, ValueError):
        raise ProfileError(f"'{key}' is not a valid integer: {value!r}") from None


def list_devices(devices_dir: Path = DEVICES_DIR) -> list[str]:
    return sorted(p.stem for p in devices_dir.glob("*.yaml"))


def load_profile(name: str, devices_dir: Path = DEVICES_DIR) -> Profile:
    path = devices_dir / f"{name}.yaml"
    if not path.is_file():
        raise ProfileError(f"Unknown device '{name}'. Available: {', '.join(list_devices(devices_dir)) or 'none'}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "app_slot_size" not in raw:
        raise ProfileError(f"{path.name}: missing required key 'app_slot_size'")
    return Profile(
        name=name,
        display_name=raw.get("display_name", name),
        platform=raw.get("platform", "esp32c3"),
        update_id=raw.get("update_id", name),
        app_ptn=raw.get("app_ptn", "app_0"),
        app_slot_size=_to_int(raw["app_slot_size"], "app_slot_size"),
        parent=raw.get("parent"),
        pt_offset=_to_int(raw.get("pt_offset", 0x10000), "pt_offset"),
    )
