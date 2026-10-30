# Shelly Plus Plug IT (Gen2)

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: confirmed](https://img.shields.io/badge/state-confirmed-brightgreen.svg?style=flat-square)
![Generation: 2](https://img.shields.io/badge/gen-2-lightgrey.svg?style=flat-square)
![Chip: ESP32](https://img.shields.io/badge/chip-ESP32-blue.svg?style=flat-square)
![UART: not needed](https://img.shields.io/badge/UART-not%20needed-brightgreen.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [📍 Pins](#pins) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

The Italian plug (SNPL-00110IT). Same chip and the same partition layout as the [Plus Plug S](PlusPlugS.md), but **different pins**: do not
copy a Plus Plug S config.

| Fact | Value |
| --- | --- |
| Profile | `PlusPlugIT` |
| Flash | 4 MB |
| Official package | 2.0.1 |
| Partition table | **`0x8000`** (ESP-IDF default) |
| Bootloader address | `0x1000` |
| App slot size | `0x190000` |
| Bootloader `min_version` | `1.0.9` (set in the profile) |

> [!NOTE]
> **Confirmed:** the whole chain ran on a real device, without UART: `send` of a package with `--esphome-factory` from stock 2.0.1
> (the loader was replaced: `Boot: cur 010003ff, new 00000000, min 010009ff, update? 1`), ESPHome booted, joined the Wi-Fi, and a later
> ESPHome OTA took effect. The reporter used a profile made with `add-device` from the same official package; it is identical to the one
> in this repository apart from the name ([#83](https://github.com/oxynatOr/free-shelly-ota/issues/83)).

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/PlusPlugIT-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0x8000"`.

```yaml
esp32:
  variant: ESP32
  board: esp32dev
  flash_size: 4MB
  partitions: PlusPlugIT-stock.csv       # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_FREERTOS_UNICORE: y
      CONFIG_PARTITION_TABLE_OFFSET: "0x8000"
      CONFIG_ESPTOOLPY_FLASHFREQ_80M: "y"   # without it `build` refuses: the bootloader header says 40 MHz
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
    allow_partition_access: true
```

## Pins

Read from the stock 2.0.1 firmware and checked on the hardware by the reporter (pienovi).

| Function | Pin |
| --- | --- |
| Relay | GPIO4 (active high) |
| Button | GPIO26 (active low) |
| LEDs | GPIO32 and GPIO33 (active low) |
| BL0937: CF / CF1 / SEL | GPIO27 / GPIO14 / GPIO12 (SEL inverted) |
| NTC | GPIO34: 10 kΩ at 25 °C, B 3950, 10 kΩ series resistor, NTC to GND (`DOWNSTREAM`) |

The power readings use ESPHome's `hlw8012` platform with `current_resistor: 0.001 ohm` and `voltage_divider: 770`. Against a reference
meter, two units needed these extra factors: voltage about 2.86 to 2.95, current about 1.06 to 1.10, power about 3.36 to 3.49. Treat them as a starting point and calibrate your own unit: after calibration unit 1 read 216.5 V / 8.75 A / 1892 W against 215 V / 8.70 A / 1871 W on a reference (about 1 % at a 1.9 kW load) and stays there, but the two units differ by 3 to 4 % (unit 1: V x2.857, I x1.057, P x3.355; unit 2: V x2.950, I x1.096, P x3.489). The reference was another smart plug, not a lab meter, and unit 2 was calibrated in cascade, so part of that spread may come from the reference.

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch PlusPlugIT --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build PlusPlugIT app.ota.bin --esphome-factory app.factory.bin --esphome-yaml plusplugit.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send PlusPlugIT out/PlusPlugIT-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** (the log goes to a file with `--log-file`):

   ```
   python ota.py send PlusPlugIT out/PlusPlugIT-app-<date>.zip --ip <device IP> --log-file
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

`send` shows these lines at the default log level, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore PlusPlugIT` first |
| 2 | `Device: The bootloader will be replaced ...` (raw log: `Boot: cur ... min ... update? 1`) | The installer will write ESPHome's bootloader. `WARNING: ESPHome's bootloader was NOT written` (`update? 0`) means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | The progress (`Update: ... %`, one line that updates in place) up to 100 %, then `Done: update installed, the device confirmed it` | The device restarts into ESPHome |

On the reporter's unit the raw log also showed `FW signatures: want 07 got 00` and `BURN BLOCK3 - OK` twice, with no write error ([eFuse note](../troubleshooting.md#efuse)).

## Notes for this device

A second unit (factory firmware 0.11.99) went Shelly, then Tasmota (`mgos32-to-tasmota32`), then ESPHome through Tasmota's firmware upgrade,
keeping Shelly's two-slot partition table. That route is not part of this tool.

That unit had a different table in flash when read at `0x8000`: app slots of `0x180000` (app_0 at `0x10000`, app_1 at `0x200000`), fs_0 at `0x190000` and fs_1 at `0x380000` (both `0x70000`), and no `aux` or `shelly` partitions. It never went through this tool, so it is not known whether an update to 2.x rewrites the table. If your unit still runs a factory firmware around 0.11.x, read its table before sending ([`inspect`](../commands.md#inspect) and the slot check of `send --dry-run`).

## Way back

While Shelly firmware runs: `python ota.py restore PlusPlugIT`. Otherwise [Recovery over UART](../recovery-uart.md).

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
