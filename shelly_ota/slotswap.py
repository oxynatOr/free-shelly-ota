"""EXPERIMENTAL (issue #111): a package whose partition table makes the installer's target slot the one ESPHome starts.

Shelly's installer finds the app slots by label and address (`app_0`, `app_1`). ESPHome's bootloader, with the otadata it
cannot read, starts the app partition whose *subtype* is ota_0. In Shelly's table `app_0` is ota_0, so the app must land in
slot 0. Here the table keeps every label, address, size and flag and only swaps the two app subtypes, so that the slot the
installer writes to is ota_0.

Only a table at a NEW address works: a `pt` part for the address where Shelly's table already is (0x10000) is stored by the
installer in a journal (`Installing new PT1`) that only Shelly's own loader reads, and the old app keeps starting (seen on
Gen3 2.0.1/2.1.0 and Gen4 2.1.1 dev boards). A package made with `build --pt-addr 0x8000` makes the installer log
`PT is being moved from 0x10000 to 0x8000` and write the table there; ESPHome's bootloader (built to read 0x8000) then starts
the swapped slot. Shelly's own table stays at its address, untouched.

The installer writes the `pt` part to flash, so a wrong table cannot be undone over the network: only a serial connection
and a flash dump bring the device back. Not tried yet: going back to Shelly's firmware afterwards (`restore`).
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import NamedTuple

from .bootswap import CRITICAL_PARTITIONS
from .builder import RELOCATED_PT_ADDR, OtaError, read_official_manifest, require_zip
from .devicegen import APP_TYPE, ENTRY, parse_partitions

APP_SLOTS = ("app_0", "app_1")   # the labels Shelly's installer writes to; slot N is app_N
OTA_0, OTA_1 = 0x10, 0x11        # ESP-IDF app subtypes ota_0 and ota_1
_OTA_SUBTYPES = range(0x10, 0x20)
_SUBTYPE_AT = 3                  # byte of an entry that holds the subtype (magic 2, type 1, subtype 1)
_MD5_MAGIC = b"\xeb\xeb"         # ESP-IDF's MD5 entry: magic, 14 x 0xFF, MD5 of every entry before it


class SwapResult(NamedTuple):
    output: Path
    target: int                    # the slot the installer writes to, now ota_0
    changed: bool                  # False: the table already had app_<target> as ota_0, the package is unchanged
    subtypes: dict                 # {label: (address, subtype)} of the two app slots in the new table
    pt_sha256: tuple[str, str]     # (before, after)


def _md5_entry(table: bytes, count: int) -> int | None:
    """Position of the MD5 entry right after the `count` partition entries, or None if the table has none."""
    pos = count * ENTRY.size
    return pos if table[pos:pos + 2] == _MD5_MAGIC else None


def swap_table(table: bytes, target: int) -> bytes:
    """Shelly's partition table with app_<target> as ota_0 and the other app slot as ota_1.

    Only the two subtype bytes change, and the MD5 entry if the table has one. Raises OtaError if the table is not one
    this can be done with (no app_0/app_1 pair of ota_0/ota_1, another OTA app partition, a wrong MD5)."""
    if target not in (0, 1):
        raise OtaError(f"Slot swap: the target slot must be 0 or 1, not {target}.")
    entries = parse_partitions(table)
    index = {e["name"]: i for i, e in enumerate(entries)}
    for name in APP_SLOTS:
        if name not in index:
            raise OtaError(f"Slot swap: the partition table has no {name}; this layout cannot be swapped.")
    apps = [entries[index[name]] for name in APP_SLOTS]
    if any(e["type"] != APP_TYPE for e in apps) or sorted(e["subtype"] for e in apps) != [OTA_0, OTA_1]:
        found = ", ".join("%s type %d subtype 0x%02x" % (e["name"], e["type"], e["subtype"]) for e in apps)
        raise OtaError(f"Slot swap: app_0 and app_1 are not the app partitions ota_0 and ota_1 in this table ({found}).")
    others = [e["name"] for e in entries
              if e["type"] == APP_TYPE and e["subtype"] in _OTA_SUBTYPES and e["name"] not in APP_SLOTS]
    if others:
        raise OtaError(f"Slot swap: the table has more OTA app partitions ({', '.join(others)}); not swapping.")
    md5_at = _md5_entry(table, len(entries))
    if md5_at is not None and table[md5_at + 16:md5_at + 32] != hashlib.md5(table[:md5_at]).digest():
        raise OtaError("Slot swap: the MD5 of the partition table does not match; not touching it.")

    new = bytearray(table)
    for slot, name in enumerate(APP_SLOTS):
        new[index[name] * ENTRY.size + _SUBTYPE_AT] = OTA_0 if slot == target else OTA_1
    if md5_at is not None:
        new[md5_at + 16:md5_at + 32] = hashlib.md5(bytes(new[:md5_at])).digest()
    new = bytes(new)
    check_swapped(table, new, target)
    return new


def check_swapped(old: bytes, new: bytes, target: int) -> None:
    """Raise OtaError unless `new` is `old` with only the app subtypes changed and app_<target> as ota_0.

    The CRITICAL_PARTITIONS of bootswap (and every other entry) keep name, type, address, size and flags."""
    before, after = parse_partitions(old), parse_partitions(new)
    if len(old) != len(new) or len(before) != len(after):
        raise OtaError("Slot swap: the new partition table has another length or number of entries.")
    for b, a in zip(before, after):
        same = (a["name"], a["type"], a["offset"], a["size"]) == (b["name"], b["type"], b["offset"], b["size"])
        if not same or (a["subtype"] != b["subtype"] and a["name"] not in APP_SLOTS):
            raise OtaError(f"Slot swap: partition {b['name']!r} would change beyond the app subtype.")
    names = {e["name"] for e in after}
    missing = sorted(CRITICAL_PARTITIONS - names)
    if missing:
        raise OtaError(f"Slot swap: the partition table lacks {', '.join(missing)}.")
    md5_at = _md5_entry(old, len(before))
    allowed = {i * ENTRY.size + _SUBTYPE_AT for i, e in enumerate(before) if e["name"] in APP_SLOTS}
    if md5_at is not None:
        allowed |= set(range(md5_at + 16, md5_at + 32))
    if any(x != y and i not in allowed for i, (x, y) in enumerate(zip(old, new))):
        raise OtaError("Slot swap: the new partition table differs in bytes other than the app subtypes and the MD5.")
    by_name = {e["name"]: e for e in after}
    if by_name[APP_SLOTS[target]]["subtype"] != OTA_0 or by_name[APP_SLOTS[1 - target]]["subtype"] != OTA_1:
        raise OtaError(f"Slot swap: app_{target} did not become ota_0.")


def check_package(zf: zipfile.ZipFile, manifest: dict) -> None:
    """Raise OtaError unless the package has a partition table to swap and a clean (erased) otadata."""
    parts = manifest["parts"]
    if "src" not in parts.get("pt", {}):
        raise OtaError("--slot-swap needs a package with its partition table ('pt' part); this one has none "
                       "(built with --drop pt?).")
    ota = parts.get("otadata")
    if ota is None:
        raise OtaError("--slot-swap needs a package with a clean otadata; this one has no 'otadata' part.")
    clean = set(zf.read(ota["src"])) == {0xFF} if "src" in ota else ota.get("fill") == 0xFF
    if not clean:
        raise OtaError("--slot-swap needs a package with a clean (erased) otadata, as `build --esphome-factory` makes "
                       "it; this one carries another boot state.")
    addr = parts["pt"].get("addr")
    if addr != RELOCATED_PT_ADDR:
        raise OtaError("--slot-swap needs a package whose partition table is moved to a new address: for the address Shelly's "
                       "table is at, the installer only stores the table in a journal that ESPHome's bootloader does not read "
                       "(log: 'Installing new PT1'), and the old app would start. Build the package with "
                       f"--esphome-factory and --pt-addr 0x{RELOCATED_PT_ADDR:x}, from an ESPHome build that leaves "
                       "CONFIG_PARTITION_TABLE_OFFSET unset (docs/bootloader-and-slots.md#experimental-slot-swap-in-the-package).")
    swap_table(zf.read(parts["pt"]["src"]), 1)   # the table must be one that can be swapped, before the device is asked


def swap_package(zip_path: Path, output: Path, target: int) -> SwapResult:
    """Write `output`: the package with the partition table swapped for `target` (see swap_table); every other file and
    every other manifest value is as it was. If nothing has to change, `output` is not written and `changed` is False."""
    with zipfile.ZipFile(require_zip(zip_path)) as zf:
        manifest = read_official_manifest(zf)
        check_package(zf, manifest)
        pt = manifest["parts"]["pt"]
        old = zf.read(pt["src"])
        new = swap_table(old, target)
        subtypes = {e["name"]: (e["offset"], e["subtype"]) for e in parse_partitions(new) if e["name"] in APP_SLOTS}
        shas = (hashlib.sha256(old).hexdigest(), hashlib.sha256(new).hexdigest())
        if new == old:
            return SwapResult(zip_path, target, False, subtypes, shas)
        pt["cs_sha256"] = shas[1]
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as out:
            for entry in zf.namelist():
                if entry == "manifest.json":
                    data = json.dumps(manifest, separators=(",", ":")).encode()
                elif entry == pt["src"]:
                    data = new
                else:
                    data = zf.read(entry)
                out.writestr(entry, data)
    with zipfile.ZipFile(output) as check:   # read back: every hash fits, and the table is the swapped one
        read_official_manifest(check)
        if check.read(pt["src"]) != new:
            raise OtaError("Slot swap: the written package does not carry the new partition table.")
    return SwapResult(output, target, True, subtypes, shas)


def describe(result: SwapResult) -> str:
    """'app_1 (0x3a0000) is ota_0, app_0 (0x20000) is ota_1'"""
    names = {OTA_0: "ota_0", OTA_1: "ota_1"}
    order = sorted(result.subtypes.items(), key=lambda kv: kv[1][1])
    return ", ".join(f"{name} (0x{addr:x}) is {names.get(sub, hex(sub))}" for name, (addr, sub) in order)
