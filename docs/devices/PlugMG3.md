# Shelly Plug M Gen3

[Back to the README](../../README.md) · [All commands](../commands.md)

The first device this tool was confirmed on.

| | |
| --- | --- |
| Profile | `PlugMG3` |
| Chip | ESP32-C3, 8 MB flash |
| Official package | 2.0.1 |
| Partition table | `0x10000` |
| App slot size | `0x2a0000` |
| State | ✅ `send` from stock 1.8.99 (running from slot 1), then two ESPHome OTAs |

## ESPHome config

```yaml
esp32:
  variant: ESP32C3
  board: esp32-c3-devkitm-1
  flash_size: 8MB
  partitions: PlugMG3-stock.csv        # copy from partitions/ in this repository
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

Pins read from the stock firmware and tested on a real plug:

| Function | Pin |
| --- | --- |
| Relay | GPIO0 |
| Button | GPIO7 |
| BL0942 power meter (UART, 9600 8N1) | TX GPIO4, RX GPIO5 |
| BL0942 CF/ZX pin (multiplexed: CF by default, zero-cross after a register write the stock firmware does) | GPIO3 |
| RGB LED (common anode, **active low**: `inverted: true` on every output) | red GPIO18, green GPIO10, blue GPIO19 |
| NTC (beta 3950, 10 k at 25 C) | probably GPIO1 (ADC1_CH1), the reading looks right |

## Flash it

```
pip install -r requirements.txt
python ota.py fetch PlugMG3 --insecure
python ota.py build PlugMG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
python ota.py send PlugMG3 out/PlugMG3-app-<date>.zip --ip <device IP> --dry-run
python ota.py send PlugMG3 out/PlugMG3-app-<date>.zip --ip <device IP> --watch 120
```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

In the `--watch` log look for these lines, in this order:

1. `Update target slot: 0 ...` from `send` (the slot check; if it says anything else, run `python ota.py restore PlugMG3` first).
2. `Boot: cur ... min ... update? 1`: the installer will write ESPHome's bootloader. `update? 0` means it will not: build again
   with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)).
3. `ota_progress` up to 95 %, then `ota_success`. The device restarts into ESPHome.

The package wipes NVS: Wi-Fi and settings are gone, ESPHome opens its own access point or joins the Wi-Fi from your config.
If nothing comes up, power-cycle the device ([Troubleshooting](../troubleshooting.md#esphome-does-not-start-after-the-update)).

## Notes for this device

- On this model ESPHome came up after a power-off of about 30 seconds; whether it would also have started without it was not tested.
- Without `--esphome-factory` ESPHome still boots, but later ESPHome OTAs only take effect after Shelly's attempt counter runs out
  ([details](../bootloader-and-slots.md#without-esphomes-bootloader-plain-package)).

## Way back

`python ota.py restore PlugMG3` sends the official firmware back while Shelly firmware still runs. Once ESPHome with
ESPHome's bootloader is running, `restore` gets no answer and only UART brings Shelly OS back
([Recovery over UART](../recovery-uart.md)): take a flash backup first if you can. Done once on a real plug: Shelly OS 2.0.1 with
loader 1.0.3 came back. Pushing the official app image through ESPHome OTA instead does not work (same page).

A Plug M restored this way has loader 1.0.3, which is why the profile sets `boot_min_version: 1.0.9`: a later `send` with
`--esphome-factory` still replaces the bootloader. Because Shelly then runs from slot 0, run `python ota.py restore PlugMG3`
first, otherwise `send` refuses (the installer would write to slot 1).
