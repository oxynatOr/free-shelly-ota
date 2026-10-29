"""Compile an ESPHome YAML into the two binaries `build` needs (firmware.ota.bin and firmware.factory.bin).

The runner is the `esphome` command if there is one, else Docker. Commands are lists without a shell, paths go through
pathlib, so it behaves the same on Windows and Linux.
"""

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .builder import OtaError

RUNNERS = ("auto", "esphome", "docker")
# A fixed version, not "latest": the same YAML should give the same build next month.
DEFAULT_IMAGE = "ghcr.io/esphome/esphome:2026.10.0"

# ESPHome keeps its toolchain (ESP-IDF, compilers, ccache, a few GB) and the build files in a data directory, by default
# next to the YAML. On a Windows bind mount that is very slow and repeated for every folder, so Docker gets a named volume
# for it, shared by all builds; only the two binaries are copied back next to the YAML afterwards.
CACHE_VOLUME = "free-shelly-esphome-cache"
_DATA = "/cache/data"
# A new volume belongs to root. On Linux the container runs as the calling user (so the copied binaries are theirs), which
# could then not write into it: this one-off step as root creates the folders and hands the volume over.
_PREPARE = "mkdir -p /cache/data /cache/idf /cache/home"
# $1 is the folder of the YAML inside the container (/config, or /config/<sub folder> when a git repository is mounted)
_COPY_BACK = (f'd=$(ls -dt {_DATA}/build/*/build | head -n 1) && n=$(basename "$(dirname "$d")") && '
              't="$1/.esphome/build/$n/build" && mkdir -p "$t" && '
              'cp -p "$d/firmware.ota.bin" "$d/firmware.factory.bin" "$t/"')

OTA_BIN = "firmware.ota.bin"
FACTORY_BIN = "firmware.factory.bin"


class CompileError(OtaError):
    pass


@dataclass
class Compiled:
    ota: Path
    factory: Path


def _install_hint(runner: str = "auto") -> str:
    docker = "Install Docker Desktop" if os.name == "nt" else "Install Docker"
    esphome = "ESPHome with: pip install esphome" if os.name == "nt" else "ESPHome with: pipx install esphome"
    if runner == "docker":
        return f"{docker}."
    if runner == "esphome":
        return f"Install {esphome}"
    return f"{docker}, or {esphome}" if os.name == "nt" else f"Install {esphome} (or Docker)"


def pick_runner(runner: str = "auto", which: Callable[[str], str | None] = shutil.which) -> str:
    """'esphome' or 'docker'; 'auto' prefers the esphome command."""
    if runner not in RUNNERS:
        raise CompileError(f"Unknown runner '{runner}'. Use one of: {', '.join(RUNNERS)}.")
    if runner in ("auto", "esphome") and which("esphome"):
        return "esphome"
    if runner in ("auto", "docker") and which("docker"):
        return "docker"
    if runner == "auto":
        raise CompileError(f"Neither 'esphome' nor 'docker' was found in the PATH. {_install_hint()}")
    raise CompileError(f"'{runner}' was not found in the PATH. {_install_hint(runner)}")


def docker_running(run: Callable[..., "subprocess.CompletedProcess"] = subprocess.run) -> bool:
    """True if the Docker daemon answers (the docker command alone is not enough: Docker Desktop must be started)."""
    try:
        done = run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == 0


def mount_root(yaml: Path) -> Path:
    """The folder Docker mounts as /config: the git repository the YAML is in (its `!include ../x.yaml` and local
    packages can then be found), else the YAML's own folder."""
    yaml = Path(yaml).resolve()
    home = Path.home().resolve()
    for folder in yaml.parents:
        if folder == home or folder.parent == folder:
            break
        if (folder / ".git").exists():
            return folder
    return yaml.parent


def _in_container(yaml: Path) -> tuple[Path, str, str]:
    """(folder mounted as /config, path of the YAML in the container, folder of the YAML in the container)."""
    yaml = Path(yaml).resolve()
    root = mount_root(yaml)
    rel = yaml.relative_to(root).as_posix()
    folder = yaml.parent.relative_to(root).as_posix()
    return root, f"/config/{rel}", "/config" if folder == "." else f"/config/{folder}"


