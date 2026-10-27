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
from typing import Callable, NamedTuple

from . import buildinfo, firmware, logview, logwatch, rpc, secrets_check, ui
from .builder import OtaError, read_official_manifest, require_zip
from .logview import Level
from .profile import Profile

DEFAULT_IP = "192.168.33.1"  # Shelly access-point default

# After a start the stock firmware refuses Shelly.Update ("Not committed") until it has confirmed itself. Observed: the
# refusal at an uptime of about 60 s (Multicolor Bulb Gen3) and a commit delay of about 90 s in a device log. This is what
# was seen, not a documented Shelly value, so the margin is generous.
SETTLE_SECONDS = 120
DEFAULT_WAIT = 120      # seconds to wait before the next pass after a refusal (--wait)
MAX_PASSES = 3          # how often send() offers to try again after a "Not committed" refusal
RESULT_WAIT = 30        # seconds to wait for the device's own "update succeeded" after it has downloaded the ZIP
# A weak Wi-Fi signal slows the download down to a crawl: a Mini 1 Gen3 at -68 dBm took about 1 % per 5 to 10 s and was at 28 % after
# the default 300 s (one report). Where exactly it starts to hurt is not known, so this is a guess from that one report.
WEAK_RSSI = -67         # dBm; at or below this send() says so and offers a longer wait
ETA_MIN_SPAN = 10.0     # seconds of download needed before the end is estimated
MAX_WAIT = 3600         # the longest the wait for a download is extended on its own (--max-wait)
SLOW_TIMEOUT = 1200     # the wait suggested for a weak signal (that report finished with --timeout 1200)


def device_info(addr: str, timeout: float = 10) -> dict:
    """Shelly.GetDeviceInfo of the device at addr ('host' or 'host:port')."""
    url = f"http://{addr}/rpc/Shelly.GetDeviceInfo"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read())
    except (OSError, ValueError) as e:
        raise rpc.DeviceUnreachable(f"No answer from the Shelly at {addr}: {e}") from e


def device_uptime(addr: str, **auth) -> int | None:
    """Seconds since the device started (Sys.GetStatus), or None if it cannot be told.

    Not every device or firmware may report it; a missing answer is not an error, the check is only a hint.
    """
    try:
        uptime = rpc.call(addr, "Sys.GetStatus", timeout=5, **auth).get("uptime")
    except OtaError:
        return None
    return int(uptime) if isinstance(uptime, (int, float)) and not isinstance(uptime, bool) else None


def device_wifi_rssi(addr: str, **auth) -> int | None:
    """Signal strength of the device's Wi-Fi in dBm (Wifi.GetStatus), or None if it cannot be told.

    Like the uptime, only a hint: a device or firmware that does not answer is not an error.
    """
    try:
        rssi = rpc.call(addr, "Wifi.GetStatus", timeout=5, **auth).get("rssi")
    except OtaError:
        return None
    return int(rssi) if isinstance(rssi, (int, float)) and not isinstance(rssi, bool) and rssi < 0 else None


def ask_seconds(ask: Callable[[str], str], question: str, suggested: float) -> float | None:
    """Ask for a wait in seconds: Enter takes the suggested one, a number another one, 's' / 'skip' skips (returns None: go on as it
    is), 'c' / 'cancel' cancels (OtaError). Anything else is asked again."""
    while True:
        answer = ask(f"{question} [{suggested:.0f} s]  Enter = that, a number = other seconds, s = skip, c = cancel: ").strip().lower()
        if answer == "":
            return suggested
        if answer in ("s", "skip"):
            return None
        if answer in ("c", "cancel"):
            raise OtaError("Cancelled.")
        try:
            seconds = float(answer)
        except ValueError:
            continue
        if seconds > 0:
            return seconds


class Refusal(NamedTuple):
    """What the device said when it refused Shelly.Update, in words for the user."""
    text: str
    retryable: bool


