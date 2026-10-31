# Device pages

[← README](../../README.md) · [Documentation](../README.md) · [Commands](../commands.md) · [Device profiles](../../devices/README.md)

One page per device: the ESPHome config with the partition table that device needs, the pins where they are known, the exact
commands, the log lines to look for and the way back to Shelly OS. Pick your device below, then read
[Commands](../commands.md) for what the options do. The README of the project lists only the devices confirmed on real hardware
(✅ and 🟡); this page lists every profile.

✅ = the whole chain ran on a real device, 🟡 = flashed on a real device, but part of the chain or of the function is not
checked yet, 🔬 = the OTA ran through on a dev board with the [DevKit image](../devkit.md), but not on the real device, 🧪 = the package builds and verifies, but nobody has flashed it yet.

## Devices

Jump to: [Gen2](#gen2-esp32) · [Gen3](#gen3-esp32-c3) · [Gen4](#gen4-esp32-c6) · [Gen1](#gen1-esp8266-in-testing). Within a group the confirmed devices come first.

### Gen2 (ESP32)

18 profiles: ✅ 2 · 🟡 2 · 🔬 5 · 🧪 9

| Device | Profile | Partition table | App slot size | State | Note |
| --- | --- | --- | --- | --- | --- |
| [Plus Plug S (V2 hardware, Gen2)](PlusPlugS.md) | `PlusPlugS` | **`0x8000`** | `0x190000` | ✅ | Flashed without UART |
| [Plus Plug IT (Gen2)](PlusPlugIT.md) | `PlusPlugIT` | **`0x8000`** | `0x190000` | ✅ | Flashed without UART |
| [Plus i4 / i4 DC (Gen2)](PlusI4.md) | `PlusI4` | **`0x8000`** | `0x190000` | 🟡 | Flashed over OTA; the inputs and the LED not checked |
| [Plus Uni (Gen2)](PlusUni.md) | `PlusUni` | **`0x8000`** | `0x190000` | 🟡 | Flashed over OTA, ESPHome's bootloader step not checked |
| [Plus 1 (Gen2)](Plus1.md) | `Plus1` | **`0x8000`** | `0x190000` | 🔬 |  |
| [Plus 1PM (Gen2)](Plus1PM.md) | `Plus1PM` | **`0x8000`** | `0x190000` | 🔬 |  |
| [Plus Plug US (Gen2)](PlugUS.md) | `PlugUS` | **`0x8000`** | `0x190000` | 🔬 |  |
| [Plus Plug UK (Gen2)](PlusPlugUK.md) | `PlusPlugUK` | **`0x8000`** | `0x190000` | 🔬 |  |
| [Plus RGBW PM (Gen2)](PlusRGBWPM.md) | `PlusRGBWPM` | **`0x8000`** | `0x190000` | 🔬 |  |
| [Pro 3EM (Gen2)](Pro3EM.md) | `Pro3EM` | **`0x8000`** | `0x200000` | 🧪 |  |
| [Plus 2PM (Gen2)](Plus2PM.md) | `Plus2PM` | **`0x8000`** | `0x190000` | 🧪 | Not run on the dev board: the stock app restarts in a loop without factory data |
| [Pro 1 (Gen2)](Pro1.md) | `Pro1` | **`0x8000`** | `0x200000` | 🧪 |  |
| [Pro 1PM (Gen2)](Pro1PM.md) | `Pro1PM` | **`0x8000`** | `0x200000` | 🧪 |  |
| [Pro 2 (Gen2)](Pro2.md) | `Pro2` | **`0x8000`** | `0x200000` | 🧪 |  |
| [Pro 2PM (Gen2)](Pro2PM.md) | `Pro2PM` | **`0x8000`** | `0x200000` | 🧪 |  |
| [Pro 3 (Gen2)](Pro3.md) | `Pro3` | **`0x8000`** | `0x200000` | 🧪 |  |
| [Pro 4PM (Gen2)](Pro4PM.md) | `Pro4PM` | **`0x8000`** | `0x200000` | 🧪 |  |
| [Pro RGBWW PM (Gen2)](ProRGBWWPM.md) | `ProRGBWWPM` | **`0x8000`** | `0x200000` | 🧪 |  |

### Gen3 (ESP32-C3)

25 profiles: ✅ 8 · 🟡 5 · 🔬 0 · 🧪 12

| Device | Profile | Partition table | App slot size | State | Note |
| --- | --- | --- | --- | --- | --- |
| [Plug M Gen3](PlugMG3.md) | `PlugMG3` | `0x10000` | `0x2a0000` | ✅ |  |
| [Plug S Gen3](PlugSG3.md) | `PlugSG3` | `0x10000` | `0x2a0000` | ✅ |  |
| [H&T Gen3](HTG3.md) | `HTG3` | **`0xf000`** | `0x280000` | ✅ |  |
| [PM Mini Gen3 (no relay)](MiniPMG3.md) | `MiniPMG3` | **`0xf000`** | `0x280000` | ✅ | Measures only, no relay |
| [Multicolor Bulb E27 Gen3](RGBCCTBulbG3.md) | `RGBCCTBulbG3` | `0x10000` | `0x280000` | ✅ |  |
| [Mini 1 Gen3](Mini1G3.md) | `Mini1G3` | **`0xf000`** | `0x2a0000` | ✅ |  |
| [1 Gen3](S1G3.md) | `S1G3` | **`0xf000`** | `0x2b0000` | ✅ |  |
| [2PM Gen3](S2PMG3.md) | `S2PMG3` | `0x10000` | `0x2c0000` | ✅ | Relays and meter not reported |
| [Plug M Gen3, beta layout](PlugMG3.md#beta-layout) | `PlugMG3-beta` | `0x10000` | `0x300000` | ✅ | Shelly 2.2.0-beta2 only |
| [Plug PM Gen3 (no relay)](PlugPMG3.md) | `PlugPMG3` | `0x10000` | `0x280000` | 🟡 | Flashed over OTA, readings not checked. Measures only, no relay |
| [Duo Bulb Gen3](DuoBulbG3.md) | `DuoBulbG3` | `0x10000` | `0x280000` | 🟡 | Flashed over OTA and runs; the GPIOs (PWM, from the stock dump) are not confirmed on the hardware |
| [Mini 1PM Gen3](Mini1PMG3.md) | `Mini1PMG3` | **`0xf000`** | `0x2a0000` | 🟡 | Flashed over OTA (two units); a second OTA, the relay under load and the meter not checked |
| [1PM Gen3](S1PMG3.md) | `S1PMG3` | **`0xf000`** | `0x2c0000` | 🟡 | Flashed over OTA with the reporter's own tooling, not `ota.py`; meter not checked |
| [The Pill](Pill.md) | `Pill` | `0x10000` | `0x280000` | 🧪 |  |
| [1L Gen3](S1LG3.md) | `S1LG3` | `0x10000` | `0x2b0000` | 🧪 |  |
| [2L Gen3](S2LG3.md) | `S2LG3` | `0x10000` | `0x2b0000` | 🧪 |  |
| [i4 Gen3](I4G3.md) | `I4G3` | **`0xf000`** | `0x280000` | 🧪 |  |
| [Dimmer Gen3](DimmerG3.md) | `DimmerG3` | `0x10000` | `0x300000` | 🧪 |  |
| [Dimmer 0/1-10V PM Gen3](Dimmer0110VPMG3.md) | `Dimmer0110VPMG3` | **`0xf000`** | `0x280000` | 🧪 |  |
| [EM Gen3](EMG3.md) | `EMG3` | `0x10000` | `0x280000` | 🧪 |  |
| [3EM-63 Gen3](S3EMG3.md) | `S3EMG3` | `0x10000` | `0x280000` | 🧪 |  |
| [Outdoor Plug S Gen3](OutdoorPlugSG3.md) | `OutdoorPlugSG3` | `0x10000` | `0x2a0000` | 🧪 |  |
| [Plus 1 Mini](Plus1Mini.md) | `Plus1Mini` | **`0x8000`** | `0x190000` | 🧪 | ESP32-C3 hardware, sold as Plus Mini |
| [Plus 1PM Mini](Plus1PMMini.md) | `Plus1PMMini` | **`0x8000`** | `0x190000` | 🧪 | ESP32-C3 hardware, sold as Plus Mini |
| [Plus PM Mini (no relay)](PlusPMMini.md) | `PlusPMMini` | **`0x8000`** | `0x190000` | 🧪 | ESP32-C3 hardware, sold as Plus Mini |

### Gen4 (ESP32-C6)

17 profiles: ✅ 0 · 🟡 1 · 🔬 7 · 🧪 9

| Device | Profile | Partition table | App slot size | State | Note |
| --- | --- | --- | --- | --- | --- |
| [Power Strip 4 Gen4](PowerStrip.md) | `PowerStrip` | `0x10000` | `0x300000` | 🟡 | Boots, outlets not checked |
| [Mini 1PM Gen4](Mini1PMG4.md) | `Mini1PMG4` | `0x10000` | `0x300000` | 🔬 |  |
| [Mini 1PM Gen4 (Zigbee)](Mini1PMG4.md#zigbee-variant) | `Mini1PMG4ZB` | `0x10000` | `0x300000` | 🔬 |  |
| [i4 Gen4](I4G4.md) | `I4G4` | `0x10000` | `0x300000` | 🔬 | Only the beta 2.2.0-beta1 is in the update API |
| [Dimmer Gen4](DimmerG4.md) | `DimmerG4` | `0x10000` | `0x300000` | 🔬 |  |
| [Dimmer 0/1-10V PM Gen4](Dimmer0110VPMG4.md) | `Dimmer0110VPMG4` | `0x10000` | `0x300000` | 🔬 |  |
| [1 Mini Gen4](Mini1G4.md) | `Mini1G4` | `0x10000` | `0x300000` | 🔬 |  |
| [EM Mini Gen4](MiniEMG4.md) | `MiniEMG4` | `0x10000` | `0x2f0000` | 🔬 |  |
| [Power Strip 4 Gen4 (Zigbee)](PowerStripZB.md) | `PowerStripZB` | `0x10000` | `0x300000` | 🧪 |  |
| [1 Gen4](S1G4.md) | `S1G4` | `0x10000` | `0x300000` | 🧪 |  |
| [1PM Gen4](S1PMG4.md) | `S1PMG4` | `0x10000` | `0x300000` | 🧪 |  |
| [2PM Gen4](S2PMG4.md) | `S2PMG4` | `0x10000` | `0x300000` | 🧪 |  |
| [1L Gen4](S1LG4.md) | `S1LG4` | `0x10000` | `0x300000` | 🧪 |  |
| [2L Gen4](S2LG4.md) | `S2LG4` | `0x10000` | `0x300000` | 🧪 |  |
| [EM Gen4](EMG4.md) | `EMG4` | `0x10000` | `0x300000` | 🧪 | 16 MB flash layout: its DevKit image needs a 16 MB board |
| [Plug US Gen4](PlugUSG4.md) | `PlugUSG4` | `0x10000` | `0x300000` | 🧪 |  |
| [Presence Gen4](PresenceG4.md) | `PresenceG4` | `0x10000` | `0x300000` | 🧪 |  |

The partition table offset goes into your ESPHome config as `CONFIG_PARTITION_TABLE_OFFSET`; `build` refuses a config that
does not match the profile. Details per device are on its page.

### Gen1 (ESP8266), in testing

Gen1 has no profile and no device page yet, so `ota.py` cannot update these devices. Shelly's Gen1 update works differently (ESP8266, rBoot, no ESP-IDF partition table), and the way back to Shelly's firmware is different too. What is known and what is still open is in [Research: Shelly Gen1](../research/gen1.md).

🔬 here means: an ESP8266 dev board (a D1 mini) with the model's stock image took ESPHome through Shelly's own updater (`/ota?url=`), in the sequence described in the research page. No real Shelly has been flashed. 🧪 means the model was not run or does not run on the bare board.

| Device | SoC | Flash | State | Tracking |
| --- | --- | --- | --- | --- |
| Shelly 1 | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🔬 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): ESPHome with the OTA prototype went through the stock updater on an ESP8266 dev board with this model's stock image (2026-10-29/30), not on a real Shelly; boot confirmation read back |
| Shelly 1PM | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🔬 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): ESPHome with the OTA prototype went through the stock updater on an ESP8266 dev board with this model's stock image (2026-10-29/30), not on a real Shelly |
| Shelly 2.5 | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🔬 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): ESPHome with the OTA prototype went through the stock updater on an ESP8266 dev board with this model's stock image (2026-10-29/30), not on a real Shelly |
| Shelly i3 | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🔬 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): ESPHome with the OTA prototype went through the stock updater on an ESP8266 dev board with this model's stock image (2026-10-29/30), not on a real Shelly |
| Shelly Uni | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🔬 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): ESPHome with the OTA prototype went through the stock updater on an ESP8266 dev board with this model's stock image (2026-10-29/30), not on a real Shelly |
| Shelly Plug S | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🔬 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): ESPHome with the OTA prototype went through the stock updater on an ESP8266 dev board with this model's stock image (2026-10-29/30), not on a real Shelly; boot confirmation read back |
| Shelly Plug US | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🔬 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): ESPHome with the OTA prototype went through the stock updater on an ESP8266 dev board with this model's stock image (2026-10-29/30), not on a real Shelly; boot confirmation read back |
| Shelly RGBW2 | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🔬 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): ESPHome with the OTA prototype went through the stock updater on an ESP8266 dev board with this model's stock image (2026-10-29/30), not on a real Shelly; boot confirmation read back |
| Shelly Bulb | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🔬 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): ESPHome with the OTA prototype went through the stock updater on an ESP8266 dev board with this model's stock image (2026-10-29/30), not on a real Shelly; boot confirmation read back |
| Shelly Duo | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🔬 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): ESPHome with the OTA prototype went through the stock updater on an ESP8266 dev board with this model's stock image (2026-10-29/30), not on a real Shelly; boot confirmation read back |
| Shelly Vintage | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🔬 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): ESPHome with the OTA prototype went through the stock updater on an ESP8266 dev board with this model's stock image (2026-10-29/30), not on a real Shelly; boot confirmation read back |
| Shelly Dimmer | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🔬 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): ESPHome with the OTA prototype went through the stock updater on an ESP8266 dev board with this model's stock image (2026-10-29/30), not on a real Shelly; boot confirmation read back |
| Shelly Dimmer 2 | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🔬 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): ESPHome with the OTA prototype went through the stock updater on an ESP8266 dev board with this model's stock image (2026-10-29/30), not on a real Shelly; boot confirmation read back |
| Shelly 1L | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🧪 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): the stock image does not boot on the bare dev board (boot loop), so the chain could not be run |
| Shelly 2 | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🧪 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): as the 1L: the stock image does not boot on the bare dev board |
| Shelly EM | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🧪 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): as the 1L: the stock image does not boot on the bare dev board |
| Shelly 3EM | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🧪 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): as the 1L: the stock image does not boot on the bare dev board |
| Shelly H&T | ESP8266 | 2 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🧪 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): the stock image stays silent on the bare dev board (probably it sleeps without its STM co-processor); pins read from the firmware, not confirmed |
| Shelly Plug (SHPLG2-1) | ESP8266 | 4 MB ![unconfirmed](https://img.shields.io/badge/-unconfirmed-yellow.svg?style=flat-square) | 🧪 | [#47](https://github.com/oxynatOr/free-shelly-ota/issues/47): other layout (slot 0 at `0x100000`): ESPHome crashes right after rBoot starts it, the cache mapping of the second megabyte is not solved |

## Tested on a dev board

These profiles went through the whole update on a dev board with the [DevKit image](../devkit.md), but not on the real device yet. What the board showed is in [Seen on a board](../devkit.md#seen-on-a-board).

| Device | Profile | Board | Date |
| --- | --- | --- | --- |
| [i4 Gen4](I4G4.md) | `I4G4` | ESP32-C6 dev board, 8 MB | 2026-10-21 |
| [Dimmer Gen4](DimmerG4.md) | `DimmerG4` | ESP32-C6 dev board, 8 MB | 2026-10-21 |
| [Dimmer 0/1-10V PM Gen4](Dimmer0110VPMG4.md) | `Dimmer0110VPMG4` | ESP32-C6 dev board, 8 MB | 2026-10-21 |
| [1 Mini Gen4](Mini1G4.md) | `Mini1G4` | ESP32-C6 dev board, 8 MB | 2026-10-21 |
| [EM Mini Gen4](MiniEMG4.md) | `MiniEMG4` | ESP32-C6 dev board, 8 MB | 2026-10-21 |
| [Mini 1PM Gen4](Mini1PMG4.md) | `Mini1PMG4` | ESP32-C6 dev board, 8 MB | 2026-10-23 |
| [Mini 1PM Gen4 (Zigbee)](Mini1PMG4.md#zigbee-variant) | `Mini1PMG4ZB` | ESP32-C6 dev board, 8 MB | 2026-10-23 |
| [Plus 1 (Gen2)](Plus1.md) | `Plus1` | ESP32 dev board (ESP32-D0WD-V3), 4 MB, ESP-Prog | 2026-10-30 |
| [Plus 1PM (Gen2)](Plus1PM.md) | `Plus1PM` | ESP32 dev board (ESP32-D0WD-V3), 4 MB, ESP-Prog | 2026-10-30 |
| [Plus Plug US (Gen2)](PlugUS.md) | `PlugUS` | ESP32 dev board (ESP32-D0WD-V3), 4 MB, ESP-Prog | 2026-10-30 |
| [Plus Plug UK (Gen2)](PlusPlugUK.md) | `PlusPlugUK` | ESP32 dev board (ESP32-D0WD-V3), 4 MB, ESP-Prog | 2026-10-30 |
| [Plus RGBW PM (Gen2)](PlusRGBWPM.md) | `PlusRGBWPM` | ESP32 dev board (ESP32-D0WD-V3), 4 MB, ESP-Prog | 2026-10-30 |

## Where devices differ

- **Partition table at `0xf000`:** [H&T Gen3](HTG3.md), [PM Mini Gen3](MiniPMG3.md), [Mini 1 Gen3](Mini1G3.md) and [Mini 1PM Gen3](Mini1PMG3.md). A default
  ESPHome build uses ESP-IDF's default `0x8000` and does not match.
- **Classic ESP32 (Gen2):** the [Plus i4](PlusI4.md), [Plus Plug S](PlusPlugS.md), [Plus Plug IT](PlusPlugIT.md), [Plus Uni](PlusUni.md) and [Pro 3EM](Pro3EM.md). Partition table at
  `0x8000`, bootloader at `0x1000`, and the ESPHome build needs the 80 MHz flash frequency. Flash is 4 MB, except on the Pro 3EM
  (16 MB, so `flash_size: 16MB`, and an extra `emdata` partition).
- **Bootloader `min_version` 1.0.9:** every profile sets it, because a device that runs Shelly's loader 1.0.3 would otherwise skip
  ESPHome's bootloader (the default is one patch above the official loader, 1.0.3; a test checks that no profile lacks it). Background:
  [Bootloader and slots](../bootloader-and-slots.md).
- **Variants:** `PowerStripZB` and `Mini1PMG4ZB` are the Zigbee firmware of the same hardware as `PowerStrip` and `Mini1PMG4`.
  The Power Strip variant has its own page, the Mini variant a section on the Mini 1PM Gen4 page.

## What a page contains

The pages follow the same layout, so you can jump to the part you need:

1. **Header:** badges for the state and the chip, quick links, and a table with profile, flash size, official package version, partition table, app slot size and,
   where one exists, the ESPHome device page; below it a NOTE on what was confirmed or checked (not on untested devices).
2. **Before you start:** one line with the checks (stock firmware, IP address, reachability, config, UART adapter); what only applies to the model is listed under "Also".
3. **ESPHome config:** the `esp32:` and `ota:` block to copy, with the partition CSV from `partitions/`.
4. **Pins:** what was read from the stock firmware or taken from a working config (not on every page).
5. **Flash it:** the `fetch`, `build`, `send` commands for this profile as numbered steps, including `--dry-run`.
6. **What to expect:** the lines `send` shows at the default log level, in order, as a table.
7. **Notes for this device:** things that only apply to this model.
8. **Way back:** how to get Shelly OS back, with `restore` or over UART.

Every page ends with the same box: the package wipes Wi-Fi and settings, there is no way back over the network once ESPHome's bootloader runs, and the request for a device report. The sentences are the same on every page on purpose, and a test keeps them so.

The pages have no photos and no complete configs. Product photos, pin photos and example configs belong on the ESPHome device page that a page links
where one exists, and ready-made configs in [`oxynatOr/esphome-configs`](https://github.com/oxynatOr/esphome-configs).

## Related pages

| Page | What is in it |
| --- | --- |
| [Commands](../commands.md) | `fetch`, `build`, `send`, `restore`, `log` and the rest, with all options |
| [Bootloader and slots](../bootloader-and-slots.md) | Why ESPHome's bootloader is shipped, `min_version`, why the app must land in slot 0 |
| [Troubleshooting](../troubleshooting.md) | Header errors, empty log, battery devices, eFuse, power cycle |
| [Recovery over UART](../recovery-uart.md) | Back to Shelly OS with `esptool` |
| [Credential check](../credential-check.md) | Secrets inside images and packages |

## Your device is not listed

[Request it](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=new-device.yml), or run
`python ota.py add-device <official.zip>` to create a profile from an official package (`--parent <base device>` for a
variant). If you flashed one of the devices above, a report helps, also when it worked:
[open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).
