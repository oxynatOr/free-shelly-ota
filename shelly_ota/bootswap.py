"""Take the ESPHome bootloader (and a clean otadata) out of a firmware.factory.bin for use in a Shelly OTA package.

With Shelly's own bootloader, later ESPHome OTA updates cannot switch slots (Shelly keeps its boot state in a private
otadata format). Shipping ESPHome's bootloader inside the package removes the need for a separate bootloader update.
Everything is checked first, because a bootloader that does not fit the hardware cannot be fixed without UART.
"""

from __future__ import annotations

import hashlib
import zipfile

from .builder import OtaError
from .devicegen import parse_partitions

# Entries ESPHome relies on at run time: a mismatch here is an error. Others (scratch, shelly) only get a warning.
CRITICAL_PARTITIONS = {"otadata", "nvs", "app_0", "app_1", "fs_0", "fs_1"}


def image_length(img: bytes) -> int:
    """Length of an ESP image including the appended SHA-256 digest (if the header says it is there)."""
    if len(img) < 24 or img[0] != 0xE9:
        raise OtaError("Not an ESP image (magic byte 0xE9 missing).")
    pos = 24
    for _ in range(img[1]):
        if pos + 8 > len(img):
            raise OtaError("Truncated image (segment header).")
        pos += 8 + int.from_bytes(img[pos + 4:pos + 8], "little")
    end = (pos + 1 + 15) // 16 * 16  # checksum byte is the last byte of the 16-byte aligned block
    return end + (32 if img[23] == 1 else 0)


def verify_image(img: bytes, what: str) -> bytes:
    """Cut the image to its real length and verify checksum and appended digest; return the image."""
    n = image_length(img)
    if n > len(img):
        raise OtaError(f"{what}: image is truncated.")
    img = img[:n]
    chk, pos = 0xEF, 24
    for _ in range(img[1]):
        size = int.from_bytes(img[pos + 4:pos + 8], "little")
        for x in img[pos + 8:pos + 8 + size]:
            chk ^= x
        pos += 8 + size
    body_end = n - 32 if img[23] == 1 else n
    if img[body_end - 1] != chk:
        raise OtaError(f"{what}: checksum does not match (corrupt image).")
    if img[23] == 1 and hashlib.sha256(img[:body_end]).digest() != img[body_end:]:
        raise OtaError(f"{what}: appended SHA-256 does not match (corrupt image).")
    return img


_FLASH_MODES = {0: "QIO", 1: "QOUT", 2: "DIO", 3: "DOUT"}
_FLASH_SIZES = {0: "1 MB", 1: "2 MB", 2: "4 MB", 3: "8 MB", 4: "16 MB"}
_FLASH_FREQS = {0x0: "40 MHz", 0xF: "80 MHz", 0x1: "26 MHz", 0x2: "20 MHz"}  # ESP32 and ESP32-C3; other chips use other codes
_CHIP_NAMES = {0x0000: "ESP32", 0x0005: "ESP32-C3", 0x000D: "ESP32-C6"}

# What to change in the ESPHome config (esp32: ...) when a header field differs. Only things seen to work are named.
_HEADER_HINTS = {
    "flash mode": (
        "Use the flash mode of the device: `esphome: platformio_options: board_build.flash_mode: dio`, or "
        "`CONFIG_ESPTOOLPY_FLASHMODE_DIO: y` under esp32 > framework > sdkconfig_options."),
    "flash size/frequency": (
        "Use the same flash size and frequency as the device. Size: `esp32: flash_size: ...` (the stock partition table "
        "tells it). Frequency: on the classic ESP32 set `CONFIG_ESPTOOLPY_FLASHFREQ_80M: y` under esp32 > framework > "
        "sdkconfig_options (the PlatformIO option had no effect there); on the ESP32-C6 `esphome: platformio_options: "
        "board_build.f_flash: 80000000L` was enough (Power Strip). Then build again."),
    "chip id": (
        "The ESPHome build is for another chip. Check `variant:` under esp32: (ESP32, ESP32C3 or ESP32C6) and the board."),
    "minimum chip revision": (
        "Remove `minimum_chip_revision` (esp32 > framework > advanced) and `sram1_as_iram` from the config you build the "
        "package from. They are fine for builds you only update with ESPHome OTA (the bootloader on the device stays), "
        "just not for a package that replaces the bootloader."),
}


def _describe(label: str, raw: bytes, platform: str) -> str:
    """A header field as text, e.g. '4 MB, 80 MHz (0x2f)'."""
    value = int.from_bytes(raw, "little")
    if label == "flash mode":
        return f"{_FLASH_MODES.get(value, 'unknown')} (0x{value:02x})"
    if label == "flash size/frequency":
        size = _FLASH_SIZES.get(value >> 4, f"size code {value >> 4}")
        freq = _FLASH_FREQS.get(value & 0xF) if platform in ("esp32", "esp32c3") else None
        return f"{size}, {freq or f'frequency code 0x{value & 0xF:x}'} (0x{value:02x})"
    if label == "chip id":
        return f"{_CHIP_NAMES.get(value, 'unknown chip')} (0x{value:04x})"
    return f"minimum revision byte {value}"


