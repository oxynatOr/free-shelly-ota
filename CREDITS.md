# Credits

[← README](README.md#credits) · [Documentation](docs/README.md) · [Device pages](docs/devices/README.md) · [Roadmap](ROADMAP.md)

[🧩 Projects](#projects) · [🙌 People](#people) · [🧱 Shelly and the tools underneath](#shelly-and-the-tools-underneath) · [❓ Missing from this list?](#missing-from-this-list)

Almost everything this tool knows was found out by other people: how a Shelly package is built, how its bootloader and slots work, which pin does what on which device. This page says who, and what we took from them. The short version is in the [README](README.md#credits).

> [!TIP]
> Please visit and support these projects and people.

## Projects

| Project | License | What we learned from it |
| --- | --- | --- |
| [tasmota/mgos32-to-tasmota32](https://github.com/tasmota/mgos32-to-tasmota32) | GPL-3.0 | Converting a Shelly OTA ZIP so the stock updater accepts third-party firmware |
| [inventor7777/ESPHome-Shelly-Plus-Plug-US](https://github.com/inventor7777/ESPHome-Shelly-Plus-Plug-US) | MIT | Replacing only the app image in Shelly's ZIP; the partition table at `0x10000`; the follow-up bootloader step (see [Bootloader and slots](docs/bootloader-and-slots.md)) |
| [automatous-io/shelly-gen4-esphome](https://github.com/automatous-io/shelly-gen4-esphome) | Apache-2.0 | Gen4 (ESP32-C6) partition layout, the A/B slot rule, install documentation |

## People

People who tested a device, sent a report or shared what they know. Newest first.

| Who | What |
| --- | --- |
| [chusovich](https://github.com/chusovich) | A device report for the [1 Gen3](docs/devices/S1G3.md) (October 2026, [#98](https://github.com/oxynatOr/free-shelly-ota/issues/98)): two devices flashed over OTA from stock 1.4.0 with the full log (loader 1.0.1, the first seen on this device) and a later ESPHome OTA, and the config setup used with `S1G3-stock.csv` |
| [WulffTech](https://github.com/WulffTech) | A device report for the [1PM Gen3](docs/devices/S1PMG3.md) and the [2PM Gen3](docs/devices/S2PMG3.md) (October 2026): one 1PM and two 2PM Gen3 converted over OTA from Shelly 2.0.1 without UART, with their own tooling; the device info, the stable ESPHome run across reboots and a later ESPHome OTA; and the observation that the installer writes a `pt` part from the package every time (it has no `min_version`), plus the finding that Shelly's CA is in the device filesystem |
| [pienovi](https://github.com/pienovi) | A device report for the [Mini 1PM Gen3](docs/devices/Mini1PMG3.md) (October 2026, [#82](https://github.com/oxynatOr/free-shelly-ota/issues/82)): two units flashed over OTA from stock 1.4.0 with the full log, the first loader 1.0.0 seen, and two [Mini 1 Gen3](docs/devices/Mini1G3.md) from stock 1.4.4 |
| [jjanssen95](https://github.com/jjanssen95) | A device report for the [Mini 1 Gen3](docs/devices/Mini1G3.md) (October 2026, [#69](https://github.com/oxynatOr/free-shelly-ota/issues/69)): the OTA from Shelly 1.4.4 to ESPHome and a later ESPHome OTA, the pins checked on the hardware (relay, button, switch input, LED), the NTC reading that comes out high, and a second device with the `Boot:` lines of `restore` and the ESPHome flash, the slot-1 case and the timeout on a weak Wi-Fi |
| [815rx1](https://github.com/815rx1) | A device report of a Plug M Gen3 (October 2026): the first run with the official 2.1.0 package and from factory firmware 1.8.99, with the full `--watch` log, the bootloader swap from loader 1.0.2, two later ESPHome OTAs (CLI and Home Assistant) and the power-cycle behaviour of relay and LED on the [device page](docs/devices/PlugMG3.md) |
| [pienovi](https://github.com/pienovi) | A device report for the [Plus Plug IT](docs/devices/PlusPlugIT.md) (October 2026, [#83](https://github.com/oxynatOr/free-shelly-ota/issues/83)): the OTA from Shelly 2.0.1 to ESPHome with the full log, the pins read from the stock firmware and checked on the hardware (relay, button, LEDs, BL0937, NTC), the power calibration factors, and a second unit going Shelly to Tasmota to ESPHome |
| [yasdfgr](https://github.com/yasdfgr) | A device report for the [Plus Uni](docs/devices/PlusUni.md) (October 2026, [#46](https://github.com/oxynatOr/free-shelly-ota/issues/46)): a successful OTA run with the full log, the first loader version seen on that device (1.0.3) and the eFuse lines; later the fix over UART and the measured pin table |
| [imsandli](https://github.com/imsandli) | The first external device report (PM Mini Gen3, October 2026): a successful OTA run with logs, the BL0942 RX pull-up and a voltage calibration for the [device page](docs/devices/MiniPMG3.md), and the idea for the check that the device can reach the PC |
| [majoto85](https://github.com/majoto85) | A device report for the [2PM Gen3](docs/devices/S2PMG3.md) (October 2026, [#92](https://github.com/oxynatOr/free-shelly-ota/issues/92)): a successful OTA run from 1.4.99 with ESPHome's bootloader, a later ESPHome OTA, the log and the eFuse lines |
| bobkersten | Author of the ESPHome device-database page for the [Shelly Plus Plug S](https://devices.esphome.io/devices/Shelly-Plus-Plug-S/), whose pins and config the [Plus Plug S page](docs/devices/PlusPlugS.md) uses (tested by the author, not by this project) |

## Shelly and the tools underneath

| Who | What |
| --- | --- |
| Shelly / Allterco Robotics | The official OTA packages and the update API (not redistributed here) |
| [ESPHome](https://esphome.io), Espressif (esptool, ESP-IDF) | The firmware framework and tooling everything builds on |

## Missing from this list?

> [!TIP]
> If this project uses something you found out and you are not named, or you would rather not be, please
> [open an issue](https://github.com/oxynatOr/free-shelly-ota/issues/new). If you flashed a device with the tool, a
> [device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml) puts you on this list, also when it worked.
