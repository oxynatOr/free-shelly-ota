# Shelly Power Strip 4 Gen4 (Zigbee)

[Back to the README](../../README.md) · [All commands](../commands.md)

The Zigbee firmware variant of the [Power Strip 4 Gen4](PowerStrip.md): same hardware, listed under `alt` in the update reply of `PowerStrip`. The profile has `parent: PowerStrip`.

| | |
| --- | --- |
| Profile | `PowerStripZB` |
| Chip | ESP32-C6, 8 MB flash |
| Official package | 2.0.1 |
| Partition table | `0x10000` |
| App slot size | `0x300000` |
| State | 🧪 builds and verifies; not flashed |

## ESPHome config

Use the config of the [Power Strip page](PowerStrip.md): same pins, same partition table, same flash options.

## Flash it

```
pip install -r requirements.txt
python ota.py fetch PowerStripZB --insecure
python ota.py build PowerStripZB app.ota.bin --esphome-factory app.factory.bin --esphome-yaml shelly-power-strip-gen4.yaml
python ota.py send PowerStripZB out/PowerStripZB-app-<date>.zip --ip <device IP> --dry-run
python ota.py send PowerStripZB out/PowerStripZB-app-<date>.zip --ip <device IP> --watch 120
```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

In the `--watch` log look for these lines, in this order:

1. `Update target slot: 0 ...` from `send` (the slot check; if it says anything else, run `python ota.py restore PowerStripZB` first).
2. `Boot: cur ... min ... update? 1`: the installer will write ESPHome's bootloader. `update? 0` means it will not: build again
   with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)).
3. `ota_progress` up to 95 %, then `ota_success`. The device restarts into ESPHome.

The package wipes NVS: Wi-Fi and settings are gone, ESPHome opens its own access point or joins the Wi-Fi from your config.
If nothing comes up, power-cycle the device ([Troubleshooting](../troubleshooting.md#esphome-does-not-start-after-the-update)).

## Notes for this device

- A device that runs the Zigbee firmware reports another app name (`PowerStripZB`), so `send PowerStripZB` is the matching
  profile.
- It has not been flashed. Please report the `--watch` log. The slot rule and `min_version` notes of the Power Strip apply.

## Way back

`python ota.py restore PowerStripZB` sends the official firmware back while Shelly firmware still runs. Once ESPHome with
ESPHome's bootloader is running, `restore` gets no answer and only UART brings Shelly OS back
([Recovery over UART](../recovery-uart.md)): take a flash backup first if you can.
