# Pro 4PM (Gen2)

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: untested](https://img.shields.io/badge/state-untested-lightgrey.svg?style=flat-square)
![Generation: 2](https://img.shields.io/badge/gen-2-lightgrey.svg?style=flat-square)
![Chip: ESP32](https://img.shields.io/badge/chip-ESP32-blue.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

Gen2 / classic ESP32: dIN rail module, four relays with power metering. Partition table at the ESP-IDF default `0x8000`, bootloader at `0x1000`, 80 MHz flash frequency, like the [Plus Plug S](PlusPlugS.md).

| Fact | Value |
| --- | --- |
| Profile | `Pro4PM` |
| Flash | 8 MB (bootloader header and partition table) |
| Official package | 2.1.1 |
| Partition table | **`0x8000`** (ESP-IDF default) |
| Bootloader address | `0x1000` |
| App slot size | `0x200000` |

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/Pro4PM-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0x8000"`.

```yaml
esp32:
  variant: ESP32
  board: esp32dev
  flash_size: 8MB
  partitions: Pro4PM-stock.csv        # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_PARTITION_TABLE_OFFSET: "0x8000"
      CONFIG_ESPTOOLPY_FLASHFREQ_80M: "y"   # without it `build` refuses: the bootloader header says 80 MHz
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
    allow_partition_access: true
```

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch Pro4PM --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build Pro4PM app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send Pro4PM out/Pro4PM-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** (the log goes to a file with `--log-file`):

   ```
   python ota.py send Pro4PM out/Pro4PM-app-<date>.zip --ip <device IP> --log-file
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

`send` shows these lines at the default log level, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore Pro4PM` first |
| 2 | `Device: The bootloader will be replaced ...` (raw log: `Boot: cur ... min ... update? 1`) | The installer will write ESPHome's bootloader. `WARNING: ESPHome's bootloader was NOT written` (`update? 0`) means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | The progress (`Update: ... %`, one line that updates in place) up to 100 %, then `Done: update installed, the device confirmed it` | The device restarts into ESPHome |

## Notes for this device

**Not tried on a device.** The profile is made from Shelly's package for the app name `Pro4PM`; nobody has flashed it yet. The stock partition table is in `partitions/Pro4PM-stock.csv`. The DevKit image `python ota.py devkit Pro4PM` is built for it, but it has not been run on a dev board either (so the state stays 🧪, see [DevKit](../devkit.md)).

**Pins.** Not mapped here. No stock dump of this device has been analysed here; pins read from firmware or templates are "not confirmed" until someone has measured them.

**Bootloader `min_version`.** The official package carries Shelly OS loader 1.0.2. The profile sets `boot_min_version: 1.0.9`, the
default of the newer profiles, because a unit that Shelly has already updated can report 1.0.3 and would then skip a package with
1.0.3. The loader of a real Pro 4PM has not been seen yet.

**The slot.** The Plus Plug S, a device of the same generation, first received the app in slot 1 and needed `restore` once; `send` checks
the target slot for you ([why](../bootloader-and-slots.md#the-app-must-land-in-slot-0)).

Please report the file written by `--log-file`, especially the lines `Update target slot`, `Boot: cur ... update?` and `Will write to slot`.

## Way back

`python ota.py restore Pro4PM` sends the official firmware back while Shelly firmware still runs.

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
