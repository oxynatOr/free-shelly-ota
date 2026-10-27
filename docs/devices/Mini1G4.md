# Shelly 1 Mini Gen4

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: DevKit-tested](https://img.shields.io/badge/state-devkit%20tested-blueviolet.svg?style=flat-square)
![Chip: ESP32-C6](https://img.shields.io/badge/chip-ESP32--C6-blue.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

Gen4 / ESP32-C6.

| Fact | Value |
| --- | --- |
| Profile | `Mini1G4` |
| Flash | 8 MB |
| Official package | 2.0.1 |
| Partition table | `0x10000` |
| App slot size | `0x300000` |

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/Mini1G4-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0x10000"`.

```yaml
esp32:
  variant: ESP32C6
  board: esp32-c6-devkitc-1
  flash_size: 8MB
  partitions: Mini1G4-stock.csv        # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      COMPILER_OPTIMIZATION_SIZE: y
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

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch Mini1G4 --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build Mini1G4 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send Mini1G4 out/Mini1G4-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** and watch the log:

   ```
   python ota.py send Mini1G4 out/Mini1G4-app-<date>.zip --ip <device IP> --watch 120
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

In the `--watch` log look for these lines, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore Mini1G4` first |
| 2 | `Boot: cur ... min ... update? 1` | The installer will write ESPHome's bootloader. `update? 0` means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | `ota_progress` up to 95 %, then `ota_success` | The device restarts into ESPHome |

## Notes for this device

Played through on a dev board with the DevKit image on 2026-10-21 (see [Seen on a board](../devkit.md#seen-on-a-board)); not on the real device yet. Please report the `--watch` log of a real device, especially the lines `Update target slot`, `Boot: cur ... update?` and `Will write to slot`.

The profile sets `boot_min_version: "1.0.9"`: devices of this family run Shelly's loader 1.0.3, which would otherwise skip ESPHome's bootloader (`update? 0`).

## Way back

`python ota.py restore Mini1G4` sends the official firmware back while Shelly firmware still runs.

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
