"""Flash layout of a Shelly Gen1 (ESP8266, rBoot) as the gen1_ota component needs it, read from a partition CSV.

The CSV is in the format of the stock partition tables of the Gen2+ profiles (ESP-IDF style: name, type, subtype, offset,
size, flags), so one kind of file describes every Shelly:

    # Name,      Type, SubType, Offset,   Size,    Flags
    rboot,       boot, rboot,   0x0,      0x1000,
    rboot_cfg,   data, rboot,   0x1000,   0x1000,
    app_0,       app,  ota_0,   0x8000,   0xB3000,
    fs_0,        data, spiffs,  0xBB000,  0x40000,
    app_1,       app,  ota_1,   0x108000, 0xB3000,
    fs_1,        data, spiffs,  0x1BB000, 0x40000,

What the component uses: `rboot_cfg` (the rBoot config sector), `app_0` (the slot ESPHome runs from and is installed into),
`app_1` (the other slot, the stock firmware, never touched) and `fs_0` (the file system of slot 0, whose free end holds the
staging area). A row `stage` can set the staging area by hand. Everything else is derived (`Layout` below): the largest image,
the linker script origin, where ESPHome keeps its preferences / EEPROM / RF calibration.

`partitions_from_manifest` writes such a CSV from the manifest.json of an official Gen1 package, so a new model needs no
hand-written numbers.

Pure Python, no ESPHome import: used by the component (build time) and by tools/gen1_ota.py.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

SEC = 4096
IROM_BASE = 0x40200000  # the 1 MB window of the flash that the cache maps
WINDOW = 0x100000
IMAGE_LIMIT = 0x68000  # largest image when the staging area lies inside slot 0 (Shelly 1 style)
PREFS_LIMIT = 0xFA000  # ESPHome preferences must stay below this in the first MB when the stage is free flash


class LayoutError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    name: str
    type: str
    subtype: str
    offset: int
    size: int

    @property
    def end(self) -> int:
        return self.offset + self.size


@dataclass(frozen=True)
class Layout:
    cfg: int
    slot0: int
    slot0_size: int
    slot1: int
    slot1_size: int
    stage: int
    stage_size: int

    # --- derived -------------------------------------------------------------------------------------------------
    @property
    def stage_end(self) -> int:
        return self.stage + self.stage_size

    @property
    def max_image(self) -> int:
        """Largest image the component accepts: the new image must not run into the staging area when that lies in slot 0."""
        if self.slot0 <= self.stage < self.slot0 + self.slot0_size:
            return self.stage - self.slot0
        return min(self.stage_size, self.slot0_size)

    @property
    def irom_org(self) -> int:
        """Where the sketch has to be linked: the slot's offset inside its 1 MB window, after the 0x10 byte rBoot header."""
        return IROM_BASE + (self.slot0 % WINDOW) + 0x10

    @property
    def irom_len(self) -> int:
        return self.slot0_size - 0x10

    @property
    def cache_bank(self) -> int:
        """Which 1 MB window of the flash the slot is in. 0 is the one the Arduino SDK maps by default; other values need the SDK
        cache mapping (SDK byte, see tools/gen1_ota.py convert --partitions). Not solved yet: see README."""
        return self.slot0 // WINDOW

    @property
    def prefs_end(self) -> int:
        """ESPHome keeps its preferences below this offset (the linker symbol _SPIFFS_end), directly under the EEPROM sector."""
        return self.stage_end

    @property
    def eeprom(self) -> int:
        return self.prefs_end + SEC

    @property
    def rfcal_sector(self) -> int:
        """Sector for the SDK RF calibration (the SDK would use flash size - 0x4000, which is the stock RF init data)."""
        return (self.eeprom + SEC) // SEC

    def validate(self) -> "Layout":
        for name in ("cfg", "slot0", "slot1", "stage"):
            v = getattr(self, name)
            if v % SEC:
                raise LayoutError(f"{name} 0x{v:X} is not sector aligned")
        if self.slot0_size % SEC or self.slot1_size % SEC or self.stage_size % SEC:
            raise LayoutError("sizes must be multiples of 4096")
        if self.slot0_size != self.slot1_size:
            raise LayoutError("app_0 and app_1 must have the same size (the stock updater swaps them)")
        regions = [("rboot_cfg", self.cfg, SEC), ("app_0", self.slot0, self.slot0_size), ("app_1", self.slot1, self.slot1_size)]
        for i, (an, a, asz) in enumerate(regions):
            for bn, b, bsz in regions[i + 1:]:
                if a < b + bsz and b < a + asz:
                    raise LayoutError(f"{an} and {bn} overlap")
        for name, a, asz in regions[:1] + regions[2:]:
            if self.stage < a + asz and a < self.stage_end:
                raise LayoutError(f"stage overlaps {name}")
        if self.max_image < 0x10000:
            raise LayoutError(f"max image 0x{self.max_image:X} is too small")
        if self.rfcal_sector * SEC >= WINDOW:
            raise LayoutError("RF calibration sector 0x%X is outside the first MB" % self.rfcal_sector)
        return self


def _num(s: str) -> int:
    s = s.strip()
    mult = 1
    if s[-1:] in ("K", "k"):
        mult, s = 1024, s[:-1]
    elif s[-1:] in ("M", "m"):
        mult, s = 1024 * 1024, s[:-1]
    return int(s, 0) * mult


def parse_partitions(text: str) -> list[Entry]:
    entries = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        p = [x.strip() for x in line.split(",")]
        if len(p) < 5:
            raise LayoutError(f"line {n}: expected Name, Type, SubType, Offset, Size")
        try:
            entries.append(Entry(p[0], p[1], p[2], _num(p[3]), _num(p[4])))
        except ValueError:
            raise LayoutError(f"line {n}: offset/size are not numbers") from None
    return entries


