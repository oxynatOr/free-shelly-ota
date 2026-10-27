# Device pages

[← README](../../README.md) · [Documentation](../README.md) · [Commands](../commands.md) · [Device profiles](../../devices/README.md)

One page per device: the ESPHome config with the partition table that device needs, the pins where they are known, the exact
commands, the log lines to look for and the way back to Shelly OS. Pick your device below, then read
[Commands](../commands.md) for what the options do. The README of the project lists only the devices confirmed on real hardware
(✅ and 🟡); this page lists every profile.

✅ = the whole chain ran on a real device, 🟡 = flashed on a real device, but part of the chain or of the function is not
checked yet, 🔬 = the OTA ran through on a dev board with the [DevKit image](../devkit.md), but not on the real device, 🧪 = the package builds and verifies, but nobody has flashed it yet.

## Devices

| Device | Profile | Chip | Partition table | App slot size | State | Note |
| --- | --- | --- | --- | --- | --- | --- |
| [Plug M Gen3](PlugMG3.md) | `PlugMG3` | ESP32-C3 | `0x10000` | `0x2a0000` | ✅ |  |
| [Plug M Gen3, beta layout](PlugMG3.md#beta-layout) | `PlugMG3-beta` | ESP32-C3 | `0x10000` | `0x300000` | 🧪 | Shelly 2.2.0-beta2 only |
| [Plug S Gen3](PlugSG3.md) | `PlugSG3` | ESP32-C3 | `0x10000` | `0x2a0000` | ✅ |  |
| [Plug PM Gen3 (no relay)](PlugPMG3.md) | `PlugPMG3` | ESP32-C3 | `0x10000` | `0x280000` | 🟡 | Flashed over OTA, readings not checked. Measures only, no relay |
| [H&T Gen3](HTG3.md) | `HTG3` | ESP32-C3 | **`0xf000`** | `0x280000` | ✅ |  |
| [PM Mini Gen3 (no relay)](MiniPMG3.md) | `MiniPMG3` | ESP32-C3 | **`0xf000`** | `0x280000` | ✅ | Measures only, no relay |
| [Multicolor Bulb E27 Gen3](RGBCCTBulbG3.md) | `RGBCCTBulbG3` | ESP32-C3 | `0x10000` | `0x280000` | ✅ |  |
| [Duo Bulb Gen3](DuoBulbG3.md) | `DuoBulbG3` | ESP32-C3 | `0x10000` | `0x280000` | 🟡 | Flashed over OTA and runs; the GPIOs (PWM, from the stock dump) are not confirmed on the hardware |
| [Power Strip 4 Gen4](PowerStrip.md) | `PowerStrip` | ESP32-C6 | `0x10000` | `0x300000` | 🟡 | Boots, outlets not checked |
| [Power Strip 4 Gen4 (Zigbee)](PowerStripZB.md) | `PowerStripZB` | ESP32-C6 | `0x10000` | `0x300000` | 🧪 |  |
| [Plus Plug S (V2 hardware, Gen2)](PlusPlugS.md) | `PlusPlugS` | **ESP32** | **`0x8000`** | `0x190000` | ✅ | Flashed without UART |
| [Plus Plug IT (Gen2)](PlusPlugIT.md) | `PlusPlugIT` | **ESP32** | **`0x8000`** | `0x190000` | ✅ | Flashed without UART |
| [The Pill](Pill.md) | `Pill` | ESP32-C3 | `0x10000` | `0x280000` | 🧪 |  |
| [Mini 1 Gen3](Mini1G3.md) | `Mini1G3` | ESP32-C3 | **`0xf000`** | `0x2a0000` | ✅ |  |
| [Mini 1PM Gen3](Mini1PMG3.md) | `Mini1PMG3` | ESP32-C3 | **`0xf000`** | `0x2a0000` | 🟡 | Flashed over OTA (two units); a second OTA, the relay under load and the meter not checked |
| [Mini 1PM Gen4](Mini1PMG4.md) | `Mini1PMG4` | ESP32-C6 | `0x10000` | `0x300000` | 🔬 |  |
| [Mini 1PM Gen4 (Zigbee)](Mini1PMG4.md#zigbee-variant) | `Mini1PMG4ZB` | ESP32-C6 | `0x10000` | `0x300000` | 🔬 |  |
| [Plus Uni (Gen2)](PlusUni.md) | `PlusUni` | **ESP32** | **`0x8000`** | `0x190000` | 🟡 | Flashed over OTA, ESPHome's bootloader step not checked |
| [Pro 3EM (Gen2)](Pro3EM.md) | `Pro3EM` | **ESP32** | **`0x8000`** | `0x200000` | 🧪 |  |
| [1 Gen3](S1G3.md) | `S1G3` | ESP32-C3 | **`0xf000`** | `0x2b0000` | ✅ |  |
| [1PM Gen3](S1PMG3.md) | `S1PMG3` | ESP32-C3 | **`0xf000`** | `0x2c0000` | 🟡 | Flashed over OTA with the reporter's own tooling, not `ota.py`; meter not checked |
| [2PM Gen3](S2PMG3.md) | `S2PMG3` | ESP32-C3 | `0x10000` | `0x2c0000` | ✅ | Relays and meter not reported |
| [1L Gen3](S1LG3.md) | `S1LG3` | ESP32-C3 | `0x10000` | `0x2b0000` | 🧪 |  |
| [2L Gen3](S2LG3.md) | `S2LG3` | ESP32-C3 | `0x10000` | `0x2b0000` | 🧪 |  |
| [i4 Gen3](I4G3.md) | `I4G3` | ESP32-C3 | **`0xf000`** | `0x280000` | 🧪 |  |
| [Dimmer Gen3](DimmerG3.md) | `DimmerG3` | ESP32-C3 | `0x10000` | `0x300000` | 🧪 |  |
| [Dimmer 0/1-10V PM Gen3](Dimmer0110VPMG3.md) | `Dimmer0110VPMG3` | ESP32-C3 | **`0xf000`** | `0x280000` | 🧪 |  |
| [EM Gen3](EMG3.md) | `EMG3` | ESP32-C3 | `0x10000` | `0x280000` | 🧪 |  |
| [3EM-63 Gen3](S3EMG3.md) | `S3EMG3` | ESP32-C3 | `0x10000` | `0x280000` | 🧪 |  |
| [Outdoor Plug S Gen3](OutdoorPlugSG3.md) | `OutdoorPlugSG3` | ESP32-C3 | `0x10000` | `0x2a0000` | 🧪 |  |
| [BLU Gateway Gen3](BluGwG3.md) | `BluGwG3` | ESP32-C3 | `0x10000` | `0x240000` | 🧪 |  |
| [1 Gen4](S1G4.md) | `S1G4` | ESP32-C6 | `0x10000` | `0x300000` | 🧪 |  |
| [1PM Gen4](S1PMG4.md) | `S1PMG4` | ESP32-C6 | `0x10000` | `0x300000` | 🧪 |  |
| [2PM Gen4](S2PMG4.md) | `S2PMG4` | ESP32-C6 | `0x10000` | `0x300000` | 🧪 |  |
| [1L Gen4](S1LG4.md) | `S1LG4` | ESP32-C6 | `0x10000` | `0x300000` | 🧪 |  |
| [2L Gen4](S2LG4.md) | `S2LG4` | ESP32-C6 | `0x10000` | `0x300000` | 🧪 |  |
| [i4 Gen4](I4G4.md) | `I4G4` | ESP32-C6 | `0x10000` | `0x300000` | 🔬 | Only the beta 2.2.0-beta1 is in the update API |
| [Dimmer Gen4](DimmerG4.md) | `DimmerG4` | ESP32-C6 | `0x10000` | `0x300000` | 🔬 |  |
| [Dimmer 0/1-10V PM Gen4](Dimmer0110VPMG4.md) | `Dimmer0110VPMG4` | ESP32-C6 | `0x10000` | `0x300000` | 🔬 |  |
| [EM Gen4](EMG4.md) | `EMG4` | ESP32-C6 | `0x10000` | `0x300000` | 🧪 | 16 MB flash layout: its DevKit image needs a 16 MB board |
| [1 Mini Gen4](Mini1G4.md) | `Mini1G4` | ESP32-C6 | `0x10000` | `0x300000` | 🔬 |  |
| [EM Mini Gen4](MiniEMG4.md) | `MiniEMG4` | ESP32-C6 | `0x10000` | `0x2f0000` | 🔬 |  |
| [Plug US Gen4](PlugUSG4.md) | `PlugUSG4` | ESP32-C6 | `0x10000` | `0x300000` | 🧪 |  |
| [Presence Gen4](PresenceG4.md) | `PresenceG4` | ESP32-C6 | `0x10000` | `0x300000` | 🧪 |  |

The partition table offset goes into your ESPHome config as `CONFIG_PARTITION_TABLE_OFFSET`; `build` refuses a config that
does not match the profile. Details per device are on its page.

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

## Where devices differ

- **Partition table at `0xf000`:** [H&T Gen3](HTG3.md), [PM Mini Gen3](MiniPMG3.md), [Mini 1 Gen3](Mini1G3.md) and [Mini 1PM Gen3](Mini1PMG3.md). A default
  ESPHome build uses ESP-IDF's default `0x8000` and does not match.
- **Classic ESP32 (Gen2):** the [Plus Plug S](PlusPlugS.md), [Plus Plug IT](PlusPlugIT.md), [Plus Uni](PlusUni.md) and [Pro 3EM](Pro3EM.md). Partition table at
  `0x8000`, bootloader at `0x1000`, and the ESPHome build needs the 80 MHz flash frequency. Flash is 4 MB, except on the Pro 3EM
  (16 MB, so `flash_size: 16MB`, and an extra `emdata` partition).
- **Gen4 / ESP32-C6:** [Power Strip](PowerStrip.md), [Power Strip (Zigbee)](PowerStripZB.md) and
  [Mini 1PM Gen4](Mini1PMG4.md) have the largest app slots (`0x300000`).
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
