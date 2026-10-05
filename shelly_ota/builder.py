"""Build a Shelly Gen3 OTA ZIP around an ESPHome app image.

Only the "app" part is replaced (size + cs_sha256 + file content). All other
parts are taken 1:1 from the official ZIP unless explicitly dropped.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__, secrets_check
from .profile import Profile

DROPPABLE_PARTS = ("boot", "pt", "otadata", "nvs", "fs")
CHIP_IDS = {"esp32c3": 0x0005, "esp32c6": 0x000D}  # esp_chip_id_t in the ESP image header


APP_DESC_MAGIC = bytes.fromhex("3254cdab")  # esp_app_desc_t.magic_word 0xABCD5432, little endian


class OtaError(Exception):
    pass


@dataclass
class BuildResult:
    output: Path
    sha256: str
    app_size: int
    app_sha256: str
    parts: list[str]
    dropped: list[str]
    official_version: str
    official_build_id: str | None
    tag: str | None = None
    warnings: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)  # parts taken from an ESPHome factory image (boot, otadata)
    secrets_found: list[str] | None = None  # names of credentials found in the image; None = not checked


def check_app_image(app: bytes, platform: str, slot_size: int, slot_name: str) -> list[str]:
    """Validate an ESP app image; raise OtaError on hard failures, return warnings."""
    warnings: list[str] = []
    if len(app) < 24 or app[0] != 0xE9:
        raise OtaError("Not an ESP app image (must start with magic byte 0xE9). Did you pass the merged "
                       "factory image instead of the plain OTA/app binary?")
    # A bootloader (so also a merged factory image) starts with 0xE9 as well; only an app image carries
    # the ESP-IDF app descriptor (magic 0xABCD5432, little endian) right after the first segment header.
    if app[32:36] != APP_DESC_MAGIC:
        raise OtaError("This is not a plain app image (no app descriptor at offset 32). It looks like a merged/"
                       "factory image or a bootloader. Use the OTA binary, e.g. firmware.ota.bin or "
                       ".pioenvs/<name>/firmware.bin, not firmware.factory.bin.")
    if len(app) > slot_size:
        raise OtaError(f"App image is {len(app)} bytes, slot {slot_name} only holds {slot_size} "
                       f"({slot_size / 1024:.0f} KB).")
    expected = CHIP_IDS.get(platform)
    chip_id = int.from_bytes(app[12:14], "little")
    if expected is not None and chip_id != expected:
        raise OtaError(f"Image chip id is 0x{chip_id:04x}, expected 0x{expected:04x} for {platform}.")
    segments = app[1]
    if not 1 <= segments <= 16:
        raise OtaError(f"Implausible segment count in image header: {segments}.")
    return warnings


def read_official_manifest(zf: zipfile.ZipFile, expected_name: str | None = None) -> dict:
    """Load manifest.json from an official ZIP and verify every part against its cs_sha256/size."""
    names = zf.namelist()
    if "manifest.json" not in names:
        raise OtaError("ZIP has no manifest.json.")
    manifest = json.loads(zf.read("manifest.json"))
    if expected_name is not None and manifest.get("name") != expected_name:
        raise OtaError(f"Package is for {manifest.get('name')!r}, expected {expected_name!r}.")
    for key in ("name", "version", "parts"):
        if key not in manifest:
            raise OtaError(f"Manifest lacks '{key}'.")
    for key, part in manifest["parts"].items():
        src = part.get("src")
        if src is None:
            continue  # e.g. nvs: fill only
        if src not in names:
            raise OtaError(f"Part '{key}' references missing file {src!r}.")
        data = zf.read(src)
        if len(data) != part.get("size"):
            raise OtaError(f"Part '{key}': size {len(data)} != manifest {part.get('size')}.")
        if hashlib.sha256(data).hexdigest() != part.get("cs_sha256"):
            raise OtaError(f"Part '{key}': SHA-256 does not match manifest (corrupt ZIP?).")
    if "app" not in manifest["parts"]:
        raise OtaError(f"Manifest has no 'app' part (parts: {sorted(manifest['parts'])}).")
    return manifest


def _bump_patch(version: str | None) -> str | None:
    """1.0.2 -> 1.0.3; None if the value is not a plain x.y.z version."""
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version or "")
    return f"{m[1]}.{m[2]}.{int(m[3]) + 1}" if m else None


def check_tag(tag: str | None) -> str | None:
    if tag and not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", tag):
        raise OtaError("Tag may only contain letters, digits, '.', '_' and '-' (max 40 chars).")
    return tag or None


def default_output_name(profile: Profile, app_path: Path, today: dt.date | None = None,
                        tag: str | None = None) -> str:
    today = today or dt.date.today()
    suffix = f"-{tag}" if tag else ""
    return f"{profile.name}-{app_path.stem}-{today:%Y%m%d}{suffix}.zip"


def build(profile: Profile, app_path: Path, official_zip: Path, output: Path, *,
          drop: tuple[str, ...] = (), tag: str | None = None, factory: Path | None = None,
          boot_min_version: str | None = None, secrets: dict[str, list[bytes]] | None = None,
          fail_on_secrets: bool = False) -> BuildResult:
    tag = check_tag(tag)
    for part in drop:
        if part not in DROPPABLE_PARTS:
            raise OtaError(f"Cannot drop '{part}'. Droppable: {', '.join(DROPPABLE_PARTS)} ('app' is required).")
    if boot_min_version and not factory:
        raise OtaError("--boot-min-version only makes sense together with --esphome-factory.")
    if boot_min_version and boot_min_version != "keep" and not re.fullmatch(r"\d+\.\d+\.\d+", boot_min_version):
        raise OtaError("--boot-min-version must look like 1.0.3, or 'keep'.")
    if factory and {"boot", "otadata"} & set(drop):
        raise OtaError("Cannot drop 'boot' or 'otadata' while taking them from a factory image.")
    resolved = {output.resolve()}
    if resolved & {official_zip.resolve(), app_path.resolve()}:
        raise OtaError("Output must not overwrite an input file.")

    app = app_path.read_bytes()
    warnings = check_app_image(app, profile.platform, profile.app_slot_size, profile.app_ptn)

    secrets_found: list[str] | None = None
    if secrets is not None:
        images = [app] + ([factory.read_bytes()] if factory else [])
        secrets_found = sorted({n for img in images for n in secrets_check.scan(img, secrets)})
        if secrets_found:
            warnings.append("CREDENTIALS IN THE IMAGE: " + ", ".join(secrets_found) + " are stored in plain text in this "
                            "package. Do not share, upload or commit it.")
            if fail_on_secrets:
                raise OtaError("The image contains credentials (" + ", ".join(secrets_found) + "); --fail-on-secrets is set. "
                               "Build a version without them if the package is meant to be shared.")
    else:
        warnings.append("Credentials were not checked (give --esphome-yaml with a secrets.yaml next to it, or --secrets FILE). "
                        "ESPHome images contain Wi-Fi data in plain text if the config has it: do not share this package.")

    with zipfile.ZipFile(official_zip) as original:
        manifest = read_official_manifest(original, profile.name)
        if manifest.get("platform") and manifest["platform"] != profile.platform:
            raise OtaError(f"Package platform {manifest['platform']!r} != profile {profile.platform!r}.")
        parts = manifest["parts"]
        if parts["app"].get("ptn") != profile.app_ptn:
            warnings.append(f"Manifest app part targets ptn={parts['app'].get('ptn')!r}, profile says "
                            f"{profile.app_ptn!r}. Check manually.")

        app_name = parts["app"]["src"]
        parts["app"]["size"] = len(app)
        parts["app"]["cs_sha256"] = hashlib.sha256(app).hexdigest()

        skip_files: set[str] = set()
        dropped = []
        for key in drop:
            if key in parts:
                if parts[key].get("src"):
                    skip_files.add(parts[key]["src"])
                del parts[key]
                dropped.append(key)

        replacements: dict[str, bytes] = {}
        replaced: list[str] = []
        if factory:
            from . import bootswap  # imported here: bootswap itself needs OtaError from this module
            replacements, boot_warnings = bootswap.prepare(factory.read_bytes(), original, manifest, app)
            warnings += boot_warnings
            for key in ("boot", "otadata"):
                data = replacements[parts[key]["src"]]
                parts[key]["size"] = len(data)
                parts[key]["cs_sha256"] = hashlib.sha256(data).hexdigest()
                replaced.append(key)
            # The installer writes the bootloader only if the installed one is older than the package's boot
            # min_version (seen on the Plug M Gen3: 1.0.2 was skipped, 1.0.3 was written). So raise it by one patch
            # level unless the option or the profile says otherwise. The H&T Gen3 reports an installed 1.0.3
            # ("Boot: cur 010003ff"), so one patch is not enough there: its profile sets boot_min_version.
            old = parts["boot"].get("min_version")
            target = boot_min_version or profile.boot_min_version or _bump_patch(old)
            if target and target != "keep" and target != old:
                parts["boot"]["min_version"] = target
                warnings.append(f"boot min_version raised from {old} to {target}, so that the Shelly installer "
                                f"writes the new bootloader (use --boot-min-version keep to leave it).")
            warnings.append("BOOTLOADER REPLACED: the package carries ESPHome's bootloader and a clean otadata. If the "
                            "bootloader does not suit the device, only UART can bring it back. Worked on the Plug M "
                            "Gen3 and the H&T Gen3; untested on other models.")

        if "nvs" in parts:
            warnings.append("NVS part is included: applying this package wipes NVS (Wi-Fi credentials, settings).")
        if "otadata" in parts and "otadata" not in replaced:
            warnings.append("otadata part is included: boot slot state is reset to the official package's.")

        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as result:
            for entry in original.namelist():
                if entry in skip_files:
                    continue
                if entry == "manifest.json":
                    data = json.dumps(manifest, separators=(",", ":")).encode()
                elif entry == app_name:
                    data = app
                elif entry in replacements:
                    data = replacements[entry]
                else:
                    data = original.read(entry)
                result.writestr(entry, data)

    # Read back and verify what was actually written.
    with zipfile.ZipFile(output) as check:
        written = read_official_manifest(check, profile.name)
        assert check.read(app_name) == app
    zip_sha = hashlib.sha256(output.read_bytes()).hexdigest()
    return BuildResult(
        output=output, sha256=zip_sha, app_size=len(app), app_sha256=hashlib.sha256(app).hexdigest(),
        parts=list(written["parts"]), dropped=dropped,
        official_version=manifest["version"], official_build_id=manifest.get("build_id"), tag=tag, warnings=warnings,
        replaced=replaced, secrets_found=secrets_found,
    )


def write_report(result: BuildResult) -> None:
    """Write <zip>.sha256 and <zip>.report.json next to the output."""
    out = result.output
    Path(str(out) + ".sha256").write_text(f"{result.sha256} *{out.name}\n", encoding="utf-8")
    report = {
        "output": out.name, "zip_sha256": result.sha256, "app_size": result.app_size,
        "app_sha256": result.app_sha256, "parts": result.parts, "dropped": result.dropped,
        "official_version": result.official_version, "official_build_id": result.official_build_id, "tag": result.tag,
        "bootloader_replaced": "boot" in result.replaced,
        "contains_secrets": result.secrets_found,  # names only (never values); null = not checked
        "warnings": result.warnings,
        "tool_version": __version__,
        "built": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    Path(str(out) + ".report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def inspect_zip(path: Path, profile: Profile | None = None) -> str:
    """Human-readable summary of an OTA ZIP; hashes are verified."""
    lines = []
    with zipfile.ZipFile(path) as zf:
        manifest = read_official_manifest(zf)
        lines.append(f"{path.name}: {manifest['name']} {manifest['version']} "
                     f"({manifest.get('build_id')}, {manifest.get('platform')})")
        for key, part in manifest["parts"].items():
            lines.append(f"  {key:8s} size={part.get('size'):>8}  ptn={part.get('ptn', '-'):8s} "
                         f"src={part.get('src', '(fill 0x%02X)' % part.get('fill', 0))}")
        app = zf.read(manifest["parts"]["app"]["src"])
        lines.append(f"  app header: magic=0x{app[0]:02X} segments={app[1]} chip_id=0x{int.from_bytes(app[12:14], 'little'):04x}")
        if profile:
            lines.append(f"  slot fit: {len(app)} / {profile.app_slot_size} bytes "
                         f"({100 * len(app) / profile.app_slot_size:.0f}%)")
        lines.append("  all part hashes OK")
    return "\n".join(lines)
