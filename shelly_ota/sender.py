"""Send an OTA ZIP to a Shelly: serve it over HTTP and tell the device to download it.

The Shelly pulls the file itself (RPC Shelly.Update with a url), so this PC must be
reachable from the device, e.g. connected to the Shelly's own access point.
"""

from __future__ import annotations

import contextlib
import fnmatch
import http.server
import json
import re
import socket
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from . import buildinfo, firmware, logwatch, rpc, secrets_check, ui
from .builder import OtaError, read_official_manifest
from .profile import Profile

DEFAULT_IP = "192.168.33.1"  # Shelly access-point default


def device_info(addr: str, timeout: float = 10) -> dict:
    """Shelly.GetDeviceInfo of the device at addr ('host' or 'host:port')."""
    url = f"http://{addr}/rpc/Shelly.GetDeviceInfo"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (OSError, ValueError) as e:
        raise OtaError(f"No answer from the Shelly at {addr}: {e}") from e


def local_ip_for(addr: str) -> str:
    """Local address this PC would use to reach addr (no packet is sent)."""
    host = addr.rsplit(":", 1)[0] if addr.count(":") == 1 else addr
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect((host, 9))
            return s.getsockname()[0]
        except OSError as e:
            raise OtaError(f"Cannot find a local address towards {host}: {e}. Use --host.") from e


class FileServer:
    """Serves exactly one file; `served` is set once a client received all of it."""

    def __init__(self, path: Path, port: int = 8000, bind: str = "0.0.0.0"):
        self.path = path
        self.name = path.name
        self.served = threading.Event()
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def _headers(self) -> bool:
                if urllib.parse.unquote(self.path.split("?")[0]) != "/" + outer.name:
                    self.send_error(404)
                    return False
                self.send_response(200)
                self.send_header("Content-Type", "application/zip")
                self.send_header("Content-Length", str(outer.path.stat().st_size))
                self.end_headers()
                return True

            def do_HEAD(self):
                self._headers()

            def do_GET(self):
                if not self._headers():
                    return
                try:
                    with outer.path.open("rb") as f:
                        while chunk := f.read(64 * 1024):
                            self.wfile.write(chunk)
                    self.wfile.flush()
                    outer.served.set()
                except OSError:
                    pass  # client dropped the connection; not served

            def log_message(self, *args):
                pass

        try:
            self.httpd = http.server.ThreadingHTTPServer((bind, port), Handler)
        except OSError as e:
            raise OtaError(f"Cannot start the web server on port {port}: {e}. Try --port.") from e
        self.port = self.httpd.server_address[1]

    def start(self) -> None:
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def url(self, host: str) -> str:
        return f"http://{host}:{self.port}/{urllib.parse.quote(self.name)}"


# The updater logs the slot it will write to as soon as the debug log is switched on, e.g.
# "shos_ota_esp32_back:949 Storing core dumps to app_1 (0x200000)". In six runs (H&T, Power Strip, Plus Plug S x4) it matched the
# later "Will write to slot 1" line. That is the slot the stock firmware is NOT running from.
TARGET_SLOT_RE = re.compile(r"Storing core dumps to app_(\d)\b")


def probe_target_slot(addr: str, host: str, log_port: int, *, wait: float = 4.0, **auth) -> int | None:
    """Ask the device which slot its updater would write to, without updating. None if no answer arrived."""
    found: list[int] = []

    def sink(text: str) -> None:
        m = TARGET_SLOT_RE.search(text)
        if m:
            found.append(int(m.group(1)))

    with logwatch.udp_log(addr, host, log_port, sink, **auth):
        deadline = time.monotonic() + wait
        while not found and time.monotonic() < deadline:
            time.sleep(0.1)
    return found[0] if found else None


