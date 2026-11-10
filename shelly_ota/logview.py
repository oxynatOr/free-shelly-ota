"""Make the output of a run readable: filter it by level, and turn the device's debug log into a few lines and a progress bar.

The Shelly sends its log as UDP datagrams, and one datagram holds several entries glued together without a separator:

    <id> 94 105.130 2 2|shos_rpc_inst.c:241     Sys.SetConfig [1@] ...<id> 95 105.139 2 2|_lwip_debug_udp.cpp:118 UDP log ...

An entry is `<device id> <number> <uptime in s> <a> <b>|<source file:line> <message>`. The last digit looks like the severity
(0 error, 1 warning, 2 information). That was read from three entries of one update (`2 1|... FW signatures`,
`2 0|... Bits are not empty`, everything else `2 2|`), it is not documented. Anything that does not fit is kept as it is.

Levels (a message or entry is shown when the session's level is at least its own):

    quiet    errors and the final result
    normal   + warnings, the lines the device pages tell you to look for, a progress line
    verbose  + notes and explanations, every entry of the update
    debug    every entry, one per line
    raw      like debug, and the device log exactly as it arrived (the behaviour before levels existed)
"""

from __future__ import annotations

import collections
import enum
import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TextIO

from . import ui


class Level(enum.IntEnum):
    quiet = 0
    normal = 1
    verbose = 2
    debug = 3
    raw = 4


LEVEL_NAMES = [level.name for level in Level]


@dataclass(frozen=True)
class LogRecord:
    """One entry of the device log."""
    device: str
    seq: int
    uptime: float       # seconds since the device started
    severity: int       # 0 error, 1 warning, 2 information (see the module docstring)
    source: str         # "file.cpp:123" or a module name
    message: str
    raw: str            # the entry exactly as received, with its header


_HEADER = r" (\d+) (\d+\.\d+) (\d) (\d)\|"
_FIRST = re.compile(r"(\S+)" + _HEADER)


def split_records(text: str, device_id: str) -> list[LogRecord | str]:
    """Cut a datagram into entries. Text that is not an entry (before the first one, or no entry at all) is kept as a str."""
    found = list(re.finditer(re.escape(device_id) + _HEADER, text))
    if not found:
        return [text.strip()] if text.strip() else []
    items: list[LogRecord | str] = []
    head = text[:found[0].start()].strip()
    if head:
        items.append(head)
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        source, _, message = text[m.end():end].strip().partition(" ")
        items.append(LogRecord(device_id, int(m[1]), float(m[2]), int(m[4]), source, message.strip(), text[m.start():end].strip()))
    return items


@dataclass(frozen=True)
class Entry:
    """What an entry means: how it is shown and from which level on."""
    kind: str           # progress, milestone, known, warn, error, result_ok, result_error, rpc, noise, info
    level: Level
    text: str
    percent: int | None = None
    key: str | None = None      # entries with the same key are shown once (below debug)


@dataclass(frozen=True)
class Rule:
    """A message pattern and what to make of it. {0}, {1} ... in text are the groups of the pattern."""
    pattern: str
    kind: str
    level: Level
    text: str
    key: str | None = None

    def apply(self, record: LogRecord) -> Entry | None:
        m = re.search(self.pattern, record.message)
        return Entry(self.kind, self.level, self.text.format(*m.groups()), key=self.key) if m else None


_EFUSE_NOTE = "The update still succeeded where this was seen; see docs/background.md#efuse"

