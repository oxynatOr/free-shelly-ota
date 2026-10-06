"""Terminal output with colors: yellow = warning, orange = critical warning, red = error, green = success.

Colors are added on top of the text only (the words WARNING:, NOTE:, Error:, OK: stay), and only when the output goes to a
terminal. NO_COLOR (https://no-color.org) and --color never switch them off, --color always forces them.
"""

from __future__ import annotations

import os
import sys
from typing import Mapping

RESET = "\033[0m"
YELLOW = "\033[33m"
ORANGE = "\033[38;5;208m"
RED = "\033[31;1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
DIM = "\033[2m"

# A WARNING line that contains one of these is shown in orange: it can brick a device, wipe data or leak credentials.
CRITICAL_WORDS = ("bootloader", "wipes nvs", "credentials in the image", "write to slot", "verification is off")
OK_PREFIXES = ("OK:", "Done:", "Update target slot: 0", "ESPHome config check OK", "Credential check OK",
               "all part hashes OK", "Wrote ", "Stored ")

_enabled = False


def should_color(mode: str, isatty: bool, env: Mapping[str, str]) -> bool:
    """auto: only on a terminal, not with NO_COLOR set, not on TERM=dumb. always/never are forced."""
    if mode == "never":
        return False
    if mode == "always":
        return True
    if env.get("NO_COLOR"):
        return False
    if env.get("TERM") == "dumb":
        return False
    return isatty


def _enable_windows_vt() -> bool:
    """Switch on ANSI escape processing in the Windows console (Windows 10 and newer). False if it is not available."""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        ok = True
        for std in (-11, -12):  # stdout, stderr
            handle = kernel32.GetStdHandle(std)
            mode = ctypes.c_ulong()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                ok = False
                continue
            ok = bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004)) and ok  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
        return ok
    except (AttributeError, OSError, ImportError):
        return False


def configure(mode: str = "auto") -> bool:
    """Decide once whether to color. Returns the result."""
    global _enabled
    want = should_color(mode, sys.stdout.isatty(), os.environ)
    if want and os.name == "nt" and mode != "always":
        want = _enable_windows_vt()
    elif want and os.name == "nt":
        _enable_windows_vt()
    _enabled = want
    return _enabled


def color_for(line: str) -> str | None:
    """The color code for a message line, chosen from its prefix (and for warnings from its content)."""
    s = line.lstrip()
    if s.startswith(("Error:", "ERROR")):
        return RED
    if s.startswith("log|"):
        return DIM
    if s.startswith("WARNING"):
        low = s.lower()
        return ORANGE if any(w in low for w in CRITICAL_WORDS) else YELLOW
    if s.startswith("NOTE"):
        return CYAN
    if s.startswith(OK_PREFIXES):
        return GREEN
    return None


def paint(text: str, enabled: bool | None = None) -> str:
    """Return text with colors, line by line. A continuation line (indented, no prefix of its own) keeps the color of the line above."""
    if not (_enabled if enabled is None else enabled):
        return text
    out_lines, current = [], None
    for line in text.split("\n"):
        code = color_for(line)
        if code is None and current is not None and line.startswith("  ") and line.strip():
            code = current
        current = code
        out_lines.append(f"{code}{line}{RESET}" if code and line.strip() else line)
    return "\n".join(out_lines)


def say(text: str = "", end: str = "\n") -> None:
    """print() for messages."""
    print(paint(text), end=end)


def error(message: str) -> str:
    """The 'Error: ...' text for sys.exit(), colored when stderr is a terminal and colors are on."""
    text = f"Error: {message}"
    return f"{RED}{text}{RESET}" if _enabled and sys.stderr.isatty() else text
