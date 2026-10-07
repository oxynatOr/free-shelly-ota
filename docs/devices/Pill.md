# Shelly The Pill

[Back to the README](../../README.md) · [All commands](../commands.md)

Not tested on hardware. Reported: the USB-C port exposes the chip's USB Serial/JTAG, so this device can be flashed and recovered with `esptool` without opening it. That makes UART recovery much easier than on the other models.

| | |
| --- | --- |
| Profile | `Pill` |
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
  partitions: Pill-stock.csv        # copy from partitions/ in this repository
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

## Pins

| GPIO | Function |
| --- | --- |
| GPIO4 | `pin0`, primary I/O on the Micro-USB sensor port (ADC, 1-Wire, DHT22, I2C SDA) |
| GPIO3 | `pin1`, secondary I/O (ADC, I2C SCL) |
| GPIO6 | `pin2`, digital I/O only |
| GPIO10 | Reset button (back of the PCB; hold more than 10 s for a factory reset) |
| GPIO8 | Status LED (active low) |
| GPIO18 / GPIO19 | USB Serial/JTAG on the USB-C port, for flashing and the console |

Source: the owner's [The Pill page](https://devices.esphome.io/devices/Shelly-The-Pill/) in the ESPHome device database. USB-C is the flashing path, so no soldering is
needed. The sensor port takes Shelly's add-ons (5-terminal, SSR, analog 0 to 30 V, DS18B20).

## Flash it

```
pip install -r requirements.txt
python ota.py fetch Pill --insecure
python ota.py build Pill app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
python ota.py send Pill out/Pill-app-<date>.zip --ip <device IP> --dry-run
python ota.py send Pill out/Pill-app-<date>.zip --ip <device IP> --watch 120
```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

In the `--watch` log look for these lines, in this order:

1. `Update target slot: 0 ...` from `send` (the slot check; if it says anything else, run `python ota.py restore Pill` first).
2. `Boot: cur ... min ... update? 1`: the installer will write ESPHome's bootloader. `update? 0` means it will not: build again
   with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)).
3. `ota_progress` up to 95 %, then `ota_success`. The device restarts into ESPHome.

The package wipes NVS: Wi-Fi and settings are gone, ESPHome opens its own access point or joins the Wi-Fi from your config.
If nothing comes up, power-cycle the device ([Troubleshooting](../troubleshooting.md#esphome-does-not-start-after-the-update)).

## Notes for this device

No device-specific findings yet. Please report the `--watch` log, especially the lines `Update target slot`, `Boot: cur ... update?` and `Will write to slot`.

## Way back

USB-C and `esptool` ([Recovery over UART](../recovery-uart.md): the same steps, with the USB-C port instead of a UART adapter, if the report holds). While Shelly firmware runs: `python ota.py restore Pill`.
