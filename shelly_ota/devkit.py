"""A flash image for a dev board, made from a package.

The official package holds the parts of a device's flash (bootloader, partition table, boot state, app, filesystem) and its
manifest says where each goes. Put at those offsets into one image, they bring Shelly's loader and firmware onto a dev board of
the same chip family, so the whole update (`send`, the installer, the bootloader swap) can be tried on a board instead of on a device.
A package built by `build` works the same way and gives the state after an install.

The image holds no data of a particular device: the `shelly` and `aux` partitions stay blank, NVS is empty.
"""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .builder import OtaError, read_official_manifest, require_zip
from .devicegen import parse_partitions
from .profile import Profile

MIB = 1 << 20
SECTOR = 0x1000
FLASH_SIZES = {"4MB": 4, "8MB": 8, "16MB": 16}   # --flash-size -> MiB
STANDARD_MIB = (4, 8, 16, 32)


@dataclass
class Placed:
    """One piece of the image."""
    key: str        # part name in the manifest
    offset: int
    size: int       # bytes in the image
    what: str       # file name in the package, or "empty (0xFF)"


@dataclass
class DevkitImage:
    data: bytes
    chip: str       # esptool's name: esp32, esp32c3, esp32c6
    name: str
    version: str
    parts: list[Placed]
    table_end: int  # where the partition table ends: the flash the firmware expects

    @property
    def needed_mib(self) -> int:
        """Smallest standard flash size that holds the whole partition table."""
        return next((m for m in STANDARD_MIB if self.table_end <= m * MIB), -(-self.table_end // MIB))

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def build_image(zip_path: Path, profile: Profile, *, flash_size: str | None = None) -> DevkitImage:
    """The image for the package at zip_path. flash_size ('4MB', '8MB', '16MB') makes it stop if the layout needs more."""
    if flash_size is not None and flash_size not in FLASH_SIZES:
        raise OtaError(f"--flash-size must be one of {', '.join(FLASH_SIZES)}.")
    with zipfile.ZipFile(require_zip(zip_path)) as zf:
        manifest = read_official_manifest(zf, profile.package_name)
        parts = manifest["parts"]
        if "pt" not in parts or "boot" not in parts:
            raise OtaError(f"{zip_path.name} has no boot or pt part: not a package for a whole device.")
        entries = {e["name"]: e for e in parse_partitions(zf.read(parts["pt"]["src"]))}
        if not entries:
            raise OtaError(f"{zip_path.name}: the partition table of the package is empty or unreadable.")

        placed: list[tuple[Placed, bytes]] = []
        for key, part in parts.items():
            ptn = part.get("ptn")
            if "addr" in part:
                offset = int(part["addr"])
            elif ptn in entries:
                offset = entries[ptn]["offset"]
            else:
                raise OtaError(f"Part {key!r}: no address and no partition {ptn!r} in the package's partition table.")
            if "src" in part:
                data, what = zf.read(part["src"]), part["src"]
            else:  # nvs: only a fill value; the image gets the whole partition erased
                size = entries[ptn]["size"] if ptn in entries else part.get("size")
                if not size:
                    raise OtaError(f"Part {key!r}: no size to fill.")
                data, what = bytes([part.get("fill", 0xFF) & 0xFF]) * int(size), "empty (0x%02X)" % (part.get("fill", 0xFF) & 0xFF)
            if ptn in entries and len(data) > entries[ptn]["size"]:
                raise OtaError(f"Part {key!r} ({len(data)} bytes) does not fit its partition {ptn!r} "
                               f"({entries[ptn]['size']} bytes).")
            placed.append((Placed(key, offset, len(data), what), data))

    placed.sort(key=lambda item: item[0].offset)
    for (a, _), (b, _) in zip(placed, placed[1:]):
        if a.offset + a.size > b.offset:
            raise OtaError(f"Parts {a.key!r} and {b.key!r} overlap (0x{a.offset:x}+0x{a.size:x} reaches 0x{b.offset:x}).")

    table_end = max(e["offset"] + e["size"] for e in entries.values())
    image = DevkitImage(b"", manifest.get("platform", ""), manifest["name"], str(manifest["version"]),
                        [p for p, _ in placed], table_end)
    if flash_size and table_end > FLASH_SIZES[flash_size] * MIB:
        raise OtaError(f"{profile.name} needs a board with {image.needed_mib} MiB flash (its partition table ends at "
                       f"0x{table_end:x}); --flash-size says {flash_size}.")

    end = max(p.offset + p.size for p, _ in placed)
    buf = bytearray(b"\xff" * (-(-end // SECTOR) * SECTOR))
    for p, data in placed:
        buf[p.offset:p.offset + len(data)] = data
    image.data = bytes(buf)
    return image


def esptool_lines(image: DevkitImage, path: Path, port: str = "COMx") -> list[str]:
    """The commands that put the image on a board (the tool does not run them)."""
    py = "python -m esptool"
    return [f"{py} --chip {image.chip} --port {port} erase-flash",
            f"{py} --chip {image.chip} --port {port} --baud 460800 write-flash --flash-mode keep --flash-size keep "
            f"--flash-freq keep 0x0 {path}"]


def summary(image: DevkitImage, path: Path, source: Path, port: str = "COMx") -> str:
    """What the command prints."""
    lines = [f"Devkit image for {image.name} {image.version} ({image.chip}), from {source}",
             "  part     offset       size  what"]
    for p in image.parts:
        lines.append(f"  {p.key:8s} 0x{p.offset:06x} {p.size:>10}  {p.what}")
    lines += [f"Image: {path} ({len(image.data)} bytes, 0x{len(image.data):x}), sha256 {image.sha256}",
              f"The board needs at least {image.needed_mib} MiB flash and the chip {image.chip} "
              f"(the partition table ends at 0x{image.table_end:x}). Check with: python -m esptool --port {port} flash-id",
              "", f"Write it (replace {port}; the first command erases the whole flash of the board):"]
    lines += [f"  {line}" for line in esptool_lines(image, path, port)]
    lines += ["", "Then open a serial monitor at 115200 Bd: the loader prints its version and 'Booting app 0'.",
              "WARNING: this overwrites the whole flash of a board, bootloader and firmware included: use it on a dev board of your own, "
              "never on a device in a wall or a socket.",
              "WARNING: the image holds Shelly's firmware (or your build, with the Wi-Fi data of its config): do not share or upload it.",
              f"NOTE: when it installs an unsigned package (log: 'FW signatures: want 07 got 00') Shelly's updater burns eFuse BLOCK3 ('BURN BLOCK3'); that cannot be undone on that chip. "
              f"Read python -m espefuse --chip {image.chip} --port {port} summary before and after.",
              "NOTE: the partitions 'shelly' and 'aux' (identity and calibration of a device) stay blank. Whether the Shelly app "
              "runs without them on a board is not known (docs/devkit.md)."]
    return "\n".join(lines)