def _header_mismatch_message(label: str, mine: bytes, shelly: bytes, platform: str) -> str:
    return (f"The ESPHome bootloader differs from Shelly's in {label}: your build has {_describe(label, mine, platform)}, "
            f"the device's package has {_describe(label, shelly, platform)}.\n"
            f"  Not replacing the bootloader: one with other settings might not start the device.\n"
            f"  Fix: {_HEADER_HINTS[label]}")


def _entry_key(e: dict) -> tuple:
    return (e["name"], e["type"], e["subtype"], e["offset"], e["size"])


def prepare(factory: bytes, official: zipfile.ZipFile, manifest: dict, app: bytes) -> tuple[dict, list[str]]:
    """Return ({zip file name: new bytes}, warnings) for the boot and otadata parts, or raise OtaError."""
    parts = manifest["parts"]
    for key in ("boot", "pt", "otadata"):
        if key not in parts or "src" not in parts[key]:
            raise OtaError(f"The official package has no '{key}' part to compare with.")
    warnings: list[str] = []

    shelly_boot = official.read(parts["boot"]["src"])
    shelly_pt = official.read(parts["pt"]["src"])
    pt_offset = parts["pt"].get("addr", 0x10000)
    boot_addr = parts["boot"].get("addr", 0)  # 0 on ESP32-C3/C6, 0x1000 on the classic ESP32
    if len(factory) < pt_offset + 4096:
        raise OtaError("The factory image is too small (it must contain the bootloader and the partition table).")

    boot = verify_image(factory[boot_addr:pt_offset], "Bootloader in the factory image")
    if boot_addr + len(boot) > pt_offset:
        raise OtaError("Bootloader does not fit in front of the partition table.")

    # The fields a wrong bootloader would get wrong first: flash mode, size/frequency, chip, minimum revision.
    for label, sl in (("flash mode", slice(2, 3)), ("flash size/frequency", slice(3, 4)),
                      ("chip id", slice(12, 14)), ("minimum chip revision", slice(14, 15))):
        if boot[sl] != shelly_boot[sl]:
            raise OtaError(_header_mismatch_message(label, boot[sl], shelly_boot[sl], str(manifest.get("platform", ""))))

    shelly_entries = parse_partitions(shelly_pt)
    esphome_entries = parse_partitions(factory[pt_offset:pt_offset + 4096])
    shelly_by_name = {e["name"]: e for e in shelly_entries}
    esphome_by_name = {e["name"]: e for e in esphome_entries}
    for name, se in shelly_by_name.items():
        ee = esphome_by_name.get(name)
        if ee is None or _entry_key(ee) != _entry_key(se):
            msg = (f"partition '{name}' differs: Shelly {_entry_key(se)[2:]} vs ESPHome "
                   f"{_entry_key(ee)[2:] if ee else 'missing'}")
            if name in CRITICAL_PARTITIONS:
                name = manifest.get("name", "<Device>")
                raise OtaError(f"The ESPHome build uses another partition layout than the device: {msg}.\n"
                               f"  Fix: build with Shelly's table: `esp32: partitions: {name}-stock.csv` (the file is in "
                               f"partitions/, or `python ota.py partition-csv {name}` writes it) and set "
                               f"CONFIG_PARTITION_TABLE_OFFSET as the CSV header says.")
            warnings.append(f"{msg}. Harmless here because Shelly's partition table is kept, but fix your "
                            f"partitions CSV.")

    otadata = shelly_by_name.get("otadata")
    ota_part = parts["otadata"]
    if otadata is None:
        raise OtaError("No otadata partition in Shelly's partition table.")
    region = factory[otadata["offset"]:otadata["offset"] + otadata["size"]]
    if len(region) != otadata["size"] or set(region) != {0xFF}:
        raise OtaError("The otadata area of the factory image is not erased (0xFF). Expected ESPHome's initial state.")

    app0 = shelly_by_name.get(parts["app"].get("ptn", "app_0"))
    if app0 is None or factory[app0["offset"]:app0["offset"] + len(app)] != app:
        raise OtaError("The factory image does not contain the app image you are packing (not the same build). "
                       "The bootloader must come from the same build as the app.\n"
                       "  Fix: take firmware.ota.bin and firmware.factory.bin from one and the same build "
                       "(rebuild once and copy both files).")

    return {
        parts["boot"]["src"]: boot,
        ota_part["src"]: b"\xff" * ota_part["size"],
    }, warnings
