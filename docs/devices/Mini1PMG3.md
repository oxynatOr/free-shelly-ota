# Shelly Mini 1PM Gen3

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: partly checked](https://img.shields.io/badge/state-partly%20checked-yellow.svg?style=flat-square)
![Chip: ESP32-C3](https://img.shields.io/badge/chip-ESP32--C3-blue.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

This is the Mini with a relay; the measuring-only [PM Mini Gen3](MiniPMG3.md) is a different device with its own profile. Like the H&T Gen3, the official package keeps its partition table at `0xf000`, so a default ESPHome build does not match.

| Fact | Value |
| --- | --- |
| Profile | `Mini1PMG3` |
| Flash | 8 MB |
| Official package | 2.1.0 (stable since 2026-10-14; Bootloader, partition table and filesystem are the same as in 2.0.1) |
| Partition table | `0xf000` |
| App slot size | `0x2a0000` |
| ESPHome device page | [Shelly 1PM Mini Gen3](https://devices.esphome.io/devices/shelly-1pm-mini-gen3/) |

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/Mini1PMG3-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0xf000"`.

```yaml
esp32:
  variant: ESP32C3
  board: esp32-c3-devkitm-1
  flash_size: 8MB
  partitions: Mini1PMG3-stock.csv        # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_PARTITION_TABLE_OFFSET: "0xf000"
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
    allow_partition_access: true
```

> [!TIP]
> The [ESPHome device page](https://devices.esphome.io/devices/shelly-1pm-mini-gen3/) has the pins and an example config. Replace its `esp32:` block with the one above, or `build` refuses it.

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch Mini1PMG3 --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build Mini1PMG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send Mini1PMG3 out/Mini1PMG3-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** (the log goes to a file with `--log-file`):

   ```
   python ota.py send Mini1PMG3 out/Mini1PMG3-app-<date>.zip --ip <device IP> --log-file
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

`send` shows these lines at the default log level, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore Mini1PMG3` first |
| 2 | `Device: The bootloader will be replaced ...` (raw log: `Boot: cur ... min ... update? 1`) | The installer will write ESPHome's bootloader. `WARNING: ESPHome's bootloader was NOT written` (`update? 0`) means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | The progress (`Update: ... %`, one line that updates in place) up to 100 %, then `Done: update installed, the device confirmed it` | The device restarts into ESPHome |

## Notes for this device

- **Result:** first report ([#82](https://github.com/oxynatOr/free-shelly-ota/issues/82)), two units, both on stock **1.4.0**, with the 2.1.0 package built from this profile (revision 2, `--esphome-factory`). `/shelly` showed slot 1 on both, but `send --dry-run` said `Update target slot: 0`, so no `restore` was needed. The update was confirmed by the device, it rebooted into ESPHome by itself, joined Wi-Fi and served the ESPHome web page. The same reporter flashed two [Mini 1 Gen3](Mini1G3.md) the same day (stock 1.4.4, package 2.0.1): both run ESPHome.
- **Loader 1.0.0 on stock 1.4.0:** the log shows `Boot: cur 010000ff, new 00000000, min 010009ff, update? 1`, the oldest loader seen on a Gen3 device so far. `boot_min_version: 1.0.9` is higher, so ESPHome's bootloader was written. Stock 1.4.0 does not print a `Will write to slot` line; the slot comes from the check of `send`. The two lines `EFUSE write error bit[1]: 5636` and `bit[2]: 5636` come after the update was confirmed and are the same as on the other Gen3 reports ([why they are harmless](../troubleshooting.md#esphome-does-not-start-after-the-update)).
- **Not checked yet:** a second (ESPHome) OTA, which is what proves that the bootloader step took effect, the relay under a load (it is almost silent without one, like the Mini 1 Gen3) and the BL0942 readings. The state goes to confirmed with a report on these.
- **Pins used in the report** (from the [ESPHome device page](https://devices.esphome.io/devices/shelly-1pm-mini-gen3/), the pins as such not verified): relay GPIO5, switch input GPIO10, button GPIO1 (inverted, pull-up), LED GPIO0 (inverted), BL0942 on UART TX GPIO6 / RX GPIO7 (RX with pull-up, as on the [PM Mini Gen3](MiniPMG3.md)), NTC GPIO3 with B 3950, 10 kOhm, `DOWNSTREAM`, as in the [Mini 1 Gen3 notes](Mini1G3.md).
- Please report the file written by `--log-file`, especially the lines `Update target slot`, `Boot: cur ... update?` and `Will write to slot`.

## Way back

`python ota.py restore Mini1PMG3` sends the official firmware back while Shelly firmware still runs.

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
