# Shelly Mini 1 Gen3

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: confirmed](https://img.shields.io/badge/state-confirmed-brightgreen.svg?style=flat-square)
![Chip: ESP32-C3](https://img.shields.io/badge/chip-ESP32--C3-blue.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

It is the [Mini 1PM Gen3](Mini1PMG3.md) without the power meter (relay, switch input, button, LED and an NTC).
Like the H&T Gen3 and the Mini 1PM Gen3, the official package keeps its partition table at `0xf000`, so a default ESPHome build does not match.

| Fact | Value |
| --- | --- |
| Profile | `Mini1G3` |
| Flash | 8 MB |
| Official package | 2.0.1 |
| Partition table | `0xf000` |
| App slot size | `0x2a0000` |
| ESPHome device page | [Shelly 1 Mini Gen3](https://devices.esphome.io/devices/shelly-1-mini-gen3/) |

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/Mini1G3-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0xf000"`.

```yaml
esp32:
  variant: ESP32C3
  board: esp32-c3-devkitm-1
  flash_size: 8MB
  partitions: Mini1G3-stock.csv        # copy from partitions/ in this repository
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
> The [ESPHome device page](https://devices.esphome.io/devices/shelly-1-mini-gen3/) has the pins. Use the `esp32:` block above, or `build` refuses your config.

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch Mini1G3 --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build Mini1G3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send Mini1G3 out/Mini1G3-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** and watch the log:

   ```
   python ota.py send Mini1G3 out/Mini1G3-app-<date>.zip --ip <device IP> --watch 120
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

In the `--watch` log look for these lines, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore Mini1G3` first |
| 2 | `Boot: cur ... min ... update? 1` | The installer will write ESPHome's bootloader. `update? 0` means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | `ota_progress` up to 95 %, then `ota_success` | The device restarts into ESPHome |

## Notes for this device

- **Result:** first report ([#69](https://github.com/oxynatOr/free-shelly-ota/issues/69)): from Shelly firmware 1.4.4 with the package built from this profile (revision 1, package 2.0.1, `--esphome-factory`). `send --dry-run` reported `Update target slot: 0`, the device reached the PC, the flash ran to 99 % and ESPHome came up on Wi-Fi without a power cycle. A later ESPHome OTA from the dashboard took effect, so ESPHome's bootloader is in place. The `Boot: cur ... update?` line of that run was not captured.
- **Second report** (same reporter, a device installed in the wall, stock 2.0.1): the dry run said `Update target slot: 1`, so `send` refused, as intended. `restore Mini1G3` (2.0.1 to 2.0.1) wrote to slot 1 (`Will write to slot 1`, `Committing update (slot 1)`) and **kept Wi-Fi and settings**; the loader line of the restore was `Boot: cur 010002ff, new 010003ff, min 010002ff, update? 0` (loader 1.0.2 on stock 2.0.1). After that the dry run showed slot 0 and the ESPHome package went in with `Boot: cur 010002ff, new 00000000, min 010009ff, update? 1`, so ESPHome's bootloader was written. Switch, relay and the API-loss fallback work.
- **Weak Wi-Fi:** the first `restore` stopped with `The device did not download the ZIP within 300s`: at -68 dBm the download ran at about 1 % per 5 s and was at 28 % when the tool stopped serving. The device kept the old firmware and nothing broke; `--timeout 1200` worked ([Troubleshooting](../troubleshooting.md#the-device-does-not-download-the-zip)).
- The profile sets `boot_min_version: 1.0.9` like the other Gen3 devices that needed it: the official package carries loader 1.0.2 and a device that came back from ESPHome runs 1.0.3, and the installer only writes a bootloader that is newer than the installed one.
- **Pins checked on the hardware** (lamp as load): relay GPIO7, button GPIO1 (inverted, pull-up), switch input GPIO10, LED GPIO0 (inverted). Without a load the relay is almost silent, so a quiet click is not a sign that it does not switch.
- **NTC (GPIO3), read from the official 2.0.1 app:** the stock firmware (`shelly_temp_sensor_ntc.cpp`) reads GPIO3 with 12 dB attenuation and converts it with a **B constant of 3950**, 10 kOhm at 25 °C, a 10 kOhm reference resistor and 3.3 V; the NTC is the lower leg of the divider, which is `DOWNSTREAM` in ESPHome's `resistance` sensor. The sensor range is -55 to 125 °C. So the topology of the ESPHome device page (`DOWNSTREAM`, 10 kOhm) is right, but its **B 3350 is not the stock value**: use `b_constant: 3950`. With the first report's reading of about 57 °C (an idle desk unit; two Mini 1 Gen3 on stock firmware showed 36 to 46 °C) that is about 52 °C, so 3950 explains part of the difference, not all of it. The absolute value stays uncalibrated until it is compared with a reference thermometer.
- **NTC, stock against ESPHome on the same device** (second report, in the wall): stock 2.0.1 showed 36.7 to 37.9 °C minutes before the flash, ESPHome with B = 3350 51.6 to 52.7 °C at the same place. B = 3950 brings the ESPHome reading to about 48 °C, so the constant explains about 4.5 of the roughly 15 °C. The reporter's guess for the rest is the Wi-Fi power save: the stock firmware had `eco_mode: true`, the ESPHome config `power_save_mode: none`, which may warm the chip itself. Not tested yet; a comparison with a room thermometer and `power_save_mode: light` is planned.

## Way back

`python ota.py restore Mini1G3` sends the official firmware back while Shelly firmware still runs.

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
