# Tests and docs build in Docker. The checkout is mounted read-only; nothing is written into it.
#
#   docker\check.ps1 ci                 tests without a firmware cache, on Python 3.10 and 3.12 (as GitHub runs them)
#   docker\check.ps1 fw [-Sync] [-Fw D] tests with the firmware cache volume; -Sync first copies new files from fw\
#   docker\check.ps1 docs               mkdocs build --strict
#
# Volumes (kept between runs): free-shelly-fw-cache (official packages), free-shelly-pip-cache.
param(
    [Parameter(Mandatory = $true)][ValidateSet('ci', 'fw', 'docs')][string]$Mode,
    [switch]$Sync,
    [string]$Fw
)

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Docker is not running. Start it and run this again (this script does not start it).'
    exit 1
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Invoke-Check([string]$Python, [string]$What, [string[]]$Extra) {
    # no double quotes inside the sh command: Windows PowerShell would drop them on the way to docker
    $command = "tr -d '\r' </src/docker/inside.sh >/tmp/inside.sh && sh /tmp/inside.sh $What"
    docker run --rm -v "${repo}:/src:ro" -v free-shelly-pip-cache:/root/.cache/pip @Extra "python:$Python-slim" sh -c $command
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if ($Mode -eq 'ci') {
    foreach ($python in '3.10', '3.12') {
        Write-Host "=== Python $python, no firmware cache"
        Invoke-Check $python 'ci' @()
    }
} elseif ($Mode -eq 'docs') {
    Invoke-Check '3.12' 'docs' @()
} else {
    if ($Sync) {
        if (-not $Fw) {
            $Fw = Join-Path $repo 'fw'
            if (-not (Test-Path $Fw)) {
                # a git worktree usually has no cache of its own: take the one of the main checkout
                $main = (git -C $repo worktree list --porcelain | Select-Object -First 1) -replace '^worktree ', ''
                $Fw = Join-Path $main 'fw'
            }
        }
        if (-not (Test-Path $Fw)) { Write-Host "No firmware cache at $Fw (give one with -Fw)."; exit 1 }
        $Fw = (Resolve-Path $Fw).Path
        Write-Host "=== copying new files from $Fw into the volume free-shelly-fw-cache"
        docker run --rm -v "${Fw}:/host:ro" -v free-shelly-fw-cache:/fw python:3.12-slim cp -ru /host/. /fw/
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    Write-Host '=== Python 3.12, firmware cache volume'
    Invoke-Check '3.12' 'fw' @('-v', 'free-shelly-fw-cache:/fw:ro')
}
