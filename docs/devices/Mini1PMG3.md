# Shelly Mini 1PM Gen3

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: partly checked](https://img.shields.io/badge/state-partly%20checked-yellow.svg?style=flat-square)
![State of the 2.2.1 layout: partly checked](https://img.shields.io/badge/state-partly%20checked-yellow.svg?style=flat-square)
![Generation: 3](https://img.shields.io/badge/gen-3-lightgrey.svg?style=flat-square)
![Chip: ESP32-C3](https://img.shields.io/badge/chip-ESP32--C3-blue.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

This is the Mini with a relay; the measuring-only [PM Mini Gen3](MiniPMG3.md) is a different device with its own profile. Like the H&T Gen3, the official package keeps its partition table at `0xf000`, so a default ESPHome build does not match.

> **Shelly's stable 2.2.1 has another layout** (app slots of `0x300000` instead of `0x2a0000`). The `Mini1PMG3` profile knows both layouts; see [2.2.1 layout](#221-layout). `build` picks the layout that matches your partition table.

| Fact | Value |
| --- | --- |
| Profile | `Mini1PMG3` (both flash layouts, see [2.2.1 layout](#221-layout)) |
| Flash | 8 MB |
| Official package | 2.2.1 (stable, seen 2026-11-20), with the 2.2.1 layout. The first layout needs a 2.1.x or older package: 2.1.0 (stable from 2026-10-14) has the same bootloader, partition table and filesystem as 2.0.1, and the hardware runs were made with 2.1.0 |
| Partition table | `0xf000` |
| App slot size | `0x2a0000` before Shelly 2.2.1, `0x300000` from 2.2.1 |
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

## 2.2.1 layout

Shelly's stable `2.2.1` for this device has a **different flash layout**, the one of the 2.2.0 betas of the other Gen3 devices ([Beta firmware with another flash layout](../bootloader-and-slots.md#beta-firmware-with-another-flash-layout)) and of the stable 2.2.0 of the [2PM Gen3](S2PMG3.md#220-layout): the app slots are `0x300000` instead of `0x2a0000`, and the filesystems and the second slot move up with them. The partition table stays at `0xf000`. The `Mini1PMG3` profile lists it under `layouts:`; `build` uses it when your partition table matches it.

| Firmware | `app_0` | `app_1` | `fs_0` / `fs_1` |
| --- | --- | --- | --- |
| 2.0.1 to 2.1.x (`Mini1PMG3`) | `0x20000` / `0x2a0000` | `0x3a0000` / `0x2a0000` | `0x2c0000` / `0x640000`, `0xe0000` each |
| 2.2.1 (`Mini1PMG3`) | `0x20000` / `0x300000` | `0x400000` / `0x300000` | `0x320000` / `0x700000`, `0xe0000` each |

`otadata`, `nvs`, `scratch` (`0x7e0000`) and `shelly` (`0x7f0000`) stay where they are.

> [!NOTE]
> **Partly checked (2026-11-24, one unit, `S3SW-001P8EU`, no UART, thanks to [andrewagner86](https://github.com/andrewagner86)):**
>
> - The table is read from the official 2.2.1 package (`partition-table.bin` at `0xf000`).
> - The unit ran Shelly 2.2.1 (`20261113-111619/2.2.1-gffa2ea1`), the same build as the package.
> - A plain package built with `Mini1PMG3-v2` (no `--esphome-factory`), whose app was a custom ESP-IDF app that replaces the bootloader itself and not ESPHome, was uploaded through Shelly's web interface (Settings → Firmware). One run: the installer took it and the app started. There is no device log of that run, so the slot it was written to is not recorded.
> - That app then took the unit back to Shelly 2.2.1 from the official ZIP (all parts: `boot`, `pt`, `otadata`, `nvs`, `app`, `fs`). Shelly 2.2.1 started again and joined the Wi-Fi.
>
> **Not checked:** ESPHome with this profile, a package built with `--esphome-factory` (the bootloader swap), `send` and `restore Mini1PMG3-v2` with `ota.py`, `inspect --device`, a later ESPHome OTA, the table in flash (no dump), the update path to 2.2.1, and whether Shelly's 2.2.0 for this device already had the layout (`layout_since` is `2.2.1`, the first version seen with it). `boot_min_version` is `1.0.9`, as for `Mini1PMG3`.

> **Partly checked with ESPHome (one unit, `S3SW-001P8EU`, thanks to [broglea](https://github.com/broglea)):**
>
> - Converted from stock 2.2.1 (`20261113-111619/2.2.1-gffa2ea1`) to ESPHome 2026.11.0 with `Mini1PMG3-v2`. The installer wrote to slot 0 and replaced the bootloader (`update? 1`). The update was confirmed although two eFuse writes failed with code 5636, the same as in the [eFuse note](../troubleshooting.md#esphome-does-not-start-after-the-update).
> - ESPHome connected through its native API. A later encrypted ESPHome OTA to a different build worked, and the device reconnected after a reboot.
> - Relay and meter under a lighting load of about 17 W: 16.9 W and 0.148 A with ESPHome, 17.3 W and 0.15 A on stock.
> - The first ESPHome build showed the relay on with zero current and power. The follow-up config released the GPIO5 pad hold after setting the output off, enabled GPIO5 input for readback, and calibrated the line voltage against the stock reading on that unit. The cause of the first symptom is not confirmed.
>
> **Not checked:** a physical reset, the electrical protection trip points, and other hardware units.

> [!CAUTION]
> **Match the package to the firmware.** `send` refuses a package of the 2.2.1 layout on firmware before 2.2.1 (`layout_since`,
> `--force` overrides). A package of the first layout on 2.2.1 only gets a warning (on a dev board with `PlugSG3` it ran).

- Fetch the package: `python ota.py fetch Mini1PMG3 --insecure` (or `--cafile`, see [ca](../commands.md#ca)); 2.2.1 is the stable release and both layouts use the package called `Mini1PMG3`.
- Build against its table: copy `partitions/Mini1PMG3-stock-2.2.1.csv`, use it as `esp32: partitions:` in the ESPHome config and keep `CONFIG_PARTITION_TABLE_OFFSET: "0xf000"`.
- Then `python ota.py build Mini1PMG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml`, and `send Mini1PMG3`.

## Way back

`python ota.py restore Mini1PMG3` sends the official firmware back while Shelly firmware still runs. For a device on the 2.2.1 layout the same command applies (not tested with `ota.py`; the official 2.2.1 ZIP written back by another app ran, see [2.2.1 layout](#221-layout)).

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **The config is yours.** The tool checks the package, not your ESPHome config: pins, relay and limits are your responsibility, and a wrong `ota:`, `api:` or Wi-Fi setting can leave the device unreachable (then only UART helps). Test the config on a dev board first.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
