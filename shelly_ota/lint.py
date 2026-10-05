"""Optional sanity check of an ESPHome YAML before building an OTA ZIP.

Checks what cannot be seen in the app binary: the partition table offset and the partition table.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .profile import Profile


class _Loader(yaml.SafeLoader):
    pass


# ESPHome YAML uses custom tags (!secret, !include, ...); we only need the plain structure.
_Loader.add_multi_constructor("!", lambda loader, suffix, node: None)


def _parse_size(text: str) -> int | None:
    try:
        return int(text.strip(), 0)
    except ValueError:
        return None


def lint_esphome(yaml_path: Path, profile: Profile) -> list[str]:
    """Return a list of problems (empty = looks fine)."""
    cfg = yaml.load(yaml_path.read_text(encoding="utf-8"), Loader=_Loader) or {}
    esp32 = cfg.get("esp32")
    if not isinstance(esp32, dict):
        return ["No 'esp32:' block found (is this an ESP32 ESPHome config?)."]
    problems = []

    framework = esp32.get("framework") or {}
    if framework.get("type") != "esp-idf":
        problems.append("esp32.framework.type should be 'esp-idf'.")
    value = (framework.get("sdkconfig_options") or {}).get("CONFIG_PARTITION_TABLE_OFFSET")
    offset = int(str(value), 0) if value is not None and str(value).strip() else None
    if offset != profile.pt_offset:  # ESP-IDF's default is 0x8000, Shelly keeps its table elsewhere
        problems.append("esp32.framework.sdkconfig_options.CONFIG_PARTITION_TABLE_OFFSET must be "
                        f"\"0x{profile.pt_offset:x}\" (found: {value!r}). "
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


def lint_warnings(yaml_path: Path, *, bootloader_shipped: bool = False) -> list[str]:
    """Things that do not block the build but matter after the first boot.

    bootloader_shipped: the package already carries ESPHome's bootloader (--esphome-factory), so no later bootloader
    update is needed and the missing allow_partition_access is not a problem.
    """
    if bootloader_shipped:
        return []
    cfg = yaml.load(yaml_path.read_text(encoding="utf-8"), Loader=_Loader) or {}
    ota = cfg.get("ota")
    entries = ota if isinstance(ota, list) else [ota] if isinstance(ota, dict) else []
    esphome_ota = [e for e in entries if isinstance(e, dict) and e.get("platform") == "esphome"]
    if not any(e.get("allow_partition_access") is True for e in esphome_ota):
        return ["ota: no 'platform: esphome' entry with 'allow_partition_access: true'. Without it ESPHome cannot "
                "update the bootloader later, and a later ESPHome OTA may fall back to the previous image "
                "(see README, 'After the first boot')."]
    return []
