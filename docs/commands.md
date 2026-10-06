# Commands

[Back to the README](../README.md)

The usual workflow is three steps:

```
python ota.py fetch PlugMG3 --insecure                  # 1. get the official package
python ota.py build PlugMG3 app.bin                     # 2. put your app into it
python ota.py send  PlugMG3 out/<file>.zip --watch 60   # 3. send it to the device
```

| Group | Command | What it does |
| --- | --- | --- |
| Prepare | `fetch` | Download the official package and keep it in `fw/` |
| Prepare | `add-device` | Create a device profile from an official ZIP (`--parent` for a variant) |
| Prepare | `partition-csv` | Write the stock partition table as ESPHome `partitions:` CSV (`-o FILE`) |
| Build | `build` | Replace the app part, check the image, write the ZIP to `out/` |
| Deploy | `send` | Check the device, serve the ZIP, trigger the update |
| Deploy | `restore` | Send the cached official firmware back |
| Deploy | `log` | Show the device's live debug log |
| Tools | `inspect` | Show and verify a ZIP |
| Tools | `list` | Show devices and cached firmware |
| Tools | `profiles` | List the profiles with their revision, check `devices/profiles.lock` (`--update-lock` writes it) |
| Tools | `clean` | Delete old ZIPs in `out/` (needs `--yes`) |
| Tools | `colors` | Show every message color once and say whether colors are on |

`python ota.py <command> -h` shows the options of any command; `python ota.py --version` the tool version
([Versions](versions.md)).

## Colors

In a terminal the messages are colored: yellow for warnings, orange for critical ones (bootloader replaced, data wiped,
wrong update target), red for errors, green for success. The words `WARNING:`, `NOTE:`, `Error:` and `OK:` stay in the text,
so logs and pipes read the same. No colors when the output is not a terminal or `NO_COLOR` is set.
`python ota.py --color never <command>` (or `always`) overrides that; the option goes before the command.
`python ota.py colors` tells you whether colors are on and, if not, why.

## fetch

Downloads the official package to `fw/shelly/<Device>/<version>/` (with a `meta.json`) and verifies the hash in the download
URL. Shelly's servers use a private CA, so TLS verification fails; `--insecure` skips it.

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `DEVICE` | yes | | Profile name, e.g. `PlugMG3` |
| `--refresh` | no | off | Check for a newer version even if one is cached |
| `--version VER` | no | latest cached | Use this cached version |
| `--insecure` | no | off | Skip the TLS check (the URL hash only guards against transfer errors) |

## build

Replaces the app part and writes `out/<Device>-<app>-<date>.zip` plus `.sha256` and `.report.json`. The app is checked for
magic byte, chip id, segment count and fit into the app slot. It never downloads on its own and never overwrites an input
file.

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `DEVICE` | yes | | Profile name |
| `APP.bin` | yes | | ESPHome app binary (the `.ota.bin`, not the merged image) |
| `--esphome-yaml YAML` | no | none | Also check the partition offset and `partitions:` CSV of this config, and run the [credential check](credential-check.md) |
| `--esphome-factory FACTORY.bin` | no | none | Also ship ESPHome's bootloader and a clean `otadata` taken from this factory image (same build as `APP.bin`). See [Bootloader and slots](bootloader-and-slots.md) |
| `--boot-min-version VER` | no | profile value, else one patch above Shelly's | Only with `--esphome-factory`: the bootloader `min_version` in the manifest. The installer writes only a newer bootloader. `keep` leaves it, which probably makes the installer skip the bootloader |
| `--secrets FILE` | no | `secrets.yaml` next to `--esphome-yaml` | Values to look for in the image |
| `--fail-on-secrets` | no | off | Stop (no output) if the image contains credentials. Use it for packages meant to be shared |
| `--tag LABEL` | no | none | Own label for file name and report; the manifest stays untouched |
| `--drop LIST` | no | nothing | Leave out parts: `boot,pt,otadata,nvs,fs` (dropping `nvs`/`otadata` is untested on devices) |
| `-o`, `--output ZIP` | no | `out/<auto name>` | Output file |
| `--dry-run` | no | off | Check everything, keep no output |

<details>
<summary>More options</summary>

| Option | Description |
| --- | --- |
| `--drop-fs` | Same as `--drop fs` |
| `--official ZIP` | Use this official ZIP instead of the cache |
| `--version VER` | Use this cached version (default: latest) |
| `--download` | Download the official ZIP if none is cached (off by default) |
| `--insecure` | With `--download`: skip the TLS check |

</details>

Without `--esphome-factory`, `--esphome-yaml` also warns if `allow_partition_access` is missing in the `ota:` block (needed to
update the bootloader later).

## send

Checks the device (`Shelly.GetDeviceInfo`, the model must match), asks before flashing, serves the ZIP on a temporary web
server and calls `Shelly.Update?url=…`. The Shelly downloads the file itself, so this PC must be reachable from it, for
example connected to the Shelly's own access point.

For a package that replaces the bootloader, `send` first reads the update target slot and refuses if it is not slot 0
([why](bootloader-and-slots.md#the-app-must-land-in-slot-0)).

> [!WARNING]
> While `send` runs, its web server listens on all interfaces of this PC and hands the ZIP to anyone on the network who asks
> for its exact file name. The ZIP may contain your Wi-Fi password, so do not run it on an untrusted network.

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `DEVICE`, `ZIP` | yes | | Profile name and the ZIP to send |
| `--ip IP` | no | `192.168.33.1` | Address of the Shelly |
| `--watch SEC` | no | off | Show the device's debug log (UDP, switched on over RPC and restored afterwards) and keep listening SEC seconds after the download |
| `--user USER` / `--password PW` | no | `admin` / none | Login, if the device has a password (digest auth) |
| `--yes` | no | off | Do not ask before flashing |
| `--dry-run` | no | off | Check the device only, send nothing |
| `--ignore-slot` | no | off | Send even if the installer would write to a slot that ESPHome's bootloader does not start |

<details>
<summary>More options</summary>

| Option | Default | Description |
| --- | --- | --- |
| `--force` | off | Send even if the device model does not match |
| `--host IP` | auto | This PC's address as seen by the Shelly |
| `--port PORT` | `8000` | Local web server port |
| `--log-port PORT` | `9514` | UDP port for the debug log |
| `--timeout SEC` | `300` | How long to wait for the device to download the ZIP |

</details>

## restore

Takes the same options as `send`, but sends the cached official firmware instead of a ZIP you choose. It works only while
Shelly firmware is still running: a device that already runs ESPHome with ESPHome's bootloader does not answer, and the way
back is UART ([Recovery over UART](recovery-uart.md)). The official package also resets NVS and `otadata`, so Wi-Fi
credentials and settings are lost.

## log

Shows the live debug log of a Shelly without sending anything:
`python ota.py log --ip 192.168.1.50 --seconds 30`. Options: `--ip`, `--user`, `--password`, `--host`, `--log-port` and
`--seconds` (default: until Ctrl+C).
