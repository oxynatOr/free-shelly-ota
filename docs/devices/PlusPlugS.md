# Shelly Plus Plug S (V2 hardware, Gen2)

[Back to the README](../../README.md) · [All commands](../commands.md)

The only Gen2 device so far. Classic ESP32 differs from the Gen3/Gen4 models in three ways: the partition table is at the ESP-IDF default `0x8000`, the bootloader sits at `0x1000`, and the ESPHome build needs the 80 MHz flash frequency.

| | |
| --- | --- |
| Profile | `PlusPlugS` |
| Chip | **ESP32** (classic, Gen2), 4 MB flash |
| Official package | 1.7.5 |
| Partition table | **`0x8000`** (ESP-IDF default) |
| Bootloader address | `0x1000` |
| App slot size | `0x190000` |
| State | ✅ without UART: `restore`, then `send` with `--esphome-factory`; an ESPHome OTA took effect (0.2.0 to 0.2.11) |

## ESPHome config

```yaml
esp32:
  variant: ESP32
  board: esp32dev
  flash_size: 4MB
  partitions: PlusPlugS-stock.csv        # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      COMPILER_OPTIMIZATION_SIZE: y
      CONFIG_PARTITION_TABLE_OFFSET: "0x8000"
      CONFIG_ESPTOOLPY_FLASHFREQ_80M: "y"   # without it `build` refuses: the bootloader header says 40 MHz
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
```

## Flash it

```
pip install -r requirements.txt
python ota.py fetch PlusPlugS --insecure
python ota.py build PlusPlugS app.ota.bin --esphome-factory app.factory.bin --esphome-yaml plusplugS.yaml
python ota.py send PlusPlugS out/PlusPlugS-app-<date>.zip --ip <device IP> --dry-run
python ota.py send PlusPlugS out/PlusPlugS-app-<date>.zip --ip <device IP> --watch 120
```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

In the `--watch` log look for these lines, in this order:

1. `Update target slot: 0 ...` from `send` (the slot check; if it says anything else, run `python ota.py restore PlusPlugS` first).
2. `Boot: cur ... min ... update? 1`: the installer will write ESPHome's bootloader. `update? 0` means it will not: build again
   with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)).
3. `ota_progress` up to 95 %, then `ota_success`. The device restarts into ESPHome.

The package wipes NVS: Wi-Fi and settings are gone, ESPHome opens its own access point or joins the Wi-Fi from your config.
If nothing comes up, power-cycle the device ([Troubleshooting](../troubleshooting.md#esphome-does-not-start-after-the-update)).

## Notes for this device

**The route that worked (no UART)**

1. First `send` of the ESPHome package: the installer wrote to **slot 1** (`Will write to slot 1`), so ESPHome's image sat in
   `app_1` while ESPHome's bootloader started the old app in `app_0`. Sending the same package again changed nothing.
2. `python ota.py restore PlusPlugS` (official package): `Boot: cur 00000000, ... update? 1` (ESPHome's bootloader reports no
   version) and **Shelly's bootloader came back over OTA**. The stock firmware then ran from slot 1.
3. `send` of the ESPHome package again: `Will write to slot 0`, success, ESPHome booted (project version 0.2.0). A following
   ESPHome OTA changed the version to 0.2.11 (owner report; the boot log of that step was not reviewed here).

`send` now does the slot check for you and tells you to run `restore` first. If you are stuck with ESPHome in `app_1`:
[hand-made otadata over UART](../troubleshooting.md#select-slot-1-with-a-hand-made-otadata) (here at `0xd000`).

**A bricked unit.** One unit that ran ESPHome and no longer started was brought back to Shelly OS over UART from the official
package ([Recovery over UART](../recovery-uart.md) uses this device as its example). `espefuse summary` showed `BLOCK3` with a
byte `0x07` set; the installer logs `FW signatures: want 07 got 00` and failed eFuse writes ("Bits are not empty"). Nothing was
burned; the meaning of the bits is unknown ([eFuse note](../troubleshooting.md#efuse)).

## Way back

While Shelly firmware runs: `python ota.py restore PlusPlugS`. Otherwise [Recovery over UART](../recovery-uart.md).
