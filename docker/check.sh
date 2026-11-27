#!/usr/bin/env bash
# Tests and docs build in Docker. The checkout is mounted read-only; nothing is written into it.
#
#   docker/check.sh ci                    tests without a firmware cache, on Python 3.10 and 3.12 (as GitHub runs them)
#   docker/check.sh fw [--sync] [--fw D]  tests with the firmware cache volume; --sync first copies new files from fw/
#   docker/check.sh docs                  mkdocs build --strict
#
# Volumes (kept between runs): free-shelly-fw-cache (official packages), free-shelly-pip-cache.
set -euo pipefail

usage() { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

mode="${1:-}"
[ $# -gt 0 ] && shift
sync=0
fw_dir=""
while [ $# -gt 0 ]; do
    case "$1" in
        --sync) sync=1 ;;
        --fw) fw_dir="${2:?--fw needs a folder}"; shift ;;
        *) usage ;;
    esac
    shift
done
case "$mode" in ci | fw | docs) ;; *) usage ;; esac

if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running. Start it and run this again (this script does not start it)." >&2
    exit 1
fi

export MSYS_NO_PATHCONV=1   # Git Bash on Windows must not rewrite the container paths
host_path() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }

repo="$(cd "$(dirname "$0")/.." && pwd)"
src="$(host_path "$repo")"

run() {   # run PYTHON MODE [extra docker options...]
    local python="$1" what="$2"
    shift 2
    docker run --rm -v "$src:/src:ro" -v free-shelly-pip-cache:/root/.cache/pip "$@" "python:$python-slim" \
        sh -c 'tr -d "\r" </src/docker/inside.sh >/tmp/inside.sh && sh /tmp/inside.sh "$1"' check "$what"
}

if [ "$mode" = ci ]; then
    for python in 3.10 3.12; do
        echo "=== Python $python, no firmware cache"
        run "$python" ci
    done
elif [ "$mode" = docs ]; then
    run 3.12 docs
else
    if [ "$sync" = 1 ]; then
        if [ -z "$fw_dir" ]; then
            fw_dir="$repo/fw"
            # a git worktree usually has no cache of its own: take the one of the main checkout
            [ -d "$fw_dir" ] || fw_dir="$(git -C "$src" worktree list --porcelain | sed -n '1s/^worktree //p')/fw"
        fi
        [ -d "$fw_dir" ] || { echo "No firmware cache at $fw_dir (give one with --fw)." >&2; exit 1; }
        echo "=== copying new files from $fw_dir into the volume free-shelly-fw-cache"
        docker run --rm -v "$(host_path "$fw_dir"):/host:ro" -v free-shelly-fw-cache:/fw python:3.12-slim cp -ru /host/. /fw/
    fi
    echo "=== Python 3.12, firmware cache volume"
    run 3.12 fw -v free-shelly-fw-cache:/fw:ro
fi
