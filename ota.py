#!/usr/bin/env python3
"""Pack an ESPHome app image into an official-style Shelly OTA ZIP (Gen2 ESP32, Gen3 ESP32-C3, Gen4 ESP32-C6).

The app part is replaced; the rest comes from the official Shelly ZIP. With --esphome-factory the bootloader and otadata
are replaced as well.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from shelly_ota import (MODULE_DIR, buildinfo, builder, devicegen, firmware, lint, logwatch, profile, secrets_check,
                        sender, ui)

EPILOG = """\
examples:
  python ota.py list
  python ota.py build PlugMG3 app.bin
  python ota.py build PlugMG3 app.bin --tag v2 --drop nvs
  python ota.py build PlugMG3 firmware.ota.bin --esphome-factory firmware.factory.bin   # recommended first install
  python ota.py send PlugMG3 out/PlugMG3-app-20261004.zip --watch 60
  python ota.py inspect out/PlugMG3-app-20261004.zip

A built package contains your Wi-Fi/API credentials in plain text if the config has them. build compares the image with
--esphome-yaml/secrets.yaml and warns (--fail-on-secrets stops); never share such a ZIP.
Applying a built ZIP wipes NVS (Wi-Fi, settings) unless you --drop nvs.
Bootloader: by default Shelly's bootloader stays. --esphome-factory swaps in ESPHome's (and a clean otadata) so later
ESPHome OTAs work. It worked on the devices marked as confirmed in the README; if it does not suit a device only UART can
recover it. The installer must also write the app to slot 0: send checks the target slot first and tells you to run
restore (the official firmware) before sending again if it would write to slot 1.
restore only works while the Shelly firmware still runs; a device already on ESPHome needs UART.
Details per command: python ota.py <command> -h
"""


def cmd_list(args) -> None:
    for name in profile.list_devices():
        p = profile.load_profile(name)
        ui.say(f"{name:12s} {p.display_name:24s} app size=0x{p.app_slot_size:x}  profile rev {p.revision}")
        for ver in firmware.list_versions(name):
            meta_path = firmware.FW_DIR / name / ver / "meta.json"
            build_id = json.loads(meta_path.read_text(encoding="utf-8")).get("build_id") if meta_path.is_file() else None
            ui.say(f"    fw {ver}  {build_id or ''}")


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
    for name in profile.list_devices():
        ui.say(f"{name:12s} revision {profile.load_profile(name).revision:<3d} content {profile.content_hash(name)}")
    problems = profile.check_lock()
    for problem in problems:
        ui.say(f"WARNING: {problem}")
    if problems:
        raise builder.OtaError(f"{len(problems)} profile problem(s); see above.")


def _fetch_official(p, *, refresh=False, version=None, insecure=False):
    """Fetch for a profile; variants (profile.parent) are looked up in their parent's update reply."""
    if p.parent:
        parent = profile.load_profile(p.parent)
        return firmware.fetch(p.name, parent.update_id, refresh=refresh, version=version,
                              insecure=insecure, alt=p.update_id)
    return firmware.fetch(p.name, p.update_id, refresh=refresh, version=version, insecure=insecure)


def cmd_fetch(args) -> None:
    p = profile.load_profile(args.device)
    path = _fetch_official(p, refresh=args.refresh, version=args.version, insecure=args.insecure)
    ui.say(f"Official firmware: {path}")


def cmd_add_device(args) -> None:
    path, info = devicegen.create_profile(args.zip, name=args.name, force=args.force, parent=args.parent)
    firmware.store_zip(info["name"], args.zip.read_bytes(), source=f"local file: {args.zip.name}")
    ui.say(f"Wrote {path.name}: {info['ptn']} @0x{info['slot_offset']:x}, slot 0x{info['slot_size']:x}")
    ui.say(f"Stored the ZIP in {firmware.FW_DIR / info['name']}")


def cmd_partition_csv(args) -> None:
    p = profile.load_profile(args.device)
    official = args.official or firmware.cached_zip(p.name, args.version)
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


