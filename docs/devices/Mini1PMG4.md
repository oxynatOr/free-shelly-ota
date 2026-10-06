# Shelly Mini 1PM Gen4

[Back to the README](../../README.md) · [All commands](../commands.md)

Not tested on hardware. Gen4 / ESP32-C6.

| | |
| --- | --- |
| Profile | `Mini1PMG4`, `Mini1PMG4ZB` |
| Chip | ESP32-C6, 8 MB flash |
| Official package | 2.0.1 |
| Partition table | `0x10000` |
| App slot size | `0x300000` |
| State | 🧪 builds and verifies; not flashed |

## ESPHome config

```yaml
esp32:
  variant: ESP32C6
  board: esp32-c6-devkitc-1
  flash_size: 8MB
  partitions: Mini1PMG4-stock.csv        # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      COMPILER_OPTIMIZATION_SIZE: y
      CONFIG_PARTITION_TABLE_OFFSET: "0x10000"
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
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

```
pip install -r requirements.txt
python ota.py fetch Mini1PMG4 --insecure
python ota.py build Mini1PMG4 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
python ota.py send Mini1PMG4 out/Mini1PMG4-app-<date>.zip --ip <device IP> --dry-run
python ota.py send Mini1PMG4 out/Mini1PMG4-app-<date>.zip --ip <device IP> --watch 120
```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

In the `--watch` log look for these lines, in this order:

1. `Update target slot: 0 ...` from `send` (the slot check; if it says anything else, run `python ota.py restore Mini1PMG4` first).
2. `Boot: cur ... min ... update? 1`: the installer will write ESPHome's bootloader. `update? 0` means it will not: build again
   with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)).
3. `ota_progress` up to 95 %, then `ota_success`. The device restarts into ESPHome.

The package wipes NVS: Wi-Fi and settings are gone, ESPHome opens its own access point or joins the Wi-Fi from your config.
If nothing comes up, power-cycle the device ([Troubleshooting](../troubleshooting.md#esphome-does-not-start-after-the-update)).

## Notes for this device

No device-specific findings yet. Please report the `--watch` log, especially the lines `Update target slot`, `Boot: cur ... update?` and `Will write to slot`.

## Zigbee variant

`Mini1PMG4ZB` is the Zigbee firmware variant of the same hardware (listed under `alt` in the update reply of `Mini1PMG4`; its profile has `parent: Mini1PMG4`). Use the same config and flash it with `python ota.py send Mini1PMG4ZB ...` after building with `build Mini1PMG4ZB`. Not tested either.

## Way back

`python ota.py restore Mini1PMG4` sends the official firmware back while Shelly firmware still runs. Once ESPHome with
ESPHome's bootloader is running, `restore` gets no answer and only UART brings Shelly OS back
([Recovery over UART](../recovery-uart.md)): take a flash backup first if you can.
