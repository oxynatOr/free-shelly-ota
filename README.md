<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
[![Stargazers][stars-shield]][stars-url]
[![Forks][forks-shield]][forks-url]
[![Issues][issues-shield]][issues-url]
[![project_license][license-shield]][license-url]
<br />
<h1 align="center">Free-Shelly OTA <sup>WIP</sup></h1>
<p align="center">
  Pack your own ESPHome firmware into an official-style Shelly OTA package — and send it to the device.
</p>

`free-shelly-ota` is a small command-line tool for **Shelly Gen2 (classic ESP32)**, **Gen3 (ESP32-C3)** and **Gen4 (ESP32-C6)**
devices (one Gen2 device so far, see the table). It takes the
official OTA package for your device, replaces only the `app` part with your ESPHome image, fixes size and SHA-256 in
the manifest, and can hand the result to the Shelly: it checks the device, serves the ZIP from this PC and triggers the
update over RPC. Optionally it shows the device's debug log while that happens.

> **Status: experimental.** Packaging is covered by tests. The whole chain (`build` and `send`) has been confirmed on
> real devices only where the table below says so (Plug M Gen3, H&T Gen3, Power Strip 4 Gen4, Plus Plug S, Multicolor Bulb Gen3, Plug S Gen3); everything else is
> untested on hardware. Keep UART access as your way back.


⚠️ Disclaimer
-------------

Installing third-party firmware voids your Shelly warranty, and Shelly cannot provide technical support for a device
running third-party code. Incorrect flashing can brick your device. Always back up your original firmware before
proceeding. You assume all responsibility for any damage, data loss, or device failure. This project is not affiliated
with Shelly, Allterco Robotics, Schneider Electric, ESPHome, CSA, or Espressif Systems.


Tested devices
--------------

