# Commands

[← README](../README.md) · [Documentation](README.md) · [Device pages](devices/README.md) · [Troubleshooting](troubleshooting.md)

[📥 fetch](#fetch) · [🔨 build](#build) · [📤 send](#send) · [↩️ restore](#restore) · [📶 ble](#ble) · [➕ add-device](#add-device) · [📋 partition-csv](#partition-csv) · [🔍 inspect](#inspect) · [🧪 devkit](#devkit) · [📃 list](#list) · [🧹 clean](#clean) · [📜 log](#log) · [🎨 Colors](#colors)

The usual workflow is three steps:

```
python ota.py fetch PlugMG3 --insecure                  # 1. get the official package
python ota.py build PlugMG3 app.bin                     # 2. put your app into it
python ota.py send  PlugMG3 out/<file>.zip              # 3. send it to the device
```

| Group | Command | What it does |
| --- | --- | --- |
| Prepare | [`fetch`](#fetch) | Download the official package and keep it in `fw/` |
| Prepare | [`add-device`](#add-device) | Create a device profile from an official ZIP (`--parent` for a variant) |
| Prepare | [`partition-csv`](#partition-csv) | Write the stock partition table as ESPHome `partitions:` CSV (`-o FILE`) |
| Build | [`build`](#build) | Replace the app part, check the image, write the ZIP to `out/` |
| Deploy | [`send`](#send) | Check the device, serve the ZIP, trigger the update |
| Deploy | [`restore`](#restore) | Send the cached official firmware back |
| Deploy | [`ble`](#ble) | Bluetooth: scan, call an RPC method, give a device without Wi-Fi its Wi-Fi |
| Deploy | [`log`](#log) | Show the device's live debug log |
| Tools | [`inspect`](#inspect) | Show and verify a ZIP |
| Tools | [`devkit`](#devkit) | Write a flash image of a package for a dev board and print the `esptool` commands |
| Tools | `list` | Show devices and cached firmware |
| Tools | `profiles` | List the profiles with their revision, check `devices/profiles.lock` (`--update-lock` writes it) |
| Tools | [`clean`](#clean) | Delete old ZIPs in `out/` (needs `--yes`) |
| Tools | [`colors`](#colors) | Show every message color once and say whether colors are on |

> [!TIP]
> `python ota.py -h` lists the commands in the groups of this table, a typical run and what to know before you flash;
> `python ota.py <command> -h` shows the options of one command, grouped by topic; `python ota.py --version` the tool version
> ([Versions](versions.md)).

## Colors

In a terminal the messages are colored: yellow for warnings, orange for critical ones (bootloader replaced, data wiped,
wrong update target), red for errors, green for success. The words `WARNING:`, `NOTE:`, `Error:` and `OK:` stay in the text,
so logs and pipes read the same. No colors when the output is not a terminal or `NO_COLOR` is set.
`python ota.py --color never <command>` (or `always`) overrides that; the option goes before the command.
`python ota.py colors` tells you whether colors are on and, if not, why.

## fetch

Downloads the official package to `fw/shelly/<Device>/<version>/` (with a `meta.json`) and verifies the hash in the download
URL.

> [!NOTE]
> Shelly's servers use a private CA, so TLS verification fails; `--insecure` skips it.

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `DEVICE` | yes | | Profile name, e.g. `PlugMG3` |
| `--refresh` | no | off | Check for a newer version even if one is cached |
| `--version VER` | no | newest stable cached | Use this cached version (a pre-release such as `2.2.0-beta1` only with this option) |
| `--channel stable\|beta` | no | `stable` | Release channel of the update API |
| `--from-version VER` | no | none | Ask the update API as a device running VER would. The server answers per installed version, which the device sends in the `Shelly-Info` header; a request without it, or from a device that already runs the newest package, may list no stable release (the H&T Gen3 looked removed that way). `fetch HTG3 --from-version 1.4.4` gets the stable 2.0.1 |
| `--insecure` | no | off | Skip the TLS check (the URL hash only guards against transfer errors) |

## build

Replaces the app part and writes `out/<Device>-<app>-<date>.zip` plus `.sha256` and `.report.json`. The app is checked for
magic byte, chip id, segment count and fit into the app slot. It never downloads on its own and never overwrites an input
file.

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `DEVICE` | yes | | Profile name |
| `APP.bin` | yes, unless `--compile` | | ESPHome app binary (the `.ota.bin`, not the merged image) |
| `--compile YAML` | no | none | Compile this ESPHome config first and use its `firmware.ota.bin` as `APP.bin` and its `firmware.factory.bin` as `--esphome-factory`; the YAML is also checked (`--esphome-yaml`). Give it instead of `APP.bin`. See [Compile](#compile) |
| `--runner auto\|esphome\|docker` | no | `auto` | Only with `--compile`: how ESPHome is run. `auto` takes the `esphome` command from the PATH, else Docker |
| `--image NAME:TAG` | no | a fixed ESPHome version | Only with `--compile` and Docker: the ESPHome image |
| `--esphome-yaml YAML` | no | none | Also check the partition offset and `partitions:` CSV of this config, and run the [credential check](credential-check.md) |
| `--esphome-factory FACTORY.bin` | no | none | Also ship ESPHome's bootloader and a clean `otadata` taken from this factory image (same build as `APP.bin`). See [Bootloader and slots](bootloader-and-slots.md) |
| `--boot-min-version VER` | no | profile value, else one patch above Shelly's | Only with `--esphome-factory`: the bootloader `min_version` in the manifest. The installer writes only a newer bootloader. `keep` leaves it, which probably makes the installer skip the bootloader |
| `--secrets FILE` | no | `secrets.yaml` next to `--esphome-yaml` | Values to look for in the image |
| `--fail-on-secrets` | no | off | Stop (no output) if the image contains credentials. Use it for packages meant to be shared |
| `--tag LABEL` | no | none | Own label for file name and report; the manifest stays untouched |
| `--drop LIST` | no | nothing | Leave out parts: `boot,pt,otadata,nvs,fs` (dropping `nvs`/`otadata` is untested on devices) |
| `-o`, `--output ZIP` | no | `out/<auto name>` | Output file. A name given here is replaced if it exists |
| `--force` | no | off | Replace the automatically named output if it already exists. Without it, `build` stops: the name carries only the app file name, the date and the tag, so two builds on one day (ESPHome always calls the app `firmware.ota.bin`) get the same one, and the first package may already be on a device. Use `--tag` or `-o` for a second package |
| `--dry-run` | no | off | Check everything, write nothing. It builds in a scratch directory, so an existing package and its `.sha256` and `.report.json` stay as they are. If the real build would stop because the output exists, it says so |

<details>
<summary>More options</summary>

| Option | Description |
| --- | --- |
| `--drop-fs` | Same as `--drop fs` |
| `--official ZIP` | Use this official ZIP instead of the cache |
| `--version VER` | Use this cached version (default: the newest stable one; a pre-release only with this option) |
| `--download` | Download the official ZIP if none is cached (off by default) |
| `--insecure` | With `--download`: skip the TLS check |
| `--channel stable\|beta` | With `--download`: release channel of the update API |
| `--from-version VER` | With `--download`: ask the update API as a device running VER would (see [`fetch`](#fetch)) |

</details>

`--esphome-yaml` also warns if `allow_partition_access` is missing in the `ota:` block, with and without `--esphome-factory`:
ESPHome needs it to update the bootloader later (without `--esphome-factory` also to avoid falling back to the previous image).

### Compile

`--compile YAML` runs ESPHome for you, so there is one command from config to package:

```
python ota.py build PlugMG3 --compile my-plug.yaml
```

The config is checked first (before the compile, which takes minutes), then compiled, and the build goes on with the two binaries and the credential check as usual. The binaries are read from `.esphome/build/<name>/build/` next to the YAML.

- **`packages:` and `!include`.** If the YAML itself has no `esp32:` block (it comes from `packages:` or an `!include`, local or `github://`), `build` asks ESPHome for the full config (`esphome config`, a few seconds; `github://` packages need the network the first time, and `git` when you use the `esphome` command; the Docker image has it) and runs the config check on that: the partition table, the offset and `allow_partition_access` are found wherever they come from. The resolved text stays in memory, it can hold secrets. A config that does not have Shelly's layout is refused here, before the compile. With `--esphome-yaml` alone (no `--compile`) the file is read as it is and `packages:` are not followed.
- **What Docker sees.** The folder of the YAML, or, if the YAML is inside a git repository, the whole repository (so `!include ../shared/x.yaml` in the same repository is found). The binaries still land next to the YAML. A YAML outside a repository sees only its own folder.
- **Runner.** `auto` uses the `esphome` command if there is one, else Docker. `--runner` forces one of them. If neither is there, `build` says what to install: Docker Desktop or `pip install esphome` on Windows, `pipx install esphome` on Linux.
- **Docker has to be running.** `build` asks the Docker daemon first and stops with "Docker is installed but not running" (start Docker Desktop on Windows, `sudo systemctl start docker` on Linux). It never starts Docker itself.
- **The cache volume.** The toolchain (ESP-IDF, compilers, ccache; 3 GB and more) and the build files live in the Docker volume `free-shelly-esphome-cache`, shared by every YAML. **The first compile downloads the toolchain and builds everything (about a minute and a half on a fast connection, longer on a slow one), later ones reuse it and take seconds.** Keep the volume: without it every compile starts from nothing. A new ESPHome version (`--image`) adds its own toolchain to the volume once. The volume is not next to the YAML on purpose: a Windows folder mounted into the container is very slow for this many small files.
- **What lands next to the YAML.** Only `firmware.ota.bin` and `firmware.factory.bin`, copied to `.esphome/build/<name>/build/`. They hold the Wi-Fi credentials of the config, so that folder is as private as the YAML and `secrets.yaml`.
- **Linux.** The container runs as your own user, so the copied files are yours. A new volume belongs to root; `build` hands it to you once before the first compile, with a short root container.
- **Housekeeping.** `docker volume inspect free-shelly-esphome-cache` shows it, `docker system df -v` its size, `docker volume rm free-shelly-esphome-cache` removes it (the next compile downloads everything again).
- **The `esphome` command** keeps its own cache (`~/.cache/esphome`) and writes the build files next to the YAML. Under WSL keep the YAML in the Linux home (`~/...`), not on `/mnt/c` or `/mnt/i`, which is slow.
- **Image.** The Docker image has a fixed ESPHome version, not `latest`, so the same YAML gives the same build next month. `--image NAME:TAG` takes another one. The `esphome` command is whatever version you installed; for two comparable packages use the same version for both.
- **Not with `APP.bin`.** Either give the binary or `--compile`; `--runner` and `--image` need `--compile`.

## send

Checks the device (`Shelly.GetDeviceInfo`, the model must match), asks before flashing, serves the ZIP on a temporary web
server and calls `Shelly.Update?url=…`. The Shelly downloads the file itself, so this PC must be reachable from it, for
example connected to the Shelly's own access point.

For a package that replaces the bootloader, `send` first reads the update target slot and refuses if it is not slot 0
([why](bootloader-and-slots.md#the-app-must-land-in-slot-0)).

It also asks the device to fetch `http://<this PC>:<port>/` itself (RPC `HTTP.GET`), so a Shelly that cannot reach this PC
(firewall, VLAN) is reported at once instead of after the `--timeout`. With `--dry-run` that is an error; a real `send` only
warns and goes on, because the download is what counts. A device without `HTTP.GET` gets a note.

> [!WARNING]
> While `send` runs, its web server listens on all interfaces of this PC and hands the ZIP to anyone on the network who asks
> for its exact file name. The ZIP may contain your Wi-Fi password, so do not run it on an untrusted network.

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `DEVICE`, `ZIP` | yes | | Profile name and the ZIP to send |
| `--ip IP` | no | `192.168.33.1` | Address of the Shelly |
| `--log-level LEVEL`, `-q`, `-v` | no | `normal` | How much is shown, see [Log levels](#log-levels) |
| `--log-file [PATH]` | no | off | Write the whole run to a file, whatever the level (without a path: `logs/<zip name>.send.log`) |
| `--watch SEC` | no | 30 s if an update is seen | After the download wait up to SEC seconds for the device to confirm the update |
| `--user USER` / `--password PW` | no | `admin` / none | Login, if the device has a password (digest auth) |
| `--yes` | no | off | Do not ask before flashing |
| `--dry-run` | no | off | Check the device (also whether it can reach this PC), send nothing |
| `--ignore-slot` | no | off | Send even if the installer would write to a slot that ESPHome's bootloader does not start |

<details>
<summary>More options</summary>

| Option | Default | Description |
| --- | --- | --- |
| `--force` | off | Send even if the device model does not match, or if the package keeps Shelly's bootloader (not built with `--esphome-factory`). Without `--force`, `send` stops in that case: the old image would come back after three starts, and only the first ESPHome OTA could change that ([why](bootloader-and-slots.md#without-esphomes-bootloader-plain-package)) |
| `--host IP` | auto | This PC's address as seen by the Shelly |
| `--port PORT` | `8000` | Local web server port |
| `--log-port PORT` | `9514` | UDP port for the debug log |
| `--timeout SEC` | `300` | How long to wait for the device to download the ZIP. A device on a weak Wi-Fi signal can need much longer (about 1 % per 5 s at -68 dBm); `send` then asks, see [Wi-Fi signal](#wi-fi-signal) |
| `--max-wait SEC` | `3600` | If the device takes the ZIP slowly but steadily, `send` estimates the end from the speed of the last minute, says so with the time left and extends the wait on its own, up to SEC in total. The speed comes from what the PC has handed out, so it works without the device's log. A download that stands still is not extended |
| `--wait SEC` | `120` | If the device refuses the update because it has only just started (`Not committed`): wait SEC seconds, then ask again before the next try |

</details>

A device that has been running for less than two minutes refuses `Shelly.Update` with `Not committed`. `send` reads the uptime
(`Sys.GetStatus`) first, says so and offers to wait. If the device refuses anyway, `send` explains it, offers to wait `--wait`
seconds and asks for a new confirmation before the next pass (at most three passes). With `--yes` it never waits or retries on its own.
See [Troubleshooting](troubleshooting.md#send-stops-with-not-committed).

### A slow download

While the device downloads, `send` works out the time left from what it has handed out (it does not need the device's log) and shows `Download 31 %, about 14 min left` as long as the device's own progress line is not there.
If the end lies beyond the wait (`--timeout`), `send` extends the wait on its own and says so, up to `--max-wait` (default 3600 s). A download that stands still is not extended; after `--timeout` the
question "Wait longer?" stays as it was.

### Wi-Fi signal

`send` reads the device's Wi-Fi signal (`Wifi.GetStatus`, a hint only: a device that does not answer is not an error) and shows it at `-v`. At **-67 dBm or weaker** it says that
the download can be very slow (a Mini 1 Gen3 at -68 dBm needed about 20 minutes) and asks how long to wait:

```
Wait for the download for [1200 s]  Enter = that, a number = other seconds, s = skip, c = cancel:
```

Enter takes the suggested wait (at least 1200 s), a number sets another one, `s` (or `skip`) skips the question and keeps `--timeout`, `c` (or `cancel`) cancels before anything is sent.
The same question comes if the wait runs out while the device is still taking the ZIP ("the device has taken about 28 % ... still downloading"): Enter waits as long again,
a number waits that long, `c` stops. `send` never waits longer on its own: with `--yes` or `--dry-run` it only says so, and a stalled download still ends with an error.
The threshold is a guess from one report.

### Log levels

While the update runs, `send` reads the device's debug log (UDP, switched on over RPC and put back afterwards). That gives the
progress and the device's own confirmation, without `--watch`. `--log-level` (or `-q`, `-v`, `-vv`) chooses how much of the output
is shown:

| Level | Shown |
| --- | --- |
| `quiet` (`-q`) | Errors, questions and the final result. After a failure the last lines of the device log are printed anyway. |
| `normal` (default) | + warnings, the key lines (target slot, bootloader decision, update started ...) and the progress: one line that updates in place (`Update [####---] 45 %, about 14 s left`; the time left appears once 20 points are done), or one line per 10 % when the output is not a terminal. `--log-level debug` shows the device's log lines instead of the bar |
| `verbose` (`-v`) | + notes and explanations, every step of the update, and how many entries were hidden |
| `debug` (`-vv`) | every entry of the device log on its own line, the RPC requests of other clients included (`RPC Shelly.GetStatus <- 192.168.1.10:47470`) |
| `raw` | like `debug`, and the device log exactly as it arrives (several entries glued together in one line) |

`--log-file` writes everything to a file, whatever the level on the screen: each message and each device log entry on its own line.
It is the file for a bug report. Without a path it is `logs/<zip name>.send.log` (`logs/<device>.restore.log` for `restore`) and
the next run overwrites it; give a path to keep it. Put the option after DEVICE and ZIP, or write `--log-file=PATH`, otherwise it
takes the next word as its path. Without a log that reaches this PC (a firewall) the progress and the confirmation are missing and
`send` ends with "Done: the device downloaded the ZIP" ([Troubleshooting](troubleshooting.md#no-progress-no-device-log)).

## restore

Takes the same options as `send`, but sends the cached official firmware instead of a ZIP you choose. `--version VER` picks a cached version (default: the newest stable one).

> [!WARNING]
> It works only while Shelly firmware is still running: a device that already runs ESPHome with ESPHome's bootloader does not
> answer, and the way back is UART ([Recovery over UART](recovery-uart.md)).

The official package may also reset NVS and `otadata`, so Wi-Fi credentials and settings can be lost (a PM Mini Gen3 that went
from 2.0.1 to 2.0.1 this way kept both; do not count on it).

## ble

`python ota.py ble ACTION [ARG ...]` talks to a Shelly over Bluetooth LE. A device that has no Wi-Fi yet cannot be reached by `send`, which needs an
address: the Zigbee firmware on a dev board (Mini 1PM Gen4) came up with `WiFi mode: off`, no access point and `provision: pending`, and only its
Bluetooth RPC was on. `ble wifi` gives it a Wi-Fi, then `send` works as usual.

| Action | What it does |
| --- | --- |
| `scan` | List the Shellies in range, the strongest first |
| `info` | `Shelly.GetDeviceInfo` (app, version, `provision`) |
| `call METHOD [JSON]` | Any RPC method, for example `call Zigbee.GetStatus` or `call Wifi.GetStatus` |
| `wifi SSID [PASSWORD]` | `Wifi.SetConfig` (station), then waits for the address and prints it. `-` as the password asks for it without showing it |

Options: `-a ADDR` / `--address ADDR` (Bluetooth address; default: the strongest Shelly in range), `--timeout SEC` (answer, default 15), `--wait SEC` (address after `wifi`, default
40), `--no-wait`. It needs `pip install bleak` (also `requirements-ble.txt`) and a Bluetooth LE adapter in this PC; all other commands work without both.

```
python ota.py ble scan
python ota.py ble wifi MyNetwork -
python ota.py send Mini1PMG4ZB out/<package>.zip --ip <the address printed> --dry-run
```

> [!NOTE]
> The Bluetooth address is not the Wi-Fi MAC (on the device seen it was the MAC + 2). A password typed on the command line stays in the shell history: use `-`.
> `restore` and the ESPHome package wipe NVS, so the Wi-Fi is gone again afterwards; `ble wifi` sets it once more.

## add-device

Creates a profile from an official ZIP: `python ota.py add-device NewDevice.zip`. `--name NAME` sets the device name (default: the name in the ZIP),
`--parent DEVICE` marks a variant of another device (for example the Zigbee version), `--force` overwrites an existing profile. The new profile starts at
`revision: 1`; run `python ota.py profiles --update-lock` afterwards ([Versions](versions.md)).

## partition-csv

Writes Shelly's stock partition table as a CSV for ESPHome's `partitions:` option, read from the cached official package
(run `fetch` first): `python ota.py partition-csv HTG3 -o HTG3-stock.csv`. Without `-o` it prints the CSV. The same files are
in `partitions/`; use this command for a profile you added yourself. Set `CONFIG_PARTITION_TABLE_OFFSET` in your config to the
profile's `pt_offset`.

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `DEVICE` | yes | | Profile name |
| `-o`, `--output CSV` | no | print | Write to this file; refuses to overwrite an existing file |
| `--force` | no | off | Overwrite an existing output file |
| `--official ZIP` | no | the cache | Use this official ZIP instead of the cached one |
| `--version VER` | no | newest stable cached | Use this cached version (a pre-release only with this option) |

## inspect

Shows and verifies a ZIP (manifest, part hashes, credential warnings): `python ota.py inspect out/<file>.zip`. `--device DEVICE` also shows how full
the app slot is.

## devkit

Writes a flash image of a package, to play the whole update through on a dev board ([Test the update on a dev board](devkit.md)):
`python ota.py devkit PlusUni`. The image goes to `out/<Device>-devkit-<version>.bin`; the tool prints the `esptool` commands and does not run them.

| Option | Default | What it does |
| --- | --- | --- |
| `--zip ZIP` | the cached official package | Use this package instead (one from `build` gives the state after an install) |
| `--version VER` | the newest stable one | Use this cached official version |
| `-o`, `--output BIN` | `out/<Device>-devkit-<version>.bin` | Write to this file |
| `--force` | off | Overwrite an existing output file |
| `--flash-size SIZE` | none | Stop if the layout needs more flash than the board has: `4MB`, `8MB` or `16MB` |
| `--port PORT` | `COMx` | Serial port in the printed commands |

> [!WARNING]
> The image overwrites the whole flash of a board and holds Shelly's firmware. Use a spare board, not a device, and do not share the file.

## list

`python ota.py list` shows one line per device: profile, name, app slot size and the cached official firmware versions. The device name is shortened to fit the terminal. `--details` (or `--all`) shows two lines per device with the profile revision and the build id of each cached firmware.

## clean

Deletes old ZIPs in `out/`. `--keep N` keeps the newest N (default 5); nothing is deleted without `--yes`.

## log

Shows the live debug log of a Shelly without sending anything:
`python ota.py log --ip 192.168.1.50 --seconds 30`. Options: `--ip`, `--user`, `--password`, `--host`, `--log-port`,
`--seconds` (default: until Ctrl+C) and `--log-level` / `-q` / `-v` (default `debug`, see [Log levels](#log-levels)).

`--replay FILE` shows a saved log without a device: a `--log-file` file, or the output of `--log-level raw`, at the level you
choose: `python ota.py log --replay logs/x.send.log --log-level normal`.

---

[Device pages](devices/README.md) · [Bootloader and slots](bootloader-and-slots.md) · [Credential check](credential-check.md) · [Versions](versions.md)