def cmd_build(args) -> None:
    p = profile.load_profile(args.device)
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
    official = args.official or firmware.cached_zip(p.name, args.version)
    if official is None:
        if not args.download:
            raise builder.OtaError(
                f"No official {p.name} ZIP in {firmware.FW_DIR / p.name}. Put one there, pass --official <zip>, "
                f"run 'ota.py fetch {p.name}', or add --download to build.")
        official = _fetch_official(p, version=args.version, insecure=args.insecure)
    output = args.output or MODULE_DIR / "out" / builder.default_output_name(p, args.app, tag=builder.check_tag(args.tag))
    result = builder.build(p, args.app, official, output, drop=drop, tag=args.tag, factory=args.esphome_factory,
                           boot_min_version=args.boot_min_version, secrets=secrets,
                           fail_on_secrets=args.fail_on_secrets)
    if not args.dry_run:
        builder.write_report(result)
    else:
        output.unlink()
    ui.say(f"{'DRY RUN, removed: ' if args.dry_run else 'OK: '}{result.output}")
    ui.say(f"  base firmware {result.official_version} ({result.official_build_id}), "
          f"app {result.app_size} bytes, parts {result.parts}")
    if result.secrets_found == []:
        ui.say(f"  Credential check OK: none of {len(secrets)} known values found in the image")
    for w in result.warnings:
        ui.say(f"  {'WARNING' if w.startswith(('CREDENTIALS', 'BOOTLOADER', 'Credentials were not')) else 'NOTE'}: {w}")
    if not args.dry_run and result.secrets_found != [] and secrets_check.git_would_track(output):
        ui.say(f"  WARNING: {output} is inside a git work tree and not ignored there; git add would pick up this package.")


def _send(args, zip_path: Path) -> None:
    p = profile.load_profile(args.device)
    sender.send(p, zip_path, args.ip, host=args.host, port=args.port, timeout=args.timeout,
                assume_yes=args.yes, dry_run=args.dry_run, force=args.force, user=args.user,
                password=args.password, watch=args.watch, log_port=args.log_port, ignore_slot=args.ignore_slot)


def cmd_send(args) -> None:
    _send(args, args.zip)


RESTORE_NOTE = """NOTE: restore sends the cached official package. It only works while the Shelly firmware is still running (only it
      understands Shelly.Update); a device that already runs ESPHome does not answer, and the way back is then UART with a
      flash backup.
      The official package resets NVS and otadata: Wi-Fi credentials and settings are lost.
      If ESPHome's bootloader is installed, the installer puts Shelly's back (seen once, on the Plus Plug S:
      'Boot: cur 00000000 ... update? 1'). It also moves the stock firmware to the other slot, which is what the next send of an
      ESPHome package needs when send reports that the installer would write to slot 1."""


def cmd_restore(args) -> None:
    zip_path = firmware.cached_zip(args.device, args.version)
    if zip_path is None:
        raise builder.OtaError(f"No official {args.device} ZIP cached. Run 'ota.py fetch {args.device}' first.")
    ui.say(f"Restoring the official firmware from {zip_path}")
    ui.say(RESTORE_NOTE)
    try:
        _send(args, zip_path)
    except builder.OtaError as e:
        if str(e).startswith("No answer from the Shelly"):
            raise builder.OtaError(f"{e}\n  Is the Shelly firmware still running? A device with ESPHome on it "
                                   f"cannot be restored this way; use UART (see the note above).") from e
        raise


def cmd_log(args) -> None:
    host = args.host or sender.local_ip_for(args.ip)
    logwatch.watch(args.ip, host, args.log_port, args.seconds, user=args.user, password=args.password)


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
    o.add_argument("--ip", default=sender.DEFAULT_IP, metavar="IP", help="Shelly address (default: %(default)s)")
    o.add_argument("--user", default="admin", help="login, if the device has a password (default: %(default)s)")
    o.add_argument("--password", metavar="PW", help="device password")
    o.add_argument("--host", metavar="IP", help="this PC's address as seen by the Shelly (default: auto)")
    o.add_argument("--log-port", type=int, default=9514, metavar="PORT", help="UDP port for the log (default: %(default)s)")
    return o


def send_options() -> argparse.ArgumentParser:
    o = argparse.ArgumentParser(add_help=False)
    o.add_argument("--yes", action="store_true", help="do not ask before flashing")
    o.add_argument("--dry-run", action="store_true", help="check the device, send nothing")
    o.add_argument("--force", action="store_true", help="send even if the device model does not match")
    o.add_argument("--ignore-slot", action="store_true",
                   help="send even if the installer would write to a slot that ESPHome's bootloader does not start")
    o.add_argument("--watch", type=float, default=0, metavar="SEC",
                   help="show the device log, and keep listening SEC seconds after the download")
    o.add_argument("--port", type=int, default=8000, help="local web server port (default: %(default)s)")
    o.add_argument("--timeout", type=float, default=300, metavar="SEC", help="wait for the download (default: %(default)s)")
    return o


