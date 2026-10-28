#!/usr/bin/env python3
"""Pack an ESPHome app image into an official-style Shelly OTA ZIP (Gen2 ESP32, Gen3 ESP32-C3, Gen4 ESP32-C6).

The app part is replaced; the rest comes from the official Shelly ZIP. With --esphome-factory the bootloader and otadata
are replaced as well.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import zipfile
import textwrap
import zipfile
from pathlib import Path

from shelly_ota import (MODULE_DIR, ble, buildinfo, builder, devicegen, devkit, firmware, lint, logview, logwatch, profile, rpc,
                        secrets_check, sender, ui)
from shelly_ota.logview import Level

LOG_FILE_AUTO = "<auto>"    # --log-file without a path

DESCRIPTION = ("Pack your ESPHome app image into an official-style Shelly OTA ZIP (Gen2 ESP32, Gen3 ESP32-C3, Gen4 ESP32-C6) "
               "and send it to the device.")

# One list for the command groups: it feeds `ota.py -h` and the sub-commands, and a test checks that no command is missing.
COMMANDS = [
    ("Prepare", [
        ("fetch", "get the official firmware ZIP (downloads if missing)"),
        ("add-device", "create a device profile from an official ZIP"),
        ("partition-csv", "write the stock partition table as ESPHome partitions CSV"),
    ]),
    ("Build", [
        ("build", "build an OTA ZIP from your app image"),
    ]),
    ("Deploy", [
        ("send", "send a ZIP to a Shelly (it downloads from this PC)"),
        ("restore", "send the cached official firmware back to a Shelly"),
        ("ble", "Bluetooth: give a device without Wi-Fi (e.g. Zigbee firmware) its Wi-Fi"),
        ("log", "show the live debug log of a Shelly"),
    ]),
    ("Tools", [
        ("inspect", "show and verify an OTA ZIP"),
        ("devkit", "write a flash image of a package for a dev board"),
        ("list", "show devices and cached firmware"),
        ("profiles", "list the device profiles with their revision, check devices/profiles.lock"),
        ("clean", "delete old ZIPs in out/ (shows what, needs --yes)"),
        ("colors", "show every message color once, and whether colors are on"),
    ]),
]
COMMAND_HELP = {name: text for _, items in COMMANDS for name, text in items}

TOP_OPTIONS = [
    ("-h, --help", "show this help"),
    ("--version", "show the version (in a git checkout also branch, commit and date)"),
    ("--color WHEN", "colored messages: auto (default: only in a terminal, not with NO_COLOR), always or never; "
                     "goes before the command"),
]
TYPICAL_RUN = [
    "python ota.py fetch PlugMG3 --insecure",
    "python ota.py build PlugMG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml",
    "python ota.py send PlugMG3 out/PlugMG3-app-<date>.zip --ip <device IP> --watch 120",
]
BEFORE_YOU_FLASH = [
    "A built ZIP can hold your Wi-Fi/API secrets: never share it (build warns; --fail-on-secrets stops).",
    "Applying it wipes NVS (Wi-Fi, settings) unless you --drop nvs.",
    "--esphome-factory replaces Shelly's bootloader. If that does not suit a device, only UART recovers it: keep UART ready.",
    "The installer must write the app to slot 0: send reads the target slot first and tells you to run restore "
    "if it would write to slot 1.",
    "restore works only while Shelly firmware still runs.",
]
RESTORE_HELP = ("note: restore works only while Shelly firmware still runs; a device that already runs\n"
                "ESPHome does not answer (UART is the way back). The official package may reset NVS and\n"
                "otadata: Wi-Fi and settings can be lost.")
PC_GROUP = "this PC"


def cmd_list(args) -> None:
    names = profile.list_devices()
    profiles = {name: profile.load_profile(name) for name in names}
    name_w = max((len(n) for n in names), default=0)
    if args.details:
        title_w = max((len(p.display_name) for p in profiles.values()), default=0)
        for name in names:
            p = profiles[name]
            ui.say(f"{name:{name_w}s}  {p.display_name:{title_w}s}  app size=0x{p.app_slot_size:x}  profile rev {p.revision}")
            for ver in firmware.list_versions(name):
                meta_path = firmware.FW_DIR / name / ver / "meta.json"
                build_id = json.loads(meta_path.read_text(encoding="utf-8")).get("build_id") if meta_path.is_file() else None
                ui.say(f"    fw {ver}  {build_id or ''}")
        return
    # one line per device; the device title is shortened so the line fits the terminal
    width = shutil.get_terminal_size((100, 24)).columns
    rows = [(name, profiles[name].display_name, f"0x{profiles[name].app_slot_size:x}",
             ", ".join(firmware.list_versions(name)) or "-") for name in names]
    slot_w = max((len(r[2]) for r in rows), default=0)
    fw_w = max((len(r[3]) for r in rows), default=0)
    title_w = max(10, min(max((len(r[1]) for r in rows), default=0), width - name_w - slot_w - fw_w - 6))
    for name, title, slot, fws in rows:
        if len(title) > title_w:
            title = title[:title_w - 2] + ".."
        ui.say(f"{name:{name_w}s}  {title:{title_w}s}  {slot:{slot_w}s}  {fws}")
    ui.say("(app slot size and cached firmware versions; --details shows revision and build ids)")


def cmd_colors(args) -> None:
    reason = ui.why_off(args.color, sys.stdout.isatty(), os.environ)
    ui.say(f"Colors are {'OFF: ' + reason if reason else 'ON'} (--color {args.color}). Every line below is one level:")
    ui.say("OK: success")
    ui.say("NOTE: information")
    ui.say("WARNING: a warning")
    ui.say("WARNING: critical warning (for example: this package replaces Shelly's bootloader)")
    ui.say("Error: something failed")
    ui.say("  log| a line of the device's debug log")
    ui.say("plain text, no level")
    ui.say("If raw codes such as [32m show up in front of the words, this console does not understand ANSI "
           "colors: use Windows Terminal, or --color never.")


def cmd_profiles(args) -> None:
    if args.update_lock:
        lock = profile.write_lock()
        ui.say(f"Wrote devices/{profile.LOCK_FILE} ({len(lock)} profiles)")
    names = profile.list_devices()
    name_w = max((len(n) for n in names), default=0)
    for name in names:
        ui.say(f"{name:{name_w}s}  revision {profile.load_profile(name).revision:<3d} content {profile.content_hash(name)}")
    problems = profile.check_lock()
    for problem in problems:
        ui.say(f"WARNING: {problem}")
    if problems:
        raise builder.OtaError(f"{len(problems)} profile problem(s); see above.")


def _fetch_official(p, *, refresh=False, version=None, insecure=False, channel="stable", from_version=None):
    """Fetch for a profile; variants (profile.parent) are looked up in their parent's update reply."""
    channel = "beta" if p.channel == "beta" else channel  # a -beta profile is for the beta channel
    if p.parent:
        parent = profile.load_profile(p.parent)
        return firmware.fetch(p.package_name, parent.update_id, refresh=refresh, version=version,
                              insecure=insecure, alt=p.update_id, channel=channel,
                              from_version=from_version)
    return firmware.fetch(p.package_name, p.update_id, refresh=refresh, version=version, insecure=insecure,
                          channel=channel, from_version=from_version)


