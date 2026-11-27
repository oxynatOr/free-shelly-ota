#!/bin/sh
# Runs inside the container (docker/check.sh and docker/check.ps1 call it). Do not run it on the host.
# /src = the checkout (read-only), /fw = the firmware cache volume (mode fw), $1 = ci | fw | docs
set -e

mkdir -p /work
cd /src
tar --exclude=./fw --exclude=./out --exclude=./logs --exclude=./site --exclude=./.git --exclude=__pycache__ \
    --exclude=./.pytest_cache -cf - . | tar -xf - -C /work
cd /work
export PYTHONDONTWRITEBYTECODE=1 PIP_ROOT_USER_ACTION=ignore PIP_DISABLE_PIP_VERSION_CHECK=1

if [ "$1" = docs ]; then
    pip install -q -r requirements-docs.txt
    NO_MKDOCS_2_WARNING=1 mkdocs build --strict
    exit 0
fi

pip install -q -r requirements.txt
if [ "$1" = fw ]; then
    ln -s /fw /work/fw
    python docker/missing_fw.py
fi

status=0
python -m unittest discover tests >/tmp/tests.log 2>&1 || status=$?
if [ "$status" -ne 0 ]; then
    cat /tmp/tests.log
else
    tail -n 4 /tmp/tests.log
fi
exit "$status"
