# Shelly Plus Plug S (V2 hardware, Gen2)

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: confirmed](https://img.shields.io/badge/state-confirmed-brightgreen.svg?style=flat-square)
![Generation: 2](https://img.shields.io/badge/gen-2-lightgrey.svg?style=flat-square)
![Chip: ESP32](https://img.shields.io/badge/chip-ESP32-blue.svg?style=flat-square)
![Package: 1.7.5](https://img.shields.io/badge/package-1.7.5-lightgrey.svg?style=flat-square)
![UART: not needed](https://img.shields.io/badge/UART-not%20needed-brightgreen.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [📍 Pins](#pins) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

The only Gen2 device so far. Classic ESP32 differs from the Gen3/Gen4 models in three ways: the partition table is at the ESP-IDF default `0x8000`, the bootloader sits at `0x1000`, and the ESPHome build needs the 80 MHz flash frequency.

| Fact | Value |
| --- | --- |
| Profile | `PlusPlugS` |
| Flash | 4 MB |
| Official package | 1.7.5 |
| Partition table | **`0x8000`** (ESP-IDF default) |
| Bootloader address | `0x1000` |
| App slot size | `0x190000` |
| Bootloader `min_version` | `1.0.9` (set in the profile) |
| ESPHome device page | [Shelly Plus Plug S](https://devices.esphome.io/devices/shelly-plus-plug-s/) |

> [!NOTE]
> **Confirmed:** the whole chain ran on a real device, without UART: `restore`, then `send` with `--esphome-factory`; an ESPHome OTA took effect (0.2.0 to 0.2.11).

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/PlusPlugS-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0x8000"`.

```yaml
esp32:
  variant: ESP32
  board: esp32dev
  flash_size: 4MB
  partitions: PlusPlugS-stock.csv        # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_PARTITION_TABLE_OFFSET: "0x8000"
      CONFIG_ESPTOOLPY_FLASHFREQ_80M: "y"   # without it `build` refuses: the bootloader header says 40 MHz
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
    allow_partition_access: true
```

> [!TIP]
> The [ESPHome device page](https://devices.esphome.io/devices/shelly-plus-plug-s/) has the pins and an example config. Replace its `esp32:` block with the one above, or `build` refuses it.

## Pins

The pins (relay, button, temperature, LED ring, the HLW8012 pins for the power measurement) are on the
[ESPHome device page](https://devices.esphome.io/devices/shelly-plus-plug-s/) (config tested by its author, bobkersten; not by
this project).

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch PlusPlugS --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build PlusPlugS app.ota.bin --esphome-factory app.factory.bin --esphome-yaml plusplugS.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send PlusPlugS out/PlusPlugS-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** (the log goes to a file with `--log-file`):

   ```
   python ota.py send PlusPlugS out/PlusPlugS-app-<date>.zip --ip <device IP> --log-file
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

`send` shows these lines at the default log level, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore PlusPlugS` first |
| 2 | `Device: The bootloader will be replaced ...` (raw log: `Boot: cur ... min ... update? 1`) | The installer will write ESPHome's bootloader. `WARNING: ESPHome's bootloader was NOT written` (`update? 0`) means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | The progress (`Update: ... %`, one line that updates in place) up to 100 %, then `Done: update installed, the device confirmed it` | The device restarts into ESPHome |

## Notes for this device

**The route that worked (no UART)**

1. First `send` of the ESPHome package: the installer wrote to **slot 1** (`Will write to slot 1`), so ESPHome's image sat in
   `app_1` while ESPHome's bootloader started the old app in `app_0`. Sending the same package again changed nothing.
2. `python ota.py restore PlusPlugS` (official package): `Boot: cur 00000000, ... update? 1` (ESPHome's bootloader reports no
   version) and **Shelly's bootloader came back over OTA**. The stock firmware then ran from slot 1.
3. `send` of the ESPHome package again: `Will write to slot 0`, success, ESPHome booted (project version 0.2.0). A following
   ESPHome OTA changed the version to 0.2.11 (owner report; the boot log of that step was not reviewed here).

`send` now does the slot check for you and tells you to run `restore` first. If you are stuck with ESPHome in `app_1`:
[hand-made otadata over UART](../troubleshooting.md#select-slot-1-with-a-hand-made-otadata) (here at `0xd000`).

**A bricked unit.** One unit that ran ESPHome and no longer started was brought back to Shelly OS over UART from the official
package ([Recovery over UART](../recovery-uart.md) uses this device as its example). `espefuse summary` showed `BLOCK3` with a
byte `0x07` set; the installer logs `FW signatures: want 07 got 00` and failed eFuse writes ("Bits are not empty"). Nothing was
burned; the meaning of the bits is unknown ([eFuse note](../troubleshooting.md#efuse)).

## Way back

While Shelly firmware runs: `python ota.py restore PlusPlugS`. Otherwise [Recovery over UART](../recovery-uart.md).

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
