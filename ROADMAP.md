# Roadmap

[← README](README.md) · [Documentation](docs/README.md) · [CHANGELOG](CHANGELOG.md) · [Credits](CREDITS.md)

[🎯 Now](#now) · [⏭️ Next](#next) · [💭 Later](#later-ideas-not-planned) · [🙋 Help wanted](#help-wanted) · [✅ Done](#done)

Where the project stands and where it goes next.

> [!NOTE]
> This is a plan, not a promise: the order changes when a test report or a new device shows up.
> State: 2026-10-28, at release 0.7.0 (see the [CHANGELOG](CHANGELOG.md)).

## Now

- **Dev board test bench.** `ota.py devkit` writes a flash image of a package, so the whole update (`send`, the installer, the bootloader swap, the slot logic) can be played
  through on a dev board instead of a device, for any profile. Seven Gen4 profiles have been through the whole update on an ESP32-C6 board with 8 MB. The Shelly app does start on a board
  that is not a Shelly, but it checks the flash size and stops on a board with less than the device has (8 MB), so a 4 MB ESP32-C3 board is too small.
  What the boards showed goes into [Test on a dev board](docs/devkit.md#seen-on-a-board).
- **Zigbee units without Wi-Fi.** The Zigbee firmware has no network and no access point; `ota.py ble wifi` (Bluetooth RPC) gave a Mini 1PM Gen4 on a dev board its Wi-Fi, and the update ran after that.
  Still open: a real Zigbee unit (Mini 1PM Gen4, Power Strip) over Bluetooth and the whole update.

## Next

- **Hardware checks** (these turn 🟡 into ✅): the Plug PM Gen3 readings (and the BL0942 RX pull-up found on the PM Mini),
  the Power Strip outlets and metering, the Duo Bulb's GPIOs (it runs over OTA, the pins are from the stock dump), the Plus Uni with this profile's `boot_min_version` 1.0.9
  (the first report ran with 1.0.3 and kept Shelly's loader) and its pins, the Mini 1PM Gen4 pins (read from the stock firmware, not measured).
- **Multicolor Bulb.** The colour temperature light (`rgbw_ct_table`, published in `oxynatOr/esphome-kp18058` since 2026-10-15) runs on the
  bulb. Still open: its colours against the stock UI at 2700, 4000 and 6500 K, the optional light packages (daylight, scenes, wake-up alarm,
  night light). The bulb config lives in `oxynatOr/esphome-configs` and pins the published commit of the component; the bulb first ran an earlier local build of it.
- **esphome-configs 0.2.0.** The Power Strip, Multicolor Bulb and Duo Bulb projects there point to `@v0.1.0`, which does not contain them; they can be adopted
  from the dashboard after the next tag (`scripts/bump-tag.py`).
- **Device pages on devices.esphome.io** for the Plug M and Plug PM (new pages) and a correction of the Plug S page, each with the OTA route via this tool
  (the PM Mini Gen3 and the Mini 1 Gen3 have pages now). A page for the Multicolor Bulb can follow now that its light component is published; the Duo Bulb when its hardware is checked.
- **More rows on the device pages.** A Tasmota row (templates on blakadder, devices that [mgos32-to-tasmota32](https://github.com/tasmota/mgos32-to-tasmota32) lists as tested) and an
  "Example config" row with the ready-made config in `oxynatOr/esphome-configs`, once that repo is finished.
- **More of the test bench.** The profiles that need other boards (the ESP32-C3 devices need a board with 8 MB; the EM Gen4 (ESP32-C6) and the Pro 3EM (classic ESP32) 16 MB), and a plan B if the Shelly app wants its `shelly` partition:
  one taken from an own dump, never shared.
- **A package from `build --compile` on a real Shelly.** It is the same as one built by hand and went through the whole update on a dev board (ESPHome 2026.10.0), but not yet on a device. `esphome config` (for configs with `packages:`) was tried through Docker only, not through the native command.
- **The `esp32:` snippet on the device pages.** `COMPILER_OPTIMIZATION_SIZE: y` under `sdkconfig_options` does nothing: ESP-IDF ignores it with a warning ("ignoring malformed line"); with the `CONFIG_` prefix the warning goes and the app stays the same size (838 482 bytes on the Plug S Gen3), because ESPHome already builds for size. Drop the line from all device pages and the DevKit configs, and from the "app too large" message of `build`, which recommends it as a fix.
- **Tests without the firmware cache.** Many tests need the local `fw/` folder, which is not in git. Small synthetic packages as
  fixtures, then a GitHub Actions run on every pull request.
- **More devices on request.** Whatever the "Request a new device" form brings.

## Later (ideas, not planned)

- **A package without Shelly's ZIP** (`build --standalone`, H&T Gen3 first). The package is built from the facts of the official one that the profile keeps (version, build id, bootloader header) and the partition CSV, with ESPHome's bootloader, `otadata` and partition table and an erased filesystem image, so it holds no file from Shelly and can be shared. Not run on a device yet, and no longer needed for the H&T Gen3: the 2.0.1 package is still served when the request carries the `Shelly-Info` header (`fetch --from-version`).
- **Shelly Gen1 (ESP8266).** Many old devices (Shelly 1, 1PM, 2.5, Plug S, ...) have no way in except UART, and their owners cannot open them. The official Gen1 package is a Mongoose OS ZIP with a `manifest.json` and an rboot layout with two app slots, updated over HTTP (`/ota?url=`), so an OTA route looks possible. Open: whether an ESPHome image can start from an rboot slot, whether the bootloader part can be replaced, and whether the current stock firmware accepts an unsigned package; the first step would be a bench test on an ESP8266 board with 2 MB flash. Needs its own sender (no RPC on Gen1) and a device and a tester with UART ([#47](https://github.com/oxynatOr/free-shelly-ota/issues/47)). If it works, the README can say all generations instead of Gen2 to Gen4.
- **Tasmota support.** Pack a Tasmota image into the official package instead of an ESPHome one, the way
  [tasmota/mgos32-to-tasmota32](https://github.com/tasmota/mgos32-to-tasmota32) converts Shelly packages. Open questions: which of the
  profiles it fits (ESP32, ESP32-C3, ESP32-C6), the partition table and bootloader Tasmota needs, and the way back. Needs a device and a
  tester who runs Tasmota.
- **ESPHome back to Shelly, over the network.** A dead end so far: the Shelly app cannot read ESP-IDF's `otadata`, so pushing the
  official app image through an ESPHome OTA does not bring Shelly OS back. `restore` works only while Shelly firmware still runs;
  after that only UART helps ([Recovery over UART](docs/recovery-uart.md)). Revisit only with new findings.
- **ESPHome as a Zigbee or Matter device on the ESP32-C6 units.** The C6 has the radio, the ESP32-C3 devices do not. Whether an ESPHome stack runs there, which pins it needs and where the stock firmware keeps its
  pairing data (Matter code, QR) is not known; nothing was tried.
- **Telling the update slot without the device log.** On the one Zigbee dev board, `Shelly.GetDeviceInfo` reported the running slot and the update went to the other one (slot 0 running: target 1; slot 1: target 0).
  That could let `send` check the slot when the log does not reach this PC. One board only, so it stays an idea until other devices agree.
- **The Bluetooth step in Home Assistant** (a component or a bridge using the same RPC calls as `shelly_ota/ble.py`), for people without a Bluetooth adapter in the PC (an ESPHome Bluetooth proxy). Only if there is demand.
- A command that prints the `esp32:` block of a profile, and device pages generated from one template with the shared sentences, so they cannot drift (a test checks the safety sentences now).
- Find the device on the network (mDNS) instead of `--ip`.
- Install with `pipx`. A `pyproject.toml` exists since 0.7.0, for development (`pip install -e .[ble]`); the tool still reads its profiles and `fw/` from the checkout.
- A `shelly-ota.toml` with defaults (`--ip`, profile, log level, compile runner and image), only if wanted.
- The ESPHome dashboard or Home Assistant add-on as a way to compile: ESPHome's own protocol for it is not documented, so `build --compile` calls the command line.

## Help wanted

| What | Who can help | Where |
| --- | --- | --- |
| Flash a 🧪 device and report the `--log-file` file | Owners of the 🧪 devices in the [list](docs/devices/README.md#devices), 23 so far | [Device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml) |
| Pro 3EM: a first hardware report and its pins. Plus Uni: its pins on the hardware (so far only read from the stock firmware) | Owners | Issues [#36](https://github.com/oxynatOr/free-shelly-ota/issues/36) and [#46](https://github.com/oxynatOr/free-shelly-ota/issues/46) |
| A Zigbee unit (Mini 1PM Gen4 Zigbee, Power Strip 4 Gen4 Zigbee): give it a Wi-Fi with `ota.py ble wifi`, then flash it, and tell us how it went | Owners | [`ble`](docs/commands.md#ble), [Device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml) |
| A board for the rest of the test bench: ESP32-C3 with 8 MB, ESP32-C6 and classic ESP32 with 16 MB | Anyone with such a board | [Which board](docs/devkit.md#which-board) |
| Plug PM Gen3: readings against a reference meter | Owners | [Device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml) |
| Your device is missing | Anyone | [Request a new device](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=new-device.yml) |

## Done

Items that stood under "Now" in an earlier version of this page.

| What | Pull request |
| --- | --- |
| Plug S Gen3: `boot_min_version` 1.0.9, like the Plug M, Plug PM and Multicolor Bulb profiles | [#48](https://github.com/oxynatOr/free-shelly-ota/pull/48) |
| `send` splits a comma separated `compatible` list into patterns | [#49](https://github.com/oxynatOr/free-shelly-ota/pull/49) |
| Official package 2.1.0 compared with 2.0.1 for the profiles with a cached package, `Official package` rows updated | [#50](https://github.com/oxynatOr/free-shelly-ota/pull/50) |
| Mini 1 Gen3: profile and device page | [#52](https://github.com/oxynatOr/free-shelly-ota/pull/52) |
| Pro 3EM add-on (`Pro3EMProAddon`): no profile of its own, the `compatible` list covers it | [#49](https://github.com/oxynatOr/free-shelly-ota/pull/49) |
| `send` stops before it sends a package that keeps Shelly's bootloader; the route without ESPHome's bootloader is described as the loader works | [#64](https://github.com/oxynatOr/free-shelly-ota/pull/64), [#65](https://github.com/oxynatOr/free-shelly-ota/pull/65) |
| Release 0.4.0 | [CHANGELOG](CHANGELOG.md#040---2026-10-18) |
| Log levels, progress and error handling for `send`, `restore` and `log`; Mini 1 Gen3 confirmed on hardware; a guide for a home-made UART adapter | [CHANGELOG](CHANGELOG.md#050---2026-10-22) |
| Release 0.5.0 | [CHANGELOG](CHANGELOG.md#050---2026-10-22) |
| 25 profiles for Gen3 and Gen4 devices (43 in total), the 🔬 state and the dev board test bench, `ota.py ble`, the time left in the progress line, shorter device pages | [CHANGELOG](CHANGELOG.md#060---2026-10-24) |
| Release 0.6.0 (pre-release) | [CHANGELOG](CHANGELOG.md#060---2026-10-24) |
| `build --compile` (ESPHome command or Docker with a cache volume, also for `packages:` and `!include`), `pyproject.toml` for development, `PlugMG3-beta` and the layout check, `BluGwG3` removed | [CHANGELOG](CHANGELOG.md#070---2026-10-28) |
| Release 0.7.0 | [CHANGELOG](CHANGELOG.md#070---2026-10-28) |
