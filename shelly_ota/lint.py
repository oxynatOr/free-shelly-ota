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


def load_config(text: str) -> dict:
    """The plain structure of an ESPHome YAML (tags like !secret and !lambda are ignored)."""
    cfg = yaml.load(text, Loader=_Loader)
    return cfg if isinstance(cfg, dict) else {}


def load_file(yaml_path: Path) -> dict:
    return load_config(yaml_path.read_text(encoding="utf-8"))


def has_esp32_block(cfg: dict) -> bool:
    return isinstance(cfg.get("esp32"), dict)


def lint_esphome(yaml_path: Path, profile: Profile, cfg: dict | None = None) -> list[str]:
    """Return a list of problems (empty = looks fine).

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
    if offset != profile.pt_offset:  # Gen3/Gen4 keep their table elsewhere (0x10000, H&T 0xf000)
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


def lint_warnings(yaml_path: Path, *, bootloader_shipped: bool = False, cfg: dict | None = None) -> list[str]:
    """Things that do not block the build but matter after the first boot.

    bootloader_shipped: the package carries ESPHome's bootloader (--esphome-factory). allow_partition_access is still
    wanted then: without it ESPHome cannot update that bootloader later.
    """
    if cfg is None:
        cfg = load_file(yaml_path)
    ota = cfg.get("ota")
    entries = ota if isinstance(ota, list) else [ota] if isinstance(ota, dict) else []
    esphome_ota = [e for e in entries if isinstance(e, dict) and e.get("platform") == "esphome"]
    if not any(e.get("allow_partition_access") is True for e in esphome_ota):
        if bootloader_shipped:
            return ["ota: no 'platform: esphome' entry with 'allow_partition_access: true'. The package carries ESPHome's "
                    "bootloader, but without this entry ESPHome cannot update it later (Builder's 'Update bootloader'). "
                    "Add it to the config (see the device page)."]
        return ["ota: no 'platform: esphome' entry with 'allow_partition_access: true'. Without it ESPHome cannot "
                "update the bootloader or the partition table later (Builder's 'Update bootloader'); normal app updates "
                "are not affected (see docs/bootloader-and-slots.md)."]
    return []
