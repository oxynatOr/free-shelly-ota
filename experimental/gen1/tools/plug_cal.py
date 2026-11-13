#!/usr/bin/env python3
"""Helper for the calibration of the Plug S meter (plugs-cali.yaml with the web interface of example-plugs-meter.yaml).

  plug_cal.py read --host H [--seconds 90]      read voltage, current and power for a while; print the distinct values and their mean
  plug_cal.py calibrate voltage|current|power VALUE --host H   set the reference value and press the calibrate button
  plug_cal.py scales --host H                   print the scales and the thresholds
  plug_cal.py reset --host H                    put all scales back to 1.0 and the thresholds to 0

The plug answers on port 80 with user "admin" and the gen1_ota password (environment variable G1OT_PASSWORD or --password-file).
The addresses use the names of the entities with their capital letters ("/sensor/Power", "/number/Cal Target Power").
Standard library only.
"""
import argparse
import base64
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SENSORS = ("Voltage", "Current", "Power")
QUANTITIES = {"voltage": ("Cal Target Voltage", "Calibrate Voltage", "Cal Scale Voltage", "V"),
              "current": ("Cal Target Current", "Calibrate Current", "Cal Scale Current", "A"),
              "power": ("Cal Target Power", "Calibrate Power", "Cal Scale Power", "W")}
SETTINGS = ("Cal Scale Voltage", "Cal Scale Current", "Cal Scale Power", "Cal Idle Power", "Cal Idle Current", "Cal Max Deviation")


def _request(base: str, method: str, path: str, user: str, password: str, timeout: float = 10.0):
    req = urllib.request.Request(base + urllib.parse.quote(path, safe="/?=&"), method=method, data=b"" if method == "POST" else None)
    token = base64.b64encode(("%s:%s" % (user, password)).encode()).decode()
    req.add_header("Authorization", "Basic " + token)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode()
    return json.loads(body) if body.strip().startswith("{") else body


def get_value(base, kind, name, user, password):
    """The plug sends sensor values as numbers and the value of a number entity as text ("1.0000"); both come back as float."""
    v = _request(base, "GET", "/%s/%s" % (kind, name), user, password)["value"]
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return float("nan")
    return v


def read_values(base, user, password, seconds, step=4.0, out=print):
    """Poll the three sensors; consecutive equal values count once (the meter refreshes each value only every ~24 s)."""
    seen = {s: [] for s in SENSORS}
    end = time.time() + seconds
    while True:
        for s in SENSORS:
            v = get_value(base, "sensor", s, user, password)
            if v is not None and (not seen[s] or seen[s][-1] != v):
                seen[s].append(v)
        if time.time() >= end:
            break
        time.sleep(step)
    unit = {"Voltage": "V", "Current": "A", "Power": "W"}
    for s in SENSORS:
        vals = seen[s]
        if vals:
            out("%-8s %d values, mean %.3f %s (min %.3f, max %.3f)" % (s, len(vals), statistics.mean(vals), unit[s], min(vals), max(vals)))
        else:
            out("%-8s no value" % s)
    return seen


def calibrate(base, quantity, value, user, password, out=print):
    target, button, scale, unit = QUANTITIES[quantity]
    before = get_value(base, "number", scale, user, password)
    _request(base, "POST", "/number/%s/set?value=%s" % (target, value), user, password)
    _request(base, "POST", "/button/%s/press" % button, user, password)
    time.sleep(1.0)
    after = get_value(base, "number", scale, user, password)
    out("%s scale: %.4f -> %.4f (reference %s %s)" % (quantity, before, after, value, unit))
    if after == before:
        out("The scale did not change: no valid reading yet (put a load on the plug and wait about 30 s), or the deviation is above the limit. See the plug's log.")
    return before, after


def _password(args) -> str:
    if args.password_file:
        return open(args.password_file, encoding="utf-8").read().strip()
    pw = os.environ.get("G1OT_PASSWORD")
    if not pw:
        sys.exit("password missing: set G1OT_PASSWORD or use --password-file")
    return pw


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("read", "calibrate", "scales", "reset"):
        p = sub.add_parser(name)
        p.add_argument("--host", required=True)
        p.add_argument("--port", type=int, default=80)
        p.add_argument("--user", default="admin")
        p.add_argument("--password-file")
        if name == "read":
            p.add_argument("--seconds", type=float, default=90.0)
        if name == "calibrate":
            p.add_argument("quantity", choices=sorted(QUANTITIES))
            p.add_argument("value", type=float)
    args = ap.parse_args(argv)
    base = "http://%s:%d" % (args.host, args.port)
    pw = _password(args)
    try:
        if args.cmd == "read":
            read_values(base, args.user, pw, args.seconds)
        elif args.cmd == "calibrate":
            calibrate(base, args.quantity, args.value, args.user, pw)
        elif args.cmd == "scales":
            for n in SETTINGS:
                print("%-20s %s" % (n, get_value(base, "number", n, args.user, pw)))
        else:
            _request(base, "POST", "/button/Reset Calibration/press", args.user, pw)
            print("calibration reset")
    except (urllib.error.URLError, OSError) as err:
        print("no answer from %s (%s). Is the plug up and is your PC in its network?" % (base, err))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
