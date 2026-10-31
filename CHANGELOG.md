# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow [Semantic Versioning](https://semver.org).

## [Unreleased]

### Changed
- `PlugMG3-beta` (Plug M Gen3, Shelly 2.2.0-beta2 layout) is confirmed (✅, was 🟡) after a device report on a plug in the wall ([#122](https://github.com/oxynatOr/free-shelly-ota/issues/122), thanks to [onkelfarmor](https://github.com/onkelfarmor)): stock 1.8.99 without UART, `restore PlugMG3-beta` twice, then `send PlugMG3-beta`; ESPHome runs from `app_0` with relay, button, RGB LED, BL0942 and NTC working. A later ESPHome OTA on that plug took effect (ESPHome ran from `app_1` afterwards). The report also gives measured BL0942 references for that unit (default voltage and power read about 11 % low; `voltage_reference: 14198.37`, `power_reference: 553.98`), on the Plug M page as a starting point. Documentation and status only; nothing in the tool changes, so nothing breaks.
- `MiniPMG3` (PM Mini Gen3) profile revision 2: new key `layout_since: 1.3.3`, so `send` refuses the package on a device whose Shelly firmware is older than 1.3.3 (the same check as for `PlugMG3-beta`, `--force` overrides, not for `restore`). Reason: a unit on stock 1.1.99 (loader `00040405`) took the 2.1.1-based ESPHome package without an error and then stayed silent, even after a power cycle; its log lacks the lines `BS is being moved`, `PT is being moved` and `Installing BL` that the updater of 1.3.3 prints, so that old updater most likely changes neither the layout nor the bootloader ([#113](https://github.com/oxynatOr/free-shelly-ota/issues/113), thanks to [aanban](https://github.com/aanban); the cause is inferred from the log, the 1.1.99 package itself is not available). **Visible, possibly breaking for few:** a device on 1.1.x to 1.3.2 can no longer be sent the package; update it with Shelly's own update first, then send. Not breaking for devices on 1.3.3 and newer: nothing changes there.
- Plug M Gen3 page and [bootloader and slots](docs/bootloader-and-slots.md): the step from stock 1.8.99 to Shelly's 2.2.0-beta2 works when `restore PlugMG3-beta` is run twice (run 1 only switches the slot: `Slot switch is required`, `Skipping app`; run 2 writes the new table). The earlier statement that 1.8.99 cannot take the beta, and the advice to go through 2.0.1 first, are replaced. Played through on a DevKit board with a dump of a 1.8.99 plug ([DevKit](docs/devkit.md#seen-on-a-board)); not yet on a plug in the wall. Thanks to [onkelfarmor](https://github.com/onkelfarmor) ([#102](https://github.com/oxynatOr/free-shelly-ota/issues/102)) for the forum finding. Documentation only; `send` still refuses the beta package on a plug older than 2.2.0, so nothing breaks.
- The device overview ([docs/devices](docs/devices/README.md#devices)) is grouped by generation (Gen2, Gen3, Gen4), the confirmed devices first in each group, and has a short Gen1 (ESP8266) section for what is being tested. The `Chip` column is gone from the overview (the group names the chip), the root README table is sorted the same way. Not breaking: the anchor `#devices` and every page URL stay. Every device page has a generation badge (a test keeps it in line with the chip badge), and open or special facts are badges where they apply: UART not needed, no relay, 16 MB flash, Zigbee variant, beta-only package, unconfirmed pins.
- README restructured: new sections *What you need* and *Contributing and reports*, a shorter Quick start (the `--compile` route first, the long notes moved to the guide), *Another device?* merged into *Contributing and reports*, links to the guides in the navigation row. The sections `Supported devices`, `Quick start`, `Documentation` and `Credits` keep their anchors; the Credits section is short (the three upstream projects, a sentence on the tool's own findings; the table of reporters lives in `CREDITS.md`), `#another-device` is gone (nothing in the repository linked to it). Not breaking: no profile, package or command changed.
- `PlusI4` (Plus i4 / i4 DC) is partly checked (🟡) after the first device report ([#106](https://github.com/oxynatOr/free-shelly-ota/issues/106), thanks to [niki11euro](https://github.com/niki11euro)): flashed over OTA from stock 1.7.6 (loader 1.0.2, replaced; the target slot was 1 until one `restore`), and the unit shows up in Home Assistant. Inputs, LED and a later ESPHome OTA are not reported yet. Documentation only, not a breaking change: no profile, package or command changed.
- Gen1 documentation: the Gen1 section of the device overview lists 19 models with what an ESP8266 dev board did with their stock images (13 went through the stock updater, 6 did not or could not), and [Research: Shelly Gen1](docs/research/gen1.md) has the results, the layout facts and the H&T pins (not confirmed). No Gen1 profile, package or command; documentation only, not breaking.
- Five Gen2 profiles went through the whole update on an ESP32 dev board with the DevKit image (2026-10-30), so they are 🔬 now: `Plus1`, `Plus1PM`, `PlugUS`, `PlusPlugUK`, `PlusRGBWPM` (classic ESP32, 4 MB). `Plus2PM` could not be run on the bare board (the stock app restarts in a loop) and stays 🧪. The README counts change (🔬 7 to 12, 🧪 35 to 30). Documentation only, not breaking: no profile, package or command changed.

### Added
- Documentation site at <https://oxynator.github.io/free-shelly-ota/>, built from `docs/` with MkDocs Material (search, dark mode, device pages grouped by generation) and deployed to GitHub Pages by a workflow; the README links to it. The pages stay as they are and still read fine on GitHub. Not breaking: no profile, package or command changed, and the tool does not need MkDocs (`requirements-docs.txt` is for building the site only).
- Two guides: [Step-by-step guide](docs/guide.md) for users (check the device, prepare, config, build, send, afterwards, failure, way back, report) and [Developer guide](docs/guide-developers.md) (new device, hardware, test ladder, reports, profile changes, tool changes, release). Documentation only, not breaking: no profile, package or command changed.
- `CONTRIBUTING.md`: how to help, the rules (evidence for hardware claims, no private data, credits, breaking-change statement) and a rule for AI-assisted contributions (welcome when checked; hardware claims need real evidence; no secrets to AI services). Documentation only, not breaking.
- Profile `PlusI4` (🧪, Shelly Plus i4 / i4 DC, Gen2, classic ESP32) made from the official 1.7.6 package, with its stock CSV and a device page, requested in [#106](https://github.com/oxynatOr/free-shelly-ota/issues/106) (thanks to [niki11euro](https://github.com/niki11euro)). `boot_min_version` is 1.0.9 like the other profiles. The pins are not read yet and it has not run on a device. Not breaking: no existing profile, package or command changed; the profile list grows from 43 to 44.
- 16 profiles for Shelly Plus and Pro devices, each with its stock CSV and a device page, all 🧪: `PlugUS`, `Plus1`, `Plus1PM`, `Plus2PM`, `PlusPlugUK`, `PlusRGBWPM`, `Pro1`, `Pro1PM`, `Pro2`, `Pro2PM`, `Pro3`, `Pro4PM`, `ProRGBWWPM` (classic ESP32) and `Plus1Mini`, `Plus1PMMini`, `PlusPMMini` (ESP32-C3, bootloader at `0x0`, partition table at `0x8000`). Made from the official packages (1.7.6, 2.0.3 or 2.1.1); `boot_min_version` is 1.0.9 like the other profiles. A DevKit image can be built for each, none has run on a board and none on a device. Not breaking: no existing profile, package or command changed; the profile list grows from 44 to 60. `devices/profiles.lock` has the 16 new entries.

## [0.7.0] - 2026-10-29

Still 0.x, so still experimental: nobody has flashed 19 of the 43 profiles, and seven more went through the update on a dev board only.

### Summary
- **`ota.py build --compile my-plug.yaml`** goes from the ESPHome YAML to the package in one command. It runs the `esphome` command, or Docker if there is none. With Docker the toolchain stays in a volume, so only the first compile is slow (about a minute and a half on the test machine, then seconds). A YAML that gets its `esp32:` block from `packages:` or `!include` is checked on the config ESPHome puts together. `build APP.bin ...` works as before. A package built this way went through the whole update on a real Plug M Gen3 (Shelly 1.8.99 to ESPHome 2026.10.0) and on an ESP32-C6 dev board.
- **Plug M Gen3 beta layout:** Shelly's 2.2.0-beta2 changes the flash table of 17 Gen3 devices. The new profile `PlugMG3-beta` covers the Plug M, and `build` and `send` now refuse a package or a device that does not fit a profile's layout.
- **Reports:** Shelly 1 Gen3 (S1G3) and 2PM Gen3 (S2PMG3) are confirmed on real devices, the 1PM Gen3 is partly checked (thanks to [chusovich](https://github.com/chusovich), [majoto85](https://github.com/majoto85) and [WulffTech](https://github.com/WulffTech)).
- **`send`** no longer waits for a reverse lookup of its own address before it starts (it could add 12 seconds and more behind a VPN).
- **Breaking, for few:** the profile `BluGwG3` (BLU Gateway) is gone, because an ESPHome image makes no sense on a gateway. **Visible:** `build` stops with an error for an official package whose partition table differs from the profile, where it used to finish. Neither touches a profile that was flashed.

### Added
- Documentation of which devices get another flash layout in Shelly's 2.2.0-beta2 (17 G3 devices, and the BLU Gateway, whose profile is removed below; scanned 2026-10-28, see [bootloader and slots](docs/bootloader-and-slots.md#beta-firmware-with-another-flash-layout)). Documentation only; `build` refuses these betas through the layout check.
- Profile `PlugMG3-beta` (🟡) for the Plug M Gen3 beta firmware layout (2.2.0-beta2: app slots of 0x300000, see the [device page](docs/devices/PlugMG3.md#beta-layout)), with its own stock CSV. Profiles got two optional keys: `package` (the official package and its `fw/` folder, when the profile has another name) and `channel: beta` (`fetch` asks for the beta channel, and the newest cached pre-release is the default package). Checked on one plug (2026-10-28): Shelly's beta written over UART, then `restore`, `send` with ESPHome's bootloader and a later ESPHome OTA all worked; the direct step from stock 1.8.99 does NOT work, not even with Shelly's own beta package (the installer replaced the bootloader but wrote neither the new table nor the app; documented as a warning). The way without UART works from Shelly 2.0.x: `restore PlugMG3-beta` (the installer converts the table), then `send PlugMG3-beta`; ESPHome started on the beta table. The profile key `layout_since` makes `send` refuse the package on a device with older firmware (not for `restore`, `--force` overrides). Not breaking: no existing profile changed, `PlugMG3` keeps refusing the beta. The profile list grows by one (it stays 43 with the removal of `BluGwG3` below).
- `build` refuses an official package whose partition table differs from the profile (app slot size or table address), also with `--drop pt`; `inspect` and `fetch` warn about it. Found with PlugMG3 2.2.0-beta2, whose app slots are 0x300000 instead of 0x2a0000 ([#102](https://github.com/oxynatOr/free-shelly-ota/issues/102), thanks to [onkelfarmor](https://github.com/onkelfarmor)). Visible effect: a build with such a package now stops with an error instead of finishing. Not breaking for any cached package of the 43 profiles: a test checks each against its profile and stock CSV.
- `build --compile YAML` compiles the ESPHome config (the `esphome` command, else Docker; `--runner`, `--image`) and builds the package from its binaries, with the config and credential checks. With Docker the toolchain and the build files are kept in a named volume (`free-shelly-esphome-cache`), so only the first compile downloads the toolchain and the build is fast on Windows. `build` asks Docker first and says so if it is not running, hands a new volume to the Linux user, and checks that the package does not exist yet before the compile, not after. The logic is `shelly_ota/compile.py`.
- `build --compile` checks a YAML that gets its `esp32:` block from `packages:` or `!include` (also `github://`): if the file has none, ESPHome puts the config together (`esphome config`) and the check runs on that, before the compile. Docker mounts the whole git repository of the YAML, so includes next to it are found. `--esphome-yaml` alone still reads the file as it is and now says so when it finds only `packages:`.
- `pyproject.toml` for development: `pip install -e .[ble]` installs `pyyaml` and `bleak`. The tool still runs from the checkout as `python ota.py`; `requirements*.txt` stay.

### Changed
- `S1PMG3` (1PM Gen3) is partly checked (🟡) and `S2PMG3` has two more units (thanks to [WulffTech](https://github.com/WulffTech)): one 1PM and two 2PM Gen3 went from Shelly 2.0.1 to ESPHome 2026.9.0 over OTA without UART, stable across reboots, relays stay off, ESPHome OTA afterwards works. They used their own tooling with the same package mechanism, not `ota.py`, so the 1PM stays 🟡. The report also shows that Shelly's installer writes the `pt` part of a package unconditionally. Documentation only, not breaking.
- `S2PMG3` (2PM Gen3) is confirmed on a real device ([#92](https://github.com/oxynatOr/free-shelly-ota/issues/92), thanks to [majoto85](https://github.com/majoto85)): OTA from Shelly 1.4.99 with ESPHome's bootloader, then a regular ESPHome OTA. Relays and meter not reported.
- Device pages: the "Before you start" checklist is a real task list (`- [ ]`, one item per line) instead of one line with `☐` signs. Documentation only, not a breaking change; `tests/test_readme.py` guards the new format.
- `S1G3` (Shelly 1 Gen3) goes from 🧪 to ✅ on the device page, in the README table and in the credits: a device report ([#98](https://github.com/oxynatOr/free-shelly-ota/issues/98), thanks to [chusovich](https://github.com/chusovich)) with two devices flashed over OTA from stock 1.4.0 (loader 1.0.1) and a later ESPHome OTA. Documentation only, not a breaking change: no profile, package or command changed.
- The `esp32:` snippet of the 39 device pages no longer has `COMPILER_OPTIMIZATION_SIZE: y` under `sdkconfig_options`. ESP-IDF ignored the line and logged "ignoring malformed line" on every build; with the `CONFIG_` prefix or with ESPHome's own `compiler_optimization: SIZE` the app is exactly as large (838 482 bytes on the Plug S Gen3), because ESPHome already builds for size. **Not breaking:** a config that still has the line builds the same. The "app image is larger than the slot" error of `build` no longer recommends that line; it names fewer components and less logging instead.

### Removed
- Profile `BluGwG3` (BLU Gateway Gen3), its stock CSV and device page. The BLU Gateway is a gateway: it connects Shelly BLU (Bluetooth) devices to the network and controls them, so an ESPHome image would take that job away and give nothing back. The profile had no report (🧪). **Breaking for anyone who used it:** `ota.py fetch`, `build`, `send`, `restore` and `devkit` no longer know `BluGwG3`. The profile count stays 43 (`PlugMG3-beta` was added). A cached `fw/shelly/BluGwG3` folder can be deleted.

### Fixed
- `send` no longer waits for a reverse lookup of its own address before it starts the web server: Python's `HTTPServer` calls `socket.getfqdn()` for a name nothing uses, and on a slow resolver (a VPN, an unreachable DNS server) that held `send` up for 12 seconds and more. Visible only as a shorter start; nothing else changes.

## [0.6.0] - 2026-10-24

This is a pre-release: 23 of the 43 profiles are only built and verified (🧪), and seven more have been through the update on a dev board but not on the device.

### Summary
- **25 new Gen3 and Gen4 profiles** (43 in total). Seven of them have been through the whole update on a dev board (🔬); the others only build and verify (🧪).
- **`ota.py devkit`** writes a flash image of a package for a dev board; **`ota.py ble`** gives a device without Wi-Fi (the Zigbee firmware) its Wi-Fi over Bluetooth. Both are new and were seen on one board only.
- **`send` and `restore`:** the progress line shows the time left, a slow download extends the wait on its own (`--max-wait`), and `restore` prints one note instead of three.
- **`build`** warns if the image was built without `allow_partition_access`.
- **README and device pages:** the README lists only the devices that ran on real hardware; the full list, the ESPHome device page links and a Note column are in `docs/devices/README.md`. The device pages are shorter.

### Added
- `Mini1PMG4` device page: a Pins section with the button (GPIO22), the BL0942 UART (RX 19, TX 20, 9600 8N1) and its IRQ input (GPIO18), **read from the stock firmware with a disassembler and not
  confirmed on a device** (marked on the page, with how sure each pin is). Relay and LED pins were not read.
- `ota.py ble scan|info|call|wifi`: talk to a Shelly over Bluetooth LE (its RPC channel), mainly to give a device without Wi-Fi its Wi-Fi (`ble wifi SSID -`, then `send` with
  the printed address). Found on the Mini 1PM Gen4 Zigbee firmware on a dev board: no Wi-Fi, no access point, `provision: pending`. The logic is `shelly_ota/ble.py`, `bleak` is optional
  (`requirements-ble.txt`, imported only when `ble` runs). Tested against a fake connection (framing, chunking, errors); on hardware only on that one board.
- `build` also checks the image itself for `allow_partition_access: true` (ESPHome's "Partition access allowed" text) and warns if it is
  missing, also without `--esphome-yaml`.
- 25 profiles for Shelly Gen3 and Gen4 devices, made from the official packages, each with its partition CSV, a device page and a row in the
  README: Gen3 (ESP32-C3) `S1G3` (1), `S1PMG3` (1PM), `S2PMG3` (2PM), `S1LG3` (1L), `S2LG3` (2L), `I4G3` (i4), `DimmerG3`,
  `Dimmer0110VPMG3` (Dimmer 0/1-10V PM), `EMG3`, `S3EMG3` (3EM-63), `OutdoorPlugSG3`, `BluGwG3` (BLU Gateway); Gen4 (ESP32-C6) `S1G4`, `S1PMG4`,
  `S2PMG4`, `S1LG4`, `S2LG4`, `I4G4`, `DimmerG4`, `Dimmer0110VPMG4`, `EMG4`, `Mini1G4` (1 Mini), `MiniEMG4` (EM Mini), `PlugUSG4`, `PresenceG4`.
  Every profile sets `boot_min_version: 1.0.9`. The packages build and verify; **none was flashed on a real device yet**. The EM Gen4 has a 16 MB
  flash layout (its DevKit image needs a 16 MB board), the i4 Gen4 is only listed with the beta 2.2.0-beta1 in the update API.
- State 🔬 "DevKit-tested" (README, device pages, `docs/devkit.md`): the update ran through on a dev board with the DevKit image, not on the real
  device. `Mini1G4`, `Mini1PMG4`, `Mini1PMG4ZB`, `MiniEMG4`, `DimmerG4`, `Dimmer0110VPMG4` and `I4G4` have it, from runs on an ESP32-C6 dev board with 8 MB
  ("Seen on a board" in `docs/devkit.md`). A real device moves a profile to 🟡 or ✅.
- `PlusPlugIT` profile and device page (Shelly Plus Plug IT, SNPL-00110IT, ESP32, Gen2): confirmed on hardware by a device report, with the pins read from the stock firmware ([#83](https://github.com/oxynatOr/free-shelly-ota/issues/83)).
- `send` checks the device's Wi-Fi signal (`Wifi.GetStatus`). At -67 dBm or weaker it says what that does to the download and asks "seconds / s / c" how long to wait (Enter takes 1200 s, `s` skips, `c` cancels). If the wait runs out while the device is still taking the ZIP, `send` asks the same way instead of stopping. It never waits longer on its own: with `--yes` or `--dry-run` it only says so. The threshold is a guess from one report ([Wi-Fi signal](docs/commands.md#wi-fi-signal)).

### Changed
- The device report form lists all 43 profiles in its "Device" dropdown (it had 15, so reports for the 28 others had to use "Other"); `tests/test_labels.py` keeps it in step with the profiles.
- Device pages are shorter: "Before you start" is one line (what only applies to a model is listed under "Also"), and the three boxes (the NVS note, the warning about the way back, the request for a report) are one
  box with three bullets at the end of the page. The sentences are still the same on every page, and `tests/test_readme.py` checks that word for word.
- `restore` prints one NOTE (what it does and that a device with ESPHome does not answer) instead of three; the explanation of the slot change and the
  second NVS sentence are gone or only shown with `-v` (the WARNING with the question already says the NVS is wiped).
- The progress line (`Update [####---] 76 %`) shows an estimate of the time left (`, about 14 s left`) once 20 percentage points are done (the first real step to the current one; the installer's 0 % phase is not counted),
  measured from the speed of this run. Checked against a real log: 40 s shown at 22 % for 39 s left. Only on a terminal; a log file keeps the 10 % lines.
- `send` follows the download: from the bytes it has handed out it estimates the time left, shows `Download 31 %, about 14 min left` while the device's own
  progress line is not there, and extends the wait on its own when the device is slow but steady, with a NOTE that says so. `--max-wait SEC` (default 3600) caps
  the total; a download that stands still is not extended, and the question at the end of `--timeout` stays.
- `send`: while it waits for the update target slot (up to 8 s) a live line counts down, so the screen is not silent. The slot refusal no longer
  points to `--ignore-slot` (it stays in the docs): the message says to restore first.
- `docs/devices/README.md`: the device name in the list links to its page (the profile is plain text now) and a Note column holds what stood after the state symbol; EM Gen4 (16 MB flash layout) and i4 Gen4 (beta package only) got a note.
- Device pages `HTG3`, `Pill` and `PlusPlugS`: the pin tables were copies of the ESPHome device page and are replaced by a link to it. The pages whose pins this project checked itself (`PlugSG3`, `MiniPMG3`, `PowerStrip`) or that have no such page (`PlugMG3`, `PlugPMG3`, `DuoBulbG3`, `PlusPlugIT`, `PlusUni`) keep theirs.
- Device pages: the table at the top has a row "ESPHome device page" with the link for every device that has such a page on devices.esphome.io (16 pages; it was 8). The hint in the ESPHome config section no longer claims what the other page contains. `tests/test_readme.py` checks the row.
- The README lists only the devices that ran on real hardware (✅ and 🟡) so that its table stays short; every profile, with the DevKit-tested (🔬) and
  the untested (🧪) ones, is in `docs/devices/README.md`, which has a section "Tested on a dev board" below the full list. `tests/test_readme.py` checks
  both tables against the profiles.
- `PlusUni` page: the follow-up of the first report ([#46](https://github.com/oxynatOr/free-shelly-ota/issues/46)): the unit was fixed with one UART flash and then took OTAs, and ESPHome's "Update bootloader" over OTA worked. New pin table (analog input, counter, two inputs, two solid-state relays, LED) measured by the tester; the 1-Wire pin (GPIO13) and the reset button (GPIO32) were read from the 2.0.1 firmware and are marked as not yet measured; the firmware confirms all the measured pins. The config note says to keep `allow_partition_access: true` in the first config.
- `Mini1PMG3` page: first device report ([#82](https://github.com/oxynatOr/free-shelly-ota/issues/82)), two units from stock 1.4.0 with the 2.1.0 package run ESPHome; state 🟡 until a second OTA, the relay under load and the meter are checked. First loader 1.0.0 seen (`Boot: cur 010000ff ... update? 1`).
- `Mini1G3` page: a second report (a device in the wall): the `Boot:` lines of `restore` and of the ESPHome flash, the slot-1 case fixed by `restore` with Wi-Fi settings kept, and the NTC of the stock firmware against ESPHome on the same device. Troubleshooting and `commands.md`: `--timeout 1200` for a device on a weak Wi-Fi.
- `PowerStrip` page: the ADE7953 chip select and IRQ pins and the outlet mapping corrected from [devices.esphome.io PR #1811](https://github.com/esphome/devices.esphome.io/pull/1811)
  (chip 0, CS GPIO15, measures outlets 4+3; chip 1, CS GPIO10, outlets 2+1; IRQ GPIO5 / GPIO6), with notes on the polarity of channel B and the missing factor 4 in the readings.
- `DuoBulbG3` page: the bulb was flashed over OTA with this tool and runs; the GPIOs are still not confirmed on the hardware.

## [0.5.0] - 2026-10-22

### Added
- Log levels for `send`, `restore` and `log`: `--log-level quiet|normal|verbose|debug|raw`, `-q`, `-v`, `-vv`. They apply to the tool's own
  messages and to the device log. Default `normal` shows warnings, the key lines of the update (target slot, bootloader decision, update
  started), a progress line that updates in place (one line per 10 % without a terminal) and the result; `verbose` adds notes and every
  step, `debug` every entry on its own line, `raw` the log as it arrives (the output before levels). After a failure the last lines of the
  device log are printed whatever the level.
- `send` reads the device log while the update runs (without `--watch`): progress in %, and the device's own confirmation (`ota_success`)
  instead of only "the device downloaded the ZIP". A device error event stops `send` with its text. If the log does not reach this PC, `send`
  falls back to the old message. `--watch SEC` now waits up to SEC seconds for the confirmation (default 30 s if an update was seen)
  instead of listening for SEC seconds after the download.
- `--log-file [PATH]`: the whole run, every message and every device log entry one per line, whatever the level on the screen. Without a
  path `logs/<zip name>.send.log` (`logs/<device>.restore.log` for `restore`). This is the file for a bug report; the device-report issue
  form asks for it. `ota.py log --replay FILE` shows a saved log (or the output of `--log-level raw`) at any level, without a device.
- `shelly_ota/logview.py`: splits the device log into entries (a datagram holds several, glued together), recognises them with a table of
  rules (progress, slot, bootloader decision, eFuse notes, RPC chatter of other clients) and filters them by level. The refused eFuse writes
  that every update logs are one note, not five errors. The severity digit of an entry (0 error, 1 warning, 2 information) was read from a
  few entries and is not documented; the event name `ota_error` is assumed. Anything unknown is shown as it is.
- `send` and `restore`: the wait after a fresh start is one line that counts down in place, and the progress of the update is one line at the bottom of the screen that stays there while the log lines above it go on. Without a terminal both fall back to lines (every 30 s, every 10 %). A finished progress line is printed once (the device logs 100 % twice).
- Messages: `NOTE:`, `WARNING:` and `Error:` are wrapped to the terminal (at most 140 columns) after a punctuation mark where possible, a long message has its label alone on a line and the text indented below it, only the label is colored, and a command to copy (`python ota.py ...`) stands on a line of its own, bold. Hand-broken lines in the sources are joined first.
- `ota.py list` shows one line per device (`--details` for the revision and build ids).
- `send`, `inspect`, `devkit --zip`, `add-device` and `build --official`: a file that is not a ZIP, usually a DevKit image (`.bin`), gets a message that says what it is and which command writes it to a board, instead of a traceback.
- `send` asks for the uptime after the slot check, so a wrong slot or device no longer costs the wait first; the countdown shows in half-second steps; it says at once when the device has downloaded the ZIP.

- Recovery over UART: a section "Build your own UART adapter" (`docs/recovery-uart.md`). An ESP32 dev board with a USB-UART chip and one wire from `EN` to `GND` is enough, no FTDI stick needed:
  parts, wiring (the dev board's `RX`/`TX` are not crossed), the UART pads of the ESP32, ESP32-C3 and ESP32-C6, a check of the adapter, how to enter download mode, a table of
  typical errors, and a short note for a plain USB-to-UART module. The wiring is general ESP practice; this project did not re-run it.
### Changed
- Device pages, the README and the device-report issue form: the log lines to look for are the ones `send` shows at the default level;
  reports attach the `--log-file` file instead of the output of `send --watch`.
- `send`: error handling. A device that has only just started refuses `Shelly.Update` with HTTP 500 `Not committed`; `send` now reads the uptime
  (`Sys.GetStatus`) before the confirmation, says so and offers to wait. If the device refuses anyway it explains the refusal, offers to wait
  (`--wait SEC`, default 120) and asks for a new confirmation before every further pass (at most three; `--yes` never retries). Refusals are
  explained by their message, not by the code: `-109` is also used for the battery limit. Errors no longer repeat the long download URL.
- `send`: the warning "update target slot could not be read" says whether no UDP datagram arrived (firewall, `--log-port`, `--host`) or the log
  arrives without the slot line (usually a device that has just started). The probe waits 8 s instead of 4 s.
- `send`: the log setting of the device is only put back if it could be read first (before, a failed read could overwrite it with an empty
  value), and a refused restore is reported. Waiting for the download can be interrupted with Ctrl+C on Windows.
- `ota.py` shows a message instead of a Python traceback for Ctrl+C (exit 130), closed input, a file that is not a ZIP and other file errors.
  `rpc.RpcError` and `rpc.DeviceUnreachable` replace error-text matching in `restore`.
- Power Strip example config (`configs/shelly-power-strip-gen4/`): README and YAML name this tool instead of "ShellyOTA", the build command is relative to the
  repository root, and the slot-0 note links the Power Strip device page and "The app must land in slot 0" instead of a README section that is gone.
- `Mini1G3` is confirmed on hardware (first report, #69): flash from Shelly 1.4.4 over OTA, ESPHome OTA afterwards. Relay, button, switch input and LED pins checked; the NTC calibration of the ESPHome device page reads high on that unit. The stock firmware converts the NTC with B 3950 (read from the official 2.0.1 app), not the 3350 of that page.
- H&T Gen3 page: Shelly's update API answers per installed version, so a request without the `Shelly-Info` header showed no stable release (it
  looked like a removed one on 2026-10-10); `fetch HTG3 --from-version 1.4.4` gets the stable 2.0.1. The H&T Gen3 with display is reported to run with ESPHome.
- README header with a bigger logo; `docs/commands.md` documents `--channel` and `--from-version` of `fetch` and `build`, and `--version` of `restore`.

## [0.4.0] - 2026-10-18

### Added
- Profiles `PlusUni` (Shelly Plus Uni) and `Pro3EM` (Shelly Pro 3EM), both classic ESP32 (Gen2) made from the official 2.0.1 packages, with partition CSVs
  and device pages. The Pro 3EM has 16 MB flash (app slot `0x200000`, extra `emdata` partition), the Plus Uni 4 MB (`0x190000`). Both set
  `boot_min_version: 1.0.9` (the packages carry loader 1.0.2; the first report from a real unit, issue #46, showed 1.0.3). Packages build and verify; not tested on
  hardware. No pin tables: the ESPHome device database has no page for either device. `Pro3EMProAddon` (Pro 3EM with Pro Sensor Addon) has no profile.
- Profile `Mini1G3` (Shelly Mini 1 Gen3, the Mini 1PM Gen3 without the power meter; partition table at `0xf000`, `boot_min_version: 1.0.9`) with partition CSV and a device page. Package builds and verifies; not tested on hardware.
- Profile `PlugPMG3` (Shelly Plug PM Gen3, S3PL-30116EU; it only measures, there is no relay) with its partition CSV, generated from the official
  2.0.1 package (app slots `0x280000`, smaller than the Plug M / Plug S). The profile sets `boot_min_version: 1.0.9`: the device runs Shelly OS
  loader 1.0.3, so the default 1.0.3 was skipped and later ESPHome OTAs did not take effect. The plug was flashed over OTA with this tool (owner report, 2026-10-12); its readings are not checked, so the page says 🟡.
- Profile `MiniPMG3` (Shelly PM Mini Gen3, S3PM-001PCEU16; measures only, no relay) with partition CSV and device page, made from the official 2.1.0 package (partition table `0xf000`, app slot
  `0x280000`, `boot_min_version: 1.0.9`). Hardware-confirmed by the first external device report ([imsandli](https://github.com/imsandli)): `send` from stock 2.0.1 with ESPHome's bootloader (loader 1.0.2 replaced), ESPHome OTAs
  afterwards, BL0942 readings. The page documents the BL0942 UART pins, the RX pull-up it needs and a voltage calibration. This is not the Mini 1PM Gen3 (`Mini1PMG3`), which stays untested.
- Device page `docs/devices/PlugPMG3.md` and a README row for the Plug PM Gen3: ESPHome `esp32:` block, pin table (read from the stock 2.0.1 firmware,
  not verified in a running ESPHome), commands and a UART restore command derived from the package manifest (not run on this plug).
- `ota.py devkit PROFILE`: a flash image of a package for a dev board, so the whole update (`send`, the installer, the bootloader swap, the slot logic) can be played through on a board
  instead of a device, for every profile. It takes the cached official package or any package (`--zip`; one from `build` gives the state after an install), puts every part at the offset of
  its partition table (NVS empty, no `shelly` or `aux` data), refuses a part that does not fit its partition, overlaps, or a board with too little flash (`--flash-size`), writes
  `out/<Device>-devkit-<version>.bin` and prints the `esptool` commands; it flashes nothing itself. New page `docs/devkit.md` (board table per profile, stages, what to look for, variations,
  limits). Not run on a board yet: whether the Shelly app starts on a board that is not a Shelly is open. `tests/test_devkit.py` checks the image of every profile.
- `send` (and `restore`) ask the device to fetch `http://<this PC>:<port>/` itself (RPC `HTTP.GET`) before they send. `--dry-run` fails with the device's
  `Connection error` if it cannot reach this PC, a real `send` prints a warning and goes on, and a device without `HTTP.GET` only gets a note. Suggested by [imsandli](https://github.com/imsandli) in the
  first device report (PM Mini Gen3), where the Shelly sat in an IoT VLAN that could not reach the PC and the plain run would have ended in the 300 s timeout.
  Not run on a real device yet: the exact error reply of the device is known from the report only.
- `fetch` and `build --download` take `--from-version VER`: the update API answers per installed version (header `Shelly-Info`, found in the firmware), e.g. `--from-version 1.4.4` returns the stable 2.0.1 for the H&T Gen3 while the plain query returns only a beta.
- `fetch` and `build --download` take `--channel beta` to download the beta release from the update API (`stable` stays the default). A non-stable channel always asks the API unless `--version` is given.
- GitHub issue form **Request a new device** (model, `app` name, firmware, chip, whether you can test it; no dumps or secrets). The README links to it.
- GitHub issue forms: **Device report** (device, tool and Shelly version, method, result, `send --watch` output, with a reminder to remove
  secrets and the device cloud key) and **Bug or wrong message**. The README links to the device report.
- `.github/labels.yml` and `.github/sync_labels.py`: the issue labels as a file. The groups `type:`, `tester:`, `status:`, `area:`, `device:` and `risk:` replace GitHub's default labels; `new-device` becomes `type: device-request`, and every request also gets a `tester:` label (the answer to "Can you test it?": with UART, no UART, none), so a wish and an offer to test can be told apart. `sync_labels.py` makes GitHub match the file with `gh` (a dry run unless `--apply`; it never deletes). The three issue forms set `type: bug`, `type: device-report` and `type: device-request`: the label `device-report` the form asked for never existed on GitHub, so device reports came in without a label. `tests/test_labels.py` checks that the forms only use labels from the file.
- Index pages: `docs/README.md` (where to start, all pages, what to read when something goes wrong), `docs/devices/README.md` (all device pages with partition
  table offset and app slot size, where devices differ, what a page contains) and `devices/README.md` (the profiles, the profile keys, how to change a profile).
- `CREDITS.md`: the projects the tool learned from (as in the README), the people who tested devices and sent reports (imsandli, bobkersten), Shelly and the tooling, and how to get on or off the list. The README links to it.
- `ROADMAP.md`: what is planned (now, next, later) and where testers can help; linked from the README.
- `docs/assets/social-preview.png` (1280×640): the image for GitHub's social preview (Settings → General → Social preview; it cannot be set from the repository).
- `tests/test_readme.py`: every profile is in the README device table, the "N profiles: ✅ … 🟡 … 🧪 …" line above it matches the table, the state symbols of the README and of
  `docs/devices/README.md` agree, and every relative link, anchor and image of the README exists.
- `tests/test_readme.py` also checks that no tracked picture lies outside `docs/assets/` (the logo and the social preview): device photos belong on the ESPHome device pages.

### Changed
- `send` stops before it sends an ESPHome package that keeps Shelly's bootloader (built without `--esphome-factory`). The message is written in capitals and says what happens: Shelly's loader
  starts the ESPHome image three times, goes back to the other slot and keeps it, and only an ESPHome OTA during those starts changes that, once; after it, OTAs are written but never started
  and only UART helps (Plus Uni, issue #46). `--force` sends anyway, with the same text as a warning. The official package (`restore`, or sent by hand) is not affected. The note after
  the update no longer says "may switch back after a few restarts" and no longer points to a README section that does not exist; it is only printed for such a package, not after `restore`.
- Shelly's stable 2.1.0 (built 2026-10-14) checked for the Mini 1PM Gen3, Mini 1PM Gen4 (and Zigbee), PM Mini Gen3, Plug M, Plug PM, Plug S, Power Strip (and Zigbee) and Pro 3EM
  by comparing the packages with the cached 2.0.1 ones: bootloader, partition table and filesystem image are identical, `boot.min_version` is still 1.0.2, and the app grows by about
  7.5 kB (the Pro 3EM app shrinks by 68 kB). No profile changes. The `Official package` row of those device pages says 2.1.0 now; the hardware runs were made with 2.0.1. The
  Plug M app fills 98.8 % of its slot in 2.1.0, about 33 kB are left.
- The `ota:` block in the config examples (the README and 13 device pages) has `allow_partition_access: true` now, as the Plug M and Plug PM pages already had:
  ESPHome can then update the bootloader later (ESPHome Builder's "Update bootloader"). `tests/test_readme.py` keeps the pages that way. The `--esphome-yaml` check warns about a
  missing `allow_partition_access` with `--esphome-factory` too now (it stayed silent there before: the package carries ESPHome's bootloader, but without the entry ESPHome cannot
  update it later; changed after the Plus Uni report, issue #46); the text of the warning differs for the two cases.
- Profiles `Mini1PMG4`, `Mini1PMG4ZB`, `Pill`, `PlusPlugS` and `PowerStripZB` (revision 2): `boot_min_version: 1.0.9`. Without it the default is one patch above the official loader, 1.0.3,
  and the installer skips ESPHome's bootloader on a unit that already runs loader 1.0.3 (`update? 0`, as in the Plus Uni report [#46](https://github.com/oxynatOr/free-shelly-ota/issues/46);
  also seen on the H&T). Every profile sets 1.0.9 now and a test checks it. The new value was not run on these devices; the Plus Plug S route was confirmed with the old one.
- Profile `PlugSG3` (revision 2): `boot_min_version: 1.0.9`. The Plug S Gen3 package carries the same bootloader as the Plug M Gen3 package (byte-identical, loader 1.0.3),
  so a plug that already runs it would skip the default 1.0.3 and silently keep Shelly's bootloader. The earlier run used the default on a plug with loader 1.0.2; the new
  value is not run on a Plug S Gen3 yet.
- Profile `PlugMG3` (revision 2): `boot_min_version: 1.0.9`. The official package carries Shelly OS loader 1.0.3, so a Plug M restored from it
  would skip the default 1.0.3 and silently keep Shelly's bootloader (same cause as on the H&T and the Plug PM Gen3).
- Profile `RGBCCTBulbG3` (revision 2): `boot_min_version: 1.0.9`. After a return to stock the Multicolor Bulb runs Shelly OS loader 1.0.3, so the default
  1.0.3 would be skipped; with 1.0.9 the ESPHome bootloader was written (hardware-confirmed on a real bulb, 2026-10-11).
- Profile `DuoBulbG3` (revision 2): `boot_min_version: 1.0.9`, like the other Gen3 devices that needed it (Multicolor Bulb, same main board, loader 1.0.3 after a return to stock).
  Without it the installer may skip ESPHome's bootloader. Not run on a Duo Bulb yet.
- Profile `Mini1PMG3` (revision 2): `boot_min_version: 1.0.9`, like the other Gen3 profiles: the installed loader on the Gen3 devices seen so far was 1.0.2 or 1.0.3
  (not logged on this model yet), and a value that is not higher than the installed one is skipped. Not run on a Mini 1PM Gen3.
- Plus Uni: first device report ([#46](https://github.com/oxynatOr/free-shelly-ota/issues/46), thanks to [yasdfgr](https://github.com/yasdfgr)): flashed over OTA from stock 2.0.1 with
  `--esphome-factory`, ESPHome runs and one later ESPHome OTA took effect; further ones were written but never started. The device page, `docs/devices/README.md` and the README row go from
  🧪 to 🟡 (the counter is now 6 ✅, 4 🟡, 7 🧪), because the tester's package had `min_version` 1.0.3 (a profile that is not in this repository), which was not higher than the installed loader
  1.0.3 (`Boot: cur 010003ff ... update? 0`): ESPHome's bootloader was skipped, so the step with this profile's `boot_min_version: 1.0.9` is not checked on this model. The page records the
  log lines, the loader (1.0.3, the first seen on a Plus Uni), the `BURN BLOCK3 - OK` lines, the ESPHome warnings about `minimum_chip_revision` and `sram1_as_iram` (do not add them for the package)
  and the 7-pin UART header from Shelly's Knowledge Base (read from its drawing, not checked on a board). `docs/troubleshooting.md` (eFuse) and `CREDITS.md` follow.
- `docs/bootloader-and-slots.md` ("Without ESPHome's bootloader") and the Plug M page described Shelly's loader wrongly ("later OTAs take effect after the attempt counter runs out"). Read from the
  loader code and reproduced on a plain ESP32 test board with the Plus Uni loader: ESPHome gets three starts, the loader then goes back to the other slot and commits it, and only an ESPHome OTA that
  arrives during those starts changes that, once; later OTAs are written but never started. The UART fix in the same file gives ESPHome's bootloader address per chip (`0x1000` on the classic ESP32,
  not `0x0`) and the simpler way, the `.factory.bin` at `0x0`.
- Plug M Gen3: a second plug reported from outside (device report #54, thanks to 815rx1): stock 1.8.99 to ESPHome with the official **2.1.0** package and `--esphome-factory`,
  then two ESPHome OTAs (CLI and the Home Assistant builder). The device page records that the 2.1.0 package ran on hardware, the log lines of the run (`Boot: cur 010002ff, ..., update? 1`:
  `boot_min_version: 1.0.9` also works on a factory unit with loader 1.0.2), that relay and LED needed a power-off of about 30 s although ESPHome, Wi-Fi and the sensors ran at once,
  and that no `EFUSE write error` appeared. Bootloader and slots and the troubleshooting notes (power cycle, eFuse) got one sentence each. No profile change.
- H&T Gen3 page: Shelly's update API lists only the beta `2.2.0-beta1` for this device (the 2.0.1 release is no longer served). The page fetches it with `--channel beta`, builds
  with `--version 2.2.0-beta1`, and says that the beta has the same partition table and bootloader header as 2.0.1 but was not flashed with this tool.
- All device pages (17 profiles on 16 pages, the Mini 1PM Gen4 page covers two) have a new layout: badges for state and chip, quick links with icons, a `Fact | Value` table
  (the state and the chip are only in the badges), a "Before you start" checklist, callouts (NOTE for what was confirmed or checked, IMPORTANT for the partition table,
  TIP to start from the ESPHome device page, WARNING for the way back, TIP to send a device report), "Flash it" as numbered steps and the log lines of "What to expect" as
  a table. The device-specific text (config, pins, notes, way back) is the same; two lines moved: the first sentence of the intro on untested pages ("Not tested on
  hardware") is now the badge, and the links to the device database in the pin sources are plain text, because the link is in the table. `docs/devices/README.md`
  describes the layout.
- Device pages link the ESPHome device page where one exists: Plug S Gen3, H&T Gen3, The Pill, Plus Plug S, Power Strip 4 Gen4, PM Mini Gen3, Mini 1PM Gen3 (the database calls it
  "Shelly 1PM Mini Gen3") and Mini 1 Gen3 ("Shelly 1 Mini Gen3"). The Plug M Gen3, Plug PM Gen3, Duo Bulb Gen3, Multicolor Bulb, Mini 1PM Gen4, Plus Uni and Pro 3EM have none (sitemap checked 2026-10-16).
- Device pages: pin tables for Plug S Gen3, Duo Bulb Gen3, H&T Gen3, The Pill and Plus Plug S, taken from the ESPHome device database pages of the owner
  (and bobkersten for the Plus Plug S) and checked against the firmware where possible. The Plug S Gen3 state is plain ✅ now; the Duo Bulb pages say
  the ESPHome config runs (UART) while the OTA path is not run.
- README reworked. The device table has a `Note` column (the `State` column holds only the symbol) and a third state, 🟡 = flashed on a real device, but part of the chain
  or of the function is not checked: Plug PM Gen3 (readings), Power Strip (outlets) and Duo Bulb Gen3 (OTA not run) move there from ✅/🧪; the legend and the State lines of
  `docs/devices/README.md` and those three device pages follow. The non-affiliation text is a NOTE next to the WARNING instead of part of it, the Quick start goes
  in working order (config, compile, `fetch`/`build`/`send`), explains `--insecure`, uses `--ip` (the default `192.168.33.1` is only right on the Shelly's own access point),
  says to copy the partition CSV next to the YAML, adds the web-server note to the CAUTION and comes before "Another device?". The intro lists the three commands instead of one long
  sentence, says "no UART needed to install" next to "keep UART ready as your way back" and has a small diagram (Mermaid) of what goes into `build` and what `send` delivers.
  A summary line above the device table counts the states. The header has the logo (`docs/assets/logo.png`) in front of the title, the tagline below, then
  the badges and a row of links to the main sections; the badges are status, version, issues and license in a flat style (stars and forks removed, `WIP` in the title replaced
  by the status badge).
- README: "Another device?" is a section of its own (request it, make a profile yourself, send a device report) instead of one
  sentence under the device table.
- The pages outside the README and the device pages have the same frame as those: a navigation row that starts with `← README`, a row of links to the sections, callouts (NOTE, TIP, IMPORTANT, WARNING, CAUTION) for what must not be missed, tables where a list of cases was, and related links at the end. This covers `docs/*.md`, `devices/README.md`, `ROADMAP.md` and `CREDITS.md`; `docs/troubleshooting.md` groups its sections (sending and building, after the update, background), `docs/versions.md` has one heading per kind of version, `docs/bootloader-and-slots.md` starts with a table of the four questions. Headings keep their text, so every existing link and anchor still works. `tests/test_readme.py` checks the frame (title, navigation row, no emoji in headings, known callout types, links and anchors).
- `ota.py -h` and the help of every command are easier to scan. The top-level help lists the commands in the groups of `docs/commands.md` (Prepare, Build, Deploy,
  Tools), a typical run, what to know before flashing and the device names once. Each command has a short usage line, and its options are grouped by topic (`send`:
  the Shelly, this PC, what to do; `build`: app and bootloader, secrets, output, parts, base firmware). Long option texts are shorter and point to
  `docs/commands.md`. Options, defaults and behaviour are unchanged; `--color` shows `WHEN` in the usage. `tests/test_help.py` checks that every command is in a group, has a
  working `-h` and that no help line is wider than the terminal.
- `build` stops when the automatically named output already exists (`--force` replaces it; `--tag LABEL` or `-o ZIP` give another name). A second build on the same day used to replace the
  first package silently, which may already be on a device. A name given with `-o` is still replaced without `--force`. `build --dry-run` reports it as a note instead of stopping.
- `tests/test_readme.py` also checks the device pages: the standard sections in order, the state badge against the README, the profile in the commands, and all
  relative links and anchors.
- `docs/commands.md` documents `add-device`, `inspect`, `clean` and `partition-csv`.
- `docs/commands.md` and the note `restore` prints: the official package *may* reset NVS (a PM Mini Gen3 going from 2.0.1 to 2.0.1 kept Wi-Fi and settings).
  `docs/troubleshooting.md`: the eFuse note also lists `EFUSE write error bit[1]: 5636` after `Incoming fw signatures: 00` on a PM Mini Gen3 (update and ESPHome were fine).
  Both from the first device report by [imsandli](https://github.com/imsandli).
- Recovery over UART: the ESP32-C3 command for the Plug M Gen3 (restored from ESPHome, boot log reviewed), and a note that pushing the
  official app image over ESPHome OTA is not a way back (the Shelly app cannot read ESP-IDF's `otadata`).
- `ROADMAP.md`: the items of "Now" that are done (Plug S Gen3 `boot_min_version`, the `compatible` list, the 2.1.0 check, the Mini 1 Gen3 profile, the decision against a `Pro3EMProAddon` profile, the description of the route without ESPHome's bootloader) moved to a new "Done" table with their pull requests; the state date and the count of untested devices are current.

### Fixed
- `build --dry-run` no longer touches an existing package. It built to the real output path and deleted it afterwards, so a dry run to check another config on the same day (same
  automatic name `<Device>-firmware.ota-<date>.zip`, as ESPHome always names the app `firmware.ota.bin`) replaced and removed the package that had just been built and flashed, and left its
  `.sha256` and `.report.json` behind. The dry run now builds in a scratch directory and prints `DRY RUN, nothing written`. Reported with a Plug M Gen3 build.
- `send` no longer blames the firewall when the device's log works but does not name an app slot. The Plug M Gen3 on stock 1.8.99 logs `Storing core dumps to scratch (0x720000)`
  instead of `app_N`; `send` showed "the update target slot could not be read (UDP log blocked? ...)" although the datagrams arrived. It now says that this firmware does not reveal the
  target slot before the update, names the line it saw and points to `Will write to slot N` in the `--watch` log. Still only a warning: the slot is unknown, so nothing is refused. The installer
  wrote to slot 0 there (device running from slot 1), which the Plug M Gen3 page and [Bootloader and slots](docs/bootloader-and-slots.md#the-app-must-land-in-slot-0) now record.
  `probe_target_slot()` returns a `SlotProbe(slot, core_dump_target)` instead of an `int | None`. Found in a device report.
- `send --watch` / `restore --watch`: the closing note "no separate bootloader update is needed" was printed even when the device log said `Boot: cur ..., min ..., update? 0` (issue #46, Plus Uni). Now the log line is parsed: with a package that replaces Shelly's bootloader and `update? 0`, a WARNING says ESPHome's bootloader was not written (cur and min as versions, e.g. 010003ff = 1.0.3) and to build again with a higher `--boot-min-version` or `boot_min_version:`, and the note is left out. With `--watch` the note now comes after the listening time. Without `--watch` the tool cannot see the line and the note is unchanged.
- Without `--version`, `build`, `send`, `restore`, `fetch` and `partition-csv` took the highest cached version, and a downloaded pre-release such as `2.2.0-beta1`
  sorted above the stable `2.0.1`, so the beta would have been used silently. The default is now the newest stable cached version; a pre-release needs
  `--version`, or is used only when it is all that is cached.
- `send` read the package's `compatible` value as one pattern, so a comma separated list never matched. The Pro 3EM package says
  `Pro3EM,Pro3EMProAddon`, and a unit that reports `Pro3EMProAddon` stopped at the model check. The value is split at the commas now and every pattern is
  tried; such a unit gets the note "matches the package's compatible pattern" and goes on. No separate `Pro3EMProAddon` profile (not needed for this).

### Removed
- The `configs/` folder (example ESPHome configs for the Power Strip 4 Gen4 and the Multicolor Bulb E27 Gen3, with the light packages and pin notes; added in 0.3.0): device
  configs belong to the ESPHome device pages and to [`oxynatOr/esphome-configs`](https://github.com/oxynatOr/esphome-configs), not to the tool that installs the firmware.
  The Power Strip and Multicolor Bulb pages and `docs/README.md` no longer point into this repository. The files stay in the git history and in the tags `v0.3.0` and
  `v0.3.1`. The Multicolor Bulb config had the colour temperature light `rgbw_ct_table` (component of `oxynatOr/esphome-kp18058`) and eight optional light packages;
  they, the Power Strip config and a Duo Bulb config are in `oxynatOr/esphome-configs` now. The device pages carry no photos either: pictures belong on the ESPHome device page (`docs/devices/README.md` says so).
- Profile `Cury` (Shelly Cury), its partition CSV and device page (added in 0.3.1): the device has an NFC reader, regulated heaters and a
  voltage doubler that ESPHome cannot drive, and its pins are not decoded, so it is not a useful target. It is parked outside the repository.

## [0.3.1] - 2026-10-06

### Added
- Profile `Cury` (Shelly Cury) with partition CSV and a device page. Package builds and verifies; not tested on hardware.
- Profile `Pill` (Shelly The Pill) with partition CSV and a device page. Package builds and verifies; not tested on hardware. Reported: the USB-C port exposes USB Serial/JTAG, so it can be flashed and recovered with esptool.
- Profile `Mini1PMG3` (Shelly Mini 1PM Gen3, partition table at `0xf000`) with partition CSV and a device page. Package builds and verifies; not tested on hardware.
- Profiles `Mini1PMG4` and `Mini1PMG4ZB` (Shelly Mini 1PM Gen4, Zigbee variant via `parent:`) with partition CSVs and a device page. Package builds and verifies; not tested on hardware.

## [0.3.0] - 2026-10-06

### Added
- `PlugSG3` (Plug S Gen3) is hardware-confirmed: `send` with `--esphome-factory`, ESPHome runs (base config without relay or metering).
- `RGBCCTBulbG3` (Multicolor Bulb Gen3): `send` with `--esphome-factory` ran through and ESPHome runs. The light itself is not confirmed.
- `PowerStrip` is hardware-confirmed (ESPHome boots with ESPHome's bootloader). Its profile sets `boot_min_version: 1.0.9`.
- Profile `PlusPlugS` (Shelly Plus Plug S, classic ESP32, Gen2) with partition CSV. Support for the classic ESP32: chip id 0,
  bootloader at `0x1000` (from the manifest), partition table at ESP-IDF's default `0x8000` (the ESPHome offset option may stay
  unset). Hardware-confirmed on a Plus Plug S V2 without UART: `restore`, then `send` (target slot 0), ESPHome booted and an
  ESPHome OTA took effect. UART recovery from the official package brought the bricked unit back to Shelly OS beforehand.
- README: "Recovery over UART".
- `send` checks the update target slot before sending a package that replaces the bootloader: it reads the device's
  `Storing core dumps to app_N` log line (briefly switching on the UDP log), refuses if N is not 0 (ESPHome's bootloader starts
  `app_0`) and points to `ota.py restore`; `--ignore-slot` overrides. Also shown by `--dry-run`.
- README: Plus Plug S (Gen2) install notes: the installer wrote the app to slot 1, ESPHome's bootloader started `app_0`, and
  `ota.py restore` (official package) put Shelly's bootloader back over OTA, after which the next `send` targeted slot 0. A UART
  `otadata` entry that selects `app_1` is documented as a fallback. Also: the ESPHome build must use the 80 MHz flash header
  (`CONFIG_ESPTOOLPY_FLASHFREQ_80M`), otherwise `build` refuses to replace the bootloader.
- Colored messages (`shelly_ota/ui.py`): yellow warnings, orange critical warnings, red errors, green success, cyan notes, dimmed
  device log lines. Only in a terminal; `NO_COLOR` and `--color auto|always|never` (before the command) control it. The
  words WARNING/NOTE/Error/OK stay in the text.
- Versions you can tell apart (`shelly_ota/buildinfo.py`): `--version` and a first line `free-shelly-ota <version (branch, git
  describe, date)>` on every command; the build report records the tool state, the profile name and revision and the build options
  (flags only); `send` prints the package's origin and notes a profile that changed since the build.
- Profile revisions: each `devices/*.yaml` has a `revision:`; `devices/profiles.lock` and the new `ota.py profiles` command (with
  `--update-lock`) guard against changing a profile without raising it; `list` shows the revision; `add-device` writes
  `revision: 1`.
- Documentation: the README is short now (device table, quick start, links); the rest moved to `docs/` with one page per
  device (`docs/devices/<Profile>.md`: ESPHome config, commands, log lines, pitfalls) and pages for commands, bootloader and
  slots, troubleshooting, recovery over UART, credential check and versions.

### Changed
- `send` notes that ESPHome's bootloader starts `app_0`, so the installer must write to slot 0 (`Will write to slot 0` in the
  `--watch` log); README documents the failure seen on the Power Strip Gen4 (stock 1.7.99 wrote to slot 1) and the fix (one
  official update first).
- `build` errors about the ESPHome bootloader header, the partition layout, a `.factory.bin` from another build, a wrong chip and
  an app that is too big now show both values in plain words (for example "4 MB, 40 MHz (0x20)" against "4 MB, 80 MHz (0x2f)")
  and a "Fix:" line naming the ESPHome setting that worked on the tested devices.
- README status lists the six hardware-confirmed devices.
- Messages checked for Gen2/Gen3/Gen4: removed the `slot 0` warning in `send` (it was wrong for H&T and Plus Plug S and clashed
  with the target-slot check; `send` now prints "reported slot" instead); the bootloader notes no longer say "confirmed on the
  Plug M Gen3 only"; the plain-package hint explains Shelly's uncommitted-boot counter instead of "keep UART ready";
  `--boot-min-version` help names the profile default and the `Boot: cur ... update?` log line; `list` says `app size`
  (it printed `slot=` for a size); `model=None` is shown as `n/a`; docstrings and README intro name Gen2/3/4.

## [0.2.0] - 2026-10-05

### Added
- `partition-csv` command and `partitions/<Device>-stock.csv` for every profile: the stock partition table as ESPHome
  `partitions:` CSV (so the README's Quick start works without extra files).
- Profile `HTG3` (Shelly H&T Gen3), hardware-confirmed with `--esphome-factory`.
- Optional profile key `pt_offset` (partition table address, default `0x10000`); `add-device` reads it from the package.
  The H&T Gen3 keeps its table at `0xf000`.

- Optional profile key `boot_min_version`: default for `--boot-min-version` with `--esphome-factory`. `HTG3` sets `1.0.9`:
  the H&T Gen3 installer reports an installed bootloader 1.0.3, so the generic "one patch above the package" (1.0.3) was
  skipped and Shelly's loader stayed. With 1.0.9 the bootloader is written (hardware-confirmed).

### Changed
- README: notes on the web server exposure during `send`, the UDP firewall for `--watch`, and the eFuse write errors seen on
  the H&T Gen3; the HTG3 row now covers an ESPHome OTA after the package install (confirmed).
- README: how to check that the bootloader was really replaced (installer log `Boot: cur ... min ...`, UART boot log) and
  the UART fix.

### Removed
- Profiles `PlugUSG4` and `PlugUSG4ZB` (Plug US Gen4): cannot be tested by the maintainer. `add-device` still creates
  profiles for them. The variant tests now use `PowerStrip` / `PowerStripZB`.

### Fixed
- `--esphome-yaml` check no longer hard-codes the partition table offset 0x10000; it uses the profile's `pt_offset`.
- RPC errors now include the device's answer (e.g. `OTA not allowed (Battery below 30 percent. )`) instead of only the HTTP code.

## [0.1.0] - 2026-10-04
First release (experimental).

### Added
- `build`, `send`, `restore`, `log`, `fetch`, `add-device`, `inspect`, `list`, `clean`; profiles for 8 Shelly Gen3/Gen4 devices
  (hardware-confirmed: Plug M Gen3 only).
- `--esphome-factory` / `--boot-min-version`: ship ESPHome's bootloader and a clean `otadata` in the package.
- Credential check: `build` compares the image with the ESPHome config and `secrets.yaml`, warns with the names of matches,
  records them in the report; `--secrets FILE`, `--fail-on-secrets`; `send` and `inspect` warn again.
- `ota.py --version`, `tool_version` in the build report.

### Changed
- Help texts and post-flash messages describe the bootloader options and their risk; the follow-up "update the bootloader"
  note and the `allow_partition_access` warning no longer appear when the package already carries ESPHome's bootloader.
- `send` says when it could not check whether the bootloader is replaced (no cached official ZIP).
