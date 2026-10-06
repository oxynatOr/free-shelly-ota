# Shelly Mini 1PM Gen3

[Back to the README](../../README.md) · [All commands](../commands.md)

Not tested on hardware. Like the H&T Gen3, the official package keeps its partition table at `0xf000`, so a default ESPHome build does not match.

| | |
| --- | --- |
| Profile | `Mini1PMG3` |
| Chip | ESP32-C3, 8 MB flash |
| Official package | 2.0.1 |
| Partition table | `0xf000` |
| App slot size | `0x2a0000` |
| State | 🧪 builds and verifies; not flashed |

## ESPHome config

```yaml
esp32:
  variant: ESP32C3
  board: esp32-c3-devkitm-1
  flash_size: 8MB
  partitions: Mini1PMG3-stock.csv        # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      COMPILER_OPTIMIZATION_SIZE: y
      CONFIG_PARTITION_TABLE_OFFSET: "0xf000"
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
```

## Flash it

```
pip install -r requirements.txt
python ota.py fetch Mini1PMG3 --insecure
python ota.py build Mini1PMG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
python ota.py send Mini1PMG3 out/Mini1PMG3-app-<date>.zip --ip <device IP> --dry-run
python ota.py send Mini1PMG3 out/Mini1PMG3-app-<date>.zip --ip <device IP> --watch 120
```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

In the `--watch` log look for these lines, in this order:

1. `Update target slot: 0 ...` from `send` (the slot check; if it says anything else, run `python ota.py restore Mini1PMG3` first).
2. `Boot: cur ... min ... update? 1`: the installer will write ESPHome's bootloader. `update? 0` means it will not: build again
   with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)).
3. `ota_progress` up to 95 %, then `ota_success`. The device restarts into ESPHome.

The package wipes NVS: Wi-Fi and settings are gone, ESPHome opens its own access point or joins the Wi-Fi from your config.
If nothing comes up, power-cycle the device ([Troubleshooting](../troubleshooting.md#esphome-does-not-start-after-the-update)).

## Notes for this device

No device-specific findings yet. Please report the `--watch` log, especially the lines `Update target slot`, `Boot: cur ... update?` and `Will write to slot`.

## Way back

`python ota.py restore Mini1PMG3` sends the official firmware back while Shelly firmware still runs. Once ESPHome with
ESPHome's bootloader is running, `restore` gets no answer and only UART brings Shelly OS back
([Recovery over UART](../recovery-uart.md)): take a flash backup first if you can.