def explain_update_refusal(e: rpc.RpcError) -> Refusal:
    """Turn the device's refusal of Shelly.Update into advice. Matches on the message: code -109 covers several reasons."""
    message = e.device_message or str(e)
    lowered = message.lower()
    if "not committed" in lowered:
        return Refusal(
            f"The device refused the update: \"{message}\". After a start the stock firmware does not accept an update until "
            f"it has confirmed itself (seen after about 90 s to a few minutes). Keep the device powered and send again "
            f"after a couple of minutes.", True)
    if "battery" in lowered:
        return Refusal(
            f"The device refused the update: \"{message}\". Charge the battery (the stock updater wants at least 30 %) and "
            f"make sure the device is awake.", False)
    return Refusal(f"The device refused the update: \"{message}\"" + (f" (code {e.code})" if e.code is not None else "") + ".",
                   False)


def _wait_with_countdown(seconds: float, out: Callable[[str], None], sleep: Callable[[float], None], live: bool = False) -> None:
    """Wait with a countdown: one line that updates in place on a terminal (live), otherwise a line every 30 s."""
    ui.countdown(seconds, "Waiting", sleep=sleep, out=None if live else out)


def _settle(addr: str, auth: dict, *, say: Callable[[Level, str], None], ask: Callable[[str], str],
            sleep: Callable[[float], None], dry_run: bool, assume_yes: bool, live: bool = False) -> None:
    """Right after a start the stock firmware refuses an update. If the device says it has just started, tell the user
    and offer to wait. Never waits on its own: not with --dry-run and not with --yes (then it only says so)."""
    uptime = device_uptime(addr, **auth)
    if uptime is None or uptime >= SETTLE_SECONDS:
        return
    pause = SETTLE_SECONDS - uptime + 5
    say(Level.normal, f"NOTE: the device has been running for only {uptime} s. Right after a start the stock firmware refuses "
                      f"an update (\"Not committed\"); about {SETTLE_SECONDS} s has been enough so far.")
    if dry_run or assume_yes:
        return
    if ask(f"Wait about {pause} s before sending? Type 'yes' to wait: ").strip().lower() != "yes":
        say(Level.normal, "Not waiting; the device may refuse the update.")
        return
    _wait_with_countdown(pause, lambda text: say(Level.normal, text), sleep, live)


def _check_wifi(addr: str, auth: dict, *, say: Callable[[Level, str], None], ask: Callable[[str], str], timeout: float,
                dry_run: bool, assume_yes: bool) -> float:
    """Read the Wi-Fi signal; if it is weak, say what that does to the download and offer a longer wait. Returns the wait for
    the download in seconds. Never changes anything on its own: with --dry-run or --yes it only says so."""
    rssi = device_wifi_rssi(addr, **auth)
    if rssi is None:
        return timeout
    say(Level.verbose, f"Wi-Fi signal of the device: {rssi} dBm.")
    if rssi > WEAK_RSSI:
        return timeout
    say(Level.normal, f"NOTE: weak Wi-Fi signal of the device ({rssi} dBm). It downloads the ZIP over Wi-Fi, which can be very slow: a "
                      f"Mini 1 Gen3 at -68 dBm needed about 20 minutes. The wait for the download is {timeout:.0f} s "
                      f"(--timeout); moving the device or the access point closer helps more.")
    if dry_run or assume_yes:
        return timeout
    chosen = ask_seconds(ask, "Wait for the download for", max(timeout, SLOW_TIMEOUT))
    return timeout if chosen is None else chosen


def local_ip_for(addr: str) -> str:
    """Local address this PC would use to reach addr (no packet is sent)."""
    host = addr.rsplit(":", 1)[0] if addr.count(":") == 1 else addr
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect((host, 9))
            return s.getsockname()[0]
        except OSError as e:
            raise OtaError(f"Cannot find a local address towards {host}: {e}. Use --host.") from e