def build_command(runner: str, yaml: Path, image: str = DEFAULT_IMAGE, *, posix: bool | None = None,
                  uid_gid: tuple[int, int] | None = None, action: str = "compile") -> list[str]:
    """The command line that runs `esphome <action> yaml` (compile, or config to print the resolved config);
    runner is 'esphome' or 'docker'.

    On Linux the container runs as the calling user (uid_gid), so the build files are not owned by root.
    """
    yaml = Path(yaml).resolve()
    if runner == "esphome":
        return ["esphome", action, str(yaml)]
    if runner != "docker":
        raise CompileError(f"Unknown runner '{runner}'.")
    if posix is None:
        posix = os.name == "posix"
    if uid_gid is None and posix:
        uid_gid = (os.getuid(), os.getgid())  # type: ignore[attr-defined]
    root, in_container, _ = _in_container(yaml)
    cmd = _docker_base(root, posix, uid_gid)
    cmd += ["-e", f"ESPHOME_DATA_DIR={_DATA}", "-e", "ESPHOME_ESP_IDF_PREFIX=/cache/idf", "-e", "HOME=/cache/home"]
    return cmd + [image, action, in_container]


def _docker_base(root: Path, posix: bool, uid_gid: tuple[int, int] | None) -> list[str]:
    cmd = ["docker", "run", "--rm", "-v", f"{root}:/config", "-v", f"{CACHE_VOLUME}:/cache"]
    if posix and uid_gid is not None:
        cmd += ["--user", f"{uid_gid[0]}:{uid_gid[1]}"]
    return cmd


def prepare_volume_command(image: str = DEFAULT_IMAGE, *, uid_gid: tuple[int, int] | None = None) -> list[str]:
    """Docker only: make sure the cache volume has its folders and belongs to uid_gid (None: Windows, the container is root)."""
    script = _PREPARE
    if uid_gid is not None and uid_gid[0] != 0:
        uid, gid = int(uid_gid[0]), int(uid_gid[1])
        script += f' && {{ [ "$(stat -c %u /cache/data)" = "{uid}" ] || chown -R {uid}:{gid} /cache; }}'
    return ["docker", "run", "--rm", "-v", f"{CACHE_VOLUME}:/cache", "--entrypoint", "sh", image, "-c", script]


def copy_back_command(yaml: Path, image: str = DEFAULT_IMAGE, *, posix: bool | None = None,
                      uid_gid: tuple[int, int] | None = None) -> list[str]:
    """Docker only: copy the newest build's two binaries from the volume to <yaml folder>/.esphome/build/<name>/build/."""
    root, _, folder = _in_container(yaml)
    if posix is None:
        posix = os.name == "posix"
    if uid_gid is None and posix:
        uid_gid = (os.getuid(), os.getgid())  # type: ignore[attr-defined]
    return _docker_base(root, posix, uid_gid) + ["--entrypoint", "sh", image, "-c", _COPY_BACK, "sh", folder]


