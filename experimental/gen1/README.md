# gen1_ota: self-update for ESPHome on a Shelly Gen1

An ESPHome external component for **Shelly Gen1 devices (ESP8266, rBoot layout)**. ESPHome's own OTA cannot work there,
because the ESP8266 OTA relies on the `eboot` bootloader and a Shelly Gen1 has rBoot instead. This component receives a new
firmware over the network, installs it into the app slot and arms rBoot's fallback to the stock firmware.

Status: **tested on a Wemos D1 mini that carries the Shelly 1 or Plug S flash layout; on a real device only the first start of the Plug S test image was seen** (2026-11-11: access point up, button switched the relay). See "What is tested".
A first test route for the Gen1 Plug S is in [PLUGS-TEST.md](PLUGS-TEST.md) (draft).

## What does not work yet

ESPHome's own wireless install does not work on a Shelly Gen1: `ota:` (platform `esphome`), the ESPHome dashboard's "Install wirelessly" and
`esphome upload` need the `eboot` bootloader, and a Gen1 keeps rBoot. Updates go through this folder's tool instead (`gen1_ota.py send` or `push`, see
below), and a config must keep `gen1_ota:` and `wifi:` (with `ap:`) or the next update cannot reach the plug. Making the dashboard's wireless install work
(the component would speak ESPHome's OTA protocol and convert the image on the device) is a goal; it is not started.

## What it does

- Receives a firmware image on a TCP port (default 8267), authenticated with a password (HMAC-SHA256 challenge/response).
- Stages the image in free flash, verifies the transfer CRC and the rBoot image structure and checksum.
- Copies it over slot 0 with a RAM-only routine (the flash that holds the running code is overwritten), then lets the
  hardware watchdog reset the chip. Before the copy the boot config points at the stock slot, so a power loss in the
  middle boots the stock firmware.
- After the copy the boot config is set to "slot 0, unconfirmed, fallback = slot 1". The new app confirms itself after
  `confirm_after` (default 10 s) of running; a new app that crashes before that falls back to the stock firmware.
- Keeps the SDK's RF calibration away from the sector where the stock firmware keeps its RF init data (0x1FC000), which
  would otherwise make the stock boot-loop after the first ESPHome start.

## Layout: from a partition CSV

The flash layout (rBoot config sector, slot 0 and slot 1, the staging area) is not hard-coded. It comes from a partition CSV in the
format of the stock partition tables of the Gen2+ profiles (`Name, Type, SubType, Offset, Size`):

```yaml
gen1_ota:
  password: !secret gen1_ota_password
  partitions: SHSW-1-stock.csv     # next to the configuration, or one of components/gen1_ota/partitions/
```

```
# Name,       Type, SubType, Offset,    Size,
rboot,        boot, rboot,   0x0,       0x1000,
rboot_cfg,    data, rboot,   0x1000,    0x1000,
app_0,        app,  ota_0,   0x8000,    0xB3000,     # ESPHome runs from here and is installed here
fs_0,         data, spiffs,  0xBB000,   0x40000,
app_1,        app,  ota_1,   0x108000,  0xB3000,     # the other slot (the stock firmware), never touched
fs_1,         data, spiffs,  0x1BB000,  0x40000,
```

Used rows: `rboot_cfg`, `app_0`, `app_1` and `fs_0`. The staging area is the unused end of `fs_0` when it follows `app_0` (Shelly 1
style), else the free flash below `app_0`; a row `stage` sets it by hand. Everything else is derived (`layout.py`): the largest
accepted image, the linker script (generated, with the slot's origin), where ESPHome keeps its preferences and EEPROM, and the
sector for the SDK RF calibration. The build passes the numbers to the receiver as defines, so one component serves every layout.

`components/gen1_ota/partitions/` holds one file per Gen1 model (`SHSW-1-stock.csv`, `SHPLG-S-stock.csv`, `SHPLG2-1-stock.csv`, ...), read
from the manifest of the official package. For another package: `python tools/gen1_ota.py partitions <official-package.zip|manifest.json> -o my.csv`.
`convert`, `check`, `send` and `push` take `--partitions CSV` so the size limit of the layout is used.

Seen in the packages: the rBoot config sector is at 0x1000 on the Shelly 1, 1PM, 1L, 2, 2.5, EM, 3EM, i3 and Uni, and at 0x7000 on the
Plug S, Plug US, RGBW2, Bulb, Duo, Vintage, Dimmer, Dimmer 2 and H&T. **A build with the wrong CSV would read the wrong sector** (the
component then answers `ERR layout` and never confirms its boot), so use the CSV of your model.

Limits: the preferences, EEPROM and RF calibration must stay in the first MB of the flash (an ESPHome limit), and a slot above
1 MB (the Plug 2) needs the SDK cache mapping, which does **not** work yet: ESPHome still crashes right after rBoot starts it
(bench result, notes not part of this repository). `convert --partitions` sets the SDK cache byte for the second MB; that is experimental.

## Flash layout of the Shelly 1 (2 MB, rBoot "big flash"; the `shelly1` preset)

| Address | Content |
|---|---|
| 0x0000 | rBoot (the stock one, never replaced) |
| 0x1000 | rBoot config (current rom, previous rom, unconfirmed flag, rom addresses) |
| 0x8000 | slot 0: the ESPHome app, 0xB3000 bytes. Images up to 0x68000 (425,984 bytes) are accepted |
| 0x70000 | staging area for the incoming image (below 0xFA000) |
| 0xFA000 | ESPHome preferences (`_SPIFFS_end` in the linker script) |
| 0xFB000 | EEPROM / PHY data (`_EEPROM_start`) |
| 0xFC000 | RF calibration (moved here by the component) |
| 0xFD000-0xFFFFF | SDK system parameters |
| 0x108000 | slot 1: the stock firmware (never touched), its file system at 0x1BB000 |
| 0x1FB000 | stock RF calibration (the stock writes it itself) |
| 0x1FC000 | stock RF init data (ESPHome must not touch it) |

The component refuses to do anything if the boot config does not show exactly the layout it was built with (`ERR layout`).

## Use

```yaml
external_components:
  - source:
      type: local            # or git, once this lives in a repository
      path: components

esp8266:
  board: esp_wroom_02

# No `ota:` block: ESPHome's own OTA needs eboot.
gen1_ota:
  password: !secret gen1_ota_password   # at least 8 characters
  # port: 8267
  # confirm_after: 10s
```

Build as usual (`esphome compile`). The ESPHome build produces `firmware.bin` (eboot + sketch) and `firmware.ota.bin`
(sketch); the tool takes either.

### Updating a device that already runs this component

```
export G1OT_PASSWORD=...        # or --password-file
python tools/gen1_ota.py push .esphome/build/<name>/.pioenvs/<name>/firmware.bin --host <ip>
```

`push` = `convert` (ESPHome binary to rBoot image) + `check` + `send`. Exit status 0 only if the device answered `OK`. The device
resets itself a few seconds later; the AP/IP comes back when the new app is up.

### Way back to the stock firmware, without UART

```
export G1OT_PASSWORD=...
python tools/gen1_ota.py revert --host <ip>
```

`revert` asks the running ESPHome to boot the stock firmware from the other slot. The receiver first walks the image in slot 1
(structure and checksum, so an empty or damaged slot is never booted), then points the rBoot config at slot 1 and restarts. The
stock firmware starts from its own file system (the one it kept when ESPHome was installed) and answers with its access point and
`/shelly` again. ESPHome stays in slot 0: a package for Shelly's updater (`make_stock_pkg.py ... --image`) installs it there again.

The unconfirmed flag is left at 0 on purpose: the stock reads a set flag as "I was just updated" and reverts to ESPHome. So there
is no automatic fallback after a `revert`; the slot check is the protection. A device whose ESPHome image was built before
this command existed has no `revert`; it needs one update (`push`) first.

`revert` also clears byte 9 of the rBoot config sector. The stock sets that byte when it installs a package (it reads `01` after the first install),
and while it is `01` the stock downloads a new package after a `revert` but does not write it, so ESPHome cannot be installed again (found on a real
Plug S, reproduced on the dev board: with byte 9 set to 0 the stock wrote the package). A plug reverted by an image built before 2026-11-12 needs byte 9
set to 0 once over UART, see PLUGS-TEST.md.

### First installation

The device has to end up with the **stock firmware in slot 1** (the fallback) and ESPHome in slot 0. Two ways:

1. **Over the stock updater, no serial adapter.** A factory device runs the stock from slot 0, so an ESPHome package would
   land in slot 1, where ESPHome does not run (see "Why slot 0 only"). The sequence that works (verified on the bench):
   1. `make_stock_pkg.py <stock-dir> --image <image> --out esphome.zip`, serve it over HTTP, call
      `http://<shelly>/ota?url=http://<pc>:8000/esphome.zip`. It lands in slot 1, crashes, rBoot falls back to the stock in slot 0.
   2. `make_stock_pkg.py <stock-dir> --flip --out flip.zip` and update with it: the stock accepts a package with a changed
      build id and writes it to slot 1, the device now runs the stock from slot 1.
   3. Update with `esphome.zip` again: it lands in slot 0, boots, confirms itself.
   The stock updater needs a stored (uncompressed) zip with the full manifest; it does not check a signature.
   `<stock-dir>` is the extracted official Shelly firmware zip. Those files belong to Shelly and are not part of this project.
2. **Over serial (UART):** write the image to 0x8000, the stock app to 0x108000 and the stock file system to 0x1BB000, and set the
   boot config (current rom 0, flags 0). Needs the stock files too.


## Protocol (port 8267)

1. Device sends 16 random bytes (nonce).
2. Client sends `"G1OT"`, u32 size, u32 crc32 (zlib), little endian, then `HMAC-SHA256(password, nonce || those 12 bytes)`.
3. Device answers `READY\n`, or `ERR auth`, `ERR size`, `ERR layout` and closes (a wrong password also costs one second).
4. Client sends the image. The device stages it, verifies CRC and image structure, answers `OK\n` (or `ERR crc`, `ERR verify`,
   `ERR flash`, `ERR image`, `ERR receive`) and installs.

Way back: the same handshake with `"G1RV"` and size and crc 0. The device answers `OK\n` and restarts into the stock firmware, or
`ERR stock` (no valid image in the other slot), `ERR layout`, `ERR state` (not running from slot 0) or `ERR flash`. No image follows.

A password protects against strangers on the network. It does not prove who built the image (there is no signature), and the
traffic is not encrypted.

## Why slot 0 only

rBoot does not map the flash window for slot 1; the stock app does it itself (`Cache_Read_Disable`, read the boot config,
`Cache_Read_Enable(odd, mb, 1)`). The Arduino SDK that ESPHome uses leaves the default mapping, so an ESPHome build linked for slot 1
would run the slot-0 bytes. Early mapping experiments broke the SDK's init, so the app is linked for slot 0 (`gen1_slot0.ld`,
irom at 0x40208010) and always installed there. This is why the first installation needs the flip sequence.

## What is tested

On the D1 mini with the Shelly 1 layout (2 MB header, 4 MB chip), ESPHome 2026.10.0 (Arduino core 3.1.2, SDK 2.2.1):

| Test | Result |
|---|---|
| Build on a clean toolchain cache | the linker script is found, irom at 0x40208010 |
| Boot, confirmation after 10 s | flag and attempt counter cleared |
| Stock sectors 0x1FB000-0x1FC000 after an ESPHome run | byte-identical to the stock baseline |
| Stock boots after ESPHome ran | yes |
| Wrong password | `ERR auth` |
| Corrupt checksum / too small / too large | `ERR image` / `ERR size` / `ERR size` |
| Update A to B over WiFi with the tool | `OK`, B boots and confirms |
| New app that crashes right after boot | rBoot falls back to the stock after one failed boot |
| Reset 2.5 s after the `OK` (during the copy) | stock boots, no boot loop |
| `revert` (Plug S layout, 2026-11-11) | `OK`, the stock boots from slot 1 with its own file system and answers `/shelly`; a package for the stock updater then puts ESPHome back into slot 0 |
| `revert` leaving byte 9 of the rBoot config at 1 (Plug S layout, 2026-11-12) | the stock downloads a new package (`GET` seen) and restarts, but slot 0 stays unchanged: the stock did not write it |
| `revert` clearing byte 9, then a package through the stock updater | slot 0 holds the new image, ESPHome runs and confirms (config afterwards: current 0, previous 1, flag 0) |
| `revert` with the unconfirmed flag set | the stock tries to take over the old file system and reverts to ESPHome (`Update failed, reverting to ROM 0`): this is why the flag stays 0 |

Host side: `python -m pytest tests` (conversion, image check, protocol against a simulated device).

## What is not tested

- A real Shelly 1 or any Gen1 device other than the Plug S (on the Plug S the first start, the config afterwards, restarts after power cuts, the relay, a second update, `revert`, installing again afterwards, both LEDs and the meter wiring were reported; the three-update case, the NTC temperature and the meter calibration were not tried). Flash size assumed 2 MB, GPIO pins of the relay and input not set up in the example:
  the stock app uses GPIO4 for the relay and GPIO5 for the switch input, read from the firmware).
