# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow [Semantic Versioning](https://semver.org).

## [Unreleased]

### Changed
- Profile `PlugMG3` (revision 2): `boot_min_version: 1.0.9`. The official package carries Shelly OS loader 1.0.3, so a Plug M restored from it
  would skip the default 1.0.3 and silently keep Shelly's bootloader (same cause as on the H&T and the Plug PM Gen3).
- Recovery over UART: the ESP32-C3 command for the Plug M Gen3 (restored from ESPHome, boot log reviewed), and a note that pushing the
  official app image over ESPHome OTA is not a way back (the Shelly app cannot read ESP-IDF's `otadata`).
- Device pages: pin tables for Plug S Gen3, Duo Bulb Gen3, H&T Gen3, The Pill and Plus Plug S, taken from the ESPHome device database pages of the owner
  (and bobkersten for the Plus Plug S) and checked against the firmware where possible. The Plug S Gen3 state is plain ✅ now; the Duo Bulb pages say
  the ESPHome config runs (UART) while the OTA path is not run.
- `docs/commands.md` documents `add-device`, `inspect` and `clean`.

### Removed
- Profile `Cury` (Shelly Cury), its partition CSV and device page (added in 0.3.1): the device has an NFC reader, regulated heaters and a
  voltage doubler that ESPHome cannot drive, and its pins are not decoded, so it is not a useful target. It is parked outside the repository.

### Added
- Profile `PlugPMG3` (Shelly Plug PM Gen3, S3PL-30116EU; it only measures, there is no relay) with its partition CSV, generated from the official
  2.0.1 package (app slots `0x280000`, smaller than the Plug M / Plug S). The profile sets `boot_min_version: 1.0.9`: the device runs Shelly OS
  loader 1.0.3, so the default 1.0.3 was skipped and later ESPHome OTAs did not take effect. The hardware result of the package route is not
  recorded here yet, so there is no device page and no README row.
- GitHub issue form **Request a new device** (model, `app` name, firmware, chip, whether you can test it; no dumps or secrets). The README links to it.

### Added
- GitHub issue forms: **Device report** (device, tool and Shelly version, method, result, `send --watch` output, with a reminder to remove
  secrets and the device cloud key) and **Bug or wrong message**. The README links to the device report.

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