def cmd_fetch(args) -> None:
    p = profile.load_profile(args.device)
    path = _fetch_official(p, refresh=args.refresh, version=args.version, insecure=args.insecure,
                           channel=args.channel, from_version=args.from_version)
    ui.say(f"Official firmware: {path}")
    with zipfile.ZipFile(path) as zf:
        for problem in builder.package_layout_problems(p, zf, builder.read_official_manifest(zf)):
            ui.say(f"WARNING: this package has another flash layout than the {p.name} profile: {problem}. "
                   f"`build` refuses it.")


def cmd_add_device(args) -> None:
    path, info = devicegen.create_profile(args.zip, name=args.name, force=args.force, parent=args.parent)
    firmware.store_zip(info["name"], args.zip.read_bytes(), source=f"local file: {args.zip.name}")
    ui.say(f"Wrote {path.name}: {info['ptn']} @0x{info['slot_offset']:x}, slot 0x{info['slot_size']:x}")
    ui.say(f"Stored the ZIP in {firmware.FW_DIR / info['name']}")


def cmd_partition_csv(args) -> None:
    p = profile.load_profile(args.device)
    official = args.official or firmware.cached_zip(p.package_name, args.version, prerelease=p.channel == "beta")
    if official is None:
        raise builder.OtaError(f"No official {p.name} ZIP cached. Run 'ota.py fetch {p.name}' first, or pass --official <zip>.")
    text = devicegen.partition_csv(official)
    if args.output:
        if args.output.exists() and not args.force:
            raise builder.OtaError(f"{args.output} already exists (use --force to overwrite).")
        args.output.write_text(text, encoding="utf-8")
        ui.say(f"Wrote {args.output}")
    else:
        print(text, end="")


def cmd_devkit(args) -> None:
    p = profile.load_profile(args.device)
    source = args.zip or firmware.cached_zip(p.package_name, args.version, prerelease=p.channel == "beta")
    if source is None:
        raise builder.OtaError(f"No official {p.name} ZIP cached. Run 'ota.py fetch {p.name}' first, or pass --zip <package>.")
    image = devkit.build_image(source, p, flash_size=args.flash_size)
    output = args.output or MODULE_DIR / "out" / f"{p.name}-devkit-{image.version}.bin"
    if output.exists() and not args.force:
        raise builder.OtaError(f"{output} already exists (use --force to overwrite).")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image.data)
    ui.say(devkit.summary(image, output, source, args.port))
    note = secrets_check.report_note(source) if args.zip else None
    if note:
        ui.say(f"{note[0]}: {note[1]}")