- The `boot` part (rBoot itself), which the stock updater marks as not updatable.
- A power cut during the one-sector config write of `revert`. On one real Plug S `send` and `revert` worked (the stock came back with its settings and WiFi); installing
  ESPHome again afterwards failed because of byte 9 (see above); after the one-time UART fix it worked on that plug. `revert` with the fixed image and installing again without UART worked there too.
- Power loss at other moments of the copy, and several updates in a row on the same device.
- Images close to the 425,984 byte limit; a running image larger than the limit would overlap the staging area (the check only
  looks at incoming images).
- Other Gen1 models; their flash layout may differ (the component checks the boot config and refuses otherwise).

## Files

`plugs.yaml` is a complete ESPHome configuration for the Plug S Gen1 (WiFi with the plug's own network as fallback, API, relay, button, both LEDs,
meter with limits, energy, temperature, `gen1_ota` instead of `ota:`), written from the ESPHome documentation with the pins and values of the ESPHome
device page. It built, started and kept its fallback network on the dev board; the LEDs and the meter wiring were confirmed on a real plug with the test image (2026-11-13); the meter is not calibrated and the NTC temperature part has not been tried.
`example-plugs-test.yaml` and `example-plugs-meter.yaml` are the small test images used for the first runs.

| Path | Purpose |
|---|---|
| `components/gen1_ota/` | the ESPHome component (Python glue, C++ receiver, `layout.py`, `partitions/*.csv` per model; the linker script is generated) |
| `tools/gen1_ota.py` | convert, check, send, push |
| `tools/make_stock_pkg.py` | packages for the stock updater (first installation) |
| `tests/test_tool.py`, `tests/test_layout.py` | host-side tests |
| `example.yaml`, `example-plug2.yaml`, `secrets.yaml.example` | minimal configurations (Shelly 1, Plug 2) |

## Notes for whoever picks this up

- ESPHome ignores `extra_scripts` in its native build, so `__init__.py` writes the linker script into `<build>/.pioenvs/<name>/ld`
  (searched by the native build) and, for the PlatformIO build, installs it with a pre-build script.
- The wrapper `-Wl,--wrap=user_rf_cal_sector_set` is specific to the SDK 2.2.x path of the Arduino core. A core that uses SDK 3
  registers a partition table instead and needs a different fix.
- `firmware.bin` from ESPHome starts with eboot; `gen1_ota.py convert` detects that by the address of the first segment.
- rBoot's checksum covers only the inner image, not the irom segment; the transfer CRC covers everything.
- Licence: Apache 2.0 like the rest of this repository (see `../../LICENSE` and `../../NOTICE`). Shelly's files (stock firmware, packages,
  flash images) are not part of this folder and must not be added; `.gitignore` already excludes `*.bin`, `out/` and `secrets.yaml`.
