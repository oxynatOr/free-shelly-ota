# Shelly Multicolor Bulb E27 Gen3

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: confirmed](https://img.shields.io/badge/state-confirmed-brightgreen.svg?style=flat-square)
![Chip: ESP32-C3](https://img.shields.io/badge/chip-ESP32--C3-blue.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

The LEDs sit behind a **KP18068** 5-channel driver on SDA GPIO4 / SCL GPIO5. ESPHome has no official driver for it, so the example config uses the external component [oxynatOr/esphome-kp18058](https://github.com/oxynatOr/esphome-kp18058).

| Fact | Value |
| --- | --- |
| Profile | `RGBCCTBulbG3` |
| Flash | 8 MB |
| Official package | 2.0.1 |
| Partition table | `0x10000` |
| App slot size | `0x280000` |

> [!NOTE]
> **Confirmed:** the whole chain ran on a real device: `send` with `--esphome-factory` ran through, ESPHome runs and the light was tested on the bulb (owner, 2026-10-11): channel order and the single warm white LED confirmed. Colour accuracy, the lowest dimming steps and the driver currents are not measured. The colour temperature light of the example config (`rgbw_ct_table`, stock table) was flashed afterwards and runs (owner, 2026-10-16); its colours were not compared with the stock firmware.

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/RGBCCTBulbG3-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0x10000"`.

```yaml
esp32:
  variant: ESP32C3
  board: esp32-c3-devkitm-1
  flash_size: 8MB
  partitions: RGBCCTBulbG3-stock.csv        # copy from partitions/ in this repository
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

The full example config (RGB + colour temperature light with the stock firmware's table and white balance, current codes as the Shelly firmware sends them)
and the optional light packages (daylight, scenes, wake-up alarm, night light, over-temperature protection, dim range) are kept in
[`oxynatOr/esphome-configs`](https://github.com/oxynatOr/esphome-configs), not in this repository. The config pulls the driver component
[`esphome-kp18058`](https://github.com/oxynatOr/esphome-kp18058) through `external_components`.

Channel order, read from the stock firmware and tested on the bulb (owner, 2026-10-11): OUT1 = blue, OUT2 = red, OUT3 = green,
OUT4 = the one warm white LED; OUT5 shows nothing on its own. OUT4 and OUT5 get the same value (one white
level). The stock firmware makes colour temperatures from 2700 to 6500 K by mixing red, green and blue into that white (a 9-point table); the
example config does the same with the light platform `rgbw_ct_table` (see its README).

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch RGBCCTBulbG3 --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build RGBCCTBulbG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml shelly-rgbcct-bulb-g3.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send RGBCCTBulbG3 out/RGBCCTBulbG3-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** (the log goes to a file with `--log-file`):

   ```
   python ota.py send RGBCCTBulbG3 out/RGBCCTBulbG3-app-<date>.zip --ip <device IP> --log-file
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

`send` shows these lines at the default log level, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore RGBCCTBulbG3` first |
| 2 | `Device: The bootloader will be replaced ...` (raw log: `Boot: cur ... min ... update? 1`) | The installer will write ESPHome's bootloader. `WARNING: ESPHome's bootloader was NOT written` (`update? 0`) means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | The progress (`Update: ... %`, one line that updates in place) up to 100 %, then `Done: update installed, the device confirmed it` | The device restarts into ESPHome |

## Notes for this device

- **Installed loader:** on the first install the bulb ran `Shelly OS loader 1.0.2` (visible on UART), and the default `min_version` 1.0.3 was enough.
  After a return to stock the bulb runs loader 1.0.3, so the profile sets `boot_min_version: 1.0.9`; with it the ESPHome bootloader was written
  (hardware-confirmed 2026-10-11).
- **Dark bulb?** The driver component bit-bangs the two pins and expects an ACK for every byte. Try `ignore_ack: true` first;
  the other suspects are the address byte `0xE1` (Shelly's I2C hardware sends `0xE0`) and the internal pull-ups at a faster clock
  than Shelly's 100 kHz. Details: [Notes & troubleshooting](https://github.com/oxynatOr/esphome-kp18058#notes--troubleshooting) of the driver component.

## Way back

`python ota.py restore RGBCCTBulbG3` sends the official firmware back while Shelly firmware still runs.

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
