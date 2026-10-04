<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
[![Stargazers][stars-shield]][stars-url]
[![Forks][forks-shield]][forks-url]
[![Issues][issues-shield]][issues-url]
[![project_license][license-shield]][license-url]
<br />
<h1 align="center">Free-Shelly OTA <sup>WIP</sup></h1>
<p align="center">
  Pack your own ESPHome firmware into an official-style Shelly OTA package — and send it to the device.
</p>

`free-shelly-ota` is a small command-line tool for **Shelly Gen3 (ESP32-C3)** and **Gen4 (ESP32-C6)** devices. It takes the
official OTA package for your device, replaces only the `app` part with your ESPHome image, fixes size and SHA-256 in
the manifest, and can hand the result to the Shelly: it checks the device, serves the ZIP from this PC and triggers the
update over RPC. Optionally it shows the device's debug log while that happens.

> **Status: experimental.** Packaging is covered by tests. The whole chain (`build` and `send`) has been confirmed on
> one real device so far, the Shelly Plug M Gen3; everything else is untested on hardware. Keep UART access as your
> way back.


⚠️ Disclaimer
-------------

Installing third-party firmware voids your Shelly warranty, and Shelly cannot provide technical support for a device
running third-party code. Incorrect flashing can brick your device. Always back up your original firmware before
proceeding. You assume all responsibility for any damage, data loss, or device failure. This project is not affiliated
with Shelly, Allterco Robotics, Schneider Electric, ESPHome, CSA, or Espressif Systems.


Tested devices
--------------

| Manufacturer | Device                       | Profile       | Chip     | Package | Tested on hardware |
| ---          | ---                          | ---           | ---      | ---     | --- |
| Shelly       | Plug M Gen3                  | `PlugMG3`     | ESP32-C3 | 2.0.1   | ✅ `send` from stock 1.8.99, then two ESPHome OTAs |
| Shelly       | Duo Bulb Gen3                | `DuoBulbG3`   | ESP32-C3 | 2.0.1   | not yet |
| Shelly       | Multicolor Bulb E27 Gen3     | `RGBCCTBulbG3`| ESP32-C3 | 2.0.1   | not yet |
| Shelly       | Plug S Gen3                  | `PlugSG3`     | ESP32-C3 | 2.0.1   | not yet |
| Shelly       | Plug US Gen4                 | `PlugUSG4`    | ESP32-C6 | 2.0.1   | not yet |
| Shelly       | Plug US Gen4 (Zigbee)        | `PlugUSG4ZB`  | ESP32-C6 | 2.0.1   | not yet |
| Shelly       | Power Strip 4 Gen4           | `PowerStrip`  | ESP32-C6 | 2.0.1   | not yet |
| Shelly       | Power Strip 4 Gen4 (Zigbee)  | `PowerStripZB`| ESP32-C6 | 2.0.1   | not yet |

> "Not yet" means the package builds, every part hash verifies and the image checks pass, but flashing a real device
> has not been confirmed in this repo. Reports welcome.

More devices: `python ota.py add-device <official.zip>` creates a profile from an official package
(`--parent <base device>` for a variant of a model, e.g. the Zigbee version).


Quick start
-----------

```
pip install -r requirements.txt
python ota.py fetch PlugMG3 --insecure
python ota.py build PlugMG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml my-plug.yaml
python ota.py send PlugMG3 out/PlugMG3-app-<date>.zip --watch 60
```

Your ESPHome config needs Shelly's partition table and offset:

```yaml
esp32:
  partitions: PlugMG3-stock.csv
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_PARTITION_TABLE_OFFSET: "0x10000"

ota:
  - platform: esphome
    allow_partition_access: true   # needed later to update the bootloader
```

`--esphome-yaml` makes `build` check the offset and the partition table (errors) and warns if `allow_partition_access` is missing.


Commands
--------

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
| Build | `build` | Replace the app part, check the image, write the ZIP to `out/` |
| Deploy | `send` | Check the device, serve the ZIP, trigger the update |
| Deploy | `restore` | Send the cached official firmware back |
| Deploy | `log` | Show the device's live debug log |
| Tools | `inspect` | Show and verify a ZIP |
| Tools | `list` | Show devices and cached firmware |
| Tools | `clean` | Delete old ZIPs in `out/` (needs `--yes`) |

`python ota.py <command> -h` shows the options of any command.

### fetch

Downloads the official package to `fw/shelly/<Device>/<version>/` (with a `meta.json`) and verifies the hash in the
download URL. Shelly's servers use a private CA, so TLS verification fails; `--insecure` skips it.

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `DEVICE` | yes | | Profile name, e.g. `PlugMG3` |
| `--refresh` | no | off | Check for a newer version even if one is cached |
| `--version VER` | no | latest cached | Use this cached version |
| `--insecure` | no | off | Skip the TLS check (the URL hash only guards against transfer errors) |

### build

