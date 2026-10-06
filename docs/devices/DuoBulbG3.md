# Shelly Duo Bulb Gen3

[Back to the README](../../README.md) · [All commands](../commands.md)

Not tested on hardware. The owner reports the same main board as the Multicolor Bulb with a different lamp module. The Duo's stock firmware has no I2C code: it drives the LEDs with PWM (LEDC), so the LED driver config of the [Multicolor Bulb](RGBCCTBulbG3.md) does not apply. The LED pins are not decoded yet.

| | |
| --- | --- |
| Profile | `DuoBulbG3` |
| Chip | ESP32-C3, 8 MB flash |
| Official package | 2.0.1 |
| Partition table | `0x10000` |
| App slot size | `0x280000` |
| State | 🧪 builds and verifies; not flashed |

## ESPHome config

```yaml
esp32:
  variant: ESP32C3
  board: esp32-c3-devkitm-1
  flash_size: 8MB
  partitions: DuoBulbG3-stock.csv        # copy from partitions/ in this repository
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

## Flash it

```
pip install -r requirements.txt
python ota.py fetch DuoBulbG3 --insecure
python ota.py build DuoBulbG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
python ota.py send DuoBulbG3 out/DuoBulbG3-app-<date>.zip --ip <device IP> --dry-run
python ota.py send DuoBulbG3 out/DuoBulbG3-app-<date>.zip --ip <device IP> --watch 120
```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

In the `--watch` log look for these lines, in this order:

1. `Update target slot: 0 ...` from `send` (the slot check; if it says anything else, run `python ota.py restore DuoBulbG3` first).
2. `Boot: cur ... min ... update? 1`: the installer will write ESPHome's bootloader. `update? 0` means it will not: build again
   with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)).
3. `ota_progress` up to 95 %, then `ota_success`. The device restarts into ESPHome.

The package wipes NVS: Wi-Fi and settings are gone, ESPHome opens its own access point or joins the Wi-Fi from your config.
If nothing comes up, power-cycle the device ([Troubleshooting](../troubleshooting.md#esphome-does-not-start-after-the-update)).

## Notes for this device

The OTA chain should work the same way as on the Multicolor Bulb (installed loader 1.0.2, default `min_version` 1.0.3), but it has
not been run. Please report the `--watch` log.

## Way back

`python ota.py restore DuoBulbG3` sends the official firmware back while Shelly firmware still runs. Once ESPHome with
ESPHome's bootloader is running, `restore` gets no answer and only UART brings Shelly OS back
([Recovery over UART](../recovery-uart.md)): take a flash backup first if you can.
