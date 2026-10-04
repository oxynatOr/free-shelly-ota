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
    if len(factory) < pt_offset + 4096:
        raise OtaError("The factory image is too small (it must contain the bootloader and the partition table).")

    boot = verify_image(factory[:pt_offset], "Bootloader in the factory image")
    if len(boot) > pt_offset:
        raise OtaError("Bootloader does not fit in front of the partition table.")

    # The fields a wrong bootloader would get wrong first: flash mode, size/frequency, chip, minimum revision.
    for label, sl in (("flash mode", slice(2, 3)), ("flash size/frequency", slice(3, 4)),
                      ("chip id", slice(12, 14)), ("minimum chip revision", slice(14, 15))):
        if boot[sl] != shelly_boot[sl]:
            raise OtaError(f"The ESPHome bootloader differs from Shelly's in {label} "
                           f"({boot[sl].hex()} vs {shelly_boot[sl].hex()}). Not replacing the bootloader: "
                           f"the device might not start.")

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
                raise OtaError(f"The ESPHome build uses another partition layout than the device: {msg}.")
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
                       "The bootloader must come from the same build as the app.")

    return {
        parts["boot"]["src"]: boot,
        ota_part["src"]: b"\xff" * ota_part["size"],
    }, warnings
