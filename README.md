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

`free-shelly-ota` is a command-line tool for **Shelly Gen2 (ESP32)**, **Gen3 (ESP32-C3)** and **Gen4 (ESP32-C6)** devices.
It takes the official OTA package for your device, replaces the `app` part with your ESPHome image, fixes size and SHA-256
in the manifest, and can hand the result to the Shelly: it checks the device, serves the ZIP from this PC and triggers the
update over RPC. No UART needed.

> [!WARNING]
> **Experimental.** The whole chain has been confirmed on real devices only where the table below says so. Have UART access
> ready as your way back: a bootloader that does not suit a device can only be fixed over UART
> ([Recovery over UART](docs/recovery-uart.md)).
> Installing third-party firmware voids your Shelly warranty, and incorrect flashing can brick your device. You assume all
> responsibility. This project is not affiliated with Shelly, Allterco Robotics, Schneider Electric, ESPHome, CSA or
> Espressif Systems.

**Not in this project:** ESPHome binaries and Shelly firmware. You compile your own ESPHome image; the tool downloads the
official package from Shelly when you run `fetch`.


## Supported devices

✅ = the whole chain ran on a real device, 🧪 = the package builds and verifies, but nobody has flashed it yet.
Click the profile for the device page: ESPHome config, the exact commands and what to expect.

| Device | Profile | Chip | State |
| --- | --- | --- | --- |
| Plug M Gen3 | [`PlugMG3`](docs/devices/PlugMG3.md) | ESP32-C3 | ✅ |
| Plug S Gen3 | [`PlugSG3`](docs/devices/PlugSG3.md) | ESP32-C3 | ✅ base config |
| H&T Gen3 | [`HTG3`](docs/devices/HTG3.md) | ESP32-C3 | ✅ |
| Multicolor Bulb E27 Gen3 | [`RGBCCTBulbG3`](docs/devices/RGBCCTBulbG3.md) | ESP32-C3 | ✅ OTA, light not confirmed |
| Duo Bulb Gen3 | [`DuoBulbG3`](docs/devices/DuoBulbG3.md) | ESP32-C3 | 🧪 |
| Power Strip 4 Gen4 | [`PowerStrip`](docs/devices/PowerStrip.md) | ESP32-C6 | ✅ boots, outlets not checked |
| Power Strip 4 Gen4 (Zigbee) | [`PowerStripZB`](docs/devices/PowerStripZB.md) | ESP32-C6 | 🧪 |
| Plus Plug S (V2 hardware, Gen2) | [`PlusPlugS`](docs/devices/PlusPlugS.md) | ESP32 | ✅ without UART |

Another device? `python ota.py add-device <official.zip>` creates a profile from an official package
(`--parent <base device>` for a variant, e.g. the Zigbee version). Reports are welcome.


## Quick start

```
pip install -r requirements.txt
python ota.py fetch PlugMG3 --insecure
python ota.py build PlugMG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml my-plug.yaml
python ota.py send PlugMG3 out/PlugMG3-app-<date>.zip --watch 60
```

Your ESPHome config must use Shelly's partition table and offset (`partitions/<Profile>-stock.csv`, one per device; the
device page lists the offset). Without it `build` refuses. With `--esphome-factory` the package also carries ESPHome's
bootloader, so later ESPHome OTAs work without extra steps — see [Bootloader and slots](docs/bootloader-and-slots.md).

```yaml
esp32:
  partitions: PlugMG3-stock.csv
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_PARTITION_TABLE_OFFSET: "0x10000"   # per device: see its page
    advanced:
      enable_ota_rollback: false
ota:
  - platform: esphome
```

> [!CAUTION]
> The package wipes NVS (Wi-Fi and settings), and a package built from your config can contain your Wi-Fi password.
> Never share or commit it ([Credential check](docs/credential-check.md)).


## Documentation

| Page | What is in it |
| --- | --- |
| [Device pages](docs/devices) | One page per device: config, commands, log lines, pitfalls |
| [Commands](docs/commands.md) | `fetch`, `build`, `send`, `restore`, `log` and the rest, with all options |
| [Bootloader and slots](docs/bootloader-and-slots.md) | Why ESPHome's bootloader is shipped, `min_version`, why the app must land in slot 0 |
| [Troubleshooting](docs/troubleshooting.md) | Header errors, empty log, battery devices, eFuse, power cycle |
| [Recovery over UART](docs/recovery-uart.md) | Back to Shelly OS with `esptool` |
| [Credential check](docs/credential-check.md) | Secrets inside images and packages |
| [Versions](docs/versions.md) | Tool version, build report, profile revisions |
| [CHANGELOG](CHANGELOG.md) | What changed |


## Credits

Almost everything this tool knows was found out by other people. Please visit and support their projects:

| Project | License | What we learned from it |
| --- | --- | --- |
| [tasmota/mgos32-to-tasmota32](https://github.com/tasmota/mgos32-to-tasmota32) | GPL-3.0 | Converting a Shelly OTA ZIP so the stock updater accepts third-party firmware |
| [inventor7777/ESPHome-Shelly-Plus-Plug-US](https://github.com/inventor7777/ESPHome-Shelly-Plus-Plug-US) | MIT | Replacing only the app image in Shelly's ZIP; the partition table at `0x10000`; the follow-up bootloader step |
| [automatous-io/shelly-gen4-esphome](https://github.com/automatous-io/shelly-gen4-esphome) | Apache-2.0 | Gen4 (ESP32-C6) partition layout, the A/B slot rule, install documentation |
| Shelly / Allterco Robotics | – | The official OTA packages and update API (not redistributed here) |
| [ESPHome](https://esphome.io), Espressif (esptool, ESP-IDF) | – | The firmware framework and tooling everything builds on |


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
