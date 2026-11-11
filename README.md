<h1 align="left">
  <img src="docs/assets/logo.png" width="80" align="left" alt="Free-Shelly OTA logo">
  Free-Shelly OTA<br>
  <sup><sup><sub>Pack your own ESPHome firmware into an official-style Shelly OTA package and send it to the device.</sub></sup></sup>
</h1>

[![Status][status-shield]][status-url]
[![Version][version-shield]][version-url]
[![Issues][issues-shield]][issues-url]
[![License][license-shield]][license-url]

[Quick start](#quick-start) · [Supported devices](#supported-devices) · [Download](https://github.com/oxynatOr/free-shelly-ota/releases) · [Step-by-step guide](docs/guide.md) · [Documentation](#documentation) · [Docs site](https://oxynator.github.io/free-shelly-ota/) · [Contributing](CONTRIBUTING.md) · [Request a device](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=new-device.yml)

`free-shelly-ota` is a command-line tool for **Shelly Gen2 (ESP32)**, **Gen3 (ESP32-C3)** and **Gen4 (ESP32-C6)** devices.
It turns your ESPHome firmware into an update the Shelly accepts, and sends it over the network:

1. **`fetch`** downloads the official OTA package for your device from Shelly.
2. **`build`** replaces its `app` part with your ESPHome image and fixes size and SHA-256 in the manifest.
3. **`send`** checks the device, serves the ZIP from this PC and triggers the update over RPC.

Installing runs over the network, no soldering. A UART adapter is only your safety net if a flash goes wrong.

> [!WARNING]
> **Experimental.** The whole chain is confirmed on real devices only where the table below shows ✅.
>
> - **Have a UART adapter ready.** If a flash goes wrong, UART is the only way back ([Recovery over UART](docs/recovery-uart.md)).
> - **Your config is yours.** The ESPHome config (pins, relay, sensors, limits) is your responsibility. The tool checks the package (partition table, offset, size, bootloader), not whether the config works or is safe. The configs on the device pages are examples from reports, not tested for your unit.
> - **A wrong `ota:`, `api:` or Wi-Fi setting can lock you out.** If the flashed config has no working network or OTA (missing `allow_partition_access`, wrong Wi-Fi, a key or encryption you cannot match later), the device is not reachable and only UART helps, as seen with the Power Strip. Test the config first, ideally on a dev board.
> - **Warranty.** Installing third-party firmware voids your Shelly warranty.
> - **Risk.** Incorrect flashing can brick your device. You assume all responsibility.

## Quick start

You need a Shelly of a supported model on **Shelly's own firmware**, **Python 3.10+**, **ESPHome** or **Docker**, and a UART adapter as safety net. New to this? The [Step-by-step guide](docs/guide.md) covers everything from checking the device to the way back. The short version:

**Download.** Get the [latest release](https://github.com/oxynatOr/free-shelly-ota/releases) (*Source code (zip)*) and unpack it, or run `git clone https://github.com/oxynatOr/free-shelly-ota`, then `pip install -r requirements.txt`.

**1. Write your ESPHome config.** It must use Shelly's partition table and offset: copy `partitions/<Profile>-stock.csv` next to your YAML and set `CONFIG_PARTITION_TABLE_OFFSET` to the value on the device page. Without it `build` refuses; it checks the partition table, not the rest of your config. The exact YAML is in the [guide, step 5](docs/guide.md#5-write-the-esphome-config).

**2. Compile and pack.** `--compile` runs ESPHome for you (the `esphome` command, else Docker; the first Docker compile downloads the toolchain, see [Compile](docs/commands.md#compile)).

```
# download the official package
python ota.py fetch PlugMG3 --insecure

# compile your config and put the app into the package; the ZIP goes to out/
python ota.py build PlugMG3 --compile my-plug.yaml
```

Compiled it yourself? Give `build` the two files ESPHome wrote: `python ota.py build PlugMG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml my-plug.yaml`.

**3. Send it.**

```
python ota.py send PlugMG3 out/PlugMG3-app-<date>.zip --ip <device IP>
```

- `PlugMG3` is the example; use your device's profile (the name is on its device page, see [Supported devices](#supported-devices)).
- `--insecure` is needed because Shelly's servers use a private CA (unless you have that CA as a PEM file: `python ota.py ca` writes it from a package, and `--cafile PEM` keeps TLS on); the hash in the download URL still guards against transfer errors ([`fetch`](docs/commands.md#fetch)).
- Add `--dry-run` first to check the device without sending anything ([`send`](docs/commands.md#send)).
- A device without Wi-Fi (Zigbee firmware) needs [`ble wifi`](docs/commands.md#ble) first.

> [!CAUTION]
> The package wipes NVS (Wi-Fi and settings), and a package built from your config can contain your Wi-Fi password.
> Never share or commit the ZIP ([Credential check](docs/credential-check.md)). While `send` runs, its temporary web server
> hands the ZIP to anyone on your network who asks for its exact file name, so use a network you trust.


## Supported devices

**62 profiles:** ✅ 13 confirmed · 🟡 9 partly checked · 🔬 11 DevKit-tested · 🧪 29 untested

Click a device for its page. Open a generation to see its devices: up to five that ran on real hardware, confirmed (✅) ones first, then partly checked (🟡). The counts cover every profile; the full list, with 🔬 and 🧪, is in the [device overview](docs/devices/README.md#devices).

<details>
<summary><b>Gen2 (ESP32)</b>: 18 profiles: ✅ 3 · 🟡 2 · 🔬 4 · 🧪 9</summary>

![Chip: ESP32](https://img.shields.io/badge/chip-ESP32-blue.svg?style=flat-square)

| Device | State |
| --- | --- |
| [Plus Plug S (V2 hardware, Gen2)](docs/devices/PlusPlugS.md) | ✅ |
| [Plus Plug IT (Gen2)](docs/devices/PlusPlugIT.md) | ✅ |
| [Plus RGBW PM (Gen2)](docs/devices/PlusRGBWPM.md) | ✅ |
| [Plus i4 / i4 DC (Gen2)](docs/devices/PlusI4.md) | 🟡 |
| [Plus Uni (Gen2)](docs/devices/PlusUni.md) | 🟡 |

All 18 Gen2 profiles: [device overview](docs/devices/README.md#gen2-esp32)

</details>

<details>
<summary><b>Gen3 (ESP32-C3)</b>: 27 profiles: ✅ 9 · 🟡 6 · 🔬 0 · 🧪 12</summary>

![Chip: ESP32-C3](https://img.shields.io/badge/chip-ESP32--C3-blue.svg?style=flat-square)

| Device | State |
| --- | --- |
| [Plug M Gen3](docs/devices/PlugMG3.md) | ✅ |
| [Plug S Gen3](docs/devices/PlugSG3.md) | ✅ |
| [H&T Gen3](docs/devices/HTG3.md) | ✅ |
| [PM Mini Gen3 (no relay)](docs/devices/MiniPMG3.md) | ✅ |
| [Multicolor Bulb E27 Gen3](docs/devices/RGBCCTBulbG3.md) | ✅ |

All 27 Gen3 profiles: [device overview](docs/devices/README.md#gen3-esp32-c3)

</details>

<details>
<summary><b>Gen4 (ESP32-C6)</b>: 17 profiles: ✅ 1 · 🟡 1 · 🔬 7 · 🧪 8</summary>

![Chip: ESP32-C6](https://img.shields.io/badge/chip-ESP32--C6-blue.svg?style=flat-square)

| Device | State |
| --- | --- |
| [1 Gen4](docs/devices/S1G4.md) | ✅ |
| [Power Strip 4 Gen4](docs/devices/PowerStrip.md) | 🟡 |

All 17 Gen4 profiles: [device overview](docs/devices/README.md#gen4-esp32-c6)

</details>

> - ✅ The whole chain ran on a real device.
> - 🟡 Flashed on a real device, but part of the chain or of the function is not checked yet (see the device page).
> - 🔬 The OTA ran through on a dev board with the [DevKit image](docs/devkit.md), but not on the real device yet.
> - 🧪 The package builds and verifies, but nobody has flashed it yet.


## Documentation

Start with the [Step-by-step guide](docs/guide.md). The same pages are on the [documentation site](https://oxynator.github.io/free-shelly-ota/), with search. The [documentation index](docs/README.md) lists everything; the pages you will need most:

| Page | What is in it |
| --- | --- |
| [Step-by-step guide](docs/guide.md) | The whole way, from check to way back |
| [Device pages](docs/devices) | Config, pins, commands and pitfalls per device |
| [Commands](docs/commands.md) | All commands and options |
| [Troubleshooting](docs/troubleshooting.md) · [Recovery over UART](docs/recovery-uart.md) | When something goes wrong |
| [Bootloader and slots](docs/bootloader-and-slots.md) | Why ESPHome's bootloader is shipped and the app must land in slot 0 |
| [Developer guide](docs/guide-developers.md) · [CHANGELOG](CHANGELOG.md) · [Roadmap](ROADMAP.md) | Adding devices, what changed, what is planned |


## Contributing and reports

Your device is not in the table, or you flashed one? Please tell us, also when it worked. A device needs a **profile** (made from the official package, takes minutes); what takes time is a hardware test.

- [Request a device](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=new-device.yml); it helps most if you offer to test it.
- [Open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml) and attach the file `send --log-file` writes. [Report a bug](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=bug.yml) if the tool misbehaved.
- Make the profile yourself: `python ota.py add-device <official.zip>`, see [Device profiles](devices/README.md#adding-a-profile).
- Code, docs and AI-assisted work are welcome when they are checked: [CONTRIBUTING.md](CONTRIBUTING.md).

> [!CAUTION]
> Please do not attach flash dumps or built ZIPs to an issue: they can contain your Wi-Fi password and per-device secrets.


## Credits

This project builds on the research of others: [tasmota/mgos32-to-tasmota32](https://github.com/tasmota/mgos32-to-tasmota32) (GPL-3.0),
[inventor7777/ESPHome-Shelly-Plus-Plug-US](https://github.com/inventor7777/ESPHome-Shelly-Plus-Plug-US) (MIT) and
[automatous-io/shelly-gen4-esphome](https://github.com/automatous-io/shelly-gen4-esphome) (Apache-2.0). Please visit and support them.
The tool's own findings (the loader's boot state, the slot rule, `min_version`, the pin tables, the DevKit) were worked out here and on real
devices, with the help of the people who tested and reported. [CREDITS.md](CREDITS.md) names them all and says what each contributed.


## Disclaimer

> [!NOTE]
> This project is **not** affiliated with Shelly, Allterco Robotics, Schneider Electric, ESPHome, CSA or Espressif Systems.
>
> It contains **no ESPHome binaries and no Shelly firmware**: you compile your own ESPHome image, and `fetch` downloads the
> official package from Shelly.


## License

Distributed under the [Apache License 2.0](LICENSE); see also [NOTICE](NOTICE).
Section 6 of the license grants no rights to any trademark: Shelly, ESPHome, Espressif and the other names used here
belong to their owners, and this project has nothing to do with them beyond working with their products.


<!-- MARKDOWN LINKS & IMAGES -->
[status-shield]: https://img.shields.io/badge/status-experimental-orange.svg?style=flat-square
[status-url]: #supported-devices
[version-shield]: https://img.shields.io/github/v/tag/oxynatOr/free-shelly-ota.svg?style=flat-square&label=version
[version-url]: https://github.com/oxynatOr/free-shelly-ota/tags
[issues-shield]: https://img.shields.io/github/issues/oxynatOr/free-shelly-ota.svg?style=flat-square
[issues-url]: https://github.com/oxynatOr/free-shelly-ota/issues
[license-shield]: https://img.shields.io/github/license/oxynatOr/free-shelly-ota.svg?style=flat-square
[license-url]: https://github.com/oxynatOr/free-shelly-ota/blob/main/LICENSE