class _VersionAction(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, default=argparse.SUPPRESS, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        print(f"{parser.prog} {buildinfo.current().short()}")
        parser.exit()


def main() -> None:
    ap = argparse.ArgumentParser(prog="ota.py", description=__doc__, epilog=EPILOG,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action=_VersionAction, help="show the version and, in a git checkout, branch, commit and date")
    ap.add_argument("--color", choices=["auto", "always", "never"], default="auto",
                    help="colored messages: yellow warning, orange critical, red error, green ok (default: auto = only in "
                         "a terminal, and not with NO_COLOR set). Put it before the command.")
    sub = ap.add_subparsers(dest="cmd", required=True, title="commands", metavar="<command>")
    fmt = argparse.RawDescriptionHelpFormatter
    dev_help = f"device name ({', '.join(profile.list_devices())})"
    dev, snd = device_options(), send_options()

    sub.add_parser("list", help="show devices and cached firmware").set_defaults(func=cmd_list)

    f = sub.add_parser("fetch", help="get the official firmware ZIP (downloads if missing)",
                       formatter_class=fmt, epilog="example: python ota.py fetch DuoBulbG3 --insecure")
    f.add_argument("device", metavar="DEVICE", help=dev_help)
    f.add_argument("--refresh", action="store_true", help="check for a newer version even if cached")
    f.add_argument("--version", metavar="VER", help="use this cached version")
    f.add_argument("--insecure", action="store_true", help="skip TLS check (Shelly uses a private CA)")
    f.set_defaults(func=cmd_fetch)

    a = sub.add_parser("add-device", help="create a device profile from an official ZIP",
                       formatter_class=fmt, epilog="example: python ota.py add-device NewDevice.zip")
    a.add_argument("zip", type=Path, metavar="ZIP", help="official Shelly OTA ZIP")
    a.add_argument("--name", help="device name (default: name in the ZIP)")
    a.add_argument("--parent", metavar="DEVICE", help="base device, if this is a variant (e.g. PlugUSG4 for PlugUSG4ZB)")
    a.add_argument("--force", action="store_true", help="overwrite an existing profile")
    a.set_defaults(func=cmd_add_device)

    pc = sub.add_parser("partition-csv", help="write the stock partition table as ESPHome partitions CSV",
                        formatter_class=fmt, epilog="example: python ota.py partition-csv HTG3 -o HTG3-stock.csv")
    pc.add_argument("device", metavar="DEVICE", help=dev_help)
    pc.add_argument("-o", "--output", type=Path, metavar="CSV", help="write to this file (default: print)")
    pc.add_argument("--force", action="store_true", help="overwrite an existing output file")
    pc.add_argument("--official", type=Path, metavar="ZIP", help="use this official ZIP instead of the cache")
    pc.add_argument("--version", metavar="VER", help="use this cached version (default: latest)")
    pc.set_defaults(func=cmd_partition_csv)

    b = sub.add_parser("build", help="build an OTA ZIP from your app image", formatter_class=fmt,
                       epilog="example: python ota.py build PlugMG3 app.bin --tag v2 --drop nvs")
    b.add_argument("device", metavar="DEVICE", help=dev_help)
    b.add_argument("app", type=Path, metavar="APP.bin", help="ESPHome app binary (not the merged image)")
    b.add_argument("-o", "--output", type=Path, metavar="ZIP", help="output file (default: out/<auto name>)")
    b.add_argument("--tag", metavar="LABEL", help="own label for file name and report (manifest unchanged)")
    b.add_argument("--esphome-yaml", type=Path, metavar="YAML", help="also check this ESPHome config")
    b.add_argument("--esphome-factory", type=Path, metavar="FACTORY.bin",
                   help="also replace Shelly's bootloader and otadata with ESPHome's, taken from this factory image "
                        "(must be the same build as APP.bin; checked first). Later ESPHome OTAs then work without a "
                        "separate bootloader update. Confirmed devices are marked in the README; if the bootloader "
                        "does not suit a device, only UART can recover it. The installer must write the app to slot 0 "
                        "(send checks that first)")
    b.add_argument("--boot-min-version", metavar="VER",
                   help="with --esphome-factory: bootloader min_version in the manifest. The Shelly installer only "
                        "writes a bootloader newer than the installed one. Default: the profile's boot_min_version "
                        "if it has one (H&T, Power Strip: 1.0.9), otherwise one patch level above the official one "
                        "(1.0.2 -> 1.0.3). The update log line 'Boot: cur ... min ... update?' shows whether it was "
                        "written; with 'update? 0' use a higher value. 'keep' leaves it unchanged, which probably "
                        "makes the installer skip the bootloader (then the old one stays)")
    b.add_argument("--secrets", type=Path, metavar="FILE",
                   help="secrets.yaml to compare the image with (default: secrets.yaml next to --esphome-yaml)")
    b.add_argument("--fail-on-secrets", action="store_true",
                   help="stop if the image contains credentials from the config/secrets (default: only warn). "
                        "Use it for packages that are meant to be shared")
    b.add_argument("--dry-run", action="store_true", help="check only, keep no output")
    g = b.add_argument_group("parts")
    g.add_argument("--drop", default="", metavar="LIST", help="leave out parts: boot,pt,otadata,nvs,fs")
    g.add_argument("--drop-fs", action="store_true", help="same as --drop fs")
    g = b.add_argument_group("base firmware")
    g.add_argument("--official", type=Path, metavar="ZIP", help="use this official ZIP")
    g.add_argument("--version", metavar="VER", help="use this cached version (default: latest)")
    g.add_argument("--download", action="store_true", help="download if nothing is cached")
    g.add_argument("--insecure", action="store_true", help="with --download: skip TLS check")
    b.set_defaults(func=cmd_build)

    t = sub.add_parser("send", help="send a ZIP to a Shelly (it downloads from this PC)", parents=[dev, snd],
                       formatter_class=fmt, epilog="example: python ota.py send DuoBulbG3 out/x.zip --ip 192.168.1.50")
    t.add_argument("device", metavar="DEVICE", help=dev_help)
    t.add_argument("zip", type=Path, metavar="ZIP")
    t.set_defaults(func=cmd_send)

    r = sub.add_parser("restore", help="send the cached official firmware back to a Shelly", parents=[dev, snd],
                       formatter_class=fmt,
                       epilog="example: python ota.py restore DuoBulbG3 --ip 192.168.1.50\n\n" + RESTORE_NOTE)
    r.add_argument("device", metavar="DEVICE", help=dev_help)
    r.add_argument("--version", metavar="VER", help="cached version (default: latest)")
    r.set_defaults(func=cmd_restore)

    lg = sub.add_parser("log", help="show the live debug log of a Shelly", parents=[dev], formatter_class=fmt,
                        epilog="example: python ota.py log --ip 192.168.1.50 --seconds 30")
    lg.add_argument("--seconds", type=float, metavar="SEC", help="stop after SEC seconds (default: Ctrl+C)")
    lg.set_defaults(func=cmd_log)

    c = sub.add_parser("clean", help="delete old ZIPs in out/ (shows what, needs --yes)")
    c.add_argument("--keep", type=int, default=5, metavar="N", help="newest ZIPs to keep (default: %(default)s)")
    c.add_argument("--yes", action="store_true", help="really delete")
    c.set_defaults(func=cmd_clean)

    co = sub.add_parser("colors", help="show every message color once, and whether colors are on")
    co.set_defaults(func=cmd_colors)

    pr = sub.add_parser("profiles", help="list the device profiles with their revision and check devices/profiles.lock")
    pr.add_argument("--update-lock", action="store_true",
                    help="record the current revision and content of every profile (after raising a revision)")
    pr.set_defaults(func=cmd_profiles)

    i = sub.add_parser("inspect", help="show and verify an OTA ZIP")
    i.add_argument("zip", type=Path, metavar="ZIP")
    i.add_argument("--device", metavar="DEVICE", help="also show how full the app slot is")
    i.set_defaults(func=cmd_inspect)

    args = ap.parse_args()
    ui.configure(args.color)
    if not (args.func is cmd_partition_csv and not args.output):   # that command prints data to stdout
        ui.say(f"free-shelly-ota {buildinfo.current().short()}")
    try:
        args.func(args)
    except (builder.OtaError, profile.ProfileError, FileNotFoundError) as e:
        sys.exit(ui.error(e))


if __name__ == "__main__":
    main()
