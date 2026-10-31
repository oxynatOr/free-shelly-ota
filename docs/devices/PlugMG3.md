# Shelly Plug M Gen3

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: confirmed](https://img.shields.io/badge/state-confirmed-brightgreen.svg?style=flat-square)
![State of the beta layout: confirmed](https://img.shields.io/badge/state-confirmed-brightgreen.svg?style=flat-square)
![Generation: 3](https://img.shields.io/badge/gen-3-lightgrey.svg?style=flat-square)
![Chip: ESP32-C3](https://img.shields.io/badge/chip-ESP32--C3-blue.svg?style=flat-square)
![Package: 2.1.0](https://img.shields.io/badge/package-2.1.0-lightgrey.svg?style=flat-square)
![UART: not needed](https://img.shields.io/badge/UART-not%20needed-brightgreen.svg?style=flat-square)
![Variant: beta layout](https://img.shields.io/badge/variant-beta%20layout-orange.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [📍 Pins](#pins) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

The first device this tool was confirmed on. A second plug, reported by [815rx1](https://github.com/815rx1) (October 2026, thanks), went through the same chain with the 2.1.0 package.

> **Shelly's 2.2.0-beta2 has another layout** (app slots of `0x300000` instead of `0x2a0000`), found by [onkelfarmor](https://github.com/onkelfarmor) ([#102](https://github.com/oxynatOr/free-shelly-ota/issues/102), thanks). It has its own profile, `PlugMG3-beta`, confirmed on a plug in the wall ([#122](https://github.com/oxynatOr/free-shelly-ota/issues/122)); see [Beta layout](#beta-layout). `build` refuses to mix the two layouts.

| Fact | Value |
| --- | --- |
| Profile | `PlugMG3`, `PlugMG3-beta` (for Shelly's 2.2.0-beta2 layout, see [Beta layout](#beta-layout)) |
| Flash | 8 MB |
| Official package | 2.1.0 (stable since 2026-10-14; on 2026-10-27 the update API lists no stable release for this device and the 2.0.1 and 2.1.0 files answer 404 on Shelly's CDN, so keep your cached package; bootloader, partition table and filesystem are the same as in 2.0.1; flashed on a real plug with 2.1.0 and with 2.0.1) |
| Partition table | `0x10000` |
| App slot size | `0x2a0000` |

> [!NOTE]
> **Confirmed:** the whole chain ran on two real plugs: `send` from stock 1.8.99 (running from slot 1), then two ESPHome OTAs. The second plug used the official 2.1.0 package and ESPHome 2026.9.1; both OTAs (ESPHome CLI and the Home Assistant ESPHome builder) took effect.

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/PlugMG3-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0x10000"`.

```yaml
esp32:
  variant: ESP32C3
  board: esp32-c3-devkitm-1
  flash_size: 8MB
  partitions: PlugMG3-stock.csv        # copy from partitions/ in this repository
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

## Pins

Pins read from the stock firmware and tested on a real plug:

| Function | Pin |
| --- | --- |
| Relay | GPIO0 |
| Button | GPIO7 |
| BL0942 power meter (UART, 9600 8N1) | TX GPIO4, RX GPIO5 |
| BL0942 CF/ZX pin (multiplexed: CF by default, zero-cross after a register write the stock firmware does) | GPIO3 |
| RGB LED (common anode, **active low**: `inverted: true` on every output) | red GPIO18, green GPIO10, blue GPIO19 |
| NTC (beta 3950, 10 k at 25 C) | GPIO1 (ADC1_CH1), 37.3 °C in ESPHome against 36.9 °C in Shelly's firmware a few minutes earlier ([#122](https://github.com/oxynatOr/free-shelly-ota/issues/122)) |

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch PlugMG3 --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build PlugMG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send PlugMG3 out/PlugMG3-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** (the log goes to a file with `--log-file`):

   ```
   python ota.py send PlugMG3 out/PlugMG3-app-<date>.zip --ip <device IP> --log-file
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

`send` shows these lines at the default log level, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore PlugMG3` first. On stock 1.8.99 you get a warning instead ([why](#notes-for-this-device)) |
| 2 | `Device: The bootloader will be replaced ...` (raw log: `Boot: cur ... min ... update? 1`) | The installer will write ESPHome's bootloader. `WARNING: ESPHome's bootloader was NOT written` (`update? 0`) means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | The progress (`Update: ... %`, one line that updates in place) up to 100 %, then `Done: update installed, the device confirmed it` | The device restarts into ESPHome |

The reported run of the second plug, from stock 1.8.99 with the 2.1.0 package and `--esphome-factory` (the `Boot:` line is the one to look for):

```
  log| I a_esp32_backend.cpp:422 Will write to slot 0
  log| I a_esp32_backend.cpp:672 Boot: cur 010002ff, new 00000000, min 010009ff, update? 1
  log| I a_esp32_backend.cpp:182 Installing BL 20960@app_0(0x20000) -> boot(0)...
  log| I shos_ota.cpp:640        Update succeeded (OK), will reboot, uba=3, cd=0/ct=25 s
  log| W shelly_update.cpp:581   FW signatures: want 07 got 00
```

No `EFUSE write error` line appeared, only the `FW signatures` one ([eFuse note](../troubleshooting.md#efuse)).

## Notes for this device

- On stock 1.8.99 the slot check of `send` cannot run: the device logs `Storing core dumps to scratch (0x720000)` instead of `app_N`,
  so `send` warns that the firmware does not reveal the update target slot and goes on. The installer wrote to the slot the stock
  firmware was not running from (device on slot 1, `Will write to slot 0`); look for that line with `--watch`.
- On this model ESPHome came up after a power-off of about 30 seconds; whether it would also have started without it was not tested.
- The second plug showed what "not started" can look like: ESPHome, Wi-Fi, the API and the sensors (voltage, frequency, temperature, power under a 1.8 kW load) worked at once, but the relay and the LED did not react, although ESPHome reported the switch as on. After about 30 seconds without power both worked.
- That plug ran Shelly OS loader 1.0.2 (factory firmware 1.8.99, `Boot: cur 010002ff`). `boot_min_version: 1.0.9` was enough there: `update? 1`, and ESPHome's bootloader was written. A plug that came back from ESPHome through the official 2.0.1 package runs loader 1.0.3 ([why the profile uses 1.0.9](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)).
- Without `--esphome-factory` Shelly's loader stays: ESPHome runs for three starts, then the old firmware comes back unless an ESPHome OTA arrived in time, and only the first
  such OTA can take effect. `send` refuses such a package without `--force` ([details](../bootloader-and-slots.md#without-esphomes-bootloader-plain-package)).
- **BL0942 calibration (one unit, 2026-10-31, [#122](https://github.com/oxynatOr/free-shelly-ota/issues/122)):** with ESPHome's default references voltage and power read about 11 % low and the current was right. Measured against a second Plug M Gen3 on stock 1.8.99 in series (about 610 W resistive load, 25 samples over 2 minutes, spread below 0.1 %), the ESPHome plug read 0.8939 (voltage), 0.9951 (current) and 0.8892 (power) of Shelly's values. New reference = default × ratio, with the energy reference scaled like the power one:

  ```yaml
  sensor:
    - platform: bl0942
      voltage_reference: 14198.37
      current_reference: 249839.95
      power_reference: 553.98
      energy_reference: 4754.98
  ```

  With these both plugs agreed within 0.5 % (235.35 V against 235.40 V, 2.54 A against 2.53 A, 597.5 W against 594.6 W). They are a starting point: calibrate your own unit. Shelly's factory voltage scale is nearly the same on every Gen3 plug dump compared (within about 0.5 %), so the voltage divider looks like a hardware constant and the default `voltage_reference` is low for this hardware in general; the [PM Mini Gen3](MiniPMG3.md) page shows the same (about 10 % low).

## Beta layout

Shelly's `2.2.0-beta2` for this plug (found by [onkelfarmor](https://github.com/onkelfarmor), [#102](https://github.com/oxynatOr/free-shelly-ota/issues/102)) has a **different flash layout**: the app slots are `0x300000` instead of `0x2a0000`, and the filesystem and the second slot move up with them. The profile `PlugMG3-beta` describes it; `PlugMG3` does not fit it and `build` refuses the mix.

> [!NOTE]
> **Partly checked (2026-10-28, one plug):** Shelly's 2.2.0-beta2 was written over UART, then `restore` and `send PlugMG3-beta` with `--esphome-factory` (the installer wrote to slot 0 and replaced the loader 1.0.3), ESPHome started, and a second ESPHome OTA from the Home Assistant builder (ESPHome 2026.10.1) succeeded. ESPHome ran from `app_1` at `0x400000` and logged Shelly's beta table (`app_0` `0x20000` / `0x300000`, `app_1` `0x400000` / `0x300000`, `scratch` and `shelly` unchanged).
>
> **The way for a plug that runs Shelly's 2.0.x (2026-10-28, same plug, no UART):** stock 1.8.99, then `restore PlugMG3` (2.0.1), then `restore PlugMG3-beta` (the installer of 2.0.x writes the new table as `PT1` and the app to slot 1, the plug reported 2.2.0-beta2), then `send PlugMG3-beta` with the ESPHome package. ESPHome started with Shelly's beta table, joined the Wi-Fi and ran from `app_0` (`0x20000`) with the ESPHome bootloader.
>
> Relay and meter were not reported.
>
> **The way for a plug on stock 1.8.99: run `restore PlugMG3-beta` twice (2026-10-31, DevKit board).** Shelly's installer of 1.8.99 needs two runs, as reported in the Shelly forum for 2.2.0-beta1 ([thread 15141](https://community.shelly.cloud/topic/15141-update-m-plug-to-v-200-fails/), found by [onkelfarmor](https://github.com/onkelfarmor), [#102](https://github.com/oxynatOr/free-shelly-ota/issues/102)). Run 1: `Will write to slot 0`, `Slot switch is required`, `Skipping app`, `Skipping fs`; the plug reports success and comes back on 1.8.99, now on slot 0 instead of 1. Run 2: `Will write to slot 1`, `Installing new PT1`; the plug reports 2.2.0-beta2 on slot 1. Wait until the plug has been running for more than about 130 s before each run, otherwise it answers `Not committed`. Then `send PlugMG3-beta` with the ESPHome package went through (`The installer writes to slot 0`, loader `010002ff` replaced), and ESPHome's access point appeared. This was played on a DevKit board (ESP32-C3, 8 MB) flashed with a dump of a stock 1.8.99 plug, see [DevKit](../devkit.md#seen-on-a-board), and then confirmed on a plug in the wall (below). The 2026-10-28 attempt on 1.8.99 was therefore only the first of the two runs.
>
> ```
> python ota.py restore PlugMG3-beta --watch 120     # run 1: stays on 1.8.99, slot 0
> python ota.py restore PlugMG3-beta --watch 120     # run 2, after more than 130 s uptime: 2.2.0-beta2
> python ota.py send PlugMG3-beta <esphome package>
> ```
>
> **Confirmed on a plug in the wall (2026-10-31, [onkelfarmor](https://github.com/onkelfarmor), [#122](https://github.com/oxynatOr/free-shelly-ota/issues/122), thanks):** stock 1.8.99 on slot 1, no UART, the same three steps. Run 1 came back on 1.8.99 on slot 0 with the Wi-Fi settings kept; run 2 (at 144 s uptime) logged `Installing new PT1 (a00c9381)` and the plug reported 2.2.0-beta2 on slot 1; `send` wrote to slot 0 and replaced the loader (`010002ff`). ESPHome 2026.8.0 answered on the API about 5 s after the reboot and ran from `app_0` with Shelly's beta table. Working: relay, button (GPIO7), RGB LED, BL0942 (voltage, current, power, frequency) and the NTC. The relay did not switch until the plug had been without power for about 30 s (the LED already worked before that), as on the other plug. A regular ESPHome OTA afterwards (`esphome upload`, ESPHome 2026.8.0) took effect, and ESPHome then ran from `app_1` (`0x400000`): ESPHome's bootloader switches slots with the beta table, and the plug also starts on its own after power cuts. The BL0942 calibration is in [Notes for this device](#notes-for-this-device).

> [!CAUTION]
> **Do not send this package to a plug that still has the old layout** (Shelly 1.8.99, 2.0.1, 2.1.0). Take the step to Shelly's own beta package first (below), and send this package only to a plug that already runs the beta layout. Tried on 2026-10-28 with stock 1.8.99, in one run: the installer replaced the bootloader with ESPHome's, but wrote neither the new partition table nor the app (`Skipping app`, `Skipping fs` in its log). The plug then started the old stock app from `app_0` by luck, because ESPHome's bootloader with an unset `otadata` tries all slots; with an empty `app_0` it would not have started and only UART brings it back. `send` refuses this package on a plug whose firmware is older than 2.2.0 (`--force` overrides, with UART at hand).

Shelly can pull the beta at any time (the 2.0.1 and 2.1.0 files are gone from the CDN since 2026-10-27): keep your copy in `fw/`.

- Fetch the beta: `python ota.py fetch PlugMG3-beta --insecure` (the profile asks for the beta channel).
- Build against its table: `python ota.py partition-csv PlugMG3-beta -o PlugMG3-beta-stock.csv`, use it as `esp32: partitions:` in the ESPHome config and keep `CONFIG_PARTITION_TABLE_OFFSET: "0x10000"`.
- Then `python ota.py build PlugMG3-beta app.ota.bin --esphome-factory factory.bin`, as above.

## Way back

`python ota.py restore PlugMG3` sends the official firmware back while Shelly firmware still runs.

Done once on a real plug: Shelly OS 2.0.1 with
loader 1.0.3 came back. Pushing the official app image through ESPHome OTA instead does not work (same page).

A Plug M restored this way has loader 1.0.3, which is why the profile sets `boot_min_version: 1.0.9`: a later `send` with
`--esphome-factory` still replaces the bootloader. Because Shelly then runs from slot 0, run `python ota.py restore PlugMG3`
first, otherwise `send` refuses (the installer would write to slot 1).

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