def cmd_build(args) -> None:
    p = profile.load_profile(args.device)
    # The automatic name only carries app file name, date and tag: two builds on one day get the same one, and ESPHome
    # always calls the app firmware.ota.bin. An existing package may already be on a device, so it is never replaced
    # silently (a name given with -o is deliberate and is overwritten, as before).
    output = args.output or MODULE_DIR / "out" / builder.default_output_name(p, args.app, tag=builder.check_tag(args.tag))
    would_replace = output.exists() and args.output is None and not args.force
    if would_replace and not args.dry_run:
        raise builder.OtaError(f"{output} already exists. Use --tag LABEL or -o ZIP for another name, or --force to replace it.")
    if args.esphome_yaml:
        problems = lint.lint_esphome(args.esphome_yaml, p)
        if problems:
            raise builder.OtaError("ESPHome config check failed:\n  - " + "\n  - ".join(problems))
        ui.say(f"ESPHome config check OK ({args.esphome_yaml.name})")
        for w in lint.lint_warnings(args.esphome_yaml, bootloader_shipped=bool(args.esphome_factory)):
            ui.say(f"  WARNING: {w}")
    secrets = None
    if args.esphome_yaml or args.secrets:
        secrets, problem = secrets_check.collect(args.esphome_yaml, args.secrets)
        if problem:
            secrets = None
    drop = tuple(x for x in args.drop.split(",") if x)
    if args.drop_fs:
        drop += ("fs",)
    official = args.official or firmware.cached_zip(p.package_name, args.version, prerelease=p.channel == "beta")
    if official is None:
        if not args.download:
            raise builder.OtaError(
                f"No official {p.name} ZIP in {firmware.FW_DIR / p.name}. Put one there, pass --official <zip>, "
                f"run 'ota.py fetch {p.name}', or add --download to build.")
        official = _fetch_official(p, version=args.version, insecure=args.insecure, channel=args.channel,
                                  from_version=args.from_version)

    def run_build(target: Path) -> builder.BuildResult:
        return builder.build(p, args.app, official, target, drop=drop, tag=args.tag, factory=args.esphome_factory,
                             boot_min_version=args.boot_min_version, secrets=secrets,
                             fail_on_secrets=args.fail_on_secrets)

    if args.dry_run:
        # Build in a scratch directory, so that an existing package (or its .sha256 and .report.json) stays untouched.
        builder.check_output_is_no_input(output, official, args.app)
        with tempfile.TemporaryDirectory(prefix="free-shelly-ota-dryrun-") as dryrun:
            result = run_build(Path(dryrun) / output.name)
        ui.say(f"DRY RUN, nothing written (a real build would write {output})")
        if would_replace:
            ui.say(f"  NOTE: {output.name} already exists, so a real build would stop here. "
                   f"Use --tag LABEL or -o ZIP for another name, or --force to replace it.")
    else:
        result = run_build(output)
        builder.write_report(result)
        ui.say(f"OK: {result.output}")
    ui.say(f"  base firmware {result.official_version} ({result.official_build_id}), "
          f"app {result.app_size} bytes, parts {result.parts}")
    if result.secrets_found == []:
        ui.say(f"  Credential check OK: none of {len(secrets)} known values found in the image")
    for w in result.warnings:
        ui.say(f"  {'WARNING' if w.startswith(('CREDENTIALS', 'BOOTLOADER', 'Credentials were not')) else 'NOTE'}: {w}")
    if not args.dry_run and result.secrets_found != [] and secrets_check.git_would_track(output):
        ui.say(f"  WARNING: {output} is inside a git work tree and not ignored there; git add would pick up this package.")


def _level(args, default: Level) -> Level:
    """--log-level wins over -q, which wins over -v / -vv."""
    name = getattr(args, "log_level", None)
    if name:
        return Level[name]
    if getattr(args, "quiet", False):
        return Level.quiet
    verbose = getattr(args, "verbose", 0) or 0
    return default if verbose == 0 else Level.verbose if verbose == 1 else Level.debug


def _open_logfile(args, level: Level, default_name: str) -> logview.LogFile | None:
    """--log-file: the whole run in a file, whatever the console level. Without a path: logs/<default_name>."""
    value = getattr(args, "log_file", None)
    if value is None:
        return None
    path = MODULE_DIR / "logs" / default_name if value == LOG_FILE_AUTO else Path(value)
    logfile = logview.LogFile(path)
    logfile.write("tool", f"free-shelly-ota {buildinfo.current().short()}")
    if level >= Level.normal:
        ui.say(f"Writing the full log to {path}")
    return logfile


