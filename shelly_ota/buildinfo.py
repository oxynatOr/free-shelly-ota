"""Which copy of the tool is this? The version, plus (when run from a git checkout) branch, commit, tag distance and date.

Used by --version, the line printed at the start of every command, and the build report, so a log or a package can be
traced back to the exact state of the tool that produced it.
"""

from __future__ import annotations

import functools
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from . import MODULE_DIR, __version__


@dataclass(frozen=True)
class BuildInfo:
    version: str
    describe: str | None = None   # git describe --tags --always --dirty, e.g. v0.2.0-3-gb225e1f-dirty
    commit: str | None = None
    branch: str | None = None
    date: str | None = None       # date of the commit (YYYY-MM-DD)
    dirty: bool = False           # uncommitted changes in the tool's own files

    def short(self) -> str:
        """'0.2.0 (feature/x, v0.2.0-3-gb225e1f-dirty, 2026-10-06)' or just '0.2.0' outside a git checkout."""
        extra = [p for p in (self.branch if self.branch != "HEAD" else "detached", self.describe, self.date) if p]
        return f"{self.version} ({', '.join(extra)})" if extra else self.version

    def as_dict(self) -> dict:
        return asdict(self)


def _git(*args: str, run=subprocess.run) -> str | None:
    try:
        r = run(["git", *args], cwd=MODULE_DIR, capture_output=True, text=True, encoding="utf-8", timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    out = (r.stdout or "").strip()
    return out if r.returncode == 0 and out else None


def get(run=subprocess.run) -> BuildInfo:
    """Version and, if the tool lives in its own git checkout, where that checkout stands."""
    top = _git("rev-parse", "--show-toplevel", run=run)
    # Only trust git when the tool itself is the repository: an unpacked copy inside someone else's repo must not
    # report that repo's commit.
    if not top or Path(top).resolve() != MODULE_DIR.resolve():
        return BuildInfo(__version__)
    describe = _git("describe", "--tags", "--always", "--dirty", run=run)
    return BuildInfo(
        version=__version__,
        describe=describe,
        commit=_git("rev-parse", "--short", "HEAD", run=run),
        branch=_git("rev-parse", "--abbrev-ref", "HEAD", run=run),
        date=_git("log", "-1", "--format=%cs", run=run),
        dirty=bool(describe and describe.endswith("-dirty")),
    )


@functools.lru_cache(maxsize=1)
def current() -> BuildInfo:
    """get(), asked only once per run."""
    return get()