class DownloadWatch:
    """Estimates when the download ends, from what the file server has handed out (works without the device's log).

    The speed is measured over the last `window` seconds, so a slow start or a stall shows up and the estimate follows it."""

    def __init__(self, size: int, window: float = 60.0, min_span: float | None = None):
        self.size = size
        self.window = window
        self.min_span = ETA_MIN_SPAN if min_span is None else min_span
        self.samples: list[tuple[float, int]] = []

    def add(self, now: float, sent: int) -> None:
        self.samples.append((now, sent))
        while len(self.samples) > 2 and now - self.samples[1][0] >= self.window:
            self.samples.pop(0)

    def percent(self) -> int:
        return min(100, 100 * self.samples[-1][1] // max(self.size, 1)) if self.samples else 0

    def eta(self) -> float | None:
        """Seconds until the last byte at the speed of the window; None while there is too little to tell."""
        if len(self.samples) < 2:
            return None
        (t0, b0), (t1, b1) = self.samples[0], self.samples[-1]
        if t1 - t0 < self.min_span or b1 <= b0:
            return None
        return (self.size - b1) / ((b1 - b0) / (t1 - t0))


class FileServer:
    """Serves exactly one file; `served` is set once a client received all of it."""

    def __init__(self, path: Path, port: int = 8000, bind: str = "0.0.0.0"):
        self.path = path
        self.name = path.name
        self.served = threading.Event()
        self.size = path.stat().st_size
        self.bytes_sent = 0   # handed to the socket so far, all requests together: about as far as the device has read
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
                            outer.bytes_sent += len(chunk)
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
# Not every firmware names an app slot there: the Plug M Gen3 on stock 1.8.99 logs "Storing core dumps to scratch (0x720000)"
# and still wrote to slot 0 (running from slot 1). Such a line arrives, but it does not reveal the slot.
CORE_DUMP_RE = re.compile(r"Storing core dumps to (\w+)")
APP_SLOT_RE = re.compile(r"app_(\d)")


class SlotProbe(NamedTuple):
    slot: int | None               # the slot the updater will write to; None if the log does not name one
    core_dump_target: str | None   # what the "Storing core dumps to ..." line named ("app_1", "scratch"); None: no such line
    datagrams: int = 0             # UDP datagrams received meanwhile: 0 means the log does not reach this PC at all


def probe_slot(addr: str, host: str, log_port: int, *, wait: float = 8.0, tick: Callable[[float], None] | None = None,
               **auth) -> SlotProbe:
    """Ask the device which slot its updater would write to, without updating.

    SlotProbe(None, None) if no matching log line arrived (log blocked, or an old firmware); SlotProbe(None, "scratch")
    if it arrived but names something other than app_N. `datagrams` counts what arrived meanwhile. `tick(seconds left)` is
    called about once a second while it waits."""
    found: list[SlotProbe] = []

    def sink(text: str) -> None:
        m = CORE_DUMP_RE.search(text)
        if m and not found:
            app = APP_SLOT_RE.fullmatch(m.group(1))
            found.append(SlotProbe(int(app.group(1)) if app else None, m.group(1)))

    with logwatch.udp_log(addr, host, log_port, sink, **auth) as stats:
        deadline = time.monotonic() + wait
        shown = None
        while not found and time.monotonic() < deadline:
            left = int(deadline - time.monotonic()) + 1
            if tick and left != shown:
                shown = left
                tick(left)
            time.sleep(0.1)
    return (found[0] if found else SlotProbe(None, None))._replace(datagrams=stats.datagrams)


probe_target_slot = probe_slot     # the name main uses; it returns the same SlotProbe

# What a device answers when its RPC HTTP.GET cannot connect (seen in a device report: "Connection error: -13").
CONNECTION_ERROR_RE = re.compile(r'Connection error[^"}\\(]*')   # not the "(code -103)" that RpcError appends


def check_reach(addr: str, host: str, port: int, *, timeout: float = 30, **auth) -> tuple[bool | None, str]:
    """Ask the device to fetch http://host:port/ itself (RPC HTTP.GET): can the Shelly reach this PC?

    The file server answers 404 there, which is enough: any HTTP status proves the way is open. Returns
    (True, "HTTP 404"), (False, the device's connection error) or (None, why it could not be checked)."""
    target = f"http://{host}:{port}/"
    try:
        body = rpc.request(f"http://{addr}/rpc/HTTP.GET?url={urllib.parse.quote(target, safe='')}",
                           timeout=timeout, **auth)
    except OtaError as e:
        m = CONNECTION_ERROR_RE.search(str(e))
        return (False, m.group(0).strip()) if m else (None, str(e))
    try:
        reply = json.loads(body)
    except ValueError:
        return None, "the answer is not JSON"
    if not isinstance(reply, dict):
        return None, f"unexpected answer {body[:80]!r}"
    code = reply.get("code")
    if isinstance(code, int) and code > 0:
        return True, f"HTTP {code}"
    m = CONNECTION_ERROR_RE.search(str(reply.get("message", "")))
    return (False, m.group(0).strip()) if m else (None, f"unexpected answer {body[:80]!r}")


def reach_text(state: bool | None, detail: str, host: str, port: int) -> str:
    """One line for the result of check_reach."""
    if state is True:
        return f"The device can reach this PC (its own request to http://{host}:{port}/ got {detail})."
    if state is False:
        return (f"The device cannot reach this PC at http://{host}:{port}/ ({detail}), so it cannot download the ZIP. "
                f"Check the Shelly's network: firewall (TCP port {port}), VLAN or guest-network rules; --host and "
                "--port set the address and port it is told to use.")
    return f"could not check whether the device can reach this PC ({detail})."


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


def matches_compatible(app: str, pattern: str | None) -> bool:
    """Does the app name fit the manifest's `compatible` value: one fnmatch pattern or a comma separated list of them."""
    return any(fnmatch.fnmatchcase(app, p.strip()) for p in (pattern or "").split(",") if p.strip())


class BootWatch:
    """Passes device log lines on and warns once if the updater says it keeps Shelly's bootloader (update? 0)."""

    def __init__(self, out: Callable[[str], None], expect_new_loader: bool):
        self.out, self.expect_new_loader, self.skipped = out, expect_new_loader, False

    def feed(self, text: str) -> None:
        self.out(text)
        boot = logwatch.parse_boot_line(text)
        if boot and not boot["update"] and self.expect_new_loader and not self.skipped:
            self.skipped = True
            self.out(logwatch.boot_skipped_warning(boot))


def quiet_about_kept_loader(boot_replaced: bool | None, keeps_loader: bool, restoring: bool) -> bool | None:
    """What logview.Session.expect_new_loader gets. ESPHome only takes OTAs after its own bootloader was written, so
    'update? 0' is a warning for every ESPHome package, also one that is unclear or was forced without the bootloader.
    Only the official Shelly package (restore, or the unchanged ZIP sent by hand) may keep Shelly's loader: False, no warning."""
    official = restoring or (boot_replaced is False and not keeps_loader)
    return False if official else None


PLAIN_PACKAGE_DOC = "docs/bootloader-and-slots.md#without-esphomes-bootloader-plain-package"


def plain_package_text(name: str, forced: bool = False) -> str:
    """The message for an ESPHome package that keeps Shelly's bootloader: the refusal, or with --force the warning."""
    ending = ("  --force given: sending anyway." if forced else
              "  Only if you want exactly this and have UART at hand: add --force.")
    return ("THIS PACKAGE KEEPS SHELLY'S BOOTLOADER, NOT ESPHOME'S (it was not built with --esphome-factory).\n"
            "  Shelly's loader starts the ESPHome image only three times, then it goes back to the other slot (the old Shelly "
            "firmware) and keeps it. An ESPHome OTA during those starts changes that once. After it, further OTAs are written "
            f"but never started, and only UART helps (Plus Uni, issue #46; see {PLAIN_PACKAGE_DOC}).\n\n"
            "  Build the package with ESPHome's bootloader instead:\n\n"
            f"  python ota.py build {name} app.ota.bin --esphome-factory app.factory.bin ...\n\n" + ending)


def send(profile: Profile, zip_path: Path, addr: str = DEFAULT_IP, *, host: str | None = None,
         port: int = 8000, timeout: float = 300, max_wait: float = MAX_WAIT, assume_yes: bool = False, dry_run: bool = False,
         force: bool = False, user: str | None = None, password: str | None = None,
         watch: float = 0, log_port: int = 9514, ignore_slot: bool = False, probe_wait: float = 8.0,
         wait: float = DEFAULT_WAIT, sleep: Callable[[float], None] = time.sleep,
         ask: Callable[[str], str] = input, out: Callable[[str], None] = ui.say, restoring: bool = False,
         level: Level = Level.verbose, logfile: logview.LogFile | None = None,
         session: logview.Session | None = None) -> bool:
    """Returns True if the device downloaded the whole ZIP (or on a successful dry run).

    A device that has only just started refuses the update ("Not committed"). send() notices that from the uptime and
    offers to wait; if the device refuses anyway it offers to wait `wait` seconds and try again, and every new pass
    needs a new confirmation. With assume_yes it never waits or retries by itself.

    `level` decides how much is shown (see logview): the tool's own messages and the device log. The default shows
    everything except the entries of the device log. The caller owns `logfile` and closes it.
    While the update runs the device log is read (it is switched on and off again); that gives the progress and the
    device's own confirmation ("update succeeded"), without --watch. If the log does not reach this PC, send() falls back
    to reporting that the device downloaded the ZIP.
    """
    session = session or logview.Session(level=level, out=out, logfile=logfile)
    say = session.say
    zip_path = require_zip(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        manifest = read_official_manifest(zf, profile.package_name)

    info = device_info(addr)
    session.device_id = session.device_id or info.get("id")
    app = str(info.get("app", "?"))
    say(Level.normal, f"Device {addr}: {app}, fw {info.get('ver')}, id {info.get('id')}")
    say(Level.verbose, f"  model {info.get('model') or 'n/a'}, reported slot {info.get('slot', 'n/a')} "
                       "(not the update target; that is read separately)")
    auth = {"user": user, "password": password}
    if info.get("auth_en") and not (user and password):
        raise OtaError("The device has a password set: use --user and --password (user is usually 'admin').")
    exact = app.lower() in (profile.name.lower(), profile.update_id.lower())
    pattern = manifest.get("compatible")  # e.g. "PlugUSG4*" or "Pro3EM,Pro3EMProAddon": the package says which apps it fits
    by_pattern = matches_compatible(app, pattern)
    if by_pattern and not exact:
        say(Level.verbose, f"NOTE: device app {app!r} is not {profile.name!r} but matches the package's compatible pattern "
                           f"{pattern!r} (a variant of the same model).")
    elif not exact and not force:
        raise OtaError(f"Device reports app {app!r}, but this ZIP/profile is {profile.name!r}"
                       f"{f' (compatible: {pattern})' if pattern else ''}. Use --force only if you are sure.")

    host = host or local_ip_for(addr)
    server = FileServer(zip_path, port)
    url = server.url(host)
    say(Level.normal, f"ZIP: {zip_path.name} ({manifest['version']})")
    say(Level.verbose, f"  parts: {', '.join(manifest['parts'])}")
    for line in package_info(zip_path, profile):
        say(Level.normal if line.startswith(("NOTE", "WARNING")) else Level.verbose, line)
    say(Level.verbose, f"Download URL for the device: {url}")
    official_zip = firmware.cached_zip(profile.package_name, prerelease=profile.channel == "beta")
    boot_replaced: bool | None = None  # None: cannot tell (no cached official ZIP to compare with)
    keeps_loader = False  # an ESPHome app in a package that leaves Shelly's bootloader in place (no --esphome-factory)
    if official_zip:
        with zipfile.ZipFile(official_zip) as oz:
            official_parts = json.loads(oz.read("manifest.json"))["parts"]
        official_boot = official_parts.get("boot", {}).get("cs_sha256")
        boot_replaced = manifest["parts"].get("boot", {}).get("cs_sha256") != official_boot
        # the official package itself (restore, or sent by hand) keeps Shelly's bootloader by definition and is fine
        app_changed = manifest["parts"].get("app", {}).get("cs_sha256") != official_parts.get("app", {}).get("cs_sha256")
        keeps_loader = not boot_replaced and app_changed and not restoring
        if keeps_loader:
            if not force:
                server.httpd.server_close()
                raise OtaError(plain_package_text(profile.name))
            say(Level.quiet, "WARNING: " + plain_package_text(profile.name, forced=True))
        if boot_replaced:
            say(Level.quiet, "WARNING: this package replaces Shelly's bootloader. If it does not suit the device, only UART "
                              "can bring it back. Do not interrupt the power during the update.")
            say(Level.verbose, "NOTE: ESPHome's bootloader starts app_0 (the installer overwrites otadata), so the installer "
                               "must write to slot 0; otherwise the old app in app_0 starts instead (seen on the Power Strip "
                               "Gen4 and the Plus Plug S).")
            probe = SlotProbe(None, None)
            probe_failed = False
            try:
                probe = probe_slot(addr, host, log_port, wait=probe_wait, **auth,
                                   tick=(lambda left: ui.live(f"Asking the device which slot the update will use ... {left} s")) if session.out is ui.say else None)
            except OtaError as e:
                probe_failed = True
                say(Level.normal, f"NOTE: could not ask the device for its update target slot ({e}).")
            if session.out is ui.say:
                ui.live_end()
            target = probe.slot
            if target is None and probe.core_dump_target:
                # The log works, this firmware just does not say: do not send the user to the firewall.
                say(Level.normal, "WARNING: this firmware does not reveal the update target slot before the update (its log says "
                                  f"'Storing core dumps to {probe.core_dump_target}', not app_N), so the slot could not be checked. "
                                  "If the installer writes to slot 1, the old app starts instead.\n"
                                  "         With --watch the log line 'Will write to slot N' shows which slot it uses.")
            elif target is None:
                if probe_failed:
                    reason = ""
                elif probe.datagrams == 0:
                    reason = (f" No UDP datagram arrived from the device: check that incoming UDP on port {log_port} is "
                              f"allowed (Windows Firewall: the Python program), and --log-port and --host.")
                else:
                    reason = (f" The device log arrives, but the slot line did not show up within {probe_wait:.0f} s; a "
                              f"device that has just started often needs longer. Wait a minute and send again.")
                say(Level.normal, f"WARNING: the update target slot could not be read.{reason} "
                                  f"If the installer writes to slot 1, the old app starts instead.")
            elif target == 0:
                say(Level.normal, "Update target slot: 0 (the slot ESPHome's bootloader starts).")
            elif ignore_slot:
                say(Level.quiet, f"WARNING: the installer will write to slot {target}, but ESPHome's bootloader starts app_0 "
                                  "(sending anyway because of --ignore-slot).")
            else:
                server.httpd.server_close()
                raise OtaError(
                    f"The installer would write to slot {target}, but ESPHome's bootloader starts app_0, so the old "
                    "firmware would start again. Install the official firmware first; that also puts Shelly's "
                    "bootloader back and moves the stock firmware to the other slot:\n\n"
                    f"  python ota.py restore {profile.name}\n\n"
                    "  Then send again.")
    else:
        say(Level.normal, f"NOTE: no official {profile.name} ZIP cached, so it was not checked whether this package replaces "
                          "Shelly's bootloader. Fetch it and try again, or look at the package with 'ota.py inspect':\n\n"
                          f"  python ota.py fetch {profile.name} --insecure")
    session.expect_new_loader = quiet_about_kept_loader(boot_replaced, keeps_loader, restoring)
    note = secrets_check.report_note(zip_path)
    if note:
        say(Level.quiet if note[0] == "WARNING" else Level.verbose if note[0].startswith("NOTE") else Level.normal,
            f"{note[0]}: {note[1]}")
    # last, so that a refusal (wrong slot, wrong device) does not first cost the wait
    _settle(addr, auth, say=say, ask=ask, sleep=sleep, dry_run=dry_run, assume_yes=assume_yes, live=session.out is ui.say)
    try:
        timeout = _check_wifi(addr, auth, say=say, ask=ask, timeout=timeout, dry_run=dry_run, assume_yes=assume_yes)
    except OtaError:   # cancelled at the question
        server.httpd.server_close()
        raise
    if dry_run:
        server.start()  # the device fetches http://host:port/ from it; the ZIP is not requested
        try:
            state, detail = check_reach(addr, host, server.port, **auth)
        finally:
            server.stop()
        text = reach_text(state, detail, host, server.port)
        if state is False:
            raise OtaError(f"Dry run: {text}")
        say(Level.verbose if state else Level.normal, text if state else f"NOTE: {text}")
        say(Level.normal, "Dry run: nothing sent.")
        return True
    if not assume_yes:
        if "nvs" in manifest["parts"]:
            say(Level.quiet, "WARNING: this wipes NVS (Wi-Fi credentials and settings) and replaces the firmware.")
        if ask("Type 'yes' to flash this device: ").strip().lower() != "yes":
            server.httpd.server_close()
            raise OtaError("Cancelled.")

    def run_update(srv: FileServer) -> bool:
        """One pass: serve the ZIP, tell the device to fetch it, wait for the download and for the device's own
        confirmation. Stops the server at the end."""
        session.reset_result()
        srv.start()
        try:
            state, detail = check_reach(addr, host, srv.port, **auth)
            text = reach_text(state, detail, host, srv.port)
            say(Level.verbose if state else Level.normal,   # never blocks: the download decides
                text if state else f"{'WARNING' if state is False else 'NOTE'}: {text}")
            with contextlib.ExitStack() as stack:
                stats = None
                try:
                    stats = stack.enter_context(logwatch.udp_log(
                        addr, host, log_port, lambda text: say(Level.normal, text), sink=session.device, **auth))
                except OtaError as e:   # the log is a bonus here: without it only the progress and the confirmation are lost
                    say(Level.normal, f"NOTE: the device log is not available ({e}); there is no progress and no "
                                      f"confirmation from the device.")
                trigger = f"http://{addr}/rpc/Shelly.Update?url={urllib.parse.quote(srv.url(host), safe='')}"
                answer = rpc.request(trigger, timeout=30, **auth).decode(errors="replace").strip()
                say(Level.verbose, f"Device accepted the request: {answer or 'ok'}")
                say(Level.verbose, f"Waiting up to {timeout:.0f} s for the device to download the ZIP ...")
                started = time.monotonic()
                deadline = started + timeout
                seen = 0   # bytes sent at the last deadline
                dl = DownloadWatch(srv.size)
                last_sample = 0.0
                told_cap = False
                on_screen = session.out is ui.say
                while not srv.served.wait(0.5):   # short steps, so Ctrl+C works at once (also on Windows)
                    if session.result == "error":
                        break
                    now = time.monotonic()
                    if srv.bytes_sent and now - last_sample >= 1:
                        last_sample = now
                        dl.add(now, srv.bytes_sent)
                        eta = dl.eta()
                        if on_screen and not session.update_seen and eta is not None:   # the device's own bar wins once it shows
                            ui.live(f"Download {dl.percent()} %, about {ui.duration(eta)} left (Ctrl+C to stop)")
                        if eta is not None and now + eta > deadline:
                            limit_end = started + max(max_wait, timeout)
                            wanted = now + eta * 1.25 + 30
                            if wanted > limit_end and not told_cap and now + eta > limit_end:
                                told_cap = True
                                say(Level.normal, f"NOTE: at this speed the download needs about {ui.duration(eta)} more, which is "
                                                  f"beyond the longest wait of {ui.duration(max_wait)} (--max-wait). It will stop then.")
                            if min(wanted, limit_end) > deadline:
                                deadline = min(wanted, limit_end)
                                say(Level.normal, f"NOTE: the device takes the ZIP slowly ({dl.percent()} % after "
                                                  f"{ui.duration(now - started)}, about {ui.duration(eta)} to go): the wait was "
                                                  f"extended to {ui.duration(deadline - started)} in total (--max-wait caps it at "
                                                  f"{ui.duration(max_wait)}).")
                    if time.monotonic() >= deadline:
                        if srv.bytes_sent > seen and not assume_yes:   # the device is still taking it: ask, never decide alone
                            seen = srv.bytes_sent
                            say(Level.normal, f"NOTE: after {time.monotonic() - started:.0f} s the device has taken about "
                                              f"{min(100, 100 * srv.bytes_sent // max(srv.size, 1))} % of the ZIP and is still "
                                              f"downloading (a weak Wi-Fi signal?).")
                            more = ask_seconds(ask, "Wait longer for", timeout)
                            deadline = time.monotonic() + (timeout if more is None else more)
                            continue
                        waited = time.monotonic() - started
                        if srv.bytes_sent:   # it did start: slow, not unreachable
                            raise OtaError(f"The device did not finish the download within {waited:.0f}s (about "
                                           f"{min(100, 100 * srv.bytes_sent // max(srv.size, 1))} % of the ZIP). In the one case seen "
                                           f"the device stayed on its old firmware. A weak Wi-Fi signal is the usual cause: move it closer "
                                           f"or wait longer with --timeout {SLOW_TIMEOUT}.")
                        raise OtaError(f"The device did not download the ZIP within {waited:.0f}s. Check that it can "
                                       f"reach {host}:{srv.port} (firewall, network).")
                if on_screen:
                    ui.live_end()
                if srv.served.is_set():
                    say(Level.normal, "The device downloaded the ZIP and installs it now.")
                sleep(1)
                # The device confirms with its own "update succeeded" a few seconds after the download. That is only known if
                # its log shows an update at all; --watch SEC waits for it up to SEC seconds even without.
                limit = watch if watch > 0 else (RESULT_WAIT if session.update_seen else 0)
                if stats is not None and limit > 0 and not session.finished.is_set():
                    say(Level.verbose, f"Waiting up to {limit:.0f} s for the device to confirm the update ...")
                    give_up = time.monotonic() + limit
                    while not session.finished.wait(0.5):
                        if time.monotonic() >= give_up:
                            break
                if session.finished.is_set():
                    sleep(1)    # the last lines: the restart
                if session.result == "error":
                    raise OtaError(session.error_text or "The device reported an update error.")
                if session.result == "ok":
                    say(Level.quiet, "Done: update installed, the device confirmed it. It now reboots; if it stays silent, "
                                     "disconnect it from power for at least 30 s.")
                else:
                    if session.update_seen:
                        say(Level.normal, f"NOTE: the device did not confirm the update within {limit:.0f} s; its log may "
                                          f"have stopped because it is restarting.")
                    say(Level.quiet, "Done: the device downloaded the ZIP. It now flashes and reboots; if it stays silent, "
                                     "disconnect it from power for at least 30 s.")
                if boot_replaced:
                    say(Level.verbose, "After the first ESPHome boot: the log line 'ota data invalid, no current app. Assuming "
                                       "factory' is expected. The package carried ESPHome's bootloader, so no separate "
                                       "bootloader update is needed.")
                elif keeps_loader:
                    say(Level.quiet, "WARNING: this package keeps Shelly's bootloader: ESPHome gets three starts, then Shelly's "
                                     "loader goes back to the other slot (the old firmware) and keeps it. Only an ESPHome OTA "
                                     f"during those starts changes that, once; see {PLAIN_PACKAGE_DOC}. For a lasting install "
                                     "build with --esphome-factory. The log line 'ota data invalid, no current app. Assuming "
                                     "factory' is expected.")
                else:
                    say(Level.verbose, "After the first ESPHome boot: the log line 'ota data invalid, no current app. Assuming "
                                       "factory' is expected. This package keeps Shelly's bootloader, which counts uncommitted "
                                       "boots and may switch back to the old firmware after a few restarts. For a lasting "
                                       "install build with --esphome-factory (README, 'After the first boot').")
                session.summary()
            return True
        finally:
            srv.stop()

    def run_and_report(srv: FileServer) -> bool:
        """run_update, and after a failure the last lines of the device log (whatever the level). The refusal of the update
        itself explains itself and has nothing in the log worth showing."""
        try:
            return run_update(srv)
        except rpc.RpcError as e:
            if e.method != "Shelly.Update":
                session.dump_tail()
            raise
        except (OtaError, KeyboardInterrupt):
            session.dump_tail()
            raise

    passes = 1
    while True:
        try:
            return run_and_report(server)
        except rpc.RpcError as e:
            if e.method != "Shelly.Update":   # e.g. the log setup failed: not a refusal of the update
                raise
            refusal = explain_update_refusal(e)
            if not (refusal.retryable and not assume_yes and passes < MAX_PASSES):
                stopped = f" Stopped after {passes} attempts." if refusal.retryable and passes >= MAX_PASSES else ""
                raise OtaError(refusal.text + stopped) from e
            say(Level.quiet, f"WARNING: {refusal.text}")
            if ask(f"Wait about {wait:.0f} s and try again? Type 'yes' to wait: ").strip().lower() != "yes":
                raise OtaError(refusal.text) from e
            _wait_with_countdown(wait, lambda text: say(Level.normal, text), sleep, session.out is ui.say)
            # a new pass is a new decision: the first 'yes' does not cover it
            if ask("Type 'yes' to flash this device again: ").strip().lower() != "yes":
                raise OtaError("Cancelled.") from e
            passes += 1
            server = FileServer(zip_path, port)   # the old one is closed; a server cannot be reused
