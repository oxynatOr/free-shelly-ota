# Shelly Power Strip 4 Gen4

[Back to the README](../../README.md) · [All commands](../commands.md)

Gen4 / ESP32-C6. A full example config with all pins is in [`configs/shelly-power-strip-gen4/`](../../configs/shelly-power-strip-gen4).

| | |
| --- | --- |
| Profile | `PowerStrip` |
| Chip | ESP32-C6, 8 MB flash |
| Official package | 2.0.1 |
| Partition table | `0x10000` |
| App slot size | `0x300000` |
| Bootloader `min_version` | `1.0.9` (set in the profile) |
| State | ✅ ESPHome boots and joins Wi-Fi/Home Assistant (UART log). Outlets and metering not checked here |

## ESPHome config

```yaml
esp32:
  variant: ESP32C6
  board: esp32-c6-devkitc-1
  flash_size: 8MB
  partitions: PowerStrip-stock.csv        # copy from partitions/ in this repository
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

Add this under `esphome:` (the C6 needs the 80 MHz flash header, otherwise `build` refuses):

```yaml
esphome:
  platformio_options:
    board_build.flash_mode: dio
    board_build.f_flash: 80000000L
    board_build.flash_size: 8MB
```

| Function | Pin | Source |
| --- | --- | --- |
| SPI MISO / MOSI / SCLK | GPIO12 / GPIO11 / GPIO13 | stock boot log (`SPI2 init ok`) |
| ADE7953 chip select (outlets 1+2 / 3+4) | GPIO15 / GPIO10 | stock boot log (`CS0/1/2: 15/10/-1`) |
| ADE7953 IRQ (chip 0 / chip 1) | GPIO6 / GPIO7 | in use on the owner's device |
| Relays 1 to 4 | GPIO4 / GPIO2 / GPIO3 / GPIO1 | in use on the owner's device |
| Buttons 1 to 4 (pull-up, inverted) | GPIO20 / GPIO22 / GPIO23 / GPIO21 | in use on the owner's device |
| LED ring (WS2812, 12 LEDs, 3 per outlet) | GPIO18 | in use on the owner's device |

## Flash it

```
pip install -r requirements.txt
python ota.py fetch PowerStrip --insecure
python ota.py build PowerStrip app.ota.bin --esphome-factory app.factory.bin --esphome-yaml shelly-power-strip-gen4.yaml
python ota.py send PowerStrip out/PowerStrip-app-<date>.zip --ip <device IP> --dry-run
python ota.py send PowerStrip out/PowerStrip-app-<date>.zip --ip <device IP> --watch 120
```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

In the `--watch` log look for these lines, in this order:

1. `Update target slot: 0 ...` from `send` (the slot check; if it says anything else, run `python ota.py restore PowerStrip` first).
2. `Boot: cur ... min ... update? 1`: the installer will write ESPHome's bootloader. `update? 0` means it will not: build again
   with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)).
3. `ota_progress` up to 95 %, then `ota_success`. The device restarts into ESPHome.

The package wipes NVS: Wi-Fi and settings are gone, ESPHome opens its own access point or joins the Wi-Fi from your config.
If nothing comes up, power-cycle the device ([Troubleshooting](../troubleshooting.md#esphome-does-not-start-after-the-update)).

## Notes for this device

- **Stock 1.7.99:** a direct `send` did not work: the installer wrote to slot 1 and the old app in `app_0` started again,
  although the update reported success. `send` now reads the target slot first and refuses; after one official update to
  2.0.1 (or `ota.py restore PowerStrip`) a new `send` targeted slot 0 and ESPHome started
  ([slot rule](../bootloader-and-slots.md#the-app-must-land-in-slot-0)). The 1.7.99 installer also left the old partition
  table (no `scratch`); after 2.0.1 it was the new one.
- **`min_version`:** with `1.0.9` the installer wrote ESPHome's bootloader (hardware-confirmed).
- **After a good install** the UART log shows `ESP-IDF ... 2nd stage bootloader`, `ota data partition invalid and no factory,
  will try all partitions` (expected) and `Loaded app from partition at offset 0x20000`.
- **OTA encryption:** the owner's build requires it (`Encryption: required`); the example config has no `encryption:` entry.

## Way back

`python ota.py restore PowerStrip` sends the official firmware back while Shelly firmware still runs. Once ESPHome with
ESPHome's bootloader is running, `restore` gets no answer and only UART brings Shelly OS back
([Recovery over UART](../recovery-uart.md)): take a flash backup first if you can.
