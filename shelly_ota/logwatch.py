"""Read a Shelly's debug log: the device sends it as UDP datagrams to this PC.

Enabled and disabled over RPC (Sys.SetConfig debug.udp.addr). The previous setting is restored.
"""

from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager
from typing import Callable

from . import rpc, ui
from .builder import OtaError


@contextmanager
def udp_log(addr: str, host: str, port: int, out: Callable[[str], None] = ui.say, **auth):
    """Context manager: forward the device's debug log to out() while the block runs."""
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
            for line in data.decode(errors="replace").splitlines():
                out(f"  log| {line}")

    previous = None
    try:
        previous = (rpc.call(addr, "Sys.GetConfig", **auth).get("debug", {}).get("udp") or {}).get("addr")
        result = rpc.call(addr, "Sys.SetConfig", {"config": {"debug": {"udp": {"addr": f"{host}:{port}"}}}}, **auth)
        if result.get("restart_required"):
            out("NOTE: the device wants a restart for the log setting to apply.")
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        yield
    finally:
        stop.set()
        try:  # best effort: the device may be rebooting or already reflashed
            rpc.call(addr, "Sys.SetConfig", {"config": {"debug": {"udp": {"addr": previous}}}}, **auth)
        except (OtaError, OSError):
            pass
        sock.close()


def watch(addr: str, host: str, port: int, seconds: float | None, out: Callable[[str], None] = ui.say,
          **auth) -> None:
    """Print the device log for `seconds` (until Ctrl+C if None)."""
    with udp_log(addr, host, port, out, **auth):
        out(f"Listening for the log of {addr} on {host}:{port} (Ctrl+C to stop) ...")
        try:
            if seconds is None:
                while True:
                    time.sleep(1)
            else:
                time.sleep(seconds)
        except KeyboardInterrupt:
            pass
