# Research: Shelly Gen1 (ESP8266)

[← README](../../README.md) · [Documentation](../README.md) · [Roadmap](../../ROADMAP.md)

Working notes for [issue #47](https://github.com/oxynatOr/free-shelly-ota/issues/47) (Shelly 1, Gen1). Only one thing here has run on a real Shelly (the Plug S test image, see [From a real Plug S](#results-on-a-dev-board)): the first sections
are what the official package and public sources show, and [Results on a dev board](#results-on-a-dev-board) is what an ESP8266 dev board did (October 2026). Not a promise, and not part of the supported devices.

## Why it matters

Gen1 devices (Shelly 1, 1PM, 2.5, Plug S, Dimmer, Bulb, ...) are old, many are in the wall, and their owners cannot solder or hold pogo pins on a PCB.
An OTA route would help exactly those people. If it works, the README could say "all Shelly generations" instead of "Gen2 to Gen4".
That sentence only becomes true when one Gen1 device has run the whole chain.

## What the official Shelly 1 package contains

`http://firmware.shelly.cloud/gen1/SHSW-1.zip` (880 214 bytes, build `20230913-112003/v1.14.0-gcb84623`) holds one folder `switch1-1.0/`:

| File | Size | Part in `manifest.json` |
| --- | --- | --- |
| `rboot.bin` | 2 320 | `boot`, address `0x0`, **`update: false`** |
| (none) | 4 096 | `boot_cfg`, address `0x1000`, filled with `0xFF` (the rboot config: which slot starts) |
| `switch1.bin` | 613 504 | `fw`, address `0x8000` and `addr1` `0x108000` (two app slots) |
| `fs.bin` | 262 144 | `fs`, address `0xBB000` and `addr1` `0x1BB000` |
| (none) | 4 096 | `rf_cal_data`, address `0x1FB000` |
| `esp_init_data_default_v08.bin` | 128 | `sys_params`, address `0x1FC000` |

`platform` is `esp8266`, manifest `version` is `1.0`. So the layout is a 2 MB flash with **rboot** and two app slots of `0xB3000` (733 184 bytes) each; the stock app
uses 613 504 of them. There is no `otadata` and no ESP-IDF partition table.

The app image starts with `0xEA` (rboot's flash-mapped format, 4 segments); `rboot.bin` itself starts with `0xE9`.

## How the update works (read from the app)

The Shelly app is **Mongoose OS** (paths such as `/mongoose-os/platforms/esp8266/src/esp_flash_writer.c`, `ota-common/src/esp8266/esp_ota_backend.c` and
`shelly-common/shelly_update.c` are in its strings). The strings show:

- The device fetches a ZIP from a URL (`http://<ip>/ota?url=...`) with its HTTP client and reads `manifest.json` first:
  `{name, platform, version, build_id, parts}` are required, `Invalid manifest` / `Nothing interesting in the update (wrong platform?)` otherwise.
- Each file is checked against `size` and `cs_sha1` / `cs_sha256` of the manifest, then written to the slot that is **not** running, `boot_cfg` is updated and the
  device restarts. A failed start reverts (`Update failed, reverting to ROM %d`); a new app has to commit itself (`Previous update has not been committed yet`).
- The manifest can carry signatures (`sig0` ... `sig7`, strings `Signature verified` / `Want sig ..., have ...` / `Key %d: no signature`). The stock package has none.
  **Not known:** whether the stock firmware enforces them. Third-party ZIPs are known to be accepted on stock firmware (see below), but not on 1.14 specifically.
- `Version is the same as current` aborts an update, `will not update %s with %.*s` (shelly_update.c) is a name check whose rule is not known.
- The Gen1 API is plain HTTP (`/shelly`, `/status`, `/settings`, `/ota`, `/ota/check`), not the RPC of Gen2 and later. There is no `Shelly.Update`, no `Shelly.GetDeviceInfo`.

## Precedents

- **[mgos-to-tasmota](https://github.com/yaourdt/mgos-to-tasmota)** (GPL-3.0, last push 2023-02, maintainer stopped, its download server is not guaranteed): `http://<ip>/ota?url=...zip` installs
  a small **Mongoose OS stub**. The stub then downloads Tasmota and writes it over the bootloader. So third-party ZIPs are accepted by stock Gen1 firmware, and the
  working route for a foreign firmware is **two stages**, not a direct swap of the app slot. The author warns that overwriting the bootloader over OTA can brick a device.
- **[shelly-homekit](https://github.com/juangamnik/shelly-homekit)**: a Mongoose OS firmware for Gen1, installed through the same `/ota?url=` on stock firmware. It stays inside rboot's layout.
- The reverse, Tasmota back to stock, also exists (`tasmota-to-mgos`).

## What the tool does today, and what Gen1 needs

| Area | Today (Gen2 to Gen4) | Gen1 |
| --- | --- | --- |
| Chip | ESP32, ESP32-C3, ESP32-C6 (`esp_image` checks chip id, segments) | ESP8266: other image format (`0xE9` / `0xEA`), no chip id in the header |
| Package | `manifest.json` with `boot`, `pt`, `otadata`, `nvs`, `app`, `fs` | `boot`, `boot_cfg`, `fw` (two addresses), `fs`, `rf_cal_data`, `sys_params`; sha1 **and** sha256 |
| Partition table | ESP-IDF table, `partitions/<Profile>-stock.csv` for ESPHome | none; ESPHome on ESP8266 uses Arduino's layout |
| Send | RPC `Shelly.Update?url=`, slot probe over the UDP log, progress, confirmation | HTTP `/ota?url=`; log and progress probably not available |
| Device check | `Shelly.GetDeviceInfo` (model must match) | `GET /shelly` (`type`, `fw`) |
| Way back | `restore` while Shelly firmware runs; UART | same idea with the Gen1 ZIP; UART |

## Open questions (each one needs an experiment)

1. **Can an ESPHome image run from an rboot slot?** ESPHome for ESP8266 is an Arduino build: its `firmware.bin` is made for flash address `0x0` with eboot, and its own OTA copies a new image over it.
   Whether rboot can start it from `0x8000` (it is position-dependent in the flash mapping) is not known. Test on an ESP8266 board with 2 MB flash and Shelly's `rboot.bin` and `boot_cfg`, like the DevKit image does for Gen2 and later.
2. **Is the `boot` part writable?** The stock manifest says `update: false`. If the updater honours `update: true`, a package could replace rboot with ESPHome's boot code, as the Gen2 route does. If it does not, only the two-stage route of mgos-to-tasmota is left.
3. **Signatures on 1.14.** Does the current stock firmware accept an unsigned third-party manifest? `shelly-homekit` and `mgos-to-tasmota` say yes for older firmware.
4. **Size.** An ESPHome image for a Shelly 1 has to fit into `0xB3000` (733 184 bytes) minus what ESPHome's own OTA needs afterwards. It was not measured here.
5. **Later ESPHome OTAs.** After the first install, ESPHome's OTA on ESP8266 needs free flash next to the sketch; whether the rboot layout leaves it is open.
6. **Gen1 ZIP rules.** `will not update %s with %.*s` and the manifest `name` (`switch1`): what must match.
7. **Log.** Gen1 has a debug setting; whether it can send the log over UDP like Gen2 does (for progress and the slot) is not known.

## Results on a dev board

All runs used a D1 mini (ESP8266, 4 MB flash used as 2 MB) with a stock image built from the official package of the model (rBoot, both app slots, file system, boot config, as the package lays them out). The board was joined to the device's own access point and the update was started with `http://<ip>/ota?url=` against a web server on the PC. None of this ran on a real Shelly, and the board has no relay, meter or sensor.

**What the experiments showed (answers to the open questions above):**

- **Question 1, ESPHome from an rBoot slot: yes.** A sketch linked for the slot (`irom` origin `0x40200000` plus the slot offset plus `0x10`) starts from rBoot on the D1 mini. It needs its own boot confirmation: rBoot marks a new slot unconfirmed (flag in the config sector) and reverts after a few failed starts, so the running app writes the confirmation itself some seconds after boot.
- **Question 3, signatures: not checked by the 1.14 stock updater** for the packages used here. It takes an unsigned ZIP whose manifest is complete (`name`, `platform`, `version`, `build_id`, `parts` with sizes and both hashes). The ZIP entries must be stored, not compressed (`Compressed ZIP files are not supported`).
- **The flip.** The stock updater always writes to the slot that is not running, and ESPHome lives in slot 0. So the first package lands in slot 1, does not confirm and falls back; a second package that carries the stock app moves it to slot 1; the third package then lands in slot 0. The sequence ESPHome ZIP, stock ZIP, ESPHome ZIP ends with ESPHome running from slot 0 and the stock firmware in slot 1.
- **Where the rBoot config is.** The config sector is at `0x1000` on the Shelly 1, 1PM, 1L, 2, 2.5, EM, 3EM, i3 and Uni, and at `0x7000` on the Plug S, Plug US, Plug 2, RGBW2, Bulb, Duo, Vintage, Dimmer, Dimmer 2 and H&T. A build that confirms at `0x1000` does not confirm on the second group.
- **Prototype.** The runs used an ESPHome component ([`experimental/gen1/`](https://github.com/oxynatOr/free-shelly-ota/tree/main/experimental/gen1) in this repository, Apache 2.0, experimental) that takes the layout from a partition CSV in the format of the Gen2+ stock tables, so the same kind of file describes every model. It receives a later image over TCP and installs it through a small routine in IRAM.

**Per model** (stock image of the model, chain: ESPHome ZIP, stock ZIP, ESPHome ZIP):

| Model | Config sector | Result |
| --- | --- | --- |
| Shelly 1, 1PM, 2.5, i3, Uni | `0x1000` | chain OK; boot confirmation read back on the Shelly 1 |
| Plug S, Plug US, RGBW2, Bulb, Duo, Vintage, Dimmer, Dimmer 2 | `0x7000` | chain OK; the config sector afterwards shows current slot 0, previous slot 1, unconfirmed flag 0, attempts 0, and `0x1000` stays empty |
| 1L, 2, EM, 3EM | `0x1000` | the stock image boot-loops on the bare board after switching the debug output to UART 1; needs the device hardware |
| H&T | `0x7000` | the stock image stays silent on the bare board; see below |
| Plug 2 | `0x7000`, slots at `0x100000` / `0x200000` | the stock boots; the ESPHome sketch is accepted by the updater and written to slot 0, then crashes right after rBoot starts it (`Fatal exception (0)`, IllegalInstruction). The SDK cache mapping of the second megabyte is not set. Same open problem as slot 1 of the Shelly 1 |
| first Plug (SHPLG-1) | | the package is platform `cc3200` (Texas Instruments), not ESP8266: out of scope |

**H&T pins (not confirmed).** Read from the firmware image with Ghidra, not measured: the ESP8266 talks to an STM co-processor over a bit-banged SPI (MISO `12`, MOSI `13`, SCLK `14`, CS `15`), `GPIO4` looks like its BOOT0 and `GPIO5` its reset. The temperature, humidity and button are not on the ESP8266; the STM reads them and speaks a framed protocol (sync byte, command, length, payload, XOR checksum, ACK `0x79` / NACK `0x1F`). An ESPHome firmware for the H&T would have to speak it.

**Pins read from the stock firmware.** Ghidra on the v1.14.0 apps, not measured on a device (the Plug S relay was confirmed on a real plug, see below): on the Shelly 1 the relay is `GPIO4` (output) and the switch input `GPIO5`, both hard-coded; on the Plug S the relay is `GPIO15` (hard-coded output). The level for "on" was not found, and the factory-reset pin is a config value on both. The other Plug S pins (button `GPIO13`, LEDs `GPIO0` and `GPIO2`, meter `GPIO12`/`GPIO5`/`GPIO14`) are the values of the ESPHome device page, whose configuration credits a named tester; they were not read from the firmware here. The first Plug S test image has just the relay and the button. On a real Plug S the button switched the relay with that image, which confirms `GPIO13` (button) and `GPIO15` (relay) (see below); LEDs and meter are documented on that page, but not yet tried on a plug in this project.

**Plug S on the dev board (2026-11-10).** The test image `experimental/gen1/example-plugs-test.yaml` (access point, `gen1_ota`, relay and button) went through the chain with the Plug S stock image: the stock moved to slot 1, ESPHome started from slot 0, and the rBoot config at `0x7000` read current slot 0, previous slot 1, unconfirmed flag 0, attempts 0. Relay and button were not exercised (nothing on the pins). The short case was rehearsed too: with the stock already running from slot 1 (after the flip), one ESPHome package lands in slot 0 and starts, and the config reads the same afterwards. **Way back without UART (2026-11-11, dev board).** The component got a `revert` command (`G1RV`, same password handshake, `gen1_ota.py revert`): it checks the image in the other slot, points the rBoot config at it and restarts. On the Plug S layout the stock then started from slot 1 with its own file system (about 65 kB used, as left by the update) and answered on `/shelly`; Shelly's updater put ESPHome back into slot 0 afterwards. With the unconfirmed flag set the stock treats the boot as a fresh update, tries to take over the old file system and reverts to ESPHome, so the flag stays 0 and there is no automatic fallback after a `revert`. On a real Plug S `revert` worked (2026-11-11, [report](https://github.com/oxynatOr/free-shelly-ota/issues/47#issuecomment-6810022283)): the stock came back with its settings and its WiFi connection. Installing ESPHome again through Shelly's updater after the `revert` did not work there; the cause was found on the dev board (below). The first draft of a guide for a real Plug S is [PLUGS-TEST.md](https://github.com/oxynatOr/free-shelly-ota/tree/main/experimental/gen1/PLUGS-TEST.md).

**From a real Plug S (a report in #47).** An owner read the chip with esptool: ESP8266EX, 2 MB flash, and the first 3 kB of the first app slot at `0x8000`. That is the start of the stock app (rBoot layout, no partition table), and it is not the v1.14.0 image (SDK 3.0.5, a larger image than the v1.14.0 package). The same plug reports `fw` v1.14.0 on `GET /shelly`, so the slot read was the inactive one with an older firmware, and the plug runs from the other slot. Its rBoot config (`0x7000`) then read current slot 1, previous slot 0, unconfirmed flag 0, attempts 0, so the plug runs from the second slot.

**First run on a real Plug S (2026-11-11, [report](https://github.com/oxynatOr/free-shelly-ota/issues/47#issuecomment-6807795983)).** The owner used the short case: one update with the ESPHome package through the stock updater (`/ota?url=`), no flip needed because the stock already ran from slot 1. After about 30 s the access point `plugs-test` appeared and he could join it, and pressing the button switched the relay. The log shows the relay on `GPIO15`, the button on `GPIO13` and `gen1_ota` listening on port 8267. Opening port 8267 in a browser gives `authentication failed` in the log, which is expected: it is the update receiver, not a web page. Reported in follow-ups: the rBoot config reads as confirmed (current slot 0, previous slot 1, flag 0, attempts 0), the plug comes back reliably after being unplugged several times, and the relay is off after plugging in and switched on by the button. Second round: a newer image sent with `gen1_ota.py send` over the plug's network started fine, and `revert` brought the stock firmware back with all its settings and its WiFi. Putting ESPHome back through the stock updater afterwards did not work on that plug (the stock came back). Cause (found on the dev board, 2026-11-12, after the bench reproduced the failure): after the first install through Shelly's updater byte 9 of the rBoot config sector is 1, and `revert` left it at 1. While it is 1 the stock downloads a new package, restarts, but does not write it (slot 0 stays unchanged); with byte 9 set to 0 it writes it. `revert` now clears byte 9. A plug that was reverted with an older image needs byte 9 set to 0 once over UART. Confirmed on the real plug (2026-11-13, [report](https://github.com/oxynatOr/free-shelly-ota/issues/47#issuecomment-6856467981)): after byte 9 was set to 0 once over UART (the config read `e1 01 00 01 00 02 00 00 00 01` before), the update URL installed ESPHome again, `plugs-test` appeared, and the config afterwards read `e1 01 00 00 00 02 01 00 00 01`, as on the dev board. The relay starts off, the button switches it on with an audible click, and a lamp on the plug lights, so ON in ESPHome means load on. The image of that test had no LED outputs, so no LED lights. The `GET` line did not show in the owner's web server window (not needed). Not reported yet: `revert` with the fixed image on a real plug, LEDs and meter.

**Still open:** a real Shelly (the reporter of #47 has a Shelly 1 and UART access; a Plug S owner offered to test), the second megabyte for the Plug 2, the models that boot-loop on the bare board, a later ESPHome-to-ESPHome update on the real flash layout, the "on" level of the relays on the other models, why putting ESPHome back through Shelly's updater after `revert` failed on a real Plug S, and a run on any real Gen1 model besides the Plug S.

## A possible plan

1. **Bench first, no device at risk.** ESP8266 board with 2 MB, Shelly's `rboot.bin`, `boot_cfg` and a stock slot (question 1 and 2): does ESPHome start from a slot, and does the stock updater write a package that this tool builds?
2. **A Gen1 package builder** for one profile (Shelly 1), `fw` part replaced, hashes fixed, optional `boot` swap if question 2 says yes.
3. **A Gen1 sender** over `/ota?url=` with the model check and a clear warning that there is no progress.
4. **One real device** (the reporter of #47 has a Shelly 1 and UART access) before anything is listed as supported.
5. **Other Gen1 models** as profiles, once the first one is confirmed.

If question 1 and 2 are both "no", the only route left is a two-stage stub as in mgos-to-tasmota: much more work, a GPL-3.0 starting point and a binary that has to be hosted somewhere.

## Reproduce

The numbers above come from unpacking `SHSW-1.zip` (SHA-256 `2490c3f6a9b9f243fe9e00112f22baa36f9e240cb8c9e6dca5be58d946ad146f`) and reading `switch1-1.0/manifest.json`, the image header of `switch1.bin` and the strings of the app.
The package is Shelly's file and is not part of this repository.
