#!/usr/bin/env python3
"""Pack an ESPHome app image into a Shelly Gen3 OTA ZIP.

Only the app part is replaced; the rest comes from the official Shelly ZIP.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from shelly_ota import MODULE_DIR, __version__, builder, devicegen, firmware, lint, logwatch, profile, secrets_check, sender

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
ESPHome OTAs work; confirmed on the Plug M Gen3 only, and if it does not suit a device only UART can recover it.
restore only works while the Shelly firmware still runs; a device already on ESPHome needs UART.
Details per command: python ota.py <command> -h
"""


def cmd_list(args) -> None:
    for name in profile.list_devices():
        p = profile.load_profile(name)
        print(f"{name:12s} {p.display_name:24s} slot=0x{p.app_slot_size:x}")
        for ver in firmware.list_versions(name):
            meta_path = firmware.FW_DIR / name / ver / "meta.json"
            build_id = json.loads(meta_path.read_text(encoding="utf-8")).get("build_id") if meta_path.is_file() else None
            print(f"    fw {ver}  {build_id or ''}")


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
    print(f"Official firmware: {path}")


def cmd_add_device(args) -> None:
    path, info = devicegen.create_profile(args.zip, name=args.name, force=args.force, parent=args.parent)
    firmware.store_zip(info["name"], args.zip.read_bytes(), source=f"local file: {args.zip.name}")
    print(f"Wrote {path.name}: {info['ptn']} @0x{info['slot_offset']:x}, slot 0x{info['slot_size']:x}")
    print(f"Stored the ZIP in {firmware.FW_DIR / info['name']}")


def cmd_build(args) -> None:
    p = profile.load_profile(args.device)
    if args.esphome_yaml:
        problems = lint.lint_esphome(args.esphome_yaml, p)
        if problems:
            raise builder.OtaError("ESPHome config check failed:\n  - " + "\n  - ".join(problems))
        print(f"ESPHome config check OK ({args.esphome_yaml.name})")
        for w in lint.lint_warnings(args.esphome_yaml, bootloader_shipped=bool(args.esphome_factory)):
            print(f"  WARNING: {w}")
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
    print(f"{'DRY RUN, removed: ' if args.dry_run else 'OK: '}{result.output}")
    print(f"  base firmware {result.official_version} ({result.official_build_id}), "
          f"app {result.app_size} bytes, parts {result.parts}")
    if result.secrets_found == []:
        print(f"  Credential check OK: none of {len(secrets)} known values found in the image")
    for w in result.warnings:
        print(f"  {'WARNING' if w.startswith(('CREDENTIALS', 'BOOTLOADER', 'Credentials were not')) else 'NOTE'}: {w}")
    if not args.dry_run and result.secrets_found != [] and secrets_check.git_would_track(output):
        print(f"  WARNING: {output} is inside a git work tree and not ignored there; git add would pick up this package.")


def _send(args, zip_path: Path) -> None:
    p = profile.load_profile(args.device)
    sender.send(p, zip_path, args.ip, host=args.host, port=args.port, timeout=args.timeout,
                assume_yes=args.yes, dry_run=args.dry_run, force=args.force, user=args.user,
                password=args.password, watch=args.watch, log_port=args.log_port)


def cmd_send(args) -> None:
    _send(args, args.zip)


RESTORE_NOTE = """NOTE: Bootloader: by default Shelly's bootloader stays. --esphome-factory swaps in ESPHome's (and a clean otadata) so later
ESPHome OTAs work; confirmed on the Plug M Gen3 only, and if it does not suit a device only UART can recover it.
restore only works while the Shelly firmware is still running (only it understands Shelly.Update).
      A device that already runs ESPHome does not answer; the way back is then UART with a flash backup.
      The official package also resets NVS and otadata: Wi-Fi credentials and settings are lost."""


def cmd_restore(args) -> None:
    zip_path = firmware.cached_zip(args.device, args.version)
    if zip_path is None:
        raise builder.OtaError(f"No official {args.device} ZIP cached. Run 'ota.py fetch {args.device}' first.")
    print(f"Restoring the official firmware from {zip_path}")
    print(RESTORE_NOTE)
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
        print(f"Nothing to remove ({len(zips)} ZIP(s) in out/, keeping {args.keep}).")
        return
    for z in old:
        for f in [z, *out_dir.glob(z.name + ".*")]:
            print(f"{'removing' if args.yes else 'would remove'}: {f.name}")
            if args.yes:
                f.unlink()
    if not args.yes:
        print("Nothing deleted. Add --yes to delete.")


def cmd_inspect(args) -> None:
    p = profile.load_profile(args.device) if args.device else None
    print(builder.inspect_zip(args.zip, p))
    note = secrets_check.report_note(args.zip)
    if note:
        print(f"  {note[0]}: {note[1]}")


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
    o.add_argument("--watch", type=float, default=0, metavar="SEC",
                   help="show the device log, and keep listening SEC seconds after the download")
    o.add_argument("--port", type=int, default=8000, help="local web server port (default: %(default)s)")
    o.add_argument("--timeout", type=float, default=300, metavar="SEC", help="wait for the download (default: %(default)s)")
    return o


def main() -> None:
    ap = argparse.ArgumentParser(prog="ota.py", description=__doc__, epilog=EPILOG,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
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
                        "separate bootloader update. Confirmed on the Plug M Gen3 only; if the bootloader does not "
                        "suit a device, only UART can recover it")
    b.add_argument("--boot-min-version", metavar="VER",
                   help="with --esphome-factory: bootloader min_version in the manifest. The Shelly installer only "
                        "writes a bootloader newer than the installed one, so the default is one patch level above "
                        "the official one (1.0.2 -> 1.0.3). 'keep' leaves it unchanged, which probably makes the "
                        "installer skip the bootloader (then the old one stays)")
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

    i = sub.add_parser("inspect", help="show and verify an OTA ZIP")
    i.add_argument("zip", type=Path, metavar="ZIP")
    i.add_argument("--device", metavar="DEVICE", help="also show how full the app slot is")
    i.set_defaults(func=cmd_inspect)

    args = ap.parse_args()
    try:
        args.func(args)
    except (builder.OtaError, profile.ProfileError, FileNotFoundError) as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()