def _send(args, zip_path: Path, log_name: str | None = None, restoring: bool = False) -> None:
    p = profile.load_profile(args.device)
    level = _level(args, Level.normal)
    logfile = _open_logfile(args, level, log_name or f"{zip_path.stem}.send.log")
    try:
        sender.send(p, zip_path, args.ip, host=args.host, port=args.port, timeout=args.timeout, max_wait=getattr(args, "max_wait", sender.MAX_WAIT),
                    assume_yes=args.yes, dry_run=args.dry_run, force=args.force, user=args.user,
                    password=args.password, watch=args.watch, log_port=args.log_port, ignore_slot=args.ignore_slot,
                    wait=getattr(args, "wait", sender.DEFAULT_WAIT), restoring=restoring, level=level, logfile=logfile)
    finally:
        if logfile:
            logfile.close()


def cmd_send(args) -> None:
    _send(args, args.zip)


RESTORE_NOTE = """NOTE: restore sends the cached official package. It only works while the Shelly firmware is still running. A device
      that already runs ESPHome does not answer; the way back is then UART, with a flash backup."""
RESTORE_SLOT_NOTE = """NOTE: If ESPHome's bootloader is installed, the installer writes Shelly's bootloader back and moves the stock firmware to
      the other slot. That is also what `send` needs when it reports that the installer would write to slot 1."""


def cmd_restore(args) -> None:
    p = profile.load_profile(args.device)
    zip_path = firmware.cached_zip(p.package_name, args.version, prerelease=p.channel == "beta")
    if zip_path is None:
        raise builder.OtaError(f"No official {args.device} ZIP cached. Run 'ota.py fetch {args.device}' first.")
    ui.say(f"Restoring the official firmware from {zip_path}")
    ui.say(RESTORE_NOTE)
    if _level(args, Level.normal) >= Level.verbose:
        ui.say(RESTORE_SLOT_NOTE)
    try:
        _send(args, zip_path, f"{args.device}.restore.log", restoring=True)
    except rpc.DeviceUnreachable as e:
        raise builder.OtaError(f"{e}\n  Is the Shelly firmware still running? A device with ESPHome on it "
                               f"cannot be restored this way; use UART (see the note above).") from e


def cmd_ble(args) -> None:
    rest = args.args
    if args.action == "scan":
        found = ble.scan()
        if not found:
            raise builder.OtaError("No Shelly found over Bluetooth. Is it powered and close by, and is BLE RPC on?")
        for f in found:
            ui.say(f"{f.address}  {f.name}  {f.rssi} dBm")
        return
    expected = {"info": (0, 0), "call": (1, 2), "wifi": (1, 2)}[args.action]
    if not expected[0] <= len(rest) <= expected[1]:
        raise builder.OtaError({"info": "info takes no argument.", "call": "call needs METHOD and optionally a JSON object.",
                                "wifi": "wifi needs SSID and optionally PASSWORD ('-' asks for it without showing it)."}[args.action])
    address = args.address
    if not address:
        found = ble.find_device()
        address = found.address
        ui.say(f"Using {found.name or 'the Shelly'} ({address}, {found.rssi} dBm)")
    if args.action == "wifi":
        ssid, password = rest[0], rest[1] if len(rest) > 1 else ""
        if password == "-":
            import getpass
            password = getpass.getpass("Wi-Fi password: ")
        ip = ble.provision_wifi(address, ssid, password, wait=0 if args.no_wait else args.wait)
        if ip:
            ui.say(f"The device joined {ssid} and has the address {ip}.")
            ui.say(f"Next: python ota.py send DEVICE ZIP --ip {ip}   (restore first if send reports slot 1)")
        else:
            ui.say(f"Wi-Fi {ssid} is set. Ask for the address with: python ota.py ble call Wifi.GetStatus -a {address}")
        return
    method = "Shelly.GetDeviceInfo" if args.action == "info" else rest[0]
    try:
        params = json.loads(rest[1]) if args.action == "call" and len(rest) > 1 else None
    except ValueError as e:
        raise builder.OtaError(f"The parameters are not JSON: {e}") from e
    print(json.dumps(ble.rpc(address, method, params, timeout=args.timeout), indent=2))


def cmd_log(args) -> None:
    session = logview.Session(level=_level(args, Level.debug), out=ui.say)
    if args.replay:     # a saved log (from --log-file, or the output of --log-level raw), no device needed
        logview.replay(args.replay, session)
        session.summary()
        return
    host = args.host or sender.local_ip_for(args.ip)
    logwatch.watch(args.ip, host, args.log_port, args.seconds, sink=session.device, user=args.user,
                   password=args.password)
    session.summary()


