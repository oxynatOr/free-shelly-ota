"""Official Shelly firmware store: fw/shelly/<Device>/<version>/<Device>.zip + meta.json.

Original OTA ZIPs are kept on disk, one folder per version. Missing firmware is
downloaded via the Shelly update API. TLS verification is always on.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import ssl
import urllib.request
import zipfile
from pathlib import Path

from . import MODULE_DIR
from . import ui
from .builder import OtaError, read_official_manifest

FW_DIR = MODULE_DIR / "fw" / "shelly"
UPDATE_API = "https://updates.shelly.cloud/update/{update_id}"


def _version_key(version: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in re.split(r"[.\-]", version))


def list_versions(device: str, fw_dir: Path = FW_DIR) -> list[str]:
    """Cached versions of a device, oldest first."""
    base = fw_dir / device
    if not base.is_dir():
        return []
    versions = [p.name for p in base.iterdir() if (p / f"{device}.zip").is_file()]
    return sorted(versions, key=_version_key)


def cached_zip(device: str, version: str | None = None, fw_dir: Path = FW_DIR, prerelease: bool = False) -> Path | None:
    """Path of the cached official ZIP, or None.

    Without a version it is the newest stable one (a pre-release such as 2.2.0-beta1 has to be asked for with
    its version); only if nothing but pre-releases is cached, the newest of those. prerelease=True (a -beta profile)
    takes the newest pre-release instead, and None if there is none.
    """
    versions = list_versions(device, fw_dir)
    if version is None and prerelease:
        version = ([v for v in versions if "-" in v] or [None])[-1]
    elif version is None:
        stable = [v for v in versions if "-" not in v]
        version = (stable or versions or [None])[-1]
    if version is None or version not in versions:
        return None
    return fw_dir / device / version / f"{device}.zip"


def _ssl_context(insecure: bool = False) -> ssl.SSLContext:
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return ssl.create_default_context()


def _http_get(url: str, timeout: int = 60, insecure: bool = False, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "ShellyOTA/1.0", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context(insecure)) as resp:
            return resp.read()
    except OSError as e:  # URLError, ssl errors, timeouts
        hint = " (Shelly uses a private CA; retry with --insecure)" if "CERTIFICATE_VERIFY" in str(e) else ""
        raise OtaError(f"Download failed for {url}: {e}{hint}") from e


def query_update_api(update_id: str, insecure: bool = False, from_version: str | None = None) -> dict:
    """Return the raw JSON reply of the update API.

    The server answers per installed version, which the device reports in the Shelly-Info header
    (found in the firmware: {id,mac,model,batch,app,ver,fw_id}; the server needs only app and ver).
    Without it you get the newest release (currently only a beta); with e.g. ver 1.4.4 you get the
    stable release that device would be offered (2.0.1).
    """
    headers = None
    if from_version:
        headers = {"Shelly-Info": json.dumps({"app": update_id, "ver": from_version}, separators=(",", ":"))}
    body = _http_get(UPDATE_API.format(update_id=update_id), insecure=insecure, headers=headers)
    try:
        return json.loads(body)
    except ValueError:
        raise OtaError(f"Update API returned non-JSON: {body[:200]!r}") from None


def store_zip(device: str, data: bytes, source: str, api_reply: dict | None = None, fw_dir: Path = FW_DIR) -> Path:
    """Verify `data` as an official OTA ZIP for `device` and store it under its manifest version."""
    tmp = fw_dir / device / ".incoming.zip"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(data)
    try:
        with zipfile.ZipFile(tmp) as zf:
            manifest = read_official_manifest(zf, device)
    except zipfile.BadZipFile:
        tmp.unlink()
        raise OtaError("Downloaded file is not a valid ZIP.") from None
    except OtaError:
        tmp.unlink()
        raise
    version = manifest["version"]
    target = fw_dir / device / version / f"{device}.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp.replace(target)
    meta = {
        "device": device,
        "version": version,
        "build_id": manifest.get("build_id"),
        "source": source,
        "zip_sha256": hashlib.sha256(data).hexdigest(),
        "fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "api_reply": api_reply,
    }
    (target.parent / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return target


def fetch(device: str, update_id: str, *, refresh: bool = False, version: str | None = None,
          insecure: bool = False, alt: str | None = None, channel: str = "stable",
          from_version: str | None = None, fw_dir: Path = FW_DIR) -> Path:
    """Return the official ZIP, downloading it if it is not cached.

    - cached and not refresh: use the cache (version pins a specific cached version)
    - otherwise: ask the update API and download what it points to
    - channel: "stable" (default) or "beta"; a non-stable channel always asks the update API unless version is given
    - from_version: ask the update API as a device running this version would (Shelly-Info header); always asks the API
    - alt: the device is a variant listed under "alt" in the reply of its parent device (update_id is the parent's)
    """
    if (channel != "stable" or from_version) and not version:
        refresh = True  # the cache only knows what is newest, not which channel it came from
    if not refresh:
        cached = cached_zip(device, version, fw_dir)
        if cached:
            return cached
        if version:
            raise OtaError(f"Version {version} of {device} is not cached; the update API only serves the latest "
                           f"release. Put the ZIP under {fw_dir / device / version} manually.")
    if insecure:
        ui.say("WARNING: TLS certificate verification is OFF for this download.")
    reply = query_update_api(update_id, insecure, from_version) if from_version else query_update_api(update_id, insecure)
    # Observed reply: {"stable": {"version", "build_id", "url"}, "time": <unix>}
    if alt:
        entry = (reply.get("alt") or {}).get(alt)
        if not isinstance(entry, dict):
            raise OtaError(f"Variant {alt!r} is not listed in the update API reply of {update_id} "
                           f"(variants: {', '.join((reply.get('alt') or {}).keys()) or 'none'}).")
        reply = entry
    if channel == "stable":
        release = reply.get("stable") if isinstance(reply.get("stable"), dict) else reply
    else:
        release = reply.get(channel)
        if not isinstance(release, dict):
            offered = ", ".join(k for k, v in reply.items() if isinstance(v, dict)) or "none"
            raise OtaError(f"The update API has no {channel!r} release for {device} (offered: {offered}).")
    url = release.get("url")
    if not isinstance(url, str) or not url.startswith("https://"):
        offered = ", ".join(k for k, v in reply.items() if isinstance(v, dict))
        hint = (f" The API offers: {offered}. Use --channel {offered.split(', ')[0]}"
                + ("" if from_version else " or --from-version <installed version>") + ".") if offered else ""
        raise OtaError(f"No https 'url' in update API reply: {json.dumps(reply)[:300]}{hint}")
    api_version = release.get("version")
    if version and api_version and str(api_version) != version:
        raise OtaError(f"Update API offers {api_version}, not the requested {version}.")
    if not version and api_version and cached_zip(device, str(api_version), fw_dir):
        return cached_zip(device, str(api_version), fw_dir)  # already have the newest
    ui.say(f"Downloading {url}")
    data = _http_get(url, timeout=300, insecure=insecure)
    # The last URL path component is the SHA-256 of the whole ZIP.
    expected = url.rsplit("/", 1)[-1].lower()
    if re.fullmatch(r"[0-9a-f]{64}", expected) and hashlib.sha256(data).hexdigest() != expected:
        raise OtaError("Downloaded ZIP does not match the SHA-256 in its URL (corrupt or tampered).")
    path = store_zip(device, data, source=url, api_reply=reply, fw_dir=fw_dir)
    build_id = release.get("build_id")
    with zipfile.ZipFile(path) as zf:
        if build_id and json.loads(zf.read("manifest.json")).get("build_id") != build_id:
            ui.say(f"WARNING: build_id in manifest differs from update API ({build_id}).")
    return path