Replaces the app part and writes `out/<Device>-<app>-<date>.zip` plus `.sha256` and `.report.json`. The app is checked
for magic byte, chip id, segment count and fit into the app slot. It never downloads on its own and never overwrites
an input file.

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `DEVICE` | yes | | Profile name |
| `APP.bin` | yes | | ESPHome app binary (not the merged image) |
| `--esphome-yaml YAML` | no | none | Also check the partition offset and `partitions:` CSV of this config |
| `--esphome-factory FACTORY.bin` | no | none | Also ship ESPHome's bootloader and a clean `otadata` taken from this factory image, so no separate bootloader update is needed later. Heavily checked first, see [After the first boot](#after-the-first-boot) |
| `--boot-min-version VER` | no | one patch above Shelly's | Only with `--esphome-factory`: the bootloader `min_version` in the manifest. The installer writes only a newer bootloader, hence the default 1.0.2 to 1.0.3. `keep` leaves it, which probably makes the installer skip the bootloader |
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

### send

Checks the device (`Shelly.GetDeviceInfo`, model must match), asks before flashing, serves the ZIP on a temporary web
server and calls `Shelly.Update?url=…`. The Shelly downloads the file itself, so this PC must be reachable from it, for
example connected to the Shelly's own access point. `restore` takes the same options and sends the cached official
firmware instead of a ZIP you choose. It only works while the Shelly firmware is still running; a device that already
runs ESPHome does not answer, and the way back is then UART with a flash backup. The official package also resets NVS
and `otadata`, so Wi-Fi credentials and settings are lost.

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `DEVICE`, `ZIP` | yes | | Profile name and the ZIP to send |
| `--ip IP` | no | `192.168.33.1` | Address of the Shelly |
| `--watch SEC` | no | off | Show the device's debug log (UDP, switched on over RPC and restored afterwards) and keep listening SEC seconds after the download |
| `--user USER` / `--password PW` | no | `admin` / none | Login, if the device has a password (digest auth) |
| `--yes` | no | off | Do not ask before flashing |
| `--dry-run` | no | off | Check the device only, send nothing |

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

### log

Shows the live debug log of a Shelly without sending anything: `python ota.py log --ip 192.168.1.50 --seconds 30`.
Takes `--ip`, `--user`, `--password`, `--host`, `--log-port` and `--seconds` (default: until Ctrl+C).


Credits
-------

Almost everything this tool knows was found out by other people. Free-Shelly OTA is an independent implementation built on
their research and documentation. Please visit and support their projects:

