"""Read a Shelly's debug log: the device sends it as UDP datagrams to this PC.

Enabled and disabled over RPC (Sys.SetConfig debug.udp.addr). The previous setting is restored.
"""

from __future__ import annotations

import re
import socket
import threading
import time
from contextlib import contextmanager
from typing import Callable

from . import rpc, ui
from .builder import OtaError


# The updater's bootloader decision, e.g. "Boot: cur 010003ff, new 00000000, min 010003ff, update? 0".
# Versions are 0xMMmmpp followed by ff (010003ff = 1.0.3); "update? 1" means it writes the package's bootloader.
BOOT_RE = re.compile(r"Boot: cur ([0-9a-fA-F]{8}), new ([0-9a-fA-F]{8}), min ([0-9a-fA-F]{8}), update\? ([01])")


def boot_version(hex8: str) -> str:
    """'010003ff' -> '1.0.3' (major, minor, patch; the last byte is not part of the version)."""
    v = int(hex8, 16)
    return f"{v >> 24 & 0xFF}.{v >> 16 & 0xFF}.{v >> 8 & 0xFF}"


def parse_boot_line(text: str) -> dict | None:
    """cur/min as versions and update as bool from a device log line, or None if it is not the Boot line."""
    m = BOOT_RE.search(text)
    if not m:
        return None
    return {"cur": boot_version(m.group(1)), "min": boot_version(m.group(3)), "update": m.group(4) == "1"}


def boot_skipped_warning(boot: dict) -> str:
    """The WARNING text for a Boot line with update? 0."""
    return (f"WARNING: ESPHome's bootloader was NOT written: the device keeps Shelly's loader (installed {boot['cur']}, package "
            f"min {boot['min']}, update? 0). Later ESPHome OTAs may not take effect or need several restarts. Build again with "
            f"a higher --boot-min-version (for example 1.0.9) or set boot_min_version: in the profile.")


class LogStats:
    """What udp_log has received so far. Lets a caller tell 'no datagram at all' (firewall, wrong port or address)
    from 'datagrams arrive, but not the line I wait for'."""

    def __init__(self) -> None:
        self.datagrams = 0


@contextmanager
def udp_log(addr: str, host: str, port: int, out: Callable[[str], None] = ui.say, *,
            sink: Callable[[str], None] | None = None, **auth):
    """Context manager: forward the device's debug log while the block runs. Yields a LogStats.

    Without a sink every line goes to out() with a 'log| ' prefix. With a sink it gets each datagram as received (several
    entries can be glued together in one, see logview) and out() is only used for notes about the log setting itself.
    """
    stats = LogStats()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", port))
    except OSError as e:
        sock.close()
        raise OtaError(f"Cannot listen on UDP port {port}: {e}. Try --log-port.") from e
    sock.settimeout(0.5)
    stop = threading.Event()

    def reader():
        while not stop.is_set():
            try:
                data, _ = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                return
            stats.datagrams += 1
            text = data.decode(errors="replace")
            if sink is not None:
                try:
                    sink(text)
                    continue
                except Exception:   # a bug in the display must not stop the log: fall back to the plain lines
                    pass
            for line in text.splitlines():
                out(f"  log| {line}")

    thread = None
    previous = None
    read_previous = False   # only put the old setting back if it was read; otherwise we would write None over it
    try:
        previous = (rpc.call(addr, "Sys.GetConfig", **auth).get("debug", {}).get("udp") or {}).get("addr")
        read_previous = True
        # A restore may reboot before cleanup and leave this destination active.
        # Setting the same value again does not reinitialize the log sink, so the
        # one-time core-dump target line used by probe_slot is never emitted.
        # Toggle only that already-active destination; finally restores it.
        if previous == f"{host}:{port}":
            rpc.call(addr, "Sys.SetConfig", {"config": {"debug": {"udp": {"addr": None}}}}, **auth)
        result = rpc.call(addr, "Sys.SetConfig", {"config": {"debug": {"udp": {"addr": f"{host}:{port}"}}}}, **auth)
        if result.get("restart_required"):
            out("NOTE: the device wants a restart for the log setting to apply.")
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        yield stats
    finally:
        stop.set()
        try:
            if read_previous:
                try:
                    rpc.call(addr, "Sys.SetConfig", {"config": {"debug": {"udp": {"addr": previous}}}}, timeout=5, **auth)
                except rpc.DeviceUnreachable:
                    pass   # expected after a successful update: the device is rebooting or already runs the new firmware
                except OtaError as e:
                    out(f"NOTE: could not put the device's log setting back ({e}); it may keep sending its log to {host}:{port}.")
        finally:
            # The port must be free when this returns (send binds it again right after the slot probe). close() alone is not
            # enough on Linux: while the reader is blocked in recvfrom() the socket stays open until that call returns, so wait
            # for the reader first. Also runs if the restore call above fails in an unexpected way.
            if thread is not None:
                thread.join(2)
            sock.close()


def watch(addr: str, host: str, port: int, seconds: float | None, out: Callable[[str], None] = ui.say, *,
          sink: Callable[[str], None] | None = None, **auth) -> None:
    """Print the device log for `seconds` (until Ctrl+C if None)."""
    with udp_log(addr, host, port, out, sink=sink, **auth):
        out(f"Listening for the log of {addr} on {host}:{port} (Ctrl+C to stop) ...")
        try:
            if seconds is None:
                while True:
                    time.sleep(1)
            else:
                time.sleep(seconds)
        except KeyboardInterrupt:
            pass
