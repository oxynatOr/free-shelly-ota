# Shelly Mini 1PM Gen4

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: DevKit-tested](https://img.shields.io/badge/state-devkit%20tested-blueviolet.svg?style=flat-square)
![Generation: 4](https://img.shields.io/badge/gen-4-lightgrey.svg?style=flat-square)
![Chip: ESP32-C6](https://img.shields.io/badge/chip-ESP32--C6-blue.svg?style=flat-square)
![Package: 2.1.0](https://img.shields.io/badge/package-2.1.0-lightgrey.svg?style=flat-square)
![Variant: Zigbee](https://img.shields.io/badge/variant-Zigbee-orange.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [📍 Pins](#pins) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

Gen4 / ESP32-C6.

| Fact | Value |
| --- | --- |
| Profile | `Mini1PMG4`, `Mini1PMG4ZB` |
| Flash | 8 MB |
| Official package | 2.1.0 (stable since 2026-10-14, also for the Zigbee variant; Bootloader, partition table and filesystem are the same as in 2.0.1) |
| Partition table | `0x10000` |
| App slot size | `0x300000` |
| Bootloader `min_version` | `1.0.9` (set in the profile) |

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/Mini1PMG4-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0x10000"`.

```yaml
esp32:
  variant: ESP32C6
  board: esp32-c6-devkitc-1
  flash_size: 8MB
  partitions: Mini1PMG4-stock.csv        # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_PARTITION_TABLE_OFFSET: "0x10000"
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
    allow_partition_access: true
```

The C6 needs the 80 MHz flash header, otherwise `build` refuses to replace the bootloader. If it complains, add under `esphome:`:

```yaml
esphome:
  platformio_options:
    board_build.flash_mode: dio
    board_build.f_flash: 80000000L
    board_build.flash_size: 8MB
```

## Pins

> [!WARNING]
> **Read from the stock firmware, not confirmed on a device.** These values come from the code of Shelly's own firmware (Mini 1PM Gen4 2.0.1 and its Zigbee
> variant, the same initialisation in both), read with a disassembler. Nobody measured them on a board with the parts fitted. Check them on your unit before you rely on them.

| Function | Pin | How sure |
| --- | --- | --- |
| Button | **GPIO22**, reads low when pressed | Good: it is the pin of the button object and of the boot-time safe-mode check |
| BL0942 power meter (UART 1, 9600 baud, 8N1) | **RX GPIO19**, **TX GPIO20** | Baud rate and pins are in the code; which of the two is RX and which TX is the less certain part: if the meter stays silent, swap them |
| BL0942 interrupt input | GPIO18 | Medium: the firmware's own message calls it the "IRQ pin"; what the meter drives there was not checked |
| Relay, LED | not read | |

The ESPHome device page for this model does not exist yet (sitemap checked 2026-10-16), so there is nothing to compare with. The Zigbee variant and the normal
variant share the same values.

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch Mini1PMG4 --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build Mini1PMG4 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send Mini1PMG4 out/Mini1PMG4-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** (the log goes to a file with `--log-file`):

   ```
   python ota.py send Mini1PMG4 out/Mini1PMG4-app-<date>.zip --ip <device IP> --log-file
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

`send` shows these lines at the default log level, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore Mini1PMG4` first |
| 2 | `Device: The bootloader will be replaced ...` (raw log: `Boot: cur ... min ... update? 1`) | The installer will write ESPHome's bootloader. `WARNING: ESPHome's bootloader was NOT written` (`update? 0`) means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | The progress (`Update: ... %`, one line that updates in place) up to 100 %, then `Done: update installed, the device confirmed it` | The device restarts into ESPHome |

## Notes for this device

Played through on a dev board with the DevKit image on 2026-10-23 (see [Seen on a board](../devkit.md#seen-on-a-board)); not on the real device yet. Please report the `--watch` log of a real device, especially the lines `Update target slot`, `Boot: cur ... update?` and `Will write to slot`.

## Zigbee variant

`Mini1PMG4ZB` is the Zigbee firmware variant of the same hardware (listed under `alt` in the update reply of `Mini1PMG4`; its profile has `parent: Mini1PMG4`). Use the same config and flash it with `python ota.py send Mini1PMG4ZB ...` after building with `build Mini1PMG4ZB`. Played through on a dev board as well (2026-10-23, see [Seen on a board](../devkit.md#seen-on-a-board)); not on the real device. On the dev board the Zigbee firmware had no Wi-Fi and opened no access point: `python ota.py ble wifi SSID -` ([ble](../commands.md#ble)) gave it one before `send`.

## Way back

`python ota.py restore Mini1PMG4` sends the official firmware back while Shelly firmware still runs.

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