def cmd_clean(args) -> None:
    out_dir = MODULE_DIR / "out"
    zips = sorted(out_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    old = zips[args.keep:]
    if not old:
        ui.say(f"Nothing to remove ({len(zips)} ZIP(s) in out/, keeping {args.keep}).")
        return
    for z in old:
        for f in [z, *out_dir.glob(z.name + ".*")]:
            ui.say(f"{'removing' if args.yes else 'would remove'}: {f.name}")
            if args.yes:
                f.unlink()
    if not args.yes:
        ui.say("Nothing deleted. Add --yes to delete.")


def cmd_inspect(args) -> None:
    p = profile.load_profile(args.device) if args.device else None
    ui.say(builder.inspect_zip(args.zip, p))
    note = secrets_check.report_note(args.zip)
    if note:
        ui.say(f"  {note[0]}: {note[1]}")


def device_options() -> argparse.ArgumentParser:
    """Options shared by every command that talks to a Shelly."""
    o = argparse.ArgumentParser(add_help=False)
    g = o.add_argument_group("the Shelly")
    g.add_argument("--ip", default=sender.DEFAULT_IP, metavar="IP", help="Shelly address (default: %(default)s)")
    g.add_argument("--user", default="admin", help="login, if the device has a password (default: %(default)s)")
    g.add_argument("--password", metavar="PW", help="device password")
    g = o.add_argument_group(PC_GROUP)
    g.add_argument("--host", metavar="IP", help="this PC's address as seen by the Shelly (default: auto)")
    g.add_argument("--log-port", type=int, default=9514, metavar="PORT", help="UDP port for the device log (default: %(default)s)")
    return o


def level_options() -> argparse.ArgumentParser:
    """How much is shown: the tool's own messages and the device log."""
    o = argparse.ArgumentParser(add_help=False)
    o.add_argument("--log-level", choices=logview.LEVEL_NAMES, metavar="LEVEL",
                   help="quiet (errors and the result), normal (+ warnings, key lines, progress), verbose (+ notes, every step "
                        "of the update), debug (every device log entry), raw (the device log as it arrives); default: "
                        "normal, for 'log' debug")
    o.add_argument("-q", "--quiet", action="store_true", help="same as --log-level quiet")
    o.add_argument("-v", "--verbose", action="count", default=0, help="-v is --log-level verbose, -vv is debug")
    return o


def send_options() -> argparse.ArgumentParser:
    o = argparse.ArgumentParser(add_help=False)
    g = o.add_argument_group(PC_GROUP)
    g.add_argument("--port", type=int, default=8000, help="web server port the Shelly downloads from (default: %(default)s)")
    g = o.add_argument_group("what to do")
    g.add_argument("--dry-run", action="store_true", help="check the device, send nothing")
    g.add_argument("--yes", action="store_true", help="do not ask before flashing")
    g.add_argument("--force", action="store_true",
                   help="send even if the device model does not match, or the package keeps Shelly's bootloader (no --esphome-factory)")
    g.add_argument("--ignore-slot", action="store_true",
                   help="send even if the installer would write to a slot that ESPHome's bootloader does not start")
    g.add_argument("--watch", type=float, default=0, metavar="SEC",
                   help="after the download keep listening up to SEC seconds for the device to confirm the update "
                        "(default: 30 s if the device log shows an update)")
    g.add_argument("--log-file", nargs="?", const=LOG_FILE_AUTO, metavar="PATH",
                   help="write the whole run (every message, every device log entry) to a file, whatever the log level; "
                        "without a path to logs/<name>.send.log. Put it after DEVICE and ZIP, or use --log-file=PATH")
    g.add_argument("--timeout", type=float, default=300, metavar="SEC", help="wait for the download (default: %(default)s); a weak Wi-Fi signal can need much more, send asks")
    g.add_argument("--max-wait", type=float, default=sender.MAX_WAIT, metavar="SEC",
                   help="if the device downloads slowly but steadily, the wait is extended on its own, up to SEC in total (default: %(default)s)")
    g.add_argument("--wait", type=float, default=sender.DEFAULT_WAIT, metavar="SEC",
                   help="if the device refuses the update because it has only just started ('Not committed'): wait SEC "
                        "seconds, then ask again before the next try (default: %(default)s)")
    return o


class _VersionAction(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, default=argparse.SUPPRESS, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        print(f"{parser.prog} {buildinfo.current().short()}")
        parser.exit()


def _width() -> int:
    return ui.width()


def _rows(rows, indent: int, width: int, first_col: int) -> list[str]:
    """Two-column rows (name, text) with the text wrapped under itself."""
    out = []
    for name, text in rows:
        wrapped = textwrap.wrap(text, width - indent - first_col) or [""]
        out.append(f"{' ' * indent}{name:<{first_col}}{wrapped[0]}")
        out += [" " * (indent + first_col) + w for w in wrapped[1:]]
    return out


def top_help(usage: str, width: int | None = None) -> str:
    """The help of `ota.py -h`: commands in groups, a typical run and what to know before flashing."""
    width = width or _width()
    name_w = max(len(n) for _, items in COMMANDS for n, _ in items) + 3
    lines = [usage.rstrip(), ""] + textwrap.wrap(DESCRIPTION, width) + ["", "commands:"]
    for group, items in COMMANDS:
        lines.append(f"  {group}")
        lines += _rows(items, 4, width, name_w)
    lines += ["", "options:"] + _rows(TOP_OPTIONS, 2, width, 16)
    lines += ["", "typical run:"] + [f"  {c}" for c in TYPICAL_RUN]
    lines += ["", "before you flash:"]
    for item in BEFORE_YOU_FLASH:
        lines += textwrap.wrap(item, width, initial_indent="  - ", subsequent_indent="    ")
    lines += [""] + textwrap.wrap(", ".join(profile.list_devices()), width, initial_indent="devices: ",
                                  subsequent_indent="         ")
    lines += ["         (python ota.py list shows them with the cached firmware)"]
    lines += ["details: python ota.py <command> -h  (options of one command), docs/commands.md"]
    return "\n".join(lines) + "\n"


class _TopParser(argparse.ArgumentParser):
    """Parser of `ota.py` itself: only the help text is its own, parsing and errors are argparse's."""

    def format_help(self) -> str:
        return top_help(self.format_usage())


def _epilog(example: str, anchor: str, note: str = "") -> str:
    text = f"example: python ota.py {example}"
    if note:
        text += "\n\n" + note
    return text + f"\n\ndetails: docs/commands.md#{anchor}"


def _command(sub, name: str, *, usage: str | None = None, epilog: str | None = None, parents=()):
    return sub.add_parser(name, help=COMMAND_HELP[name], description=COMMAND_HELP[name], usage=usage, epilog=epilog,
                          parents=list(parents), formatter_class=argparse.RawDescriptionHelpFormatter)


def build_parser() -> argparse.ArgumentParser:
    ap = _TopParser(prog="ota.py", description=DESCRIPTION)
    ap.add_argument("--version", action=_VersionAction, help="show the version and, in a git checkout, branch, commit and date")
    ap.add_argument("--color", choices=["auto", "always", "never"], default="auto", metavar="WHEN",
                    help="colored messages (default: auto = only in a terminal, and not with NO_COLOR set). "
                         "Put it before the command.")
    sub = ap.add_subparsers(dest="cmd", required=True, title="commands", metavar="<command>", parser_class=argparse.ArgumentParser)
    dev_help = "profile name (python ota.py list shows them)"
    dev, snd, lvl = device_options(), send_options(), level_options()

    f = _command(sub, "fetch", usage="ota.py fetch DEVICE [options]", epilog=_epilog("fetch DuoBulbG3 --insecure", "fetch"))
    f.add_argument("device", metavar="DEVICE", help=dev_help)
    g = f.add_argument_group("cache")
    g.add_argument("--version", metavar="VER", help="use this cached version")
    g.add_argument("--refresh", action="store_true", help="check for a newer version even if cached")
    g = f.add_argument_group("update API")
    g.add_argument("--channel", choices=["stable", "beta"], default="stable",
                   help="release channel of the update API (default: %(default)s)")
    g.add_argument("--from-version", metavar="VER",
                   help="ask the update API as a device running VER would (e.g. 1.4.4 gets the 2.0.1 stable step)")
    g.add_argument("--insecure", action="store_true", help="skip TLS check (Shelly uses a private CA)")
    f.set_defaults(func=cmd_fetch)

    a = _command(sub, "add-device", epilog=_epilog("add-device NewDevice.zip", "add-device"))
    a.add_argument("zip", type=Path, metavar="ZIP", help="official Shelly OTA ZIP")
    a.add_argument("--name", help="device name (default: name in the ZIP)")
    a.add_argument("--parent", metavar="DEVICE", help="base device, if this is a variant (e.g. PlugUSG4 for PlugUSG4ZB)")
    a.add_argument("--force", action="store_true", help="overwrite an existing profile")
    a.set_defaults(func=cmd_add_device)

    pc = _command(sub, "partition-csv", usage="ota.py partition-csv DEVICE [options]",
                  epilog=_epilog("partition-csv HTG3 -o HTG3-stock.csv", "partition-csv"))
    pc.add_argument("device", metavar="DEVICE", help=dev_help)
    g = pc.add_argument_group("output")
    g.add_argument("-o", "--output", type=Path, metavar="CSV", help="write to this file (default: print)")
    g.add_argument("--force", action="store_true", help="overwrite an existing output file")
    g = pc.add_argument_group("base firmware")
    g.add_argument("--official", type=Path, metavar="ZIP", help="use this official ZIP instead of the cache")
    g.add_argument("--version", metavar="VER", help="use this cached version (default: the newest stable one)")
    pc.set_defaults(func=cmd_partition_csv)

    dk = _command(sub, "devkit", usage="ota.py devkit DEVICE [options]",
                  epilog=_epilog("devkit PlusUni", "devkit",
                                 "Writes out/<Device>-devkit-<version>.bin and prints the esptool commands. It flashes nothing itself."))
    dk.add_argument("device", metavar="DEVICE", help=dev_help)
    g = dk.add_argument_group("package")
    g.add_argument("--zip", type=Path, metavar="ZIP",
                   help="use this package instead of the cached official one (your own build gives the state after an install)")
    g.add_argument("--version", metavar="VER", help="use this cached official version (default: the newest stable one)")
    g = dk.add_argument_group("image")
    g.add_argument("-o", "--output", type=Path, metavar="BIN", help="write to this file (default: out/<Device>-devkit-<version>.bin)")
    g.add_argument("--force", action="store_true", help="overwrite an existing output file")
    g.add_argument("--flash-size", choices=list(devkit.FLASH_SIZES), metavar="SIZE",
                   help="stop if the layout needs more flash than the board has: 4MB, 8MB or 16MB")
    g.add_argument("--port", default="COMx", metavar="PORT", help="serial port in the printed esptool commands (default: %(default)s)")
    dk.set_defaults(func=cmd_devkit)

    b = _command(sub, "build", usage="ota.py build DEVICE APP.bin [options]",
                 epilog=_epilog("build PlugMG3 app.ota.bin --esphome-factory app.factory.bin", "build"))
    b.add_argument("device", metavar="DEVICE", help=dev_help)
    b.add_argument("app", type=Path, metavar="APP.bin", help="ESPHome app binary (the .ota.bin, not the merged image)")
    g = b.add_argument_group("app and bootloader")
    g.add_argument("--esphome-factory", type=Path, metavar="FACTORY.bin",
                   help="also swap in ESPHome's bootloader and a clean otadata from this factory image (same build as "
                        "APP.bin). Replaces Shelly's bootloader: only UART recovers a device it does not suit")
    g.add_argument("--boot-min-version", metavar="VER",
                   help="with --esphome-factory: bootloader min_version in the manifest (default: the profile's value, "
                        "else one patch above the official one). 'update? 0' in the log: use a higher value; "
                        "'keep' leaves it unchanged")
    g.add_argument("--esphome-yaml", type=Path, metavar="YAML", help="also check this ESPHome config")
    g = b.add_argument_group("secrets")
    g.add_argument("--secrets", type=Path, metavar="FILE",
                   help="secrets.yaml to compare the image with (default: next to --esphome-yaml)")
    g.add_argument("--fail-on-secrets", action="store_true",
                   help="stop if the image contains credentials (default: only warn); use it for packages meant to be shared")
    g = b.add_argument_group("output")
    g.add_argument("-o", "--output", type=Path, metavar="ZIP", help="output file (default: out/<auto name>)")
    g.add_argument("--tag", metavar="LABEL", help="own label for file name and report (manifest unchanged)")
    g.add_argument("--dry-run", action="store_true", help="check only, write nothing (an existing output is left alone)")
    g.add_argument("--force", action="store_true",
                   help="replace the automatically named output if it already exists (default: stop; a name given "
                        "with -o is always replaced)")
    g = b.add_argument_group("parts")
    g.add_argument("--drop", default="", metavar="LIST", help="leave out parts: boot,pt,otadata,nvs,fs")
    g.add_argument("--drop-fs", action="store_true", help="same as --drop fs")
    g = b.add_argument_group("base firmware")
    g.add_argument("--official", type=Path, metavar="ZIP", help="use this official ZIP")
    g.add_argument("--version", metavar="VER", help="use this cached version (default: the newest stable one)")
    g.add_argument("--download", action="store_true", help="download if nothing is cached")
    g.add_argument("--insecure", action="store_true", help="with --download: skip TLS check")
    g.add_argument("--channel", choices=["stable", "beta"], default="stable",
                   help="with --download: release channel of the update API (default: %(default)s)")
    g.add_argument("--from-version", metavar="VER", help="with --download: ask the update API as a device running VER would")
    b.set_defaults(func=cmd_build)

    t = _command(sub, "send", usage="ota.py send DEVICE ZIP [options]", parents=[dev, snd, lvl],
                 epilog=_epilog("send DuoBulbG3 out/DuoBulbG3-app-<date>.zip --ip 192.168.1.50 --dry-run", "send"))
    t.add_argument("device", metavar="DEVICE", help=dev_help)
    t.add_argument("zip", type=Path, metavar="ZIP", help="the package made by build")
    t.set_defaults(func=cmd_send)

    r = _command(sub, "restore", usage="ota.py restore DEVICE [options]", parents=[dev, snd, lvl],
                 epilog=_epilog("restore DuoBulbG3 --ip 192.168.1.50", "restore", RESTORE_HELP))
    r.add_argument("device", metavar="DEVICE", help=dev_help)
    g = r.add_argument_group("firmware")
    g.add_argument("--version", metavar="VER", help="cached version (default: the newest stable one)")
    r.set_defaults(func=cmd_restore)

    bl = _command(sub, "ble", usage="ota.py ble {scan,info,call,wifi} [ARG ...] [options]",
                  epilog=_epilog("ble wifi MyNetwork -", "ble",
                                 "scan: the Shellies in range.  info: Shelly.GetDeviceInfo.\n"
                                 "call METHOD [JSON]: any RPC method.\n"
                                 "wifi SSID [PASSWORD]: set the Wi-Fi and wait for the address ('-' asks for\n"
                                 "the password).\n"
                                 "Needs: pip install bleak, and a Bluetooth LE adapter."))
    bl.add_argument("action", choices=["scan", "info", "call", "wifi"])
    bl.add_argument("args", nargs="*", metavar="ARG", help="call: METHOD [JSON]; wifi: SSID [PASSWORD]")
    g = bl.add_argument_group("the Shelly")
    g.add_argument("-a", "--address", metavar="ADDR", help="Bluetooth address (default: the strongest Shelly in range)")
    g = bl.add_argument_group("what to do")
    g.add_argument("--timeout", type=float, default=15.0, metavar="SEC", help="wait for an answer (default: %(default)s)")
    g.add_argument("--wait", type=float, default=40.0, metavar="SEC", help="wifi: wait for the address up to SEC (default: %(default)s)")
    g.add_argument("--no-wait", action="store_true", help="wifi: do not wait for the address")
    bl.set_defaults(func=cmd_ble)

    lg = _command(sub, "log", usage="ota.py log [options]", parents=[dev, lvl],
                  epilog=_epilog("log --ip 192.168.1.50 --seconds 30", "log"))
    g = lg.add_argument_group("what to do")
    g.add_argument("--seconds", type=float, metavar="SEC", help="stop after SEC seconds (default: Ctrl+C)")
    g.add_argument("--replay", type=Path, metavar="FILE",
                   help="no device: show a saved log (a --log-file file, or the output of --log-level raw) at the chosen level")
    lg.set_defaults(func=cmd_log)

    i = _command(sub, "inspect", usage="ota.py inspect ZIP [--device DEVICE]")
    i.add_argument("zip", type=Path, metavar="ZIP")
    i.add_argument("--device", metavar="DEVICE", help="also show how full the app slot is")
    i.set_defaults(func=cmd_inspect)

    ls = _command(sub, "list", usage="ota.py list [--details]")
    ls.add_argument("--details", "--all", action="store_true", help="two lines per device: profile revision and firmware build ids")
    ls.set_defaults(func=cmd_list)

    pr = _command(sub, "profiles")
    pr.add_argument("--update-lock", action="store_true",
                    help="record the current revision and content of every profile (after raising a revision)")
    pr.set_defaults(func=cmd_profiles)

    c = _command(sub, "clean", usage="ota.py clean [--keep N] [--yes]")
    c.add_argument("--keep", type=int, default=5, metavar="N", help="newest ZIPs to keep (default: %(default)s)")
    c.add_argument("--yes", action="store_true", help="really delete")
    c.set_defaults(func=cmd_clean)

    _command(sub, "colors").set_defaults(func=cmd_colors)
    return ap


def main() -> None:
    args = build_parser().parse_args()
    ui.configure(args.color)
    quiet = getattr(args, "quiet", False) or getattr(args, "log_level", None) == "quiet"
    if not quiet and not (args.func is cmd_partition_csv and not args.output):   # that command prints data to stdout
        ui.say(f"free-shelly-ota {buildinfo.current().short()}")
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        sys.exit(130)
    except EOFError:
        sys.exit(ui.error("No answer: the input was closed."))
    except (builder.OtaError, profile.ProfileError, zipfile.BadZipFile, json.JSONDecodeError, OSError) as e:
        sys.exit(ui.error(e))
    except KeyboardInterrupt:
        sys.exit(ui.error("Interrupted (Ctrl+C)."))


if __name__ == "__main__":
    main()