def package_info(zip_path: Path, profile: Profile) -> list[str]:
    """What the package's report says about its origin: when, by which tool state, from which profile revision."""
    try:
        data = json.loads(Path(str(zip_path) + ".report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    try:
        tool = buildinfo.BuildInfo(**data["tool_build"]).short()
    except (KeyError, TypeError):
        tool = str(data.get("tool_version", "unknown version"))
    built = str(data.get("built", "")).replace("T", " ").replace("+00:00", " UTC")
    prof = data.get("profile") or {}
    lines = [f"Package: built {built or 'at an unknown time'} by free-shelly-ota {tool}"
             + (f", profile {prof['name']} revision {prof['revision']}" if prof.get("name") else "")]
    if prof.get("revision") and prof["revision"] != profile.revision:
        lines.append(f"NOTE: the {profile.name} profile has changed since this package was built (revision "
                     f"{prof['revision']}, now {profile.revision}); rebuild it if that change matters (see CHANGELOG).")
    return lines


def send(profile: Profile, zip_path: Path, addr: str = DEFAULT_IP, *, host: str | None = None,
         port: int = 8000, timeout: float = 300, assume_yes: bool = False, dry_run: bool = False,
         force: bool = False, user: str | None = None, password: str | None = None,
         watch: float = 0, log_port: int = 9514, ignore_slot: bool = False, probe_wait: float = 4.0,
         ask: Callable[[str], str] = input, out: Callable[[str], None] = ui.say) -> bool:
    """Returns True if the device downloaded the whole ZIP (or on a successful dry run)."""
    with zipfile.ZipFile(zip_path) as zf:
        manifest = read_official_manifest(zf, profile.name)

    info = device_info(addr)
    app = str(info.get("app", "?"))
    out(f"Device {addr}: app={app} model={info.get('model') or 'n/a'} fw={info.get('ver')} id={info.get('id')} "
        f"reported slot={info.get('slot', 'n/a')} (not the update target; that is read separately)")
    auth = {"user": user, "password": password}
    if info.get("auth_en") and not (user and password):
        raise OtaError("The device has a password set: use --user and --password (user is usually 'admin').")
    exact = app.lower() in (profile.name.lower(), profile.update_id.lower())
    pattern = manifest.get("compatible")  # e.g. "PlugUSG4*": the package itself says which apps it fits
    by_pattern = bool(pattern) and fnmatch.fnmatchcase(app, pattern)
    if by_pattern and not exact:
        out(f"NOTE: device app {app!r} is not {profile.name!r} but matches the package's compatible pattern "
            f"{pattern!r} (a variant of the same model).")
    elif not exact and not force:
        raise OtaError(f"Device reports app {app!r}, but this ZIP/profile is {profile.name!r}"
                       f"{f' (compatible: {pattern})' if pattern else ''}. Use --force only if you are sure.")

    host = host or local_ip_for(addr)
    server = FileServer(zip_path, port)
    url = server.url(host)
    out(f"ZIP: {zip_path.name} ({manifest['version']}, parts: {', '.join(manifest['parts'])})")
    for line in package_info(zip_path, profile):
        out(line)
    out(f"Download URL for the device: {url}")
    official_zip = firmware.cached_zip(profile.name)
    boot_replaced: bool | None = None  # None: cannot tell (no cached official ZIP to compare with)
    if official_zip:
        with zipfile.ZipFile(official_zip) as oz:
            official_boot = json.loads(oz.read("manifest.json"))["parts"].get("boot", {}).get("cs_sha256")
        boot_replaced = manifest["parts"].get("boot", {}).get("cs_sha256") != official_boot
        if boot_replaced:
            out("WARNING: this package replaces Shelly's bootloader. If it does not suit the device, only UART can "
                "bring it back. Do not interrupt the power during the update.")
            out("NOTE: ESPHome's bootloader starts app_0 (the installer overwrites otadata), so the installer must write "
                "to slot 0; otherwise the old app in app_0 starts instead (seen on the Power Strip Gen4 and the Plus Plug S).")
            target = None
            try:
                target = probe_target_slot(addr, host, log_port, wait=probe_wait, **auth)
            except OtaError as e:
                out(f"NOTE: could not ask the device for its update target slot ({e}).")
            if target is None:
                out("WARNING: the update target slot could not be read (UDP log blocked? allow UDP port "
                    f"{log_port} in the firewall). If the installer writes to slot 1, the old app starts instead.")
            elif target == 0:
                out("Update target slot: 0 (the slot ESPHome's bootloader starts).")
            elif ignore_slot:
                out(f"WARNING: the installer will write to slot {target}, but ESPHome's bootloader starts app_0 "
                    "(sending anyway because of --ignore-slot).")
            else:
                server.httpd.server_close()
                raise OtaError(
                    f"The installer would write to slot {target}, but ESPHome's bootloader starts app_0, so the old "
                    f"firmware would start again. Install the official firmware first (python ota.py restore "
                    f"{profile.name}); that also puts Shelly's bootloader back and moves the stock firmware to the "
                    "other slot. Then send again. Use --ignore-slot to send anyway.")
    else:
        out(f"NOTE: no official {profile.name} ZIP cached, so it was not checked whether this package replaces "
            f"Shelly's bootloader (run 'ota.py inspect' on it, or 'ota.py fetch {profile.name}').")
    note = secrets_check.report_note(zip_path)
    if note:
        out(f"{note[0]}: {note[1]}")
    if dry_run:
        server.httpd.server_close()
        out("Dry run: nothing sent.")
        return True
    if not assume_yes:
        if "nvs" in manifest["parts"]:
            out("WARNING: this wipes NVS (Wi-Fi credentials and settings) and replaces the firmware.")
        if ask("Type 'yes' to flash this device: ").strip().lower() != "yes":
            server.httpd.server_close()
            raise OtaError("Cancelled.")

    server.start()
    try:
        with contextlib.ExitStack() as stack:
            if watch > 0:
                stack.enter_context(logwatch.udp_log(addr, host, log_port, out, **auth))
            trigger = f"http://{addr}/rpc/Shelly.Update?url={urllib.parse.quote(url, safe='')}"
            answer = rpc.request(trigger, timeout=30, **auth).decode(errors="replace").strip()
            out(f"Device accepted the request: {answer or 'ok'}")
            out("Waiting for the device to download the ZIP ...")
            if not server.served.wait(timeout):
                raise OtaError(f"The device did not download the ZIP within {timeout:.0f}s. Check that it can "
                               f"reach {host}:{server.port} (firewall, network).")
            time.sleep(1)
            out("Done: the device downloaded the ZIP. It now flashes and reboots; if it stays silent, "
                "disconnect it from power for at least 30 s.")
            if boot_replaced:
                out("After the first ESPHome boot: the log line 'ota data invalid, no current app. Assuming factory' is "
                    "expected. The package carried ESPHome's bootloader, so no separate bootloader update is needed.")
            else:
                out("After the first ESPHome boot: the log line 'ota data invalid, no current app. Assuming factory' is "
                    "expected. This package keeps Shelly's bootloader, which counts uncommitted boots and may switch back "
                    "to the old firmware after a few restarts. For a lasting install build with --esphome-factory "
                    "(README, 'After the first boot').")
            if watch > 0:
                out(f"Still listening to the device log for {watch:.0f}s ...")
                time.sleep(watch)
        return True
    finally:
        server.stop()
