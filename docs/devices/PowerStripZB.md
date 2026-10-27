# Shelly Power Strip 4 Gen4 (Zigbee)

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: untested](https://img.shields.io/badge/state-untested-lightgrey.svg?style=flat-square)
![Chip: ESP32-C6](https://img.shields.io/badge/chip-ESP32--C6-blue.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

The Zigbee firmware variant of the [Power Strip 4 Gen4](PowerStrip.md): same hardware, listed under `alt` in the update reply of `PowerStrip`. The profile has `parent: PowerStrip`.

| Fact | Value |
| --- | --- |
| Profile | `PowerStripZB` |
| Flash | 8 MB |
| Official package | 2.1.0 (stable since 2026-10-14; Bootloader, partition table and filesystem are the same as in 2.0.1) |
| Partition table | `0x10000` |
| App slot size | `0x300000` |
| ESPHome device page | [Shelly Power Strip 4 Gen4](https://devices.esphome.io/devices/shelly-power-strip-4-gen4/) (the same hardware as `PowerStrip`) |
| Bootloader `min_version` | `1.0.9` (set in the profile) |

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

Also:

- [ ] The device runs the Zigbee firmware (it reports the app name `PowerStripZB`).

## ESPHome config

Use the config of the [Power Strip page](PowerStrip.md): same pins, same partition table, same flash options.

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch PowerStripZB --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build PowerStripZB app.ota.bin --esphome-factory app.factory.bin --esphome-yaml shelly-power-strip-gen4.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send PowerStripZB out/PowerStripZB-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** (the log goes to a file with `--log-file`):

   ```
   python ota.py send PowerStripZB out/PowerStripZB-app-<date>.zip --ip <device IP> --log-file
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

`send` shows these lines at the default log level, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore PowerStripZB` first |
| 2 | `Device: The bootloader will be replaced ...` (raw log: `Boot: cur ... min ... update? 1`) | The installer will write ESPHome's bootloader. `WARNING: ESPHome's bootloader was NOT written` (`update? 0`) means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | The progress (`Update: ... %`, one line that updates in place) up to 100 %, then `Done: update installed, the device confirmed it` | The device restarts into ESPHome |

## Notes for this device

- A device that runs the Zigbee firmware reports another app name (`PowerStripZB`), so `send PowerStripZB` is the matching
  profile.
- A unit that has no Wi-Fi yet can be given one over Bluetooth: `python ota.py ble wifi SSID -` ([ble](../commands.md#ble); seen on the Mini 1PM Gen4 Zigbee firmware, not on this model).
- It has not been flashed. Please report the file written by `--log-file`. The slot rule and `min_version` notes of the Power Strip apply.

## Way back

`python ota.py restore PowerStripZB` sends the official firmware back while Shelly firmware still runs.

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