def find_binaries(yaml_dir: Path, since: float = 0.0) -> Compiled:
    """The newest firmware.ota.bin (with its firmware.factory.bin) under yaml_dir/.esphome/build modified at or after `since`.

    ESP-IDF builds write it to <name>/build/, PlatformIO builds to <name>/.pioenvs/<name>/.
    """
    root = Path(yaml_dir) / ".esphome" / "build"
    found = sorted((p for p in [*root.glob(f"*/build/{OTA_BIN}"), *root.glob(f"*/.pioenvs/*/{OTA_BIN}")]
                    if p.stat().st_mtime >= since),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    if not found:
        raise CompileError(f"The compile ended, but no {OTA_BIN} was found under {root}.")
    ota = found[0]
    factory = ota.with_name(FACTORY_BIN)
    if not factory.is_file():
        raise CompileError(f"{factory} is missing next to {OTA_BIN}. Is this an ESP-IDF build (framework: type: esp-idf)?")
    return Compiled(ota, factory)


def _ready_docker(image: str, run: Callable[..., "subprocess.CompletedProcess"]) -> None:
    """The Docker daemon answers and the cache volume exists and belongs to the user."""
    if not docker_running(run):
        start = "Start Docker Desktop" if os.name == "nt" else "Start the Docker service (sudo systemctl start docker)"
        raise CompileError(f"Docker is installed but not running. {start} and try again.")
    uid_gid = (os.getuid(), os.getgid()) if os.name == "posix" else None  # type: ignore[attr-defined]
    try:
        prepared = run(prepare_volume_command(image, uid_gid=uid_gid), check=False)
    except OSError as e:
        raise CompileError(f"Could not start docker: {e}") from e
    if prepared.returncode != 0:
        raise CompileError("Could not prepare the Docker volume for the ESPHome cache (the messages above say why).")


def resolve_config(yaml: Path, runner: str = "auto", image: str = DEFAULT_IMAGE,
                   run: Callable[..., "subprocess.CompletedProcess"] = subprocess.run,
                   which: Callable[[str], str | None] = shutil.which) -> str:
    """The full config as ESPHome sees it (`esphome config`): `packages:`, `!include` and substitutions resolved.

    The text is only returned, never written or printed: it can hold secrets. `github://` packages need the network
    the first time.
    """
    yaml = Path(yaml)
    if not yaml.is_file():
        raise CompileError(f"YAML file not found: {yaml}")
    chosen = pick_runner(runner, which)
    if chosen == "docker":
        _ready_docker(image, run)
    cmd = build_command(chosen, yaml, image, action="config")
    try:
        done = run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    except OSError as e:
        raise CompileError(f"Could not start {cmd[0]}: {e}") from e
    if done.returncode != 0:
        raise CompileError("ESPHome could not read the config:\n  " + "\n  ".join(_why(done)))
    return done.stdout


def _why(done: "subprocess.CompletedProcess") -> list[str]:
    """The lines that say why `esphome config` failed. The message is on stderr with Docker and on stdout with the
    esphome command (stdout then goes on with a dump of the config), so both are read: from "Failed config" on if
    that is there, else the last lines without the INFO ones."""
    lines = [l.rstrip() for l in ((done.stdout or "") + "\n" + (done.stderr or "")).splitlines() if l.strip()]
    lines = [l for l in lines if not l.startswith("INFO ")]
    start = next((i for i, l in enumerate(lines) if l.startswith("Failed config")), None)
    if start is not None:
        return lines[start:start + 12]
    return lines[-20:] or ["(no message; run `esphome config` on the file to see it)"]


def compile_yaml(yaml: Path, runner: str = "auto", image: str = DEFAULT_IMAGE,
                 run: Callable[..., "subprocess.CompletedProcess"] = subprocess.run,
                 which: Callable[[str], str | None] = shutil.which) -> Compiled:
    """Compile the YAML (output goes straight to the terminal) and return the two binaries."""
    yaml = Path(yaml)
    if not yaml.is_file():
        raise CompileError(f"YAML file not found: {yaml}")
    chosen = pick_runner(runner, which)
    if chosen == "docker":
        _ready_docker(image, run)
    cmd = build_command(chosen, yaml, image)
    started = time.time() - 2  # file times can be a little coarse
    try:
        done = run(cmd, check=False)
    except OSError as e:
        raise CompileError(f"Could not start {cmd[0]}: {e}") from e
    if done.returncode != 0:
        raise CompileError(f"The compile failed (exit code {done.returncode}). The messages above say why.")
    if chosen == "docker":
        back = copy_back_command(yaml, image)
        try:
            done = run(back, check=False)
        except OSError as e:
            raise CompileError(f"Could not start docker: {e}") from e
        if done.returncode != 0:
            raise CompileError("The compile worked, but copying firmware.ota.bin out of the Docker volume failed.")
    return find_binaries(yaml.resolve().parent, since=started)