# The first rule that matches wins. The device pages tell users to look for: the target slot, "Boot: cur ... update?",
# "Will write to slot", the progress, and the success.
RULES = (
    Rule(r"FW signatures: want (\w+) got (\w+)", "known", Level.normal,
         "The installer logs refused eFuse writes (FW signatures: want {0}, got {1}). " + _EFUSE_NOTE, key="efuse"),
    Rule(r"EFUSE write error|Bits are not empty", "known", Level.normal,
         "The installer logs refused eFuse writes. " + _EFUSE_NOTE, key="efuse"),
    Rule(r"Storing core dumps to app_(\d)", "milestone", Level.verbose, "The installer's target slot: {0}"),
    Rule(r"Will write to slot (\d)", "milestone", Level.normal, "The installer writes to slot {0}"),
    Rule(r"Boot: cur (\w+), new (\w+), min (\w+), update\? 1", "milestone", Level.normal,
         "The bootloader will be replaced (current {0}, minimum {2})"),
    Rule(r"Boot: cur (\w+), new (\w+), min (\w+), update\? 0", "warn", Level.normal,
         "ESPHome's bootloader was NOT written: the device keeps Shelly's loader (installed {0}, package min {2}, update? 0). "
         "Later ESPHome OTAs may not take effect or need several restarts. Build again with a higher --boot-min-version "
         "(for example 1.0.9) or set boot_min_version: in the profile. See docs/bootloader-and-slots.md",
         key="bootskip"),
    Rule(r"Installing BL (\d+)@", "milestone", Level.normal, "Installing the bootloader ({0} bytes)"),
    Rule(r"New fw: (\S+) ver (\S+)", "milestone", Level.verbose, "The device sees the package {0} {1}"),
    Rule(r"HTTP GET http", "milestone", Level.verbose, "The device starts downloading the ZIP"),
    Rule(r"Update succeeded", "milestone", Level.verbose, "The installer reports success; the device reboots"),
    Rule(r"Rebooting in (\d+) ms", "milestone", Level.verbose, "The device reboots in {0} ms"),
    Rule(r"Finished; bytes (\d+)/(\d+), code (\d+)", "info", Level.debug, "HTTP transfer finished: bytes {0}/{1}, code {2}"),
    Rule(r"^([\w.]+) \[[^\]]*\] via \w+ ?\w* from (\S+)", "rpc", Level.debug, "RPC {0} <- {1}"),
    Rule(r"Announced \S+\.local", "noise", Level.debug, "mDNS announcement"),
    Rule(r"New min heap free: (\d+)", "noise", Level.debug, "Free heap minimum: {0} bytes"),
    Rule(r"(?i)(streaming|stopped streaming) logs to (\S+)", "noise", Level.debug, "Log {0} to {1}"),
    Rule(r"UDP log set up to", "noise", Level.debug, "UDP log set up"),
    # The power meter chip does not answer on its UART while the update runs; repeated every few seconds, harmless
    Rule(r"packet read timed out", "noise", Level.debug, "Power meter chip: packet read timed out"),
    Rule(r"Status change of (\S+):", "noise", Level.debug, "Status change of {0}"),
)

_EVENT = re.compile(r"Event from (\w+): (\{.*\})")
_WILL_WRITE = re.compile(r"Will write to slot (\d)")
_TABLE_MOVED = re.compile(r"Installing PT .*-> pt\(0x[0-9a-fA-F]+\)|PT is being moved")


def _classify_event(m: re.Match, record: LogRecord) -> Entry:
    try:
        event = json.loads(m.group(2))
    except ValueError:
        return Entry("info", Level.debug, record.message)
    name, msg = str(event.get("event", "")), str(event.get("msg", ""))
    percent = event.get("progress_percent")
    if name == "ota_progress" and isinstance(percent, (int, float)):
        return Entry("progress", Level.normal, f"Update {int(percent)} %", percent=int(percent))
    if "error" in name.lower() or "error" in msg.lower():       # "ota_error" is assumed, not seen yet
        return Entry("result_error", Level.quiet, f"The device reports an update error: {msg or name}")
    if name == "ota_success":
        return Entry("result_ok", Level.normal, "The device confirmed the update")
    if name == "ota_begin":
        return Entry("milestone", Level.normal, "The update started")
    if name == "scheduled_restart":
        return Entry("milestone", Level.verbose, f"The device restarts in {event.get('time_ms', '?')} ms")
    return Entry("info", Level.debug, f"Event {name or '?'}: {msg}".rstrip(": "))