| Manufacturer | Device                       | Profile       | Chip     | Package | Tested on hardware |
| ---          | ---                          | ---           | ---      | ---     | --- |
| Shelly       | Plug M Gen3                  | `PlugMG3`     | ESP32-C3 | 2.0.1   | ✅ `send` from stock 1.8.99, then two ESPHome OTAs |
| Shelly       | Duo Bulb Gen3                | `DuoBulbG3`   | ESP32-C3 | 2.0.1   | not yet. The owner reports the same main board as the Multicolor Bulb with a different lamp module; its stock firmware has no I2C code (LED PWM instead), so the LED driver config of the Multicolor Bulb does not apply. The OTA chain should be the same, but it has not been run |
| Shelly       | Multicolor Bulb E27 Gen3     | `RGBCCTBulbG3`| ESP32-C3 | 2.0.1   | ✅ `send` with `--esphome-factory` (installed loader 1.0.2, profile default raises it to 1.0.3) ran through and ESPHome runs (reported by the owner). The LED driver (KP18068, own component, config in the device branch) and the channel order were not confirmed yet |
| Shelly       | Plug S Gen3                  | `PlugSG3`     | ESP32-C3 | 2.0.1   | ✅ `send` with `--esphome-factory` (profile default `boot_min_version`, one patch level above the official loader) ran and ESPHome runs (reported by the owner). The build was the base config without relay or metering |
| Shelly       | H&T Gen3                     | `HTG3`        | ESP32-C3 | 2.0.1   | ✅ `send` from stock 2.0.1 (slot 0) with `--esphome-factory`: ESPHome's bootloader is written (profile sets `boot_min_version 1.0.9`, the default 1.0.3 was skipped), ESPHome boots and ESPHome OTAs take effect. Partition table at `0xf000`, so `CONFIG_PARTITION_TABLE_OFFSET: "0xf000"` |
| Shelly       | Power Strip 4 Gen4           | `PowerStrip`  | ESP32-C6 | 2.0.1   | ✅ ESPHome boots and joins Wi-Fi/Home Assistant (UART log) with ESPHome's bootloader (`boot_min_version 1.0.9`). From stock 1.7.99 a direct `send` did not work (app landed in slot 1, old app started); it worked after one official update to 2.0.1, see [Notes](#notes--troubleshooting). Outlets and metering not checked here |
| Shelly       | Power Strip 4 Gen4 (Zigbee)  | `PowerStripZB`| ESP32-C6 | 2.0.1   | not yet |
| Shelly       | Plus Plug S (V2 hardware, Gen2) | `PlusPlugS` | ESP32 | 1.7.5   | ✅ Without UART: `send` with `--esphome-factory` wrote ESPHome's bootloader (installed loader was 1.0.2; the ESPHome build needs the 80 MHz flash header, otherwise `build` refuses). The installer first targeted slot 1, so `ota.py restore` came first (it put Shelly's bootloader back), then `send` targeted slot 0, ESPHome booted, and an ESPHome OTA took effect (0.2.0 to 0.2.11); see Notes. A bricked unit was brought back to Shelly OS over UART first ([Recovery over UART](#recovery-over-uart)) |

> "Not yet" means the package builds, every part hash verifies and the image checks pass, but flashing a real device
> has not been confirmed in this repo. Reports welcome.

More devices: `python ota.py add-device <official.zip>` creates a profile from an official package
(`--parent <base device>` for a variant of a model, e.g. the Zigbee version).


Quick start
-----------

```
pip install -r requirements.txt
python ota.py fetch PlugMG3 --insecure
python ota.py build PlugMG3 app.ota.bin --esphome-factory app.factory.bin --esphome-yaml my-plug.yaml
python ota.py send PlugMG3 out/PlugMG3-app-<date>.zip --watch 60
```

Your ESPHome config needs Shelly's partition table and offset. The tables are in [`partitions/`](partitions) (one CSV per
device, copy it next to your YAML); `python ota.py partition-csv <Device> -o <file>` writes it from the official package.
The offset is where the device keeps its table (it is in the CSV header): `0x10000` for the Plug M Gen3, `0xf000` for the
H&T Gen3.

```yaml
esp32:
  partitions: PlugMG3-stock.csv
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_PARTITION_TABLE_OFFSET: "0x10000"   # H&T Gen3: "0xf000"

ota:
  - platform: esphome
    allow_partition_access: true   # only needed to update the bootloader later; not needed with --esphome-factory
```

`--esphome-yaml` makes `build` check the offset and the partition table (errors). Without `--esphome-factory` it also warns if
`allow_partition_access` is missing (needed to update the bootloader later). It also enables the [credential check](#credential-check).


Commands
--------

The usual workflow is three steps:

```
python ota.py fetch PlugMG3 --insecure                  # 1. get the official package
python ota.py build PlugMG3 app.bin                     # 2. put your app into it
python ota.py send  PlugMG3 out/<file>.zip --watch 60   # 3. send it to the device
```

| Group | Command | What it does |
| --- | --- | --- |
| Prepare | `fetch` | Download the official package and keep it in `fw/` |
| Prepare | `add-device` | Create a device profile from an official ZIP (`--parent` for a variant) |
| Prepare | `partition-csv` | Write the stock partition table as ESPHome `partitions:` CSV (`-o FILE`) |
| Build | `build` | Replace the app part, check the image, write the ZIP to `out/` |
| Deploy | `send` | Check the device, serve the ZIP, trigger the update |
| Deploy | `restore` | Send the cached official firmware back |
| Deploy | `log` | Show the device's live debug log |
| Tools | `inspect` | Show and verify a ZIP |
| Tools | `list` | Show devices and cached firmware |
| Tools | `profiles` | List the profiles with their revision, check `devices/profiles.lock` (`--update-lock` writes it) |
| Tools | `clean` | Delete old ZIPs in `out/` (needs `--yes`) |

`python ota.py <command> -h` shows the options of any command.

In a terminal the messages are colored: yellow for warnings, orange for critical ones (bootloader replaced, data wiped,
wrong update target), red for errors, green for success. The words `WARNING:`, `NOTE:`, `Error:` and `OK:` stay in the text, so
logs and pipes read the same. No colors when the output is not a terminal or `NO_COLOR` is set; `python ota.py --color never
<command>` (or `always`) overrides that. The option goes before the command. `python ota.py colors` shows every level once and says
whether colors are on (and if not, why); use it to check your console.

### fetch

Downloads the official package to `fw/shelly/<Device>/<version>/` (with a `meta.json`) and verifies the hash in the
download URL. Shelly's servers use a private CA, so TLS verification fails; `--insecure` skips it.

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `DEVICE` | yes | | Profile name, e.g. `PlugMG3` |
| `--refresh` | no | off | Check for a newer version even if one is cached |
| `--version VER` | no | latest cached | Use this cached version |
| `--insecure` | no | off | Skip the TLS check (the URL hash only guards against transfer errors) |

### build

Replaces the app part and writes `out/<Device>-<app>-<date>.zip` plus `.sha256` and `.report.json`. The app is checked
for magic byte, chip id, segment count and fit into the app slot. It never downloads on its own and never overwrites
an input file.

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `DEVICE` | yes | | Profile name |
| `APP.bin` | yes | | ESPHome app binary (not the merged image) |
| `--esphome-yaml YAML` | no | none | Also check the partition offset and `partitions:` CSV of this config |
| `--esphome-factory FACTORY.bin` | no | none | Also ship ESPHome's bootloader and a clean `otadata` taken from this factory image, so no separate bootloader update is needed later. Heavily checked first, see [After the first boot](#after-the-first-boot) |
| `--boot-min-version VER` | no | one patch above Shelly's | Only with `--esphome-factory`: the bootloader `min_version` in the manifest. The installer writes only a newer bootloader, hence the default 1.0.2 to 1.0.3. `keep` leaves it, which probably makes the installer skip the bootloader |
| `--secrets FILE` | no | `secrets.yaml` next to `--esphome-yaml` | Values to look for in the image, see [Credential check](#credential-check) |
| `--fail-on-secrets` | no | off | Stop (no output) if the image contains credentials. Use it for packages meant to be shared |
| `--tag LABEL` | no | none | Own label for file name and report; the manifest stays untouched |
| `--drop LIST` | no | nothing | Leave out parts: `boot,pt,otadata,nvs,fs` (dropping `nvs`/`otadata` is untested on devices) |
| `-o`, `--output ZIP` | no | `out/<auto name>` | Output file |
| `--dry-run` | no | off | Check everything, keep no output |

<details>
<summary>More options</summary>

| Option | Description |
| --- | --- |
| `--drop-fs` | Same as `--drop fs` |
| `--official ZIP` | Use this official ZIP instead of the cache |
| `--version VER` | Use this cached version (default: latest) |
| `--download` | Download the official ZIP if none is cached (off by default) |
| `--insecure` | With `--download`: skip the TLS check |

</details>

### send

Checks the device (`Shelly.GetDeviceInfo`, model must match), asks before flashing, serves the ZIP on a temporary web
server and calls `Shelly.Update?url=…`. The Shelly downloads the file itself, so this PC must be reachable from it, for
example connected to the Shelly's own access point. `restore` takes the same options and sends the cached official
firmware instead of a ZIP you choose. While `send` runs, its web server listens on all interfaces of this PC and hands
the ZIP to anyone on the network who asks for its exact file name; the ZIP may contain your Wi-Fi password (see
[Credential check](#credential-check)), so do not run it on an untrusted network. `restore` only works while the Shelly firmware is still running; a device that already
runs ESPHome does not answer, and the way back is then UART with a flash backup. The official package also resets NVS
and `otadata`, so Wi-Fi credentials and settings are lost.

| Option | Required | Default | Description |
| --- | --- | --- | --- |
| `DEVICE`, `ZIP` | yes | | Profile name and the ZIP to send |
| `--ip IP` | no | `192.168.33.1` | Address of the Shelly |
| `--watch SEC` | no | off | Show the device's debug log (UDP, switched on over RPC and restored afterwards) and keep listening SEC seconds after the download |
| `--user USER` / `--password PW` | no | `admin` / none | Login, if the device has a password (digest auth) |
| `--yes` | no | off | Do not ask before flashing |
| `--dry-run` | no | off | Check the device only, send nothing |

<details>
<summary>More options</summary>

| Option | Default | Description |
| --- | --- | --- |
| `--force` | off | Send even if the device model does not match |
| `--host IP` | auto | This PC's address as seen by the Shelly |
| `--port PORT` | `8000` | Local web server port |
| `--log-port PORT` | `9514` | UDP port for the debug log |
| `--timeout SEC` | `300` | How long to wait for the device to download the ZIP |

</details>

### log

Shows the live debug log of a Shelly without sending anything: `python ota.py log --ip 192.168.1.50 --seconds 30`.
Takes `--ip`, `--user`, `--password`, `--host`, `--log-port` and `--seconds` (default: until Ctrl+C).


Versions: what, how, where, when
--------------------------------

Everything that can end up in a log, a package or a bug report says which state of the tool made it.

- **The tool.** `python ota.py --version` prints for example `0.2.0 (feature/x, v0.2.0-4-gb225e1f-dirty, 2026-10-06)`: the
  version, in a git checkout also the branch, `git describe` (last tag, commits since it, commit, `-dirty` = uncommitted
  changes) and the commit date. Outside a git checkout it is just the version number (SemVer, see CHANGELOG). Every command
  starts with a line `free-shelly-ota <that>`, so a pasted log shows which state produced it (`partition-csv` without `-o`
  leaves it out, its output is data).
- **The package.** `build` writes `<zip>.report.json` with the same tool information, the profile name and revision, the options
  used (ESPHome bootloader or not, resulting `boot_min_version`, dropped parts, tag; flags only, no paths) and the build time.
  `send` reads it and prints `Package: built ... by free-shelly-ota ..., profile ... revision N`, and a note if the profile has
  changed since.
- **The profiles.** Each `devices/<Device>.yaml` has a `revision:` that counts its changes. Raise it whenever you change anything
  else in the file, then run `python ota.py profiles --update-lock`; `devices/profiles.lock` stores revision and content hash,
  and the test suite fails if a profile changed without a higher revision. `python ota.py profiles` lists them and checks
  the lock; `list` shows the revision too.


Credits
-------

Almost everything this tool knows was found out by other people. Free-Shelly OTA is an independent implementation built on
their research and documentation. Please visit and support their projects:

| Project | License | What we learned from it |
| --- | --- | --- |
| [tasmota/mgos32-to-tasmota32](https://github.com/tasmota/mgos32-to-tasmota32) | GPL-3.0 | Converting a Shelly OTA ZIP so the stock updater accepts third-party firmware; Gen3 notes (e.g. no PlugSG3 support) |
| [inventor7777/ESPHome-Shelly-Plus-Plug-US](https://github.com/inventor7777/ESPHome-Shelly-Plus-Plug-US) | MIT | Replacing only the app image in Shelly's ZIP for ESPHome; the partition table lives at `0x10000`, not `0x8000`; the follow-up bootloader step |
| [automatous-io/shelly-gen4-esphome](https://github.com/automatous-io/shelly-gen4-esphome) | Apache-2.0 | Gen4 (ESP32-C6) partition layout, the A/B slot rule, install documentation |
| Shelly / Allterco Robotics | – | The official OTA packages and update API (not redistributed here) |
| [ESPHome](https://esphome.io), Espressif (esptool, ESP-IDF) | – | The firmware framework and tooling everything builds on |


After the first boot
--------------------

With Shelly's bootloader still in place, the ESPHome log shows `esp_ota_ops: ota data invalid, no current app. Assuming factory`. This is
expected (seen on the Plug M Gen3, H&T Gen3 and Power Strip here, and in the Plug US project): Shelly keeps its own boot state in `otadata`, which
ESP-IDF cannot read. It does not stop ESPHome from booting.

With Shelly's own bootloader, later ESPHome OTAs behave oddly (see "Without it" below). The recommended way avoids that.

**Recommended: ship ESPHome's bootloader in the package (confirmed on the Plug M Gen3, H&T Gen3, Power Strip 4 Gen4,
Plus Plug S, Multicolor Bulb Gen3 and Plug S Gen3, see the table).** Build with
`--esphome-factory firmware.factory.bin`. The tool takes ESPHome's bootloader and a clean `otadata` out of the factory
image and puts them into the Shelly package instead of Shelly's; the partition table and everything else stay as
shipped. It also raises the bootloader's `min_version` in the manifest by one patch level (1.0.2 to 1.0.3). That is
needed: on the Plug M Gen3 the installer skipped the bootloader while `min_version` equalled the installed loader
(`Shelly OS loader 1.0.2`), and wrote it once the number was higher. After that, two ESPHome OTAs in a row
(0.0.1 to 0.0.2 to 0.0.3) took effect without extra restarts, and the UART boot log showed ESPHome's bootloader instead
of Shelly's. No separate "Update bootloader" step and no UART were needed.

Before building, the tool verifies:

- the bootloader's checksum and SHA-256 are intact and its header (flash mode, size/frequency, chip, minimum revision)
  equals Shelly's;
- the factory image's partition table has the same critical entries as the device (`otadata`, `nvs`, `app_0/1`,
  `fs_0/1`; differences in `scratch`/`shelly` only warn) and its `otadata` area is erased;
- the factory image contains exactly the app you are packing (same build).

**Check that it really happened.** The installer writes the bootloader only if the package's `min_version` is higher than
what it considers installed. On the H&T Gen3 that is 1.0.3 (the update log shows `Boot: cur 010003ff, ... min ...,
update? 0/1`), so the default of one patch above the official 1.0.2 (= 1.0.3) was skipped: ESPHome started, but later ESPHome
OTAs silently did not take effect (the version did not change), and `otadata` stayed in Shelly's format (`SH0S`). The H&T
profile therefore sets `boot_min_version: 1.0.9`; with that the installer wrote ESPHome's bootloader (`send --watch` shows
`Installing BL ... -> boot(0)`) and the next boot showed `ESP-IDF ... 2nd stage bootloader`. Check it yourself: Shelly's loader
prints only the ROM lines over UART, ESPHome's prints `ESP-IDF ... 2nd stage bootloader`. If a package was installed with
the wrong value, a UART fix (backup first): write ESPHome's bootloader to `0x0` and a clean (all `0xFF`) `otadata` to the
`otadata` partition (`0x11000` here), both taken from the package. Other models may report another installed version:
read `Boot: cur ...` in the `--watch` log and pass a higher `--boot-min-version` (or set `boot_min_version:` in the profile).
Untested: a later `restore` of the official package, whose `min_version` is lower than 1.0.9, may then leave ESPHome's
bootloader in place.

`send` warns again when a package replaces the bootloader, and it checks that the installer will write the app to slot 0
(see Notes). It worked on the six confirmed devices; on other models the
installer's rule may differ, and a bootloader that does not suit the device can only be fixed with UART. The Plug US
project advises against replacing the bootloader in the initial package; this goes beyond its findings.
`--boot-min-version VER` sets the value yourself, `keep` leaves Shelly's.

**Without it** (plain package, Shelly's loader stays): a later ESPHome OTA writes the new image into the other slot, but
the device keeps booting the old one until Shelly's attempt counter runs out. The loader prints
`Uncommitted boot of app 0 (attempts 1)` and counts down on every start (about three restarts here); then the next
start switches slot. ESPHome never commits, so the counter keeps running; whether the loader later switches back has
not been checked. The Plug US project handles this differently, in two steps:

1. Build with `ota: - platform: esphome` and `allow_partition_access: true`, install once over the network. ESPHome then
   alternates between the stock `app_0` and `app_1` slots.
2. Run ESPHome Builder's **Update bootloader** action. It replaces the bootloader and keeps Shelly's partition table.

**Do not interrupt power while the bootloader updates.** If it fails you need UART to recover. This step was documented
for the Shelly Plus Plug US (ESP32); it has **not been tested here on any device** (the package route above avoids it). Thanks to
[inventor7777](https://github.com/inventor7777/ESPHome-Shelly-Plus-Plug-US) for working this out.


Notes & troubleshooting
-----------------------

- **Applying a package wipes NVS** (Wi-Fi, settings) and rewrites `otadata`.
- **Slot:** the stock updater writes to the slot it is not running from. The `slot` in the first line of `send` is only what
  the device reports; the real target is read from the log (next note). A third-party report says Gen4 devices skip the
  app and stall at 87 % when updated from slot 0; that was not seen here (Power Strip, H&T and Plus Plug S all updated).
- **ESPHome must land in slot 0 (packages with ESPHome's bootloader):** after the update the installer writes its own boot
  state into `otadata`, which ESPHome's bootloader cannot read (`ota data partition invalid and no factory, will try all
  partitions`); it then starts the first valid app in the table, `app_0`. So the app only runs if the installer wrote it
  to slot 0 (`--watch` log: `Will write to slot 0`). On the Power Strip 4 Gen4 running stock 1.7.99 the installer wrote to
  slot 1 (`app_1`), and the old stock app in `app_0` started again, although the update reported success and ESPHome's
  bootloader was in place (UART log: `ESP-IDF ... 2nd stage bootloader`, `Loaded app from partition at offset 0x20000`,
  `PowerStrip 1.7.99`). After one official update to 2.0.1 and a new `send`, ESPHome started. The same 1.7.99 installer also
  left the old partition table (no `scratch`); after 2.0.1 it was the new one.

  **How `send` helps:** the installer writes to the slot the stock firmware is *not* running from. Right after the debug log
  is switched on, the device prints `Storing core dumps to app_N`, and N was the same as the later `Will write to slot N` in all
  six runs seen so far (H&T, Power Strip, Plus Plug S four times). When the package replaces the bootloader, `send` reads that
  line first (briefly switching on the UDP log, so allow UDP port 9514) and **refuses to send if N is not 0**, telling you to run
  `ota.py restore <Device>` first. `--ignore-slot` sends anyway. The `slot=` value in the first output line is not a reliable
  predictor (Plus Plug S: `slot=1` and the target was 1; H&T: `slot=0`, target 0), so the check uses the log line.
- **Plus Plug S (Gen2), without UART:** the first `send` of the ESPHome package wrote to slot 1 (`Will write to slot 1`), so
  ESPHome's image sat in `app_1` (read back over UART: its header at `0x200000`) while ESPHome's bootloader started the old
  app in `app_0`; sending the same package again changed nothing. Then `ota.py restore PlusPlugS` (the official package) showed
  `Boot: cur 00000000, ... update? 1` (ESPHome's bootloader reports no version) and put **Shelly's bootloader back over OTA**;
  the stock firmware then ran from slot 1, and the next `send` of the ESPHome package said `Will write to slot 0` and succeeded.
  ESPHome then booted (project version 0.2.0), and a following ESPHome OTA changed the version to 0.2.11 (reported by the
  device's owner; the boot log of that step was not reviewed here). So the whole chain worked without UART, once the target
  slot was 0.

  If you are already stuck (ESPHome in `app_1`, old app in `app_0`, no way to run `restore`), a UART step also works: write an
  ESP-IDF `otadata` entry that selects `app_1` (sequence number 2: partition `(2-1) % 2 = 1`) at the `otadata` offset (`0xd000`
  on this device). The 8 KB file can be made with:

  ```
  python -c "import struct,zlib;e=struct.pack('<I20sII',2,b'\xff'*20,0xFFFFFFFF,zlib.crc32(struct.pack('<I',2),0xFFFFFFFF));open('otadata_app1.bin','wb').write(e.ljust(4096,b'\xff')+b'\xff'*4096)"
  esptool --chip esp32 --port COM4 write-flash 0xd000 otadata_app1.bin
  ```

  Undo: `esptool erase-region 0xd000 0x2000` makes the bootloader start `app_0` again. After that, ESPHome's own OTA switches
  between the two slots (confirmed for the OTA path above: 0.2.0 to 0.2.11; not checked after the UART variant).
- **`build` refuses to replace the bootloader** ("differs from Shelly's in ..."): the ESPHome bootloader's header must match the
  one in the official package in flash mode, size/frequency, chip and minimum chip revision, otherwise the device might not
  start. The message prints both values and the fix. Seen so far: flash frequency 40 MHz instead of 80 MHz (classic ESP32:
  `CONFIG_ESPTOOLPY_FLASHFREQ_80M: y` under `sdkconfig_options`; ESP32-C6: `board_build.f_flash: 80000000L`), and
  `minimum_chip_revision` / `sram1_as_iram` in the config (remove them for the package; they are fine for builds you only
  update with ESPHome OTA). A differing partition table or a `.factory.bin` from another build are refused with a fix too.
- **Empty `--watch` log:** the log arrives as UDP datagrams on port 9514 (`--log-port`). A firewall that blocks incoming UDP
  on that port (on Windows, the Python program in Windows Defender Firewall) leaves the log empty; the update itself still
  works. With the log you see the installer's `ota_progress` events (0 to 95 %, then `ota_success`) and, for a package with
  ESPHome's bootloader, the line `Boot: cur ... min ... update? 0/1` that says whether the bootloader gets written.
- **eFuse:** a related project reports a permanent eFuse marker for non-official firmware (Plus Plug US). Unverified for
  Gen3. Observed on the H&T Gen3 (stock 2.0.1, unsigned package): after the update the installer logged `FW signatures:
  want 07 got 00` followed by `EFUSE write error bit[1]` and `bit[2]` with `Bits are not empty. Write operation is
  forbidden.` So it tries to write eFuse bits for a package without the signature marks, and those writes were refused
  because the bits were already set. The update still succeeded and ESPHome ran. What the bits mean is not known; this may
  be irreversible on a device where the bits were still empty, so treat it as a possible permanent change.
- **URL vs. upload:** `send` uses `Shelly.Update?url=` with a local web server. This worked on the Plug M Gen3 (stock
  firmware 1.8.99, running from slot 1). The Tasmota project advises against URL updates and uses the web UI file
  upload instead; if URL mode fails on your device, that is why.
- **Gen4 signature check (disputed):** the ESPHome device page for the Power Strip 4 Gen4 (`PowerStrip`) states that stock OTA is not
  possible because Gen4 verifies OTA images with an ECDSA signature, so it needs a UART flash. The Gen4 project above
  documents OTA installs for other Gen4 models. Which is true may depend on model and firmware version; unverified here.
  If a Gen4 device rejects the package, check the log (`send --watch`) and fall back to UART.
- **Battery devices (H&T Gen3):** the stock updater refuses to start below 30 % battery: `Shelly.Update` answers
  HTTP 500 with `{"code":-109,"message":"OTA not allowed (Battery below 30 percent. )"}` (seen on the H&T Gen3). Charge or
  replace the battery first; after that `send` ran through. `send` shows the device's answer after "HTTP 500". The device
  must also be awake.
- **Power cycle:** after the first boot a real power cycle may be needed (the cause is not understood; some state of the
  stock firmware seems to survive a soft reset). Disconnect the device from mains, wait at least 30 seconds so the
  capacitors can discharge (a quick unplug may leave the ESP powered; the time is a rule of thumb, not measured), then
  reconnect. Do not open a device that is connected to mains.
  On the Plug M Gen3, ESPHome came up after a power-off of about 30 seconds (whether it would also have started
  without it was not tested).
- **Safety:** nothing is downloaded unless you run `fetch` (or pass `--download`). Shelly firmware is not part of this
  repository (`fw/` and `out/` are git-ignored; `out/` can contain credentials, see [Credential check](#credential-check)); you download it yourself.


Recovery over UART
------------------

The official package is also a way back for a device that no longer boots (or runs something else). Its `manifest.json` says
where every part goes; the parts can be written over UART with `esptool`. This brought a Shelly Plus Plug S (V2 hardware, ESP32)
that ran ESPHome back to Shelly OS (done by hand, as described here; the log was not reviewed by this project).

1. **Disconnect the device from mains** and power it from the adapter (3.3 V). Put the chip into download mode (GPIO0 to GND at reset).
2. **Back up the whole flash first**: `esptool read-flash 0x0 <size> backup.bin` (size from `esptool flash-id`).
3. **Read the eFuses, do not burn anything**: `espefuse summary`. Continue only if flash encryption is off (`FLASH_CRYPT_CNT = 0`) and
   secure boot is off (`ABS_DONE_0`/`ABS_DONE_1 = False`); otherwise a plain image will not boot.
4. Take the official ZIP (`ota.py fetch <Device>`), unpack it, and read the addresses in `manifest.json`: `boot` and `pt` have an `addr`,
   the other parts sit in the partition named by `ptn` (offsets in the package's partition table, see `partitions/<Device>-stock.csv`).
5. Erase the NVS area, then write all parts in one command, for example for the Plus Plug S (classic ESP32):

   ```
   esptool --chip esp32 --port COM4 --baud 460800 erase-region 0x9000 0x4000
   esptool --chip esp32 --port COM4 --baud 460800 write-flash --flash-mode keep --flash-size keep --flash-freq keep 0x1000 bootloader.bin 0x8000 partition-table.bin 0xd000 boot_state.bin 0x10000 PlusPlugS.bin 0x1a0000 fs.img
   ```

6. Do **not** write the device-specific partitions (`shelly`, and `aux` on Gen2): they hold the model name and per-device data, and
   no package contains them. If they are blank, the firmware may start without calibration or identity (the MAC lives in the eFuses).

Keep the backup: writing it back (`write-flash 0x0 backup.bin`) restores the previous state.


Credential check
----------------

An ESPHome image stores Wi-Fi SSID/password, API keys and similar values **in plain text**, and so does every package built from
it. `build` therefore compares the image (and the `--esphome-factory` image) with the values from your ESPHome config and its
`secrets.yaml` (`wifi.ssid`, `wifi.password`, `wifi.ap.password`, `api.encryption.key`, `api.password`, `ota[].password`,
`web_server.auth.password`, `mqtt.password` and every other value in `secrets.yaml`). On a hit it prints a warning with the
**names** of the matches (never the values), writes them to `<zip>.report.json` as `contains_secrets`, and `send`/`inspect` warn again.
`--fail-on-secrets` turns the warning into an error. Without `--esphome-yaml`/`--secrets` nothing can be compared; the build says so.
`build` also warns if the output file lies in a git work tree where it is not ignored. Never share, upload or commit such a ZIP; a package
for others should come from a config without credentials (e.g. a Wi-Fi setup config).


Versioning
----------

[Semantic Versioning](https://semver.org); while the version is 0.x the tool is experimental and minor releases may change behaviour.
`python ota.py --version` shows it, the build report records it as `tool_version`, and changes are listed in [CHANGELOG.md](CHANGELOG.md).


<!-- LICENSE -->
## License

Distributed under the [Apache License 2.0](LICENSE); see also [NOTICE](NOTICE).
Section 6 of the license grants no rights to any trademark: Shelly, ESPHome, Espressif and the other names used here
belong to their owners, and this project has nothing to do with them beyond working with their products.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- MARKDOWN LINKS & IMAGES -->
[stars-shield]: https://img.shields.io/github/stars/oxynatOr/free-shelly-ota.svg?style=for-the-badge
[stars-url]: https://github.com/oxynatOr/free-shelly-ota/stargazers
[forks-shield]: https://img.shields.io/github/forks/oxynatOr/free-shelly-ota.svg?style=for-the-badge
[forks-url]: https://github.com/oxynatOr/free-shelly-ota/network/members
[issues-shield]: https://img.shields.io/github/issues/oxynatOr/free-shelly-ota.svg?style=for-the-badge
[issues-url]: https://github.com/oxynatOr/free-shelly-ota/issues
[license-shield]: https://img.shields.io/github/license/oxynatOr/free-shelly-ota.svg?style=for-the-badge
[license-url]: https://github.com/oxynatOr/free-shelly-ota/blob/main/LICENSE
