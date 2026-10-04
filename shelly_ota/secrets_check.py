"""Find the user's own credentials inside a built image, so a package is not shared by accident.

An ESPHome image carries Wi-Fi SSID/password, API keys and the like in plain text. We cannot guess what looks like a
password, so we compare: collect the values from the ESPHome config (and its secrets.yaml), then search the image for
them. Only the *names* of the matches are ever reported, never the values.
"""

from __future__ import annotations

import base64
import binascii
import json
import subprocess
from pathlib import Path

import yaml

MIN_LEN = 4          # shorter values would match by chance
MIN_LEN_GENERIC = 6  # values from secrets.yaml that the config does not obviously use as a credential


class _SecretRef:
    def __init__(self, name: str):
        self.name = name


class _Loader(yaml.SafeLoader):
    pass


_Loader.add_constructor("!secret", lambda loader, node: _SecretRef(loader.construct_scalar(node)))
# Other ESPHome tags (!include, !lambda, ...) are not needed here.
_Loader.add_multi_constructor("!", lambda loader, suffix, node: None)


def _read_secrets(path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if isinstance(v, (str, int, float)) and not isinstance(v, bool)}


def _variants(value: str, base64_key: bool = False) -> list[bytes]:
    out = [value.encode("utf-8")]
    if base64_key:  # ESPHome stores the API encryption key as its 32 raw bytes
        try:
            out.append(base64.b64decode(value, validate=True))
        except (binascii.Error, ValueError):
            pass
    return out


def collect(yaml_path: Path | None, secrets_file: Path | None = None) -> tuple[dict[str, list[bytes]], str | None]:
    """Return ({name: [byte patterns]}, problem). problem is set when nothing could be collected."""
    if secrets_file is None and yaml_path is not None:
        secrets_file = yaml_path.parent / "secrets.yaml"
    secrets = _read_secrets(secrets_file)
    cfg: dict = {}
    if yaml_path is not None:
        cfg = yaml.load(yaml_path.read_text(encoding="utf-8"), Loader=_Loader) or {}
        if not isinstance(cfg, dict):
            cfg = {}

    found: dict[str, list[bytes]] = {}
    seen: set[str] = set()

    def resolve(v):
        return secrets.get(v.name) if isinstance(v, _SecretRef) else v

    def add(name: str, v, base64_key: bool = False, min_len: int = MIN_LEN):
        v = resolve(v)
        if isinstance(v, bool) or not isinstance(v, (str, int, float)):
            return
        text = str(v)
        if len(text) < min_len or text in seen:
            return
        seen.add(text)
        found[name] = _variants(text, base64_key)

    def section(key):
        v = cfg.get(key)
        return v if isinstance(v, dict) else {}

    wifi = section("wifi")
    add("wifi.ssid", wifi.get("ssid"))
    add("wifi.password", wifi.get("password"))
    for i, net in enumerate(wifi.get("networks") or []):
        if isinstance(net, dict):
            add(f"wifi.networks[{i}].ssid", net.get("ssid"))
            add(f"wifi.networks[{i}].password", net.get("password"))
    ap = wifi.get("ap")
    if isinstance(ap, dict):
        add("wifi.ap.password", ap.get("password"))
    api = section("api")
    add("api.password", api.get("password"))
    enc = api.get("encryption")
    if isinstance(enc, dict):
        add("api.encryption.key", enc.get("key"), base64_key=True)
    ota = cfg.get("ota")
    for i, entry in enumerate(ota if isinstance(ota, list) else [ota]):
        if isinstance(entry, dict):
            add(f"ota[{i}].password", entry.get("password"))
    auth = section("web_server").get("auth")
    add("web_server.auth.password", auth.get("password") if isinstance(auth, dict) else None)
    add("mqtt.password", section("mqtt").get("password"))
    # Everything else in secrets.yaml (a config may reach it through substitutions or includes).
    for key, value in secrets.items():
        add(f"secrets.yaml:{key}", value, base64_key=("key" in key.lower()), min_len=MIN_LEN_GENERIC)

    if yaml_path is None and secrets_file is None:
        return found, "nothing to compare with"
    return found, None


def scan(image: bytes, candidates: dict[str, list[bytes]]) -> list[str]:
    """Names of the candidates found in the image."""
    return sorted(name for name, patterns in candidates.items() if any(p and p in image for p in patterns))


def git_would_track(path: Path) -> bool:
    """True if path is inside a git work tree and not ignored there. Quiet (False) when git is missing."""
    folder = path.resolve().parent
    try:
        inside = subprocess.run(["git", "-C", str(folder), "rev-parse", "--is-inside-work-tree"],
                                capture_output=True, text=True, timeout=10)
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return False
        ignored = subprocess.run(["git", "-C", str(folder), "check-ignore", "-q", str(path.resolve())],
                                 capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return ignored.returncode == 1  # 0 = ignored, 1 = not ignored


def report_note(zip_path: Path) -> tuple[str, str] | None:
    """Look at <zip>.report.json: ("WARNING"|"NOTE", text) about credentials in the package, or None."""
    report = Path(str(zip_path) + ".report.json")
    if not report.is_file():
        return None
    try:
        data = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    found = data.get("contains_secrets", "missing")
    if isinstance(found, list) and found:
        return "WARNING", ("this package contains credentials in plain text (" + ", ".join(found) +
                           "). Do not share, upload or commit it.")
    if found is None:
        return "NOTE", "the build did not check this package for credentials; ESPHome images contain Wi-Fi data in plain text."
    return None