def classify(record: LogRecord) -> Entry:
    m = _EVENT.search(record.message)
    if m:
        return _classify_event(m, record)
    for rule in RULES:
        entry = rule.apply(record)
        if entry:
            return entry
    detail = f"device log: {record.source}: {record.message}"
    if record.severity == 0:
        return Entry("error", Level.quiet, detail)
    if record.severity == 1:
        return Entry("warn", Level.normal, detail)
    return Entry("info", Level.debug, record.message)


_SEVERITY = {0: "ERR", 1: "WRN"}


def format_debug(item: LogRecord | str, entry: Entry | None = None) -> str:
    """One entry on one line: uptime, severity, source, message (RPC entries as 'RPC method <- client')."""
    if isinstance(item, str):
        return f"  log| {item}"
    text = entry.text if entry is not None and entry.kind == "rpc" else item.message
    return f"  log| {item.uptime:9.3f} {_SEVERITY.get(item.severity, '   ')} {item.source:<26} {text}"


class LogFile:
    """The whole run, one line each, whatever level the console shows. This is the file to attach to a bug report."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._file: TextIO = path.open("w", encoding="utf-8", newline="\n")
        self._lock = threading.Lock()

    def write(self, source: str, text: str) -> None:
        now = time.time()
        stamp = time.strftime("%H:%M:%S", time.localtime(now)) + f".{int(now * 1000) % 1000:03d}"
        with self._lock:
            for line in text.splitlines() or [""]:
                self._file.write(f"{stamp} {source:<4}| {line}\n")
            self._file.flush()

    def close(self) -> None:
        with self._lock:
            self._file.close()


class Session:
    """Everything one run shows: tool messages and the device log, filtered by level.

    `say(level, text)` is for the tool's own messages and `device(text)` is the sink for the UDP log. The last entries are kept,
    so that a failure can print them (`dump_tail`) even when the console level hid them.
    """

    def __init__(self, level: Level = Level.verbose, out: Callable[[str], None] = ui.say, logfile: LogFile | None = None,
                 device_id: str | None = None, tail: int = 30):
        self.level = level
        self.out = out
        self.logfile = logfile
        self.device_id = device_id
        self.finished = threading.Event()   # set by ota_success or an error event
        self.result: str | None = None      # "ok" or "error"
        self.error_text: str | None = None
        self.update_seen = False            # the log showed an update (progress or a result): worth waiting for its end
        # False: the package is Shelly's own (restore), "update? 0" is what is meant and says nothing. None: it is a warning,
        # because ESPHome takes no OTAs until its own bootloader has been written (also when unknown, as in a replay).
        self.expect_new_loader: bool | None = None
        # --slot-swap (experimental): the slot the partition table was swapped for. If the installer then names another slot in
        # "Will write to slot N", that is said at once: the swapped table would make the other slot the one that starts.
        self.slot_swap_target: int | None = None
        # --slot-swap: the installer's log line that says it writes the table to the new address (set by _check_slot_swap).
        self.table_moved = False
        self._tail: collections.deque[tuple[LogRecord | str, Entry]] = collections.deque(maxlen=tail)
        self._hidden: collections.Counter[str] = collections.Counter()
        self._shown_keys: set[str] = set()
        self._lock = threading.RLock()

    # tool messages
    def say(self, level: Level, text: str) -> None:
        if self.logfile:
            self.logfile.write("tool", text)
        if self.level >= level:
            self.out(text)

    # device log
    def device(self, text: str) -> None:
        """Sink for logwatch.udp_log: one datagram."""
        if self.level is Level.raw:
            for line in text.splitlines():
                self.out(f"  log| {line}")
        if self.device_id is None:
            m = _FIRST.match(text)
            if m:
                self.device_id = m.group(1)
        items = split_records(text, self.device_id) if self.device_id else ([text.strip()] if text.strip() else [])
        for item in items:
            self._take(item)

    def _take(self, item: LogRecord | str) -> None:
        entry = classify(item) if isinstance(item, LogRecord) else Entry("info", Level.debug, item)
        with self._lock:
            self._tail.append((item, entry))
            if self.logfile:
                self.logfile.write("dev", item.raw if isinstance(item, LogRecord) else item)
            if entry.kind in ("progress", "result_ok", "result_error"):
                self.update_seen = True
            if entry.kind == "result_ok":
                self.result = "ok"
                self.finished.set()
            elif entry.kind == "result_error":
                self.result, self.error_text = "error", entry.text
                self.finished.set()
            if self.level is not Level.raw:
                self._show(item, entry)
            self._check_slot_swap(item)

    def _check_slot_swap(self, item: LogRecord | str) -> None:
        if self.slot_swap_target is None:
            return
        text = item.message if isinstance(item, LogRecord) else item
        if _TABLE_MOVED.search(text):
            self.table_moved = True
        m = _WILL_WRITE.search(text)
        if m and int(m.group(1)) != self.slot_swap_target and "slot_swap" not in self._shown_keys:
            self._shown_keys.add("slot_swap")
            self.say(Level.quiet, f"WARNING: the installer writes to slot {m.group(1)}, but --slot-swap made the partition table "
                                  f"for slot {self.slot_swap_target} (read before the update). With this table ESPHome's "
                                  f"bootloader starts app_{self.slot_swap_target}, which is not the slot being written. "
                                  "If the device does not start ESPHome, a serial connection and a flash dump are needed.")

    def _show(self, item: LogRecord | str, entry: Entry) -> None:
        if self.level >= Level.debug:
            self.out(format_debug(item, entry))
            return
        if entry.kind == "progress":
            if self.level >= Level.normal:
                ui.progress("Update", entry.percent or 0, None if self.out is ui.say else self.out)
            return
        if entry.kind in ("result_ok", "result_error"):
            return                              # the sender reports the result; it is in the file and at debug
        if entry.key == "bootskip" and self.expect_new_loader is False:
            self._hidden[entry.kind] += 1       # expected: this package keeps Shelly's bootloader
            return
        if entry.key:
            if entry.key in self._shown_keys:
                self._hidden[entry.kind] += 1
                return
            self._shown_keys.add(entry.key)
        if entry.level <= self.level and entry.kind in ("milestone", "known", "warn", "error"):
            self.out(self._friendly(entry))
        else:
            self._hidden[entry.kind] += 1

    @staticmethod
    def _friendly(entry: Entry) -> str:
        return {"milestone": "Device: ", "known": "NOTE: ", "warn": "WARNING: ", "error": "ERROR: "}[entry.kind] + entry.text

    def reset_result(self) -> None:
        """Before another pass: forget the outcome of the one before."""
        with self._lock:
            self.finished.clear()
            self.result = self.error_text = None
            self.update_seen = False

    # after the run
    def summary(self) -> None:
        """A hint about what the level hid."""
        with self._lock:
            hidden, rpc = sum(self._hidden.values()), self._hidden["rpc"]
        if hidden and Level.quiet < self.level < Level.debug:
            if self.level is Level.normal:
                self.out(f"Device log: {hidden} more entries hidden (-v shows more, --log-file keeps all of it).")
            else:
                self.out(f"Device log: hidden {rpc} RPC requests and {hidden - rpc} other entries "
                         f"(--log-level debug shows them).")

    def dump_tail(self) -> None:
        """After a failure, whatever the level: the last entries of the device log and where the full log is."""
        with self._lock:
            items = list(self._tail)
            self._tail.clear()
        if items:
            self.out("Last lines of the device log:")
            for item, entry in items:
                self.out(format_debug(item, entry))
        if self.logfile:
            self.out(f"Log file: {self.logfile.path}")

    def close(self) -> None:
        if self.logfile:
            self.logfile.close()


_FILE_DEVICE = re.compile(r"^\d\d:\d\d:\d\d\.\d{3} dev \| (.*)$")
_FILE_TOOL = re.compile(r"^\d\d:\d\d:\d\d\.\d{3} tool\| ")


def replay(path: Path, session: Session) -> None:
    """Feed a saved log through a session: a --log-file file, or the output of --log-level raw (lines starting with 'log| ')."""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if _FILE_TOOL.match(line):
            continue
        m = _FILE_DEVICE.match(line)
        text = m.group(1) if m else (line.strip()[len("log| "):] if line.strip().startswith("log| ") else line)
        if text.strip():
            session.device(text)
