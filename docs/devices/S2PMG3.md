# Shelly 2PM Gen3

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: confirmed](https://img.shields.io/badge/state-confirmed-brightgreen.svg?style=flat-square)
![State of the 2.2.0 layout: partly checked](https://img.shields.io/badge/state-partly%20checked-yellow.svg?style=flat-square)
![Generation: 3](https://img.shields.io/badge/gen-3-lightgrey.svg?style=flat-square)
![Chip: ESP32-C3](https://img.shields.io/badge/chip-ESP32--C3-blue.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

Gen3 / ESP32-C3.

> **Shelly's stable 2.2.0 has another layout** (app slots of `0x300000` instead of `0x2c0000`). It has its own profile, `S2PMG3-v2`; see [2.2.0 layout](#220-layout). `build` refuses to mix the two layouts.

| Fact | Value |
| --- | --- |
| Profile | `S2PMG3`, `S2PMG3-v2` (for Shelly's 2.2.0 layout, see [2.2.0 layout](#220-layout)) |
| Flash | 8 MB |
| Official package | 2.2.0 (stable, seen 2026-11-11), with the layout of `S2PMG3-v2`. The `S2PMG3` profile needs a 2.1.x package: on 2026-11-11 Shelly's own stable update took a unit on 1.4.99 to 2.1.1 first (`fetch S2PMG3 --from-version 1.4.99` asks the update API for that step; not run) |
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
- **Way back and `--pt-addr` on this unit** (thanks to [WulffTech](https://github.com/WulffTech), from their notes, not a raw log): a 2PM Gen3 that ran ESPHome was taken back to Shelly's firmware over the network (Shelly's app image pushed with `esphome upload --file`, 90 s wait, `ota.py restore`, no UART), then a plain `send` (no `--slot-swap`) of a package built with `--pt-addr 0x8000` installed ESPHome again. Wi-Fi, mDNS, API and OTA worked, both relays switched and the power sensor followed (light 0.09 W to 2.06 W, fan 0 to 14 W). Three earlier plain sends fell back to the old firmware (the slot could not be read and the send went ahead blind); after a `restore` and a proper wait it worked. `--slot-swap` itself was not run on this unit ([details](../slot-swap.md)).
- **Slot:** the first `--dry-run` could not read the target slot (8 s timeout); a second one right after showed slot 0.
- The installer logs refused eFuse writes (`FW signatures: want 07, got 00`). The update still finished and the device confirmed it.

The profile sets `boot_min_version: "1.0.9"`: devices of this family run Shelly's loader 1.0.3, which would otherwise skip ESPHome's bootloader (`update? 0`).

## 2.2.0 layout

Shelly's stable `2.2.0` for this device has a **different flash layout**, the same one as the 2.2.0 betas of the other Gen3 devices ([Beta firmware with another flash layout](../bootloader-and-slots.md#beta-firmware-with-another-flash-layout)): the app slots are `0x300000` instead of `0x2c0000`, and the filesystems and the second slot move up with them. The profile `S2PMG3-v2` describes it; `S2PMG3` does not fit it and `build` refuses the mix.

| Firmware | `app_0` | `app_1` | `fs_0` / `fs_1` |
| --- | --- | --- | --- |
| 2.1.x (`S2PMG3`) | `0x20000` / `0x2c0000` | `0x3a0000` / `0x2c0000` | `0x2e0000` / `0x660000`, `0xc0000` each |
| 2.2.0 (`S2PMG3-v2`) | `0x20000` / `0x300000` | `0x400000` / `0x300000` | `0x320000` / `0x700000`, `0xe0000` each |

`otadata`, `nvs`, `scratch` (`0x7e0000`) and `shelly` (`0x7f0000`) stay where they are.

> [!NOTE]
> **Partly checked (2026-11-11, one unit, `S3SW-002P16EU`, thanks to [andrewagner86](https://github.com/andrewagner86)):**
>
> - The unit came with Shelly 1.4.99, which has yet another table (app slots of `0x280000`, a 1 MB filesystem, `scratch` at `0x720000` with 512 KB). Shelly's own update (`Shelly.Update`, stable channel) took it to 2.1.1 (table of the `S2PMG3` profile, from slot 1 to slot 0) and then to 2.2.0 (new table, slot 1), one run each, without UART.
> - A flash dump read over UART on 2.2.0 has the same partition entries as the table in the official 2.2.0 package. On the device all entries except `nvs` carry the `encrypted` flag (flash encryption is off, so it has no effect); the generated CSV leaves the flags out, as for the other profiles. The loader on the device was still 1.0.3 (`010003ff`).
> - `send S2PMG3-v2` with a plain package (no `--esphome-factory`, so `--force`), whose app was a custom ESP-IDF app and not ESPHome: the installer wrote to slot 0 (`The installer writes to slot 0`), kept Shelly's loader as expected for such a package (`update? 0`), the device confirmed the update and started the app from `app_0`.
>
> **Not checked:** ESPHome with this profile, a package built with `--esphome-factory` (the bootloader swap), `inspect --device`, a later ESPHome OTA, and `restore S2PMG3-v2`.

> [!CAUTION]
> **Do not send an `S2PMG3` package to a device on 2.2.0**, and no `S2PMG3-v2` package to one on 1.4.99 or 2.x before 2.2.0. `send` refuses the second case (`layout_since`, `--force` overrides); the first one is not checked by the tool and was not tried.

- Fetch the package: `python ota.py fetch S2PMG3 --insecure` (2.2.0 is the stable release; both profiles use the package called `S2PMG3`).
- Build against its table: copy `partitions/S2PMG3-v2-stock.csv`, use it as `esp32: partitions:` in the ESPHome config and keep `CONFIG_PARTITION_TABLE_OFFSET: "0x10000"`.
- Then `python ota.py build S2PMG3-v2 app.ota.bin --esphome-factory app.factory.bin`, and `send S2PMG3-v2`, as above.

## Way back

`python ota.py restore S2PMG3` sends the official firmware back while Shelly firmware still runs. For a device on the 2.2.0 layout use `python ota.py restore S2PMG3-v2` (not tested).

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **The config is yours.** The tool checks the package, not your ESPHome config: pins, relay and limits are your responsibility, and a wrong `ota:`, `api:` or Wi-Fi setting can leave the device unreachable (then only UART helps). Test the config on a dev board first.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
