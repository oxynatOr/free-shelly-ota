# Shelly 2PM Gen3

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: confirmed](https://img.shields.io/badge/state-confirmed-brightgreen.svg?style=flat-square)
![Chip: ESP32-C3](https://img.shields.io/badge/chip-ESP32--C3-blue.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

Gen3 / ESP32-C3.

| Fact | Value |
| --- | --- |
| Profile | `S2PMG3` |
| Flash | 8 MB |
| Official package | 2.1.0 |
| Partition table | `0x10000` |
| App slot size | `0x2c0000` |
| ESPHome device page | [Shelly 2 PM Gen3](https://devices.esphome.io/devices/shelly-2-pm-gen3/) |

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/S2PMG3-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0x10000"`.

```yaml
esp32:
  variant: ESP32C3
  board: esp32-c3-devkitm-1
  flash_size: 8MB
  partitions: S2PMG3-stock.csv        # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      COMPILER_OPTIMIZATION_SIZE: y
      CONFIG_PARTITION_TABLE_OFFSET: "0x10000"
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
    allow_partition_access: true
```

> [!TIP]
> The [ESPHome device page](https://devices.esphome.io/devices/shelly-2-pm-gen3/) has a config to start from. Replace its `esp32:` block with the one above, or `build` refuses it.

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch S2PMG3 --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build S2PMG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send S2PMG3 out/S2PMG3-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** and watch the log:

   ```
   python ota.py send S2PMG3 out/S2PMG3-app-<date>.zip --ip <device IP> --watch 120
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

In the `--watch` log look for these lines, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore S2PMG3` first |
| 2 | `Boot: cur ... min ... update? 1` | The installer will write ESPHome's bootloader. `update? 0` means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | `ota_progress` up to 95 %, then `ota_success` | The device restarts into ESPHome |

## Notes for this device

First report ([#92](https://github.com/oxynatOr/free-shelly-ota/issues/92), thanks to [majoto85](https://github.com/majoto85)): flashed over OTA from Shelly 1.4.99 (running from slot 1) with `--esphome-factory`. The installer wrote ESPHome's bootloader (loader `010001ff`, minimum `010009ff`) and the device booted straight into ESPHome without a power cycle, joined Wi-Fi, and a later regular ESPHome OTA took effect. Relays and the meter were not part of the report.

- **Two more units** (thanks to [WulffTech](https://github.com/WulffTech)): `S3SW-002P16EU`, from Shelly 2.0.1 to ESPHome 2026.9.0 over OTA without UART, built with their own tooling instead of `ota.py`. Both ran stable across reboots, the relays stayed off after them, and a later ESPHome OTA worked. The meter was not reported.
- **Slot:** the first `--dry-run` could not read the target slot (8 s timeout); a second one right after showed slot 0.
- The installer logs refused eFuse writes (`FW signatures: want 07, got 00`). The update still finished and the device confirmed it.

The profile sets `boot_min_version: "1.0.9"`: devices of this family run Shelly's loader 1.0.3, which would otherwise skip ESPHome's bootloader (`update? 0`).

## Way back

`python ota.py restore S2PMG3` sends the official firmware back while Shelly firmware still runs.

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
