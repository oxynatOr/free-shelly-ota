# Shelly Plus Uni (Gen2)

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: partly checked](https://img.shields.io/badge/state-partly%20checked-yellow.svg?style=flat-square)
![Chip: ESP32](https://img.shields.io/badge/chip-ESP32-blue.svg?style=flat-square)

[🧰 Before you start](#before-you-start) · [⚙️ Config](#esphome-config) · [📍 Pins](#pins) · [⚡ Flash it](#flash-it) · [👀 What to expect](#what-to-expect) · [↩️ Way back](#way-back)

A classic ESP32 like the [Plus Plug S](PlusPlugS.md): partition table at the ESP-IDF default `0x8000`, bootloader at `0x1000`, and the ESPHome build needs the 80 MHz flash frequency. Thanks to [yasdfgr](https://github.com/yasdfgr) for the device report (October 2026, [#46](https://github.com/oxynatOr/free-shelly-ota/issues/46)).

| Fact | Value |
| --- | --- |
| Profile | `PlusUni` |
| Model | SNSN-0043X (device id `shellyplusuni-...`) |
| SoC | ESP32-U4WDH (Shelly's knowledge base) |
| Flash | 4 MB (bootloader header and partition table; the knowledge base says 4 MB too) |
| Official package | 2.0.1 |
| Partition table | **`0x8000`** (ESP-IDF default) |
| Bootloader address | `0x1000` |
| App slot size | `0x190000` |
| Bootloader `min_version` | `1.0.9` (set in the profile) |
| Power supply | 8-24 VAC, 9-28 VDC (terminals `VAC1`, `VAC2`) or 5 VDC (terminals `+5 VDC`, `GND`); low voltage, no mains |
| Shelly documentation | [Shelly Plus Uni](https://kb.shelly.cloud/knowledge-base/shelly-plus-uni) (Knowledge Base) |

> [!NOTE]
> **Partly checked:** flashed over OTA on a real Plus Uni (stock 2.0.1, `send` with `--esphome-factory`, October 2026). The tester reports that ESPHome runs and that one later ESPHome OTA took effect; further ones did not (the unit keeps starting the old image). His package had `min_version` 1.0.3 instead of this profile's 1.0.9, so the installer skipped ESPHome's bootloader (`update? 0`, see the notes): that step is not checked on this model. One UART flash of ESPHome's factory image fixed it (a Raspberry Pi as adapter); since then OTAs work and an ESPHome "Update bootloader" over OTA worked too. The inputs and outputs are mapped (see [Pins](#pins)), the 1-Wire pin is not.

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point (default `192.168.33.1`)
- [ ] the device can reach this PC: same network, port 8000 (`--port`) not blocked
- [ ] your ESPHome config uses the partition table below and is compiled

Also:

- [ ] A UART adapter is at hand as your way back ([Recovery over UART](../recovery-uart.md); the UART header is under [Pins](#pins)).

## ESPHome config

> [!IMPORTANT]
> `build` refuses a config without Shelly's partition table. Copy `partitions/PlusUni-stock.csv` from this repository next to your
> YAML and keep `CONFIG_PARTITION_TABLE_OFFSET: "0x8000"`.

```yaml
esp32:
  variant: ESP32
  board: esp32dev
  flash_size: 4MB
  partitions: PlusUni-stock.csv        # copy from partitions/ in this repository
  framework:
    type: esp-idf
    sdkconfig_options:
      COMPILER_OPTIMIZATION_SIZE: y
      CONFIG_PARTITION_TABLE_OFFSET: "0x8000"
      CONFIG_ESPTOOLPY_FLASHFREQ_80M: "y"   # without it `build` refuses: the bootloader header says 80 MHz
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
    allow_partition_access: true         # keep it in the FIRST config: it lets ESPHome Builder's "Update bootloader" fix a bootloader problem over OTA
```

## Pins

**UART header.** [Shelly's knowledge base](https://kb.shelly.cloud/knowledge-base/shelly-plus-uni) shows a 7-pin header at the edge of the board, in the picture under "Addon interface" (Shelly calls it a proprietary serial interface). From the end marked 1:

| Pin | Signal | For flashing over UART |
| --- | --- | --- |
| 1 | `ESP_DBG_UART` | not used (purpose unknown) |
| 2 | `U0TXD` | the Shelly's TX: to the adapter's RX |
| 3 | `U0RXD` | the Shelly's RX: to the adapter's TX |
| 4 | `+3.3_ESP` | 3.3 V of the ESP |
| 5 | `RESET` | to GND for a reset |
| 6 | `GPIO0` | to GND while resetting: download mode |
| 7 | `GND` | ground |

> [!WARNING]
> The order is read from Shelly's drawing, not from a board. Check with a multimeter that pin 7 is connected to the `GND` terminal before you apply 3.3 V. The board has a coating film (the pads may need cleaning), and every other supply (8-24 VAC, 9-28 VDC, 5 VDC) must be disconnected while the adapter is connected. Steps: [Recovery over UART](../recovery-uart.md).

**Inputs and outputs.** Measured and tested by [yasdfgr](https://github.com/yasdfgr) on his unit ([#46](https://github.com/oxynatOr/free-shelly-ota/issues/46)); not checked on a second board. The ESPHome device database has no page for the Plus Uni (checked 2026-10-12); its page for the original
Shelly Uni is Gen1 hardware (ESP8266) and does not apply.

| GPIO | Shelly name | Wire | Function |
| --- | --- | --- | --- |
| – | `VAC1`, `VAC2` | red, black | 8-24 VAC / 9-28 VDC supply |
| 36 | `ANALOG IN` | white | analog input 0..30 VDC; scaling measured: 10.0 V reads 0.8 V at the pin |
| – | `SENSOR VCC` | yellow | supply for 1-Wire sensors |
| 13 ⚠️ | `DATA` | blue | 1-Wire data line (1 x DHT22 or 5 x DS18B20); read from the firmware, not measured |
| – | `+5 VDC`, `GND` | gray, green | 5 VDC supply; `GND` is also the sensor ground |
| 39 | `COUNT IN` | purple | pulse counter input, active low (< 1.5 V, 50 kΩ) |
| 38 | `IN1` | orange | digital input 1, active low (< 1.5 V, 50 kΩ) |
| 37 | `IN2` | brown | digital input 2, active low (< 1.5 V, 50 kΩ) |
| 19 | `OUT1` | black | solid-state relay 1 (potential-free) |
| 21 | `OUT2` | black | solid-state relay 2 (potential-free) |
| 18 | red LED on the board | | inverted |
| 32 ⚠️ | reset button on the board | | read from the firmware, not measured |

The Plus Uni 2.0.1 firmware agrees with the measured GPIOs (36, 37, 38, 39, 19, 21, 18): its init code creates the inputs, the counter, the two outputs and the LED on exactly these pins. The two ⚠️ rows come from the same code and nobody has tried them on a board: `DATA` is the pin the firmware hands to its DHT22 and 1-Wire drivers, and GPIO 32 is the one input the firmware creates under the system id 999 (the LED has that id too), which fits a reset button. Please confirm them (for example `dallas` / `dht` on GPIO13, a `binary_sensor` on GPIO32 with a button press).

GPIO 36 to 39 are input-only pins of the ESP32 and have no pull-up of their own; the board pulls the inputs up (active low).

## Flash it

1. **Install the requirements** (once):

   ```
   pip install -r requirements.txt
   ```

2. **Fetch** the official package:

   ```
   python ota.py fetch PlusUni --insecure
   ```

3. **Build:** put your app into it; the ZIP goes to `out/`:

   ```
   python ota.py build PlusUni app.ota.bin --esphome-factory app.factory.bin --esphome-yaml app.yaml
   ```

4. **Check the device** first. Nothing is sent:

   ```
   python ota.py send PlusUni out/PlusUni-app-<date>.zip --ip <device IP> --dry-run
   ```

5. **Flash it** (the log goes to a file with `--log-file`):

   ```
   python ota.py send PlusUni out/PlusUni-app-<date>.zip --ip <device IP> --log-file
   ```

`app.ota.bin` and `app.factory.bin` are the two files ESPHome compiles. `--dry-run` only checks the device and, for this
package, reads the update target slot. Command reference: [Commands](../commands.md).

## What to expect

`send` shows these lines at the default log level, in this order:

| # | Log line | Meaning |
| --- | --- | --- |
| 1 | `Update target slot: 0 ...` | The slot check of `send`. Anything else: run `python ota.py restore PlusUni` first |
| 2 | `Device: The bootloader will be replaced ...` (raw log: `Boot: cur ... min ... update? 1`) | The installer will write ESPHome's bootloader. `WARNING: ESPHome's bootloader was NOT written` (`update? 0`) means it will not: build again with a higher `--boot-min-version` ([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)) |
| 3 | The progress (`Update: ... %`, one line that updates in place) up to 100 %, then `Done: update installed, the device confirmed it` | The device restarts into ESPHome |

The reported run, from stock 2.0.1 (the first line comes from `send`, the rest from the device):

```
Update target slot: 0 (the slot ESPHome's bootloader starts).
  log| shelly_update.cpp:511   Incoming fw signatures: 00
  log| 2xx_ota_backend.cpp:409 Will write to slot 0
  log| 2xx_ota_backend.cpp:689 Boot: cur 010003ff, new 00000000, min 010003ff, update? 0
  log| shelly_update.cpp:604   FW signatures: want 07 got 00
  log| efuse                   BURN BLOCK3
  log| efuse                   BURN BLOCK3 - OK (all write block bits are set)
  log| efuse                   BURN BLOCK3
  log| efuse                   BURN BLOCK3 - OK (all write block bits are set)
  log| shos_system.c:66        Rebooting in 1000 ms
```

## Notes for this device

**Bootloader `min_version`.** The official package carries Shelly OS loader 1.0.2, but the unit in the report ran **1.0.3** on stock 2.0.1
(`Boot: cur 010003ff`), the first loader seen on a Plus Uni. The profile sets `boot_min_version: 1.0.9`, so the installer writes
ESPHome's bootloader on such a unit. The tester's package had `min 010003ff` (the default, one patch above the official 1.0.2;
this profile was probably not used), which is not higher than the installed loader, hence `update? 0`
([why](../bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)). Shelly's loader stayed; ESPHome started anyway, and one later ESPHome OTA took effect. After that, further OTAs were written but
never started: the unit kept running the old image (the tester's follow-up; no UART, so the loader's state could not be read). That is how the
loader works: it switches slots once, during its countdown, and then stays on the slot it committed
([why](../bootloader-and-slots.md#without-esphomes-bootloader-plain-package)). A run with this profile (`update? 1`) is still open.

**Fixing it over UART, and the bootloader over OTA.** The tester wired a Raspberry Pi to the UART header, flashed ESPHome's factory image once, and the unit then took OTAs normally. He also ran ESPHome Builder's **Update bootloader** over OTA afterwards, which worked. That needs `allow_partition_access: true` in the config that is running, so keep it in the first config you send: then a bootloader problem can be fixed over OTA, without UART ([steps](../bootloader-and-slots.md)). The tester did not report whether the header order of the table under Pins matched his board.

**eFuse.** After `FW signatures: want 07 got 00` the log shows `BURN BLOCK3 - OK` twice, not the `EFUSE write error` of the H&T and PM Mini.
Whether the eFuse changed on this unit was not checked ([eFuse note](../troubleshooting.md#efuse)).

**The slot.** The Plus Plug S, the other Gen2 device, first received the app in slot 1 and needed `restore` once; `send` checks
the target slot for you ([why](../bootloader-and-slots.md#the-app-must-land-in-slot-0)). Here the target was slot 0 from the start.

**ESPHome warnings.** The ESPHome log of a Plus Uni shows `Chip rev >= 3.0 detected. Set minimum_chip_revision: "3.1" ...` and
`Bootloader supports SRAM1 as IRAM ... Set sram1_as_iram: true ...`. Leave both out of the config you build the package from:
`build` refuses a bootloader whose header differs from Shelly's ([why](../troubleshooting.md#build-refuses-to-replace-the-bootloader)).
Once ESPHome runs they can be added with an ESPHome OTA, which replaces only the app. Read the chip revision of the unit from its boot
log first: an app built for a higher minimum revision than the chip has does not start.

Still open: a check of the two ⚠️ pins (1-Wire `DATA`, reset button) on a board, and a run with this profile. Please report the file written by `--log-file`, especially the lines `Update target slot`, `Boot: cur ... update?` and `Will write to slot`.

## Way back

`python ota.py restore PlusUni` sends the official firmware back while Shelly firmware still runs.

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
