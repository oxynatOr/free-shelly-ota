# Plus RGBW PM (Gen2)

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: confirmed](https://img.shields.io/badge/state-confirmed-brightgreen.svg?style=flat-square)
![Generation: 2](https://img.shields.io/badge/gen-2-lightgrey.svg?style=flat-square)
![Chip: ESP32](https://img.shields.io/badge/chip-ESP32-blue.svg?style=flat-square)
![Pins: not confirmed](https://img.shields.io/badge/pins-not%20confirmed-yellow.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [📍 Pins](#pins) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

Gen2 / classic ESP32: lED controller with four PWM outputs and power metering. Partition table at the ESP-IDF default `0x8000`, bootloader at `0x1000`, 80 MHz flash frequency, like the [Plus Plug S](PlusPlugS.md).

| Fact | Value |
| --- | --- |
| Profile | `PlusRGBWPM` |
| Flash | 4 MB (bootloader header and partition table) |
| Official package | 2.0.3 |
| Partition table | **`0x8000`** (ESP-IDF default) |
| Bootloader address | `0x1000` |
| App slot size | `0x190000` |

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md))

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/PlusRGBWPM-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0x8000"`.

```yaml
esp32:
  variant: ESP32
  board: esp32dev
  flash_size: 4MB
  partitions: PlusRGBWPM-stock.csv    # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_PARTITION_TABLE_OFFSET: "0x8000"
      CONFIG_ESPTOOLPY_FLASHFREQ_80M: "y"   # without it `build` refuses: the bootloader header says 80 MHz
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
    allow_partition_access: true
```

The reporter's running config (ESPHome 2026.10.2) also has three things that are not needed to flash: `cpu_frequency: 160MHz` with `CONFIG_FREERTOS_UNICORE: "y"` (single core, chosen on purpose to stay safe on U4WDH units; their chip is a dual-core ESP32 rev3.1) and an `on_boot` block that releases the pad hold, copied from the Gen4 (see [Pins](#pins)). None of them is proven necessary on this device.

## Pins

| Function | Pin |
| --- | --- |
| PWM 1 to 4 (LEDC, 19531 Hz) | GPIO25, GPIO27, GPIO26, GPIO4 |
| Inputs 1 to 4 (inverted) | GPIO36, GPIO37, GPIO38, GPIO39 |
| Button | GPIO22 |
| Status LED | GPIO14 |
| NTC (10 k, B 3350) | GPIO33 |
| Voltage (multiply 10.85) | GPIO34 |
| Current (offset -0.794, multiply 16.13) | GPIO35 |

Source: the [ESPHome device page](https://devices.esphome.io/), taken over by the reporter of [#133](https://github.com/oxynatOr/free-shelly-ota/issues/133), not measured by anyone here. What the reporter checked on a unit in a 12 V motorhome system:

| Checked | Result |
| --- | --- |
| PWM 1 to 3 | switch and dim from Home Assistant (awning front, awning rear, kitchen); the 4th output is not connected |
| Voltage | about 13.5 V on a 12 V system, plausible |
| NTC | 27.8 °C, plausible |
| Current | 0.35 to 0.40 A with all outputs off: the offset above does not fit this unit, it is not calibrated |
| Inputs 1 to 4, button, status LED | not checked (the unit sits behind a panel) |

Everything not in the "checked" table stays "not confirmed".

**Pad hold.** The reporter's config releases the hold of the output pins at boot, as a precaution taken over from the Gen4, where Shelly OS leaves the pad hold enabled and the update only soft-resets the chip. It is not proven necessary on this device:

```yaml
esphome:
  on_boot:
    priority: 1000
    then:
      - lambda: |-
          gpio_hold_dis(GPIO_NUM_25);
          gpio_hold_dis(GPIO_NUM_26);
          gpio_hold_dis(GPIO_NUM_27);
          gpio_hold_dis(GPIO_NUM_4);
          gpio_hold_dis(GPIO_NUM_14);
```

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch PlusRGBWPM --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build PlusRGBWPM app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send PlusRGBWPM out/PlusRGBWPM-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** (the log goes to a file with `--log-file`):

   ```
   python ota.py send PlusRGBWPM out/PlusRGBWPM-app-<date>.zip --ip <device IP> --log-file
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

`send` shows these lines at the default log level, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore PlusRGBWPM` first |
| 2 | `Device: The bootloader will be replaced ...` (raw log: `Boot: cur ... min ... update? 1`) | The installer will write ESPHome's bootloader. `WARNING: ESPHome's bootloader was NOT written` (`update? 0`) means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | The progress (`Update: ... %`, one line that updates in place) up to 100 %, then `Done: update installed, the device confirmed it` | The device restarts into ESPHome |

## Notes for this device

- **Result:** first report ([#133](https://github.com/oxynatOr/free-shelly-ota/issues/133), thanks to [CzarofAK](https://github.com/CzarofAK)), from stock **2.0.3** with the package built from this profile (`--esphome-factory`). The device downloaded the ZIP and flashed it, ESPHome runs, and a later ESPHome OTA took effect, so ESPHome's bootloader is in place. Before that, the OTA had run through on a dev board with the DevKit image (2026-10-30, row in [Seen on a board](../devkit.md#seen-on-a-board)).
- **No device log:** as on the dev board, the slot check got no UDP datagram from the device (`the update target slot could not be read`), so the package was sent with `--ignore-slot`. Right after the probe, `send` failed to listen on port 9514 (`Address already in use`), so there is no `Boot: cur ... update?` line and no progress in this log. Nothing else used the port: the probe's own socket was still bound while its reader thread waited in `recvfrom()`. The fix (wait for the reader, then close the socket) is in the next release; `--log-port 9515` avoids it. The result shows the app landed in slot 0 (ESPHome's bootloader started it), but the loader the device had is still unknown.
- **Reported:** three PWM outputs work, voltage and NTC are plausible, the current offset does not fit ([Pins](#pins)). **Not reported:** the wall inputs, the button, the status LED.

**Bootloader `min_version`.** The official package carries Shelly OS loader 1.0.2. The profile sets `boot_min_version: 1.0.9`, the
default of the newer profiles, because a unit that Shelly has already updated can report 1.0.3 and would then skip a package with
1.0.3. The loader of a real Plus RGBW PM has not been seen yet.

**The slot.** The Plus Plug S, a device of the same generation, first received the app in slot 1 and needed `restore` once; `send` checks
the target slot for you ([why](../bootloader-and-slots.md#the-app-must-land-in-slot-0)).

Please report the file written by `--log-file`, especially the lines `Update target slot`, `Boot: cur ... update?` and `Will write to slot`.

## Way back

`python ota.py restore PlusRGBWPM` sends the official firmware back while Shelly firmware still runs.

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
