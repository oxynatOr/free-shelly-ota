# Shelly Plus i4 / i4 DC (Gen2)

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: partly checked](https://img.shields.io/badge/state-partly%20checked-yellow.svg?style=flat-square)
![Chip: ESP32](https://img.shields.io/badge/chip-ESP32-blue.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [📍 Pins](#pins) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

A classic ESP32 like the [Plus Uni](PlusUni.md): partition table at the ESP-IDF default `0x8000`, bootloader at `0x1000`, and the ESPHome build needs the 80 MHz flash frequency (the bootloader header says so). Thanks to [niki11euro](https://github.com/niki11euro) for the request and the first run on the DC version (October 2026, [#106](https://github.com/oxynatOr/free-shelly-ota/issues/106)); the profile is made from Shelly's package for the app name `PlusI4`, which is the name that device reports.

| Fact | Value |
| --- | --- |
| Profile | `PlusI4` |
| Model | SNSN-0D24X (Plus i4 DC, PCB `Shelly i4DC_v0.1.4`) |
| SoC | ESP32-U4WDH (as reported) |
| Flash | 4 MB (partition table: the last partition ends at `0x400000`) |
| Official package | 1.7.6 (Shelly's update API lists no 2.x for this model, checked 2026-10-29) |
| Partition table | **`0x8000`** (ESP-IDF default) |
| Bootloader address | `0x1000` |
| App slot size | `0x190000` |
| Bootloader `min_version` | `1.0.9` (set in the profile; the package carries loader 1.0.2) |

> [!NOTE]
> **Partly checked:** flashed over OTA on a real Plus i4 DC (stock 1.7.6, `send` with `--esphome-factory`, October 2026): the installer replaced the bootloader (`Boot: cur 010002ff, min 010009ff`), reported the update as done, and the device came up as an ESPHome device in Home Assistant. The inputs and the LED are not mapped or tested yet, and a later ESPHome OTA was not reported. It is not known whether the AC version of the Plus i4 uses the same app name.

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/PlusI4-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0x8000"`.

```yaml
esp32:
  variant: ESP32
  board: esp32dev
  flash_size: 4MB
  partitions: PlusI4-stock.csv        # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      COMPILER_OPTIMIZATION_SIZE: y
      CONFIG_PARTITION_TABLE_OFFSET: "0x8000"
      CONFIG_ESPTOOLPY_FLASHFREQ_80M: "y"   # without it `build` refuses: the bootloader header says 80 MHz
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
    allow_partition_access: true         # keep it in the FIRST config: it lets ESPHome Builder's "Update bootloader" fix a bootloader problem over OTA
```

## Pins

Not mapped yet: the tester has not tried the four physical inputs and the onboard LED, and no stock dump of this device has been analysed. The four inputs are the part to map (the Plus i4 has no relay); whether the board has a status LED is not checked either. Please report what you find; pins read from the firmware are listed as "not confirmed" until someone has measured them. The UART header of the board is not documented here either: look at the board and check it with a multimeter before you connect anything ([Recovery over UART](../recovery-uart.md)).

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch PlusI4 --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build PlusI4 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send PlusI4 out/PlusI4-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** (the log goes to a file with `--log-file`):

   ```
   python ota.py send PlusI4 out/PlusI4-app-<date>.zip --ip <device IP> --log-file
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

`send` shows these lines at the default log level, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore PlusI4` first |
| 2 | `Device: The bootloader will be replaced ...` (raw log: `Boot: cur ... min ... update? 1`) | The installer will write ESPHome's bootloader. `WARNING: ESPHome's bootloader was NOT written` (`update? 0`) means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | The progress (`Update: ... %`, one line that updates in place) up to 100 %, then `Done: update installed, the device confirmed it` | The device restarts into ESPHome |

## Notes for this device

**Bootloader `min_version`.** The unit ran Shelly OS loader **1.0.2** (`Boot: cur 010002ff`), the one in the official package. The profile sets `boot_min_version: 1.0.9`, so the installer replaced it (`min 010009ff`, update, `Installing the bootloader (25888 bytes)`). A device that Shelly updated can report 1.0.3 (as on the Plus Uni); the 1.0.9 covers that too ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)).

**The slot.** The first dry run said the update would go to slot 1. The tester ran `python ota.py restore PlusI4` once; the second dry run then said slot 0, and the OTA went to slot 0. This is the same case as on the Plus Plug S: if `send` does not say `Update target slot: 0`, run `restore` first ([why](../bootloader-and-slots.md#the-app-must-land-in-slot-0)).

**eFuse.** The log showed `FW signatures: want 07 got 00`, and the tester read it as refused eFuse writes. The update still completed ([eFuse note](../troubleshooting.md#efuse)).

**ESPHome warnings.** As on other classic ESP32 devices, leave `minimum_chip_revision` and `sram1_as_iram` out of the config you build the package from: `build` refuses a bootloader whose header differs from Shelly's ([why](../troubleshooting.md#build-refuses-to-replace-the-bootloader)).

Reported size: the ESPHome app was 1,041,216 bytes, 64 % of the app slot.

Still open: the pins of the four inputs and the LED, and a later ESPHome OTA. Please report the file written by `--log-file`, especially the lines `Update target slot`, `Boot: cur ... update?` and `Will write to slot`.

## Way back

`python ota.py restore PlusI4` sends the official firmware back while Shelly firmware still runs.

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
