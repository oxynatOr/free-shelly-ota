"""Create a device profile from an official Shelly OTA ZIP."""

from __future__ import annotations

import re
import struct
import zipfile
from pathlib import Path

from .builder import OtaError, read_official_manifest
from .profile import DEVICES_DIR

ENTRY = struct.Struct("<HBBII16sI")  # magic, type, subtype, offset, size, name, flags
MAGIC = 0x50AA
APP_TYPE = 0x00


def parse_partitions(table: bytes) -> list[dict]:
    """Entries of an ESP-IDF partition table binary (MD5 and end markers are skipped)."""
    entries = []
    for pos in range(0, len(table) - ENTRY.size + 1, ENTRY.size):
        magic, ptype, subtype, offset, size, name, flags = ENTRY.unpack_from(table, pos)
        if magic != MAGIC:
            break  # 0xEBEB (MD5), 0xFFFF (end) or garbage
        entries.append({"name": name.rstrip(b"\0").decode(errors="replace"), "type": ptype,
                        "subtype": subtype, "offset": offset, "size": size})
    return entries


def create_profile(zip_path: Path, *, name: str | None = None, devices_dir: Path = DEVICES_DIR,
                   force: bool = False, parent: str | None = None) -> tuple[Path, dict]:
    """Write devices/<name>.yaml from the manifest and partition table inside the ZIP."""
    with zipfile.ZipFile(zip_path) as zf:
        manifest = read_official_manifest(zf)
        name = name or manifest["name"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise OtaError(f"Invalid device name {name!r}.")
        pt_part = manifest["parts"].get("pt")
        if not pt_part or "src" not in pt_part:
            raise OtaError("The ZIP has no partition table part ('pt'); cannot read the app slot size.")
        table = parse_partitions(zf.read(pt_part["src"]))
    pt_addr = pt_part.get("addr", 0x10000)
    ptn = manifest["parts"]["app"].get("ptn")
    slot = next((e for e in table if e["name"] == ptn and e["type"] == APP_TYPE), None)
    if slot is None:
        raise OtaError(f"Partition {ptn!r} not found in the partition table "
                       f"(found: {', '.join(e['name'] for e in table)}).")
    path = devices_dir / f"{name}.yaml"
    if path.exists() and not force:
        raise OtaError(f"{path.name} already exists (use --force to overwrite).")
    info = {"name": name, "platform": manifest.get("platform", "esp32c3"), "ptn": ptn,
            "slot_size": slot["size"], "slot_offset": slot["offset"]}
    devices_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# OTA profile for {name}, generated from the official {manifest['version']} package.\n"
        f"display_name: \"{name}\"\n"
        f"platform: {info['platform']}\n"
        f"update_id: {manifest['name']}        # name used by https://updates.shelly.cloud/update/<update_id>\n"
        + (f"parent: {parent}        # variant: listed under \"alt\" in the update API reply of {parent}\n" if parent else "")
        + f"app_ptn: {ptn}\n"
        f"app_slot_size: 0x{slot['size']:x}   # {ptn} @0x{slot['offset']:x}\n"
        + (f"pt_offset: 0x{pt_addr:x}   # partition table address (default 0x10000)\n" if pt_addr != 0x10000 else ""),
        encoding="utf-8")
    return path, info