| Project | License | What we learned from it |
| --- | --- | --- |
| [tasmota/mgos32-to-tasmota32](https://github.com/tasmota/mgos32-to-tasmota32) | GPL-3.0 | Converting a Shelly OTA ZIP so the stock updater accepts third-party firmware; Gen3 notes (e.g. no PlugSG3 support) |
| [inventor7777/ESPHome-Shelly-Plus-Plug-US](https://github.com/inventor7777/ESPHome-Shelly-Plus-Plug-US) | MIT | Replacing only the app image in Shelly's ZIP for ESPHome; the partition table lives at `0x10000`, not `0x8000`; the follow-up bootloader step |
| [automatous-io/shelly-gen4-esphome](https://github.com/automatous-io/shelly-gen4-esphome) | Apache-2.0 | Gen4 (ESP32-C6) partition layout, the A/B slot rule, install documentation |
| Shelly / Allterco Robotics | – | The official OTA packages and update API (not redistributed here) |
| [ESPHome](https://esphome.io), Espressif (esptool, ESP-IDF) | – | The firmware framework and tooling everything builds on |


After the first boot
--------------------

With Shelly's bootloader still in place, the ESPHome log shows `esp_ota_ops: ota data invalid, no current app. Assuming factory`. This is
expected (seen on the Plug M Gen3 here and in the Plug US project): Shelly keeps its own boot state in `otadata`, which
ESP-IDF cannot read. It does not stop ESPHome from booting.

With Shelly's own bootloader, later ESPHome OTAs behave oddly (see "Without it" below). The recommended way avoids that.

**Recommended: ship ESPHome's bootloader in the package (confirmed on the Plug M Gen3).** Build with
`--esphome-factory firmware.factory.bin`. The tool takes ESPHome's bootloader and a clean `otadata` out of the factory
image and puts them into the Shelly package instead of Shelly's; the partition table and everything else stay as
shipped. It also raises the bootloader's `min_version` in the manifest by one patch level (1.0.2 to 1.0.3). That is
needed: on the Plug M Gen3 the installer skipped the bootloader while `min_version` equalled the installed loader
(`Shelly OS loader 1.0.2`), and wrote it once the number was higher. After that, two ESPHome OTAs in a row
(0.0.1 to 0.0.2 to 0.0.3) took effect without extra restarts, and the UART boot log showed ESPHome's bootloader instead
of Shelly's. No separate "Update bootloader" step and no UART were needed.

Before building, the tool verifies:

- the bootloader's checksum and SHA-256 are intact and its header (flash mode, size/frequency, chip, minimum revision)
  equals Shelly's;
- the factory image's partition table has the same critical entries as the device (`otadata`, `nvs`, `app_0/1`,
  `fs_0/1`; differences in `scratch`/`shelly` only warn) and its `otadata` area is erased;
- the factory image contains exactly the app you are packing (same build).

`send` warns again when a package replaces the bootloader. It worked on the Plug M Gen3 only; on other models the
installer's rule may differ, and a bootloader that does not suit the device can only be fixed with UART. The Plug US
project advises against replacing the bootloader in the initial package; this goes beyond its findings.
`--boot-min-version VER` sets the value yourself, `keep` leaves Shelly's.

**Without it** (plain package, Shelly's loader stays): a later ESPHome OTA writes the new image into the other slot, but
the device keeps booting the old one until Shelly's attempt counter runs out. The loader prints
`Uncommitted boot of app 0 (attempts 1)` and counts down on every start (about three restarts here); then the next
start switches slot. ESPHome never commits, so the counter keeps running; whether the loader later switches back has
not been checked. The Plug US project handles this differently, in two steps:

1. Build with `ota: - platform: esphome` and `allow_partition_access: true`, install once over the network. ESPHome then
   alternates between the stock `app_0` and `app_1` slots.
2. Run ESPHome Builder's **Update bootloader** action. It replaces the bootloader and keeps Shelly's partition table.

**Do not interrupt power while the bootloader updates.** If it fails you need UART to recover. This step was documented
for the Shelly Plus Plug US (ESP32); on Gen3 (ESP32-C3) it has **not been tested here yet**. Thanks to
[inventor7777](https://github.com/inventor7777/ESPHome-Shelly-Plus-Plug-US) for working this out.


Notes & troubleshooting
-----------------------

- **Applying a package wipes NVS** (Wi-Fi, settings) and rewrites `otadata`.
- **Slot:** the stock updater writes to the slot it is not running from. `send` shows the device's `slot` and warns on
  slot 0: for Gen4 the installer is reported to skip the app there (not verified for Gen3). If nothing changes, install
  one normal stock update first.
- **eFuse:** a related project reports a permanent eFuse marker for non-official firmware (Plus Plug US).
  Unverified for Gen3.
- **URL vs. upload:** `send` uses `Shelly.Update?url=` with a local web server. This worked on the Plug M Gen3 (stock
  firmware 1.8.99, running from slot 1). The Tasmota project advises against URL updates and uses the web UI file
  upload instead; if URL mode fails on your device, that is why.
- **Gen4 signature check (disputed):** the ESPHome device page for the Power Strip 4 Gen4 (`PowerStrip`) states that stock OTA is not
  possible because Gen4 verifies OTA images with an ECDSA signature, so it needs a UART flash. The Gen4 project above
  documents OTA installs for other Gen4 models. Which is true may depend on model and firmware version; unverified here.
  If a Gen4 device rejects the package, check the log (`send --watch`) and fall back to UART.
- **Power cycle:** after the first boot a real power cycle may be needed (the cause is not understood; some state of the
  stock firmware seems to survive a soft reset). Disconnect the device from mains, wait at least 30 seconds so the
  capacitors can discharge (a quick unplug may leave the ESP powered; the time is a rule of thumb, not measured), then
  reconnect. Do not open a device that is connected to mains.
  On the Plug M Gen3, ESPHome came up after a power-off of about 30 seconds (whether it would also have started
  without it was not tested).
- **Safety:** nothing is downloaded unless you run `fetch` (or pass `--download`). Shelly firmware is not part of this
  repository (`fw/` and `out/` are git-ignored); you download it yourself.


<!-- LICENSE -->
## License

Distributed under the [Apache License 2.0](LICENSE); see also [NOTICE](NOTICE).
Section 6 of the license grants no rights to any trademark: Shelly, ESPHome, Espressif and the other names used here
belong to their owners, and this project has nothing to do with them beyond working with their products.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- MARKDOWN LINKS & IMAGES -->
[stars-shield]: https://img.shields.io/github/stars/oxynatOr/free-shelly-ota.svg?style=for-the-badge
[stars-url]: https://github.com/oxynatOr/free-shelly-ota/stargazers
[forks-shield]: https://img.shields.io/github/forks/oxynatOr/free-shelly-ota.svg?style=for-the-badge
[forks-url]: https://github.com/oxynatOr/free-shelly-ota/network/members
[issues-shield]: https://img.shields.io/github/issues/oxynatOr/free-shelly-ota.svg?style=for-the-badge
[issues-url]: https://github.com/oxynatOr/free-shelly-ota/issues
[license-shield]: https://img.shields.io/github/license/oxynatOr/free-shelly-ota.svg?style=for-the-badge
[license-url]: https://github.com/oxynatOr/free-shelly-ota/blob/main/LICENSE
