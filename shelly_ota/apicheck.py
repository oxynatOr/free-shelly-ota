"""`ota.py profiles --check-api`: what does Shelly's update API offer today, and does it still fit our profiles?

Without --download only metadata is read (one small request per profile, no device data). With --download a package
that is newer than the cache is fetched, and its flash layout and loader are compared with the profile.
"""

from __future__ import annotations

import time
import zipfile
from pathlib import Path
from typing import Callable

from . import devicegen, firmware, lint, profile
from .builder import OtaError, read_official_manifest, variant_for_zip

TRIES = 3               # the update server answers 502 or 408 now and then
OLD_DEVICE = "1.4.4"    # asked as such a device when the plain request lists no release of the channel


def _release(reply: dict, p: profile.Profile, channel: str) -> dict | None:
    """The release of `channel` in an update API reply (variants live under 'alt' of their parent's reply)."""
    if p.parent:
        reply = (reply.get("alt") or {}).get(p.update_id) or {}
    release = reply.get(channel)
    return release if isinstance(release, dict) else None


def _ask(query, update_id: str, insecure: bool, cafile: Path | None, from_version: str | None, sleep) -> dict:
    for attempt in range(TRIES):
        try:
            return query(update_id, insecure, from_version=from_version, cafile=cafile)
        except OtaError as e:
            if "CERTIFICATE_VERIFY" in str(e) or attempt == TRIES - 1:
                raise
            sleep(2 * (attempt + 1))


def _numbers(version: str) -> tuple:
    return tuple(int(x) if x.isdigit() else 0 for x in str(version).split("."))


def check_api(names: list[str], *, download: bool = False, insecure: bool = False, cafile: Path | None = None,
              out: Callable[[str], None] = print, query=None, fetch=None, sleep=time.sleep) -> list[str]:
    """One report line per profile; returns the profiles that need attention (not answered, or the package does not fit)."""
    query, fetch = query or firmware.query_update_api, fetch or firmware.fetch
    attention: list[str] = []
    for name in names:
        p = profile.load_profile(name)
        channel = "beta" if p.channel == "beta" else "stable"
        asked = profile.load_profile(p.parent).update_id if p.parent else p.update_id
        try:
            reply = _ask(query, asked, insecure, cafile, None, sleep)
            release = _release(reply, p, channel)
            beta = _release(reply, p, "beta") if channel == "stable" else None
            seen_as = None   # the device version the release was only listed for; the download has to ask the same way
            if release is None:
                release = _release(_ask(query, asked, insecure, cafile, OLD_DEVICE, sleep), p, channel)
                seen_as = OLD_DEVICE
        except OtaError as e:
            if "CERTIFICATE_VERIFY" in str(e):
                raise   # every request would fail the same way; the message says how to go on
            out(f"{name}: WARNING: update API not answered ({e})")
            attention.append(name)
            continue
        if release is None:
            out(f"{name}: no {channel} release listed")
        offered = [(channel, release, seen_as)] if release else []
        if beta:
            offered.append(("beta", beta, None))
        for kind, entry, from_version in offered:
            line, bad = _report(p, name, asked, kind, str(entry.get("version")), download=download, insecure=insecure,
                                cafile=cafile, fetch=fetch, from_version=from_version)
            out(line)
            if bad and name not in attention:
                attention.append(name)
    return attention


def _report(p: profile.Profile, name: str, asked: str, channel: str, version: str, *, download: bool, insecure: bool,
            cafile: Path | None, fetch, from_version: str | None) -> tuple[str, bool]:
    """The line for one offered version, and whether it needs attention."""
    cached = firmware.list_versions(p.package_name)
    if version in cached:
        return f"{name}: {channel} {version} cached", False
    newest = cached[-1] if cached else None
    if newest and firmware._version_key(version) < firmware._version_key(newest):
        return f"{name}: {channel} {version} offered, older than the cached {newest}", False
    line = f"{name}: {channel} {version} NEW (not cached)"
    if not download:
        return line, False
    try:
        path = fetch(p.package_name, asked, insecure=insecure, cafile=cafile, refresh=True, channel=channel,
                     alt=p.update_id if p.parent else None, from_version=from_version)
    except OtaError as e:
        return f"{line}; WARNING: download failed: {e}", True
    with zipfile.ZipFile(path) as zf:
        manifest = read_official_manifest(zf)
        variant = variant_for_zip(p, zf, manifest)
        loader = (manifest["parts"].get("boot") or {}).get("min_version")
    if variant is None:
        line += "; WARNING: a flash layout the profile does not know"
    else:
        line += "; layout fits: " + (f"since {variant.layout_since}" if variant.base else "the first one")
    shipped = lint.shipped_table(variant) if variant else None
    differ = lint.table_differences(devicegen.partition_csv(path), shipped) if shipped else []
    if differ:
        line += f"; WARNING: the table differs from {variant.csv_name} in {', '.join(differ)}"
    low_boot = bool(loader and p.boot_min_version and _numbers(p.boot_min_version) <= _numbers(loader))
    if low_boot:
        line += f"; WARNING: boot_min_version {p.boot_min_version} is not above the package's loader {loader}"
    return line, bool(variant is None or low_boot or differ)
