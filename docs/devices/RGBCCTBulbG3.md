# Shelly Multicolor Bulb E27 Gen3

[Back to the README](../../README.md) · [All commands](../commands.md)

The LEDs sit behind a **KP18068** 5-channel driver on SDA GPIO4 / SCL GPIO5. ESPHome has no official driver for it, so the example config uses the external component [oxynatOr/esphome-kp18058](https://github.com/oxynatOr/esphome-kp18058).

| | |
| --- | --- |
| Profile | `RGBCCTBulbG3` |
| Chip | ESP32-C3, 8 MB flash |
| Official package | 2.0.1 |
| Partition table | `0x10000` |
| App slot size | `0x280000` |
| State | ✅ `send` with `--esphome-factory` ran through and ESPHome runs (owner report). The light itself is not confirmed yet |

## ESPHome config

```yaml
esp32:
  variant: ESP32C3
  board: esp32-c3-devkitm-1
  flash_size: 8MB
  partitions: RGBCCTBulbG3-stock.csv        # copy from partitions/ in this repository
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

The full example config (RGBW light, per-channel test lights, current codes as the Shelly firmware sends them) is in
[`configs/shelly-rgbcct-bulb-g3/`](../../configs/shelly-rgbcct-bulb-g3). It pulls the driver component through
`external_components`.

Channel order read from the stock firmware (not measured on the bulb): OUT1 = blue, OUT2 = red, OUT3 = green; OUT4 and OUT5 get
the same value (one white level). The `Test OUT1` to `Test OUT5` lights in the example are there to confirm this.

## Flash it

```
pip install -r requirements.txt
python ota.py fetch RGBCCTBulbG3 --insecure
python ota.py build RGBCCTBulbG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml shelly-rgbcct-bulb-g3.yaml
python ota.py send RGBCCTBulbG3 out/RGBCCTBulbG3-app-<date>.zip --ip <device IP> --dry-run
python ota.py send RGBCCTBulbG3 out/RGBCCTBulbG3-app-<date>.zip --ip <device IP> --watch 120
```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

In the `--watch` log look for these lines, in this order:

1. `Update target slot: 0 ...` from `send` (the slot check; if it says anything else, run `python ota.py restore RGBCCTBulbG3` first).
2. `Boot: cur ... min ... update? 1`: the installer will write ESPHome's bootloader. `update? 0` means it will not: build again
   with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)).
3. `ota_progress` up to 95 %, then `ota_success`. The device restarts into ESPHome.

The package wipes NVS: Wi-Fi and settings are gone, ESPHome opens its own access point or joins the Wi-Fi from your config.
If nothing comes up, power-cycle the device ([Troubleshooting](../troubleshooting.md#esphome-does-not-start-after-the-update)).

## Notes for this device

- **Installed loader:** `Shelly OS loader 1.0.2` (visible on UART). The default `min_version` 1.0.3 was enough.
- **Dark bulb?** The driver component bit-bangs the two pins and expects an ACK for every byte. Try `ignore_ack: true` first;
  the other suspects are the address byte `0xE1` (Shelly's I2C hardware sends `0xE0`) and the internal pull-ups at a faster clock
  than Shelly's 100 kHz. Details: [`configs/shelly-rgbcct-bulb-g3/README.md`](../../configs/shelly-rgbcct-bulb-g3/README.md).

## Way back

`python ota.py restore RGBCCTBulbG3` sends the official firmware back while Shelly firmware still runs. Once ESPHome with
ESPHome's bootloader is running, `restore` gets no answer and only UART brings Shelly OS back
([Recovery over UART](../recovery-uart.md)): take a flash backup first if you can.
