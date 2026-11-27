"""Optional sanity check of an ESPHome YAML before building an OTA ZIP.

Checks what cannot be seen in the app binary: the partition table offset and the partition table.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from . import MODULE_DIR
from .builder import RELOCATED_PT_ADDR
from .profile import Profile


class _Loader(yaml.SafeLoader):
    pass


# ESPHome YAML uses custom tags (!secret, !include, ...); we only need the plain structure.
_Loader.add_multi_constructor("!", lambda loader, suffix, node: None)


def _parse_size(text: str) -> int | None:
    """A size or offset of a partition CSV: decimal, 0x..., or with the ESP-IDF suffixes K and M. None: not a number."""
    text = text.strip()
    factor = {"K": 1024, "M": 1024 * 1024}.get(text[-1:].upper(), 1)
    try:
        return int(text[:-1] if factor > 1 else text, 0) * factor
    except ValueError:
        return None


def csv_rows(text: str) -> dict:
    """{partition name: (offset or None, size)} of an ESP-IDF partition CSV."""
    rows = {}
    for line in text.splitlines():
        cols = [c.strip() for c in line.split(",")]
        if not line.lstrip().startswith("#") and len(cols) >= 5:
            rows[cols[0]] = (_parse_size(cols[3]), _parse_size(cols[4]))
    return rows


def table_differences(mine: str, shipped: str) -> list[str]:
    """Partitions that both tables name but place or size differently (an empty offset is not compared)."""
    theirs = csv_rows(shipped)
    return [name for name, (offset, size) in csv_rows(mine).items()
            if name in theirs and (size != theirs[name][1] or (offset is not None and offset != theirs[name][0]))]


def shipped_table(profile: Profile) -> str | None:
    """The stock CSV that ships with the tool for this profile and layout, or None."""
    path = MODULE_DIR / "partitions" / profile.csv_name
    return path.read_text(encoding="utf-8") if path.is_file() else None


def load_config(text: str) -> dict:
    """The plain structure of an ESPHome YAML (tags like !secret and !lambda are ignored)."""
    cfg = yaml.load(text, Loader=_Loader)
    return cfg if isinstance(cfg, dict) else {}


def load_file(yaml_path: Path) -> dict:
    return load_config(yaml_path.read_text(encoding="utf-8"))


def has_esp32_block(cfg: dict) -> bool:
    return isinstance(cfg.get("esp32"), dict)


def lint_esphome(yaml_path: Path, profile: Profile, cfg: dict | None = None, relocated: bool = False) -> list[str]:
    """Return a list of problems (empty = looks fine).

    relocated: the package moves the partition table (build --pt-addr), so the bootloader has to read it from
    RELOCATED_PT_ADDR (ESP-IDF's default: the offset option must be left unset or be that value).

    cfg: the config as ESPHome resolved it (`compile.resolve_config`), for a YAML that gets its `esp32:` block from
    `packages:` or `!include`. Without it the file itself is read, and those are not followed.
    """
    if cfg is None:
        cfg = load_file(yaml_path)
    esp32 = cfg.get("esp32")
    if not isinstance(esp32, dict):
        hint = (" The file uses `packages:`, which this check does not follow: put the esp32: block in the file, "
                "or use build --compile, which asks ESPHome for the full config.") if "packages" in cfg else ""
        return ["No 'esp32:' block found (is this an ESP32 ESPHome config?)." + hint]
    problems = []

    framework = esp32.get("framework") or {}
    if framework.get("type") != "esp-idf":
        problems.append("esp32.framework.type should be 'esp-idf'.")
    value = (framework.get("sdkconfig_options") or {}).get("CONFIG_PARTITION_TABLE_OFFSET")
    # Not set means ESP-IDF's default 0x8000, which is right for devices that keep their table there (classic ESP32).
    offset = int(str(value), 0) if value is not None and str(value).strip() else 0x8000
    expected = RELOCATED_PT_ADDR if relocated else profile.pt_offset
    if offset != expected:  # Gen3/Gen4 keep their table elsewhere (0x10000, H&T 0xf000)
        if relocated:
            problems.append("esp32.framework.sdkconfig_options.CONFIG_PARTITION_TABLE_OFFSET must be left out (or "
                            f"\"0x{expected:x}\") with --pt-addr, because the table is moved there (found: {value!r}).")
        else:
            problems.append("esp32.framework.sdkconfig_options.CONFIG_PARTITION_TABLE_OFFSET must be "
                            f"\"0x{expected:x}\" (found: {value!r}). "
                            "Without it the app looks for its partitions at 0x8000.")

    partitions = esp32.get("partitions")
    if not partitions:
        problems.append("esp32.partitions is not set: the app needs Shelly's stock partition table.")
    elif isinstance(partitions, str) and (yaml_path.parent / partitions).is_file():
        for line in (yaml_path.parent / partitions).read_text(encoding="utf-8").splitlines():
            cols = [c.strip() for c in line.split(",")]
            if len(cols) >= 5 and cols[0] == profile.app_ptn:
                size = _parse_size(cols[4])
                if size != profile.app_slot_size:
                    problems.append(f"{partitions}: {profile.app_ptn} size is {cols[4]}, "
                                    f"expected 0x{profile.app_slot_size:x} for {profile.name}.")
                break
        else:
            problems.append(f"{partitions}: no {profile.app_ptn} row found.")
    return problems


def lint_warnings(yaml_path: Path, *, bootloader_shipped: bool = False, cfg: dict | None = None,
                  profile: Profile | None = None) -> list[str]:
    """Things that do not block the build but matter after the first boot.

    bootloader_shipped: the package carries ESPHome's bootloader (--esphome-factory). allow_partition_access is still
    wanted then: without it ESPHome cannot update that bootloader later.
    """
    if cfg is None:
        cfg = load_file(yaml_path)
    warnings = []
    esp32 = cfg.get("esp32")
    table = esp32.get("partitions") if isinstance(esp32, dict) else None
    shipped = shipped_table(profile) if profile else None
    if shipped and isinstance(table, str) and (yaml_path.parent / table).is_file():
        differ = table_differences((yaml_path.parent / table).read_text(encoding="utf-8"), shipped)
        if differ:      # the app slot size is an error of lint_esphome; the rest does not stop a build
            warnings.append(f"{table} differs from partitions/{profile.csv_name} in: {', '.join(differ)}. The device keeps "
                            "Shelly's table; use the shipped CSV so that your build sees the same one.")
    ota = cfg.get("ota")
    entries = ota if isinstance(ota, list) else [ota] if isinstance(ota, dict) else []
    esphome_ota = [e for e in entries if isinstance(e, dict) and e.get("platform") == "esphome"]
    if not any(e.get("allow_partition_access") is True for e in esphome_ota):
        if bootloader_shipped:
            return warnings + ["ota: no 'platform: esphome' entry with 'allow_partition_access: true'. The package carries ESPHome's "
                    "bootloader, but without this entry ESPHome cannot update it later (Builder's 'Update bootloader'). "
                    "Add it to the config (see the device page)."]
        return warnings + ["ota: no 'platform: esphome' entry with 'allow_partition_access: true'. Without it ESPHome cannot "
                "update the bootloader or the partition table later (Builder's 'Update bootloader'); normal app updates "
                "are not affected (see docs/bootloader-and-slots.md)."]
    return warnings