def from_partitions(entries: list[Entry]) -> Layout:
    by = {e.name: e for e in entries}
    missing = [k for k in ("rboot_cfg", "app_0", "app_1") if k not in by]
    if missing:
        raise LayoutError("missing rows: " + ", ".join(missing))
    cfg, a0, a1 = by["rboot_cfg"], by["app_0"], by["app_1"]
    if "stage" in by:
        st = by["stage"]
        stage, stage_size = st.offset, st.size
    else:
        fs0 = by.get("fs_0")
        if fs0 is not None and fs0.offset == a0.end:  # Shelly 1 style: the unused end of slot 0's file system
            stage, stage_end = a0.offset + IMAGE_LIMIT, fs0.end - SEC
        else:  # free flash below slot 0
            low = [e.end for e in entries if e.end <= a0.offset] + [cfg.end]
            stage = (max(low) + SEC - 1) // SEC * SEC
            stage_end = min(a0.offset, PREFS_LIMIT)
        stage_size = stage_end - stage
        if stage_size <= 0:
            raise LayoutError("no room for a staging area")
    return Layout(cfg.offset, a0.offset, a0.size, a1.offset, a1.size, stage, stage_size).validate()


def parse_csv(text: str) -> Layout:
    return from_partitions(parse_partitions(text))


def partitions_from_manifest(manifest: dict, name: str = "") -> str:
    """Partition CSV text for the layout in an official Gen1 manifest.json."""
    if manifest.get("platform") != "esp8266":
        raise LayoutError(f"platform is {manifest.get('platform')!r}, not esp8266: not an rBoot Gen1 package")
    parts = manifest["parts"]
    try:
        cfg = parts["boot_cfg"]["addr"]
        slot0, slot1 = parts["fw"]["addr"], parts["fw"]["addr1"]
    except KeyError as e:
        raise LayoutError(f"manifest has no {e.args[0]}") from None
    starts = sorted({v[k] for v in parts.values() for k in ("addr", "addr1") if k in v})

    def size_of(start: int) -> int:
        later = [a for a in starts if a > start]
        return (min(later) if later else start + WINDOW) - start

    app_size = min(size_of(slot0), size_of(slot1))
    rows = [("rboot", "boot", "rboot", 0, SEC), ("rboot_cfg", "data", "rboot", cfg, SEC),
            ("app_0", "app", "ota_0", slot0, app_size), ("app_1", "app", "ota_1", slot1, app_size)]
    fs = parts.get("fs")
    if fs:
        rows.append(("fs_0", "data", "spiffs", fs["addr"], fs["size"]))
        if "addr1" in fs:
            rows.append(("fs_1", "data", "spiffs", fs["addr1"], fs["size"]))
    if "rf_cal_data" in parts:
        rows.append(("rf_cal", "data", "phy", parts["rf_cal_data"]["addr"], SEC))
    if "sys_params" in parts:
        rows.append(("sys_params", "data", "nvs", parts["sys_params"]["addr"], SEC))
    rows.sort(key=lambda r: r[3])
    lines = [f"# Gen1 stock partition layout{' of ' + name if name else ''}, read from the manifest.json of the official package.",
             "# Only used so the gen1_ota component knows where the slots are; the flash itself keeps Shelly's layout.",
             "# Name,        Type, SubType, Offset,    Size,     Flags"]
    for n, t, s, o, z in rows:
        lines.append(f"{n}, {t}, {s}, 0x{o:X}, 0x{z:X},")
    return "\n".join(lines) + "\n"


LD_TEMPLATE = """\
/* Generated by gen1_ota from the partition CSV (app_0 at flash 0x{slot0:X}, window offset 0x{off:X}). Do not edit. */
MEMORY
{{
  dport0_0_seg :                        org = 0x3FF00000, len = 0x10
  dram0_0_seg :                         org = 0x3FFE8000, len = 0x14000
  irom0_0_seg :                         org = 0x{org:X}, len = 0x{ln:X}
}}

PROVIDE ( _FS_start = 0x403FB000 );
PROVIDE ( _FS_end = 0x403FB000 );
PROVIDE ( _FS_page = 0x0 );
PROVIDE ( _FS_block = 0x0 );
PROVIDE ( _EEPROM_start = 0x{eeprom:X} );
PROVIDE ( _SPIFFS_start = 0x403FB000 );
PROVIDE ( _SPIFFS_end = 0x{prefs:X} );
PROVIDE ( _SPIFFS_page = 0x0 );
PROVIDE ( _SPIFFS_block = 0x0 );

INCLUDE "local.eagle.app.v6.common.ld"
"""


def render_ld(lay: Layout) -> str:
    return LD_TEMPLATE.format(slot0=lay.slot0, off=lay.slot0 % WINDOW, org=lay.irom_org, ln=lay.irom_len,
                              eeprom=IROM_BASE + lay.eeprom, prefs=IROM_BASE + lay.prefs_end)


def defines(lay: Layout) -> dict[str, str]:
    """C++ defines for gen1_ota.cpp."""
    return {"GEN1_CFG": f"0x{lay.cfg:X}u", "GEN1_SLOT0": f"0x{lay.slot0:X}u", "GEN1_SLOT1": f"0x{lay.slot1:X}u",
            "GEN1_STAGE": f"0x{lay.stage:X}u", "GEN1_STAGE_END": f"0x{lay.stage_end:X}u",
            "GEN1_MAX_IMAGE": f"0x{lay.max_image:X}u", "GEN1_RFCAL_SECTOR": f"0x{lay.rfcal_sector:X}u"}


def manifest_file_to_csv(path: str, name: str = "") -> str:
    with open(path, encoding="utf-8") as f:
        return partitions_from_manifest(json.load(f), name)
