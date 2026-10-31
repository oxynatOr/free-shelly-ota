# Test the update on a dev board

[← README](../README.md) · [Documentation](README.md) · [Commands](commands.md#devkit) · [Recovery over UART](recovery-uart.md)

[🎯 Why](#why) · [🧰 Which board](#which-board) · [🪜 Steps](#steps) · [👀 What to look for](#what-to-look-for) · [🔁 Variations](#variations-to-play-through) · [⚠️ Limits](#limits-and-risks)

`ota.py devkit` turns a package into a flash image for a dev board. The board then boots Shelly's own loader and firmware, and `send`, the
installer, the bootloader swap and the slot logic run against it as against a device. Resetting the board takes one `esptool` call, so the same
update can be played through again and again, for every profile, also for devices you do not own.

> [!IMPORTANT]
> **Not run on a board yet.** The images are built from the packages and a test checks every profile, but nobody has flashed one. What the Shelly app does on a
> board that is not a Shelly (blank `shelly` partition, none of the hardware) is not known. Stage 1 below decides; [Seen on a board](#seen-on-a-board) records the results.

## Why

A wrong `min_version`, a package that keeps Shelly's bootloader ([issue #46](https://github.com/oxynatOr/free-shelly-ota/issues/46)), the wrong update slot, the
eFuse lines: all of it only shows when the real installer runs. On a board that costs a reset, on a device in a wall it can cost the device.
The package already holds everything the flash needs (the manifest says where each part goes), so the image is the same as the manual steps in
[Recovery over UART](recovery-uart.md), in one file and with the tool's checks.

## Which board

The chip family must match and the flash must hold the whole partition table of the device. Most ESP32-C3 dev boards have 4 MB and are too small for the Gen3 devices.

| Profile | Device | Chip | Flash needed | Board |
| --- | --- | --- | --- | --- |
| `PlusI4` | Plus i4 / i4 DC | ESP32 | 4 MiB | classic ESP32 board, 4 MB |
| `PlusUni` | Plus Uni | ESP32 | 4 MiB | classic ESP32 board, 4 MB |
| `PlusPlugS` | Plus Plug S | ESP32 | 4 MiB | classic ESP32 board, 4 MB |
| `PlusPlugIT` | Plus Plug IT | ESP32 | 4 MiB | classic ESP32 board, 4 MB |
| `Pro3EM` | Pro 3EM | ESP32 | 16 MiB | classic ESP32 board with 16 MB (rare) |
| `PlugUS` | Plus Plug US | ESP32 | 4 MiB | classic ESP32 board, 4 MB |
| `Plus1` | Plus 1 | ESP32 | 4 MiB | classic ESP32 board, 4 MB |
| `Plus1PM` | Plus 1PM | ESP32 | 4 MiB | classic ESP32 board, 4 MB |
| `Plus2PM` | Plus 2PM | ESP32 | 4 MiB | classic ESP32 board, 4 MB |
| `Plus1Mini` | Plus 1 Mini | ESP32-C3 | 4 MiB | ESP32-C3 board with 4 MB |
| `Plus1PMMini` | Plus 1PM Mini | ESP32-C3 | 4 MiB | ESP32-C3 board with 4 MB |
| `PlusPMMini` | Plus PM Mini | ESP32-C3 | 4 MiB | ESP32-C3 board with 4 MB |
| `PlusPlugUK` | Plus Plug UK | ESP32 | 4 MiB | classic ESP32 board, 4 MB |
| `PlusRGBWPM` | Plus RGBW PM | ESP32 | 4 MiB | classic ESP32 board, 4 MB |
| `Pro1` | Pro 1 | ESP32 | 8 MiB | classic ESP32 board with 8 MB |
| `Pro1PM` | Pro 1PM | ESP32 | 8 MiB | classic ESP32 board with 8 MB |
| `Pro2` | Pro 2 | ESP32 | 8 MiB | classic ESP32 board with 8 MB |
| `Pro2PM` | Pro 2PM | ESP32 | 8 MiB | classic ESP32 board with 8 MB |
| `Pro3` | Pro 3 | ESP32 | 8 MiB | classic ESP32 board with 8 MB |
| `Pro4PM` | Pro 4PM | ESP32 | 8 MiB | classic ESP32 board with 8 MB |
| `ProRGBWWPM` | Pro RGBWW PM | ESP32 | 8 MiB | classic ESP32 board with 8 MB |
| `PlugMG3` | Plug M Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `PlugSG3` | Plug S Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `PlugPMG3` | Plug PM Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `HTG3` | H&T Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `MiniPMG3` | PM Mini Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `Mini1G3` | Mini 1 Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `Mini1PMG3` | Mini 1PM Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `Pill` | The Pill | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `DuoBulbG3` | Duo Bulb Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `RGBCCTBulbG3` | Multicolor Bulb Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `PowerStrip` | Power Strip 4 Gen4 | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `PowerStripZB` | Power Strip 4 Gen4 (Zigbee) | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `Mini1PMG4` | Mini 1PM Gen4 | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `Mini1PMG4ZB` | Mini 1PM Gen4 (Zigbee) | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `S1G3` | 1 Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `S1PMG3` | 1PM Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `S2PMG3` | 2PM Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `S1LG3` | 1L Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `S2LG3` | 2L Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `I4G3` | i4 Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `DimmerG3` | Dimmer Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `Dimmer0110VPMG3` | Dimmer 0/1-10V PM Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `EMG3` | EM Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `S3EMG3` | 3EM-63 Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `OutdoorPlugSG3` | Outdoor Plug S Gen3 | ESP32-C3 | 8 MiB | ESP32-C3 board with 8 MB |
| `S1G4` | 1 Gen4 | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `S1PMG4` | 1PM Gen4 | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `S2PMG4` | 2PM Gen4 | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `S1LG4` | 1L Gen4 | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `S2LG4` | 2L Gen4 | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `I4G4` | i4 Gen4 | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `DimmerG4` | Dimmer Gen4 | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `Dimmer0110VPMG4` | Dimmer 0/1-10V PM Gen4 | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `EMG4` | EM Gen4 | ESP32-C6 | 16 MiB | ESP32-C6 board with 16 MB |
| `Mini1G4` | 1 Mini Gen4 | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `MiniEMG4` | EM Mini Gen4 | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `PlugUSG4` | Plug US Gen4 | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |
| `PresenceG4` | Presence Gen4 | ESP32-C6 | 8 MiB | ESP32-C6 board with 8 MB |

`python -m esptool --port COMx flash-id` shows the flash size of a board. `--flash-size 4MB|8MB|16MB` makes `devkit` stop if the layout needs more.

## Steps

> [!WARNING]
> Use a spare board, never a device. The image overwrites the whole flash, bootloader included, and Shelly's updater burns an eFuse on it (see [Limits and risks](#limits-and-risks)).

1. **Stage 0, the starting point.** `python -m esptool --port COMx flash-id` and `python -m espefuse --chip <chip> --port COMx summary`. Keep the eFuse output: flash encryption and secure boot must be off,
   and you will compare it after the first update.
2. **Stage 1, the board boots.** Make the image and write it with the commands the tool prints:

   ```
   python ota.py fetch PlusUni --insecure
   python ota.py devkit PlusUni --flash-size 4MB
   ```

   Open a serial monitor at 115200 Bd. Expected: Shelly's loader prints its version and `Booting app 0`. Whether the Shelly app then runs and opens an access point is the open question.
3. **Stage 2, the tool reaches it.** Join the board's access point and check it. A board with the Zigbee firmware opens none: give it a Wi-Fi over Bluetooth first (`python ota.py ble wifi SSID -`, see [ble](commands.md#ble)) and use the address it prints for `--ip`:

   ```
   python ota.py send PlusUni out/<package>.zip --ip 192.168.33.1 --dry-run
   ```

   Expected: `Device ...: app=PlusUni`, the slot check and the reachability check.
4. **Stage 3, the update.** Send a package built with `--esphome-factory` and read the log (`send` shows it; `--log-file` keeps it, see [What to look for](#what-to-look-for)). Then read the eFuses again.
5. **Stage 4, again.** `erase-flash` and write the image once more. A run takes minutes, so the variations below are cheap.

## What to look for

| Log line | Meaning |
| --- | --- |
| `Update target slot: 0 ...` | The slot check of `send` (the Shelly app names its slot over the debug log) |
| `Boot: cur ... new ... min ... update? 1` | The installer writes the package's bootloader; `update? 0` means it keeps Shelly's |
| `Installing BL ... -> boot(0)` | The bootloader is written |
| `FW signatures: want 07 got 00` | The package is not signed by Shelly |
| `BURN BLOCK3` and `... - OK`, or `EFUSE write error` | The updater's eFuse writes (see below) |
| `ota_progress` up to 95 %, then `ota_success` | The update itself |
| `Uncommitted boot of app N (attempts 3)`, `Booting app N` | Shelly's loader (only with its bootloader) |

`espefuse summary` before and after the first update answers what the open eFuse notes in [Troubleshooting](troubleshooting.md#efuse) could not: which bits the updater changed.

## Variations to play through

- **The default (`update? 1`):** a package built with `--esphome-factory` and the profile's `boot_min_version`.
- **The bootloader is skipped:** build with `--esphome-factory --boot-min-version 1.0.3`, the value that gave `update? 0` on the Plus Uni; `send --watch` warns about it.
- **A package that keeps Shelly's bootloader:** `send` refuses it; with `--force` it reproduces [#46](https://github.com/oxynatOr/free-shelly-ota/issues/46) (three starts, then the loader goes back to the other slot; later OTAs are written but never started).
- **A second ESPHome OTA** after a full install: it takes effect.
- **The state after an install, without the installer:** `python ota.py devkit PlusUni --zip out/<your package>.zip` puts a built package on the board directly (ESPHome's bootloader and app).
- **Another version:** `--version` takes any cached official version, `--zip` any package file.

## Limits and risks

- **eFuse.** The updater logs `BURN BLOCK3` when it installs a package without Shelly's signature. That cannot be undone on that chip. Read `espefuse summary` first: on the classic ESP32, BLOCK3 may carry calibration data or a custom MAC.
- **No device data.** The partitions `shelly` and `aux` (identity and calibration) stay blank, NVS is empty. The Shelly app may start without them or may not.
- **No hardware.** There is no relay, meter or button; the app may log errors for them. Relay, LED and sensor behavior cannot be tested this way.
- **Chip and flash.** A C6 device needs a C6 board, the Pro 3EM a classic ESP32 with 16 MB. Without such a board that profile stays untested.
- **Shelly's firmware.** The image contains it. It is made locally from your cache, lies in `out/` (git-ignored) and must not be shared or uploaded; an image made with `--zip` from your own build can also hold your Wi-Fi data.

## Seen on a board

A profile gets 🔬 once a row here shows the OTA ran through on a board with its DevKit image (stage 4); it goes to 🟡/✅ as soon as the real device was flashed. Add the date, the board, the profile and what the serial monitor and `send --watch` showed, separately from what was only read from the packages.

| Date | Board | Profile | What happened |
| --- | --- | --- | --- |
| 2026-10-21 | ESP32-C6 dev board, 8 MB | `Dimmer0110VPMG4` | DevKit image flashed, then `send` of the ESPHome SoftAP package (ESPHome's bootloader, `min_version` 1.0.9) with `--watch`: ESPHome's access point appeared (`shelly-dimmer0110vpmg4`). No relay, meter or button on the board. |
| 2026-10-21 | ESP32-C6 dev board, 8 MB | `DimmerG4` | DevKit image flashed, then `send` of the ESPHome SoftAP package (ESPHome's bootloader, `min_version` 1.0.9) with `--watch`: the log showed `ota_success`, then ESPHome's access point appeared (`shelly-dimmerg4`). No relay, meter or button on the board. |
| 2026-10-21 | ESP32-C6 dev board, 8 MB | `I4G4` | DevKit image flashed, then `send` of the ESPHome SoftAP package (ESPHome's bootloader, `min_version` 1.0.9) with `--watch`: the log showed `ota_success` (progress 100 %), then ESPHome's access point appeared (`shelly-i4g4`). No relay, meter or button on the board. |
| 2026-10-21 | ESP32-C6 dev board, 8 MB | `Mini1G4` | DevKit image flashed, then `send` of the ESPHome SoftAP package (ESPHome's bootloader, `min_version` 1.0.9) with `--watch`: the installer wrote to slot 0, the bootloader was replaced (current 1.0.3, minimum 1.0.9), the log showed `ota_success`, then ESPHome's access point appeared (`shelly-mini1g4`). No relay, meter or button on the board. |
| 2026-10-21 | ESP32-C6 dev board, 8 MB | `MiniEMG4` | DevKit image flashed, then `send` of the ESPHome SoftAP package (ESPHome's bootloader, `min_version` 1.0.9): ESPHome's access point appeared (`shelly-miniemg4`); the log of the run was not reported. No relay, meter or button on the board. |
| 2026-10-23 | ESP32-C6 dev board, 8 MB | `Mini1PMG4` | DevKit image flashed, then `send` of the ESPHome SoftAP package (ESPHome's bootloader, `min_version` 1.0.9): ESPHome's access point appeared (`shelly-mini1pmg4`). During the update the stock log repeated `shos_bl0942.c: packet read timed out` (no power meter chip on the board); it is harmless and hidden below `--log-level debug`. No relay, meter or button on the board. |
| 2026-10-23 | ESP32-C6 dev board, 8 MB | `Mini1PMG4ZB` | DevKit image flashed (stock Zigbee firmware 2.0.1, loader 1.0.3); the stock image opens no access point, so the Wi-Fi was given over BLE-RPC. The first `send` was refused: the installer would write to slot 1 (the board ran slot 0). After `restore` (the official package went to slot 1, the board then reported slot 1) the target was slot 0, and `send` of the ESPHome SoftAP package (ESPHome's bootloader, `min_version` 1.0.9) went through: `Will write to slot 0`, `Boot: cur 010003ff, new 00000000, min 010009ff, update? 1`, `Installing BL … -> boot(0)`, progress to 100 %, `Update succeeded`, the known eFuse lines (`FW signatures: want 07 got 00`, `EFUSE write error`), reboot; ESPHome's access point appeared (`shelly-mini1pmg4zb`). The package is accepted by the Zigbee stock firmware under its own name. No relay, meter or button on the board. |
| 2026-10-30 | ESP32 dev board (ESP32-D0WD-V3), 4 MB, ESP-Prog | `Plus1PM` | DevKit image flashed (stock 1.7.6, loader 1.0.2), then `restore` once (the installer would have written to slot 1), then `send` of the ESPHome SoftAP package (ESPHome's bootloader, `min_version` 1.0.9): `Update target slot: 0`, `Boot: cur 010002ff, min 010009ff, update? 1`, `Installing the bootloader (25888 bytes)`, `Done: update installed, the device confirmed it`, the known eFuse lines (`FW signatures: want 07 got 00`, `BURN BLOCK3`); ESPHome's access point appeared (`devkit-plus1pm`) and answered a ping. No relay, meter or button on the board. |
| 2026-10-30 | ESP32 dev board (ESP32-D0WD-V3), 4 MB, ESP-Prog | `Plus1` | DevKit image flashed (stock 1.7.6, loader 1.0.2), then `restore` once (the installer would have written to slot 1), then `send` of the ESPHome SoftAP package (ESPHome's bootloader, `min_version` 1.0.9): `Update target slot: 0`, `Boot: cur 010002ff, min 010009ff, update? 1`, `Installing the bootloader (25888 bytes)`, `Done: update installed, the device confirmed it`, the known eFuse lines (`FW signatures: want 07 got 00`, `BURN BLOCK3`); ESPHome's access point appeared (`devkit-plus1`) and answered a ping. No relay, meter or button on the board. |
| 2026-10-30 | ESP32 dev board (ESP32-D0WD-V3), 4 MB, ESP-Prog | `PlugUS` | DevKit image flashed (stock 1.7.6, loader 1.0.2), then `restore` once (the installer would have written to slot 1), then `send` of the ESPHome SoftAP package (ESPHome's bootloader, `min_version` 1.0.9): `Update target slot: 0`, `Boot: cur 010002ff, min 010009ff, update? 1`, `Installing the bootloader (25888 bytes)`, `Done: update installed, the device confirmed it`, the known eFuse lines (`FW signatures: want 07 got 00`, `BURN BLOCK3`); ESPHome's access point appeared (`devkit-plugus`) and answered a ping. No relay, meter or button on the board. |
| 2026-10-30 | ESP32 dev board (ESP32-D0WD-V3), 4 MB, ESP-Prog | `PlusPlugUK` | DevKit image flashed (stock 2.0.3, loader 1.0.3), then `restore` once (the installer would have written to slot 1), then `send` of the ESPHome SoftAP package (ESPHome's bootloader, `min_version` 1.0.9): `Update target slot: 0`, `Boot: cur 010003ff, min 010009ff, update? 1`, `Installing the bootloader (25888 bytes)`, `Done: update installed, the device confirmed it`, the known eFuse lines (`FW signatures: want 07 got 00`, `BURN BLOCK3`); ESPHome's access point appeared (`devkit-pluspluguk`) and answered a ping. No relay, meter or button on the board. |
| 2026-10-30 | ESP32 dev board (ESP32-D0WD-V3), 4 MB, ESP-Prog | `PlusRGBWPM` | DevKit image flashed (stock 2.0.3, loader 1.0.3). The slot check of `send` got no UDP log from the device (`No UDP datagram arrived`, also with `--host`), so after one `restore` the ESPHome SoftAP package (ESPHome's bootloader, `min_version` 1.0.9) was sent with `--ignore-slot`: the device downloaded it, ESPHome's access point appeared (`devkit-plusrgbwpm`) and answered a ping, and the bootloader read back from the flash was ESPHome's. The stock log shows `Failed to load factory data` and analog input errors (blank `shelly` partition, no hardware). No LED outputs or meter on the board. |
| 2026-10-30 | ESP32 dev board (ESP32-D0WD-V3), 4 MB, ESP-Prog | `Plus2PM` | DevKit image flashed (stock 1.7.6, loader 1.0.2): the stock app restarts again and again (44 restarts in about 75 s, `UNABLE TO LOAD FACTORY DATA` for the blank `shelly` partition) and does not answer, so the update could not be tried. State stays 🧪. |
| 2026-10-30 | ESP32-C3 dev board, 8 MB | `MiniPMG3` | DevKit image of the official 2.1.1 package (loader 1.0.3). The Shelly app starts on the blank board and opens its access point. The first `send` of the ESPHome SoftAP package was refused: the installer would write to slot 1. After `restore` the target was slot 0, and `send` went through: `Boot: cur 010003ff, min 010009ff`, the bootloader was replaced, progress to 100 %, `Done: update installed, the device confirmed it`, the known eFuse lines (`FW signatures: want 07, got 00`); ESPHome's access point appeared (`shelly-MiniPMG3`). The profile is already ✅ from a real device (started on 2.0.1); this run checks 2.1.1 as the base after a field report of a silent device. The serial console of the board stayed silent on its UART throughout. No relay, meter or button on the board. |
| 2026-10-30 | ESP32-C3 dev board, 8 MB | `MiniPMG3` (stock 1.3.3) | DevKit image of the official 1.3.3 package (the step the update API names for a unit on 1.1.99; loader `010000ff`; partition table at `0x8000`). `send` of the 2.1.1-based ESPHome package: the dry run could not name the target slot (the log says `Storing core dumps to scratch`); the updater printed `BS is being moved from 0x10000 to 0x11000`, `PT is being moved from 0x8000 to 0xf000`, `Boot: cur 010000ff, new 00000000, min 010009ff, update? 1` and `Installing BL 20544@app_1(0x3a0000) -> boot(0)`, then confirmed the update. After the restart the stock 1.3.3 web interface was back and no ESPHome access point appeared: the installer had written to slot 1 (the known slot case). Played through again from a fresh image: `restore` (slot 1, loader `010000ff` to `010003ff`, 2.1.1), the dry run then named slot 0, `send` replaced the bootloader (`010003ff` to `010009ff`) and ESPHome's access point appeared (`shelly-MiniPMG3`). This is not the silent device of [#113](https://github.com/oxynatOr/free-shelly-ota/issues/113), whose 1.1.99 log shows none of these lines. No relay, meter or button on the board. |
| 2026-10-31 | ESP32-C3 dev board, 8 MB | `PlugMG3` / `PlugMG3-beta` | Image: a flash dump of a stock Plug M Gen3 on 1.8.99 (running from slot 1, old table with app slots `0x2a0000`, `scratch` at `0x720000`), written as it was with NVS blanked. The Shelly app starts and opens its access point; the Wi-Fi was given through the board's AP. `restore PlugMG3-beta` run 1: `Will write to slot 0`, `Slot switch is required`, `Skipping app`, `Skipping fs`, success reported, the board came back on 1.8.99, slot 0. Run 2 (after more than 130 s uptime; a run at 24 s was answered `Not committed`): `Will write to slot 1`, `Installing new PT1`, the board reported 2.2.0-beta2 on slot 1. `send PlugMG3-beta` with an ESPHome SoftAP package built against the beta table: the dry run read target slot 0, the installer wrote to slot 0, replaced the bootloader (current `010002ff`, minimum `010009ff`), the known eFuse lines (`FW signatures: want 07, got 00`); ESPHome's access point appeared (`shelly-PlugMG3`). The partition table in flash was not read back. Plain `esptool` needed the board in boot mode after the update. No relay, meter or button on the board. |

The classic-ESP32 rows were run in one go with an ESP-Prog, whose DTR/RTS lines reset the board and put it into download mode without a button. On the first run the installer burned eFuse BLOCK3 (one byte, `0x07`); the other eFuses (flash encryption, secure boot, JTAG, UART download) stayed as they were.

---

> [!TIP]
> **Tried it?** Tell us what the board did: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml) or a bug.

[`devkit`](commands.md#devkit) · [Recovery over UART](recovery-uart.md) · [Bootloader and slots](bootloader-and-slots.md) · [Troubleshooting](troubleshooting.md)
