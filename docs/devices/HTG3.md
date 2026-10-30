# Shelly H&T Gen3

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: confirmed](https://img.shields.io/badge/state-confirmed-brightgreen.svg?style=flat-square)
![Generation: 3](https://img.shields.io/badge/gen-3-lightgrey.svg?style=flat-square)
![Chip: ESP32-C3](https://img.shields.io/badge/chip-ESP32--C3-blue.svg?style=flat-square)
![Package: beta only](https://img.shields.io/badge/package-beta%20only-yellow.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [📍 Pins](#pins) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

A battery device. The partition table is at `0xf000`, so a default ESPHome build does not match and `build` refuses it.

| Fact | Value |
| --- | --- |
| Profile | `HTG3` |
| Flash | 8 MB |
| Official package | 2.0.1 (the hardware runs); Shelly lists only the beta 2.2.0-beta1 now, see the notes |
| Partition table | **`0xf000`** (not `0x10000`) |
| App slot size | `0x280000` |
| Bootloader `min_version` | `1.0.9` (set in the profile) |
| ESPHome device page | [Shelly H&T Gen3](https://devices.esphome.io/devices/shelly-ht-gen3/) |

> [!NOTE]
> **Confirmed:** the whole chain ran on a real device: `send` from stock 2.0.1 (slot 0) with `--esphome-factory`; ESPHome boots and ESPHome OTAs take effect.

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

Also:

- [ ] The batteries are charged (the stock updater refuses below 30 %) and the device is awake ([Troubleshooting](../troubleshooting.md#battery-devices-ht-gen3)).

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/HTG3-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0xf000"`.

```yaml
esp32:
  variant: ESP32C3
  board: esp32-c3-devkitm-1
  flash_size: 8MB
  partitions: HTG3-stock.csv        # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_PARTITION_TABLE_OFFSET: "0xf000"
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
    allow_partition_access: true
```

> [!TIP]
> The [ESPHome device page](https://devices.esphome.io/devices/shelly-ht-gen3/) has the pins and an example config. Replace its `esp32:` block with the one above, or `build` refuses it.

## Pins

The pins (button, I2C bus with the SHT31 and the e-paper display, the ADCs for the battery and the power rail, the battery and USB detection) are on the
[ESPHome device page](https://devices.esphome.io/devices/shelly-ht-gen3/), with a full config. The UART pads on the board are bare test points:
pogo pins or test clips work, or solder temporary wires.

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package. Shelly's update API lists only a beta for this device at the moment, so ask for it
   (see the notes; a `fetch` without `--channel beta` finds no release):

   ```
   python ota.py fetch HTG3 --insecure --channel beta
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`. A pre-release is only used with `--version` (or when it is all that is cached):

   ```
   python ota.py build HTG3 app.ota.bin --version 2.2.0-beta1 --esphome-factory app.factory.bin --esphome-yaml app.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send HTG3 out/HTG3-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** and watch the log:

   ```
   python ota.py send HTG3 out/HTG3-app-<date>.zip --ip <device IP> --watch 120
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

In the `--watch` log look for these lines, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore HTG3` first |
| 2 | `Boot: cur ... min ... update? 1` | The installer will write ESPHome's bootloader. `update? 0` means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | `ota_progress` up to 95 %, then `ota_success` | The device restarts into ESPHome |

## Notes for this device

- **Official package:** the update API answers per installed version: the device sends its app and version in the `Shelly-Info`
  header, and a request without it, or from a device that already runs 2.0.1, shows no stable release (this looked like a removed
  release on 2026-10-10; it was not). `python ota.py fetch HTG3 --from-version 1.4.4` gets the stable 2.0.1 (checked 2026-10-21, the
  same package as the cached one). The beta channel lists `2.2.0-beta1`: same partition table and bootloader header as 2.0.1, the app
  is 90 % of the slot. It was **not flashed with this tool**; the hardware runs above used 2.0.1.
- **H&T Gen3 with display:** runs with ESPHome too (reported, no details).
- **Battery:** the stock updater refuses to start below 30 %: HTTP 500, `OTA not allowed (Battery below 30 percent. )`. Charge
  first and keep the device awake ([Troubleshooting](../troubleshooting.md#battery-devices-ht-gen3)).
- **`min_version`:** this device reports an installed loader 1.0.3, so the default (1.0.3) was skipped; with 1.0.9 the installer
  wrote ESPHome's bootloader ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)).
- **eFuse:** the log shows `FW signatures: want 07 got 00` and refused eFuse writes ("Bits are not empty"). The update still
  succeeded ([eFuse note](../troubleshooting.md#efuse)).

## Way back

`python ota.py restore HTG3` sends the official firmware back while Shelly firmware still runs.

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
