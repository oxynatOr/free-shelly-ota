# Step-by-step guide: ESPHome on a Shelly

[← README](../README.md) · [Documentation](README.md) · [Device pages](devices/README.md) · [Commands](commands.md) · [Troubleshooting](troubleshooting.md)

[0 Before you begin](#0-before-you-begin) · [1 Your device](#1-check-your-device) · [2 Your PC](#2-prepare-your-pc) · [3 Way back](#3-prepare-your-way-back) · [4 Starting state](#4-bring-the-device-into-the-right-starting-state) · [5 Config](#5-write-the-esphome-config) · [6 Package](#6-compile-and-build-the-package) · [7 Preflight](#7-preflight-check) · [8 Send](#8-send-it) · [9 After](#9-after-the-update) · [10 Failure](#10-if-something-goes-wrong) · [11 Way back](#11-the-way-back-to-shelly-os) · [12 Report](#12-tell-us-how-it-went) · [Special cases](#special-cases) · [Cheat sheet](#cheat-sheet) · [Checklist](#checklist)

This is the whole path from "I have a Shelly" to "it runs my ESPHome firmware and updates itself over the network", and the way back.
It does not repeat every detail: where a topic has its own page, the step links to it. The shortest version is the
[Quick start](../README.md#quick-start); the guide for people who want to add a device or work on the tool is
[Developer guide](guide-developers.md).

## 0. Before you begin

What this does, in one paragraph: `ota.py` downloads Shelly's own update package for your model, swaps the app inside it for your
ESPHome image, and tells the running Shelly firmware to install that "update". No soldering is needed to install.

Read this, then decide:

- **It is experimental.** Only the devices marked ✅ in the [device table](devices/README.md#devices) ran the whole chain on real hardware. 🟡 means part of it is
  unchecked, 🔬 means it ran on a dev board only, 🧪 means nobody has flashed it.
- **Warranty.** Third-party firmware voids it.
- **A bad flash can brick the device.** The fix is UART (a serial connection to the board inside), which means opening the device.
  Keep that in mind before you start, not after.
- **The installer burns an eFuse bit on some devices** (`FW signatures: want 07 got 00`, then `EFUSE write error` or `BURN BLOCK3`).
  What the bits mean is not known, and the change may be permanent ([eFuse](troubleshooting.md#efuse)).
- **Settings are wiped.** Wi-Fi, schedules, scenes, cloud link: all gone. ESPHome starts from your config.
- **Mains voltage.** Never open a device that is connected to mains. Never connect UART to one that is.
- **Battery devices (H&T)** need a charged battery and must be awake ([Special cases](#battery-device-ht-gen3)).

If you accept that, go on. If you are unsure, test the whole update on a spare dev board first ([Test on a dev board](devkit.md)).

## 1. Check your device

1. **Find the exact model.** Gen2, Gen3 and Gen4 devices are not interchangeable. "Plug S" and "Plus Plug S" are different devices, "Mini 1PM Gen3" and
   "PM Mini Gen3" are different devices. The model code is on the label; the device itself tells the app name:

   ```
   http://<device IP>/rpc/Shelly.GetDeviceInfo
   ```

   Look at `app` and `ver`. Add `--ip <device IP>` to later commands; `send` compares the model and refuses a mismatch.
2. **Find the profile.** Open the [device pages](devices/README.md#devices). The profile name (for example `PlugMG3`) is what you give to every command.
   `python ota.py list` (after step 2) shows all profiles. No profile for your model? See [Another device](#a-device-without-a-profile).
3. **Read the device page completely.** It has the exact ESPHome config for that model, the pins, the log lines to expect and the pitfalls seen so far.
4. **Check what the device runs now.**
   - It must run **Shelly firmware**, not ESPHome. (Already ESPHome? Then use ESPHome's own OTA and skip this guide.)
   - Note the firmware version. Some versions need an extra step (1.8.99 on the Plug M Gen3, a device on slot 1, a beta). The device page says which.
   - A **beta firmware** can have another flash layout (2.2.0-beta2). `build` and `send` refuse a mismatch; see [Beta firmware](bootloader-and-slots.md#beta-firmware-with-another-flash-layout).
5. **Check the state symbol** of your device and decide if you want to be one of the first.

## 2. Prepare your PC

Needed once.

1. **Python 3.10 or newer.** Check with `python --version`.
2. **The tool.** Download the [latest release](https://github.com/oxynatOr/free-shelly-ota/releases) (*Source code (zip)*) and unpack it, or `git clone https://github.com/oxynatOr/free-shelly-ota`.
3. **Its requirement** (from inside the folder):

   ```
   pip install -r requirements.txt
   ```

4. **A way to compile ESPHome.** One of these:
   - the `esphome` command (`pip install esphome`, `pipx install esphome` on Linux), or
   - **Docker** (Docker Desktop on Windows; it has to be running). `build --compile` uses it automatically. The first compile downloads a 3 GB toolchain into the
     Docker volume `free-shelly-esphome-cache`; keep the volume ([Compile](commands.md#compile)).
   - Under WSL keep your YAML in the Linux home, not under `/mnt/c`.
5. **Optional: Bluetooth.** Only for a device with no Wi-Fi (Zigbee firmware): `pip install bleak` and a Bluetooth LE adapter.
6. **Firewall.** `send` starts a small web server and listens for the device's log. Allow the Python program on the network you use:
   TCP **8000** (the ZIP, `--port`) and UDP **9514** (the log, `--log-port`). On Windows the first run asks; choose *private networks*.
7. **Network.** The device must be able to open a connection **to this PC**. A PC in the normal LAN and a Shelly in an IoT VLAN or guest network is the usual reason for
   a failing update ([The device does not download the ZIP](troubleshooting.md#the-device-does-not-download-the-zip)). If in doubt, put the PC into the device's network
   for the update, or connect it to the Shelly's own access point (`192.168.33.1`).
8. **Look at the tool:** `python ota.py -h`, and `python ota.py list` shows the profiles.

## 3. Prepare your way back

The network update has no network way back once ESPHome's bootloader runs. Decide now.

1. **Get a UART adapter** or build one from an ESP32 dev board ([Build your own UART adapter](recovery-uart.md#build-your-own-uart-adapter)). You need not use it, but if a
   flash fails it is the only fix.
2. **Know where the pads are.** Look at your device page, or the label photos of others. Do not open the device yet.
3. **A flash backup** is only possible over UART (`esptool read-flash`). If you can, make one before you flash: it restores the previous state byte for byte,
   including the device-specific data. Step 2 of [Recovery over UART](recovery-uart.md#steps). If you do not open the device, you do not have a backup; the tool's `restore`
   brings back the *official* firmware, not your device's own data.
4. **Note down what you will lose:** the device's Wi-Fi, schedules, scenes, calibration you set, and its entry in the Shelly app.

## 4. Bring the device into the right starting state

The installer needs the device in a state it can accept. Do these checks in the order below; most devices need none of the fixes.

1. **Powered and awake** for at least two minutes before you send (the stock firmware answers `Not committed` for a while after a start).
2. **No password trouble.** If the device has a login set, add `--user USER --password PW` to `send`.
3. **The target slot has to be 0.** The installer writes to the slot it is *not* running from. If the device runs from slot 0, the app lands in slot 1 and the old app
   starts again. `send` reads it and refuses ([The app must land in slot 0](bootloader-and-slots.md#the-app-must-land-in-slot-0)). The cure is one step:

   ```
   python ota.py restore <Profile> --ip <device IP>
   ```

   That sends the cached official firmware (run `fetch` first); the device then runs the other slot. You can do this blindly if your device page says so.
4. **Old factory firmware.** Some devices (Plug M Gen3 on 1.8.99, Plus i4 on 1.7.6) have special remarks on their page. Follow the page.
5. **Battery devices:** battery at 30 % or more.
6. **Bad Wi-Fi signal:** a device at -67 dBm or weaker can need 20 minutes or more to download. Move it or the access point closer; `send` will ask how long to wait.

## 5. Write the ESPHome config

Your own YAML decides what the device does. Rules that make the update work:

1. **Partition table.** Copy `partitions/<Profile>-stock.csv` from this repository next to your YAML. For a profile you made yourself:
   `python ota.py partition-csv <Profile> -o <Profile>-stock.csv`.
2. **Offset.** `CONFIG_PARTITION_TABLE_OFFSET` must be the profile's `pt_offset` (`0x10000` for most, `0xf000` for H&T, Mini 1 Gen3, Mini 1PM Gen3, PM Mini Gen3,
   1 Gen3, 1PM Gen3, i4 Gen3, Dimmer 0/1-10V PM Gen3; `0x8000` for the classic ESP32 Gen2 devices). Your device page states it.
3. **The block that every config needs:**

   ```yaml
   esp32:
     partitions: PlugMG3-stock.csv                 # your device's file
     framework:
       type: esp-idf                                # not arduino
       sdkconfig_options:
         CONFIG_PARTITION_TABLE_OFFSET: "0x10000"   # from the device page
       advanced:
         enable_ota_rollback: false

   ota:
     - platform: esphome
       allow_partition_access: true
   ```

   `variant`, `board` and `flash_size` come from the device page. `allow_partition_access: true` is what lets ESPHome later replace the bootloader, if needed.
4. **A way into the device after the flash.** NVS is wiped, so the old Wi-Fi is gone. Put your Wi-Fi in `wifi:` **and** a fallback access point
   (`ap:`) so you can reach it if the network is wrong. Add `api:` or `web_server:` to see it. Without any of that you flash a device you cannot reach.
5. **Pins.** Take them from the device page. Pins marked "not confirmed" were read from the firmware and not measured: test them with an own, small config first.
6. **Secrets.** Keep passwords in `secrets.yaml`, never in the YAML you share. The package you build holds them in plain text ([Credential check](credential-check.md)).
7. **Sanity-check the config only:**

   ```
   esphome config my-device.yaml
   ```

   The tool checks the partition rules again in step 6.

## 6. Compile and build the package

### Option A: one command

```
python ota.py fetch <Profile> --insecure
python ota.py build <Profile> --compile my-device.yaml
```

`--compile` checks the config first, compiles it (esphome command, else Docker) and builds the package with ESPHome's bootloader. It writes `out/<Profile>-<app>-<date>.zip`.

### Option B: compile yourself

```
esphome compile my-device.yaml
python ota.py fetch <Profile> --insecure
python ota.py build <Profile> firmware.ota.bin --esphome-factory firmware.factory.bin --esphome-yaml my-device.yaml
```

`firmware.ota.bin` is the app, `firmware.factory.bin` the full image. Both must come from the **same compile**.

### What to watch in the output

- `fetch` needs `--insecure`; the hash in the download URL is still checked. It keeps the package in `fw/` (keep that folder: Shelly can remove a version from its
  server, as happened with the Plug M Gen3 2.0.1 and 2.1.0).
- `build` checks magic byte, chip id, segments, that the image fits the slot, the bootloader header and the partition table. A refusal is a reason to stop, not to force.
  The most common refusals are in [Build refuses to replace the bootloader](troubleshooting.md#build-refuses-to-replace-the-bootloader).
- `build` warns if your config does not set `allow_partition_access`, or if the image holds credentials. It writes `out/<zip>.sha256` and `.report.json`.
- For a ZIP **only you will use**, secrets in it are expected. For one you **share**, build from a config without credentials and add `--fail-on-secrets`.
- Do **not** leave out `--esphome-factory`: without ESPHome's bootloader the old firmware comes back after three starts, and `send` refuses to send it.
  Reasons: [Bootloader and slots](bootloader-and-slots.md#without-esphomes-bootloader-plain-package).
- The bootloader `min_version` is taken from the profile. Do not change it with `--boot-min-version` unless a device page or a report tells you to.

### Look at the result

```
python ota.py inspect out/<file>.zip --device <Profile>
```

It shows the manifest, the hashes and how full the app slot is.

## 7. Preflight check

1. **The device** is on Shelly firmware, awake, running for more than two minutes, battery OK, in range.
2. **The address.** On a normal network use the IP from your router. Without any network the Shelly's own access point is `192.168.33.1`; join it with the PC.
3. **Dry run** (sends nothing):

   ```
   python ota.py send <Profile> out/<file>.zip --ip <device IP> --dry-run
   ```

   It checks that the model matches, reads the update target slot and asks the device to fetch this PC's web server. Expect `Update target slot: 0`.
   Stop here and fix the cause if you see:
   - a model mismatch → wrong profile,
   - slot not 0 → `restore` ([step 4](#4-bring-the-device-into-the-right-starting-state)),
   - `Connection error` on the reachability check → firewall or VLAN,
   - "firmware does not reveal the update target slot" → note it and use `--watch` in step 8,
   - "target slot could not be read" → UDP 9514 is blocked or the device just started.
4. **Power.** The device must not lose power for the next ten minutes. Do not use a plug on a smart socket that you could switch off, and do not pull anything.
5. **Close other tools** that talk to the device (the Shelly app, scripts).

## 8. Send it

```
python ota.py send <Profile> out/<file>.zip --ip <device IP> --log-file
```

`--log-file` keeps the whole run in `logs/` for a bug report. Put it after the ZIP name.

What happens, in order:

1. `send` checks the model, shows the package details and **asks for confirmation**. Read the warnings it prints (bootloader will be replaced, NVS wiped).
2. It starts the web server and switches on the device's debug log.
3. The device downloads the ZIP (from seconds to many minutes; the speed depends on its Wi-Fi). `send` shows the progress and extends the wait on its own when the download is steady.
4. The installer writes the parts. Lines to look for:
   - `Update target slot: 0` and `Will write to slot 0`,
   - `Boot: cur ... min ... update? 1` and `Installing BL ... -> boot(0)`: ESPHome's bootloader is written. **`update? 0` is a warning:** it will not be, and later OTAs will not take
     effect ([min_version](bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)),
   - the progress up to 100 %, then `Done: update installed, the device confirmed it`.
5. The device restarts into ESPHome.

Do **not** unplug, switch off or restart the device while it writes. A power cut at this point is what needs UART.

Normal lines you can ignore: `FW signatures: want 07 got 00` and, on some models, refused `EFUSE write` lines (shown as one note).

If `send` says "Done: the device downloaded the ZIP" instead, the device log did not reach this PC (UDP 9514). The update itself may still have worked; go on with step 9.

If `send` stops with `Not committed`, the device started less than two minutes ago: let it wait or run again later ([details](troubleshooting.md#send-stops-with-not-committed)).

## 9. After the update

1. **Wait.** Give it two to three minutes to restart and join the Wi-Fi.
2. **Find it.** In the router's client list, in Home Assistant (*Settings → Devices → ESPHome*), or via the fallback access point of your config. If it
   does not show up, power-cycle it for at least 30 seconds ([ESPHome does not start](troubleshooting.md#esphome-does-not-start-after-the-update)). That is not a failure: several devices
   needed it, some only had a dead relay and LED until then.
3. **Look at the log** (ESPHome logs, or a UART terminal at 115200 Bd): `ESP-IDF ... 2nd stage bootloader` and `Loaded app from partition at offset 0x20000` are the good signs.
4. **Test the hardware properly**: relay (with a harmless load first), button, LED, meter against a known load, temperature. Compare with the stock values you noted.
   Report anything that is wrong ([step 12](#12-tell-us-how-it-went)).
5. **Prove the second OTA.** Change something harmless (a version string in your config), compile, and update with ESPHome's own OTA (CLI, or the ESPHome Builder in Home Assistant).
   Check that the *new* version really runs. If it only appears to work, the bootloader was not replaced or the app is in the wrong slot ([see here](troubleshooting.md#esphome-otas-work-but-the-version-does-not-change)).
   From now on ESPHome alternates the two slots itself; you do not need this tool for updates.
6. **Clean up.** The ZIP in `out/` may hold your Wi-Fi password: do not share or commit it. `python ota.py clean --keep 3 --yes` removes old ones.
   Keep `fw/` (the official package, your `restore` source).
7. **Mount the device** only after all the above worked.

## 10. If something goes wrong

Start with `--log-file`, it is the answer to most questions. Quick map:

| Symptom | Where to look |
| --- | --- |
| `send` refuses: target slot is not 0 | `python ota.py restore <Profile>` and send again ([why](bootloader-and-slots.md#the-app-must-land-in-slot-0)) |
| `Not committed` | Wait; device must run 2+ minutes ([page](troubleshooting.md#send-stops-with-not-committed)) |
| Device does not download the ZIP | VLAN or firewall, port 8000; `send --dry-run`; weak signal ([page](troubleshooting.md#the-device-does-not-download-the-zip)) |
| No progress shown | UDP 9514 blocked ([page](troubleshooting.md#no-progress-no-device-log)) |
| `build` refuses the bootloader or layout | [Build refuses](troubleshooting.md#build-refuses-to-replace-the-bootloader), [Beta layout](bootloader-and-slots.md#beta-firmware-with-another-flash-layout) |
| `build --compile` fails | [Compile problems](troubleshooting.md#build---compile-is-slow-or-stops-before-the-compile) |
| H&T: "Battery below 30 percent" | Charge it ([page](troubleshooting.md#battery-devices-ht-gen3)) |
| Update "succeeded" but the old firmware runs | Wrong slot or no new bootloader ([page](troubleshooting.md#esphome-does-not-start-after-the-update)) |
| ESPHome runs for three starts, then Shelly is back | The package had Shelly's bootloader. UART with ESPHome's bootloader ([page](bootloader-and-slots.md#without-esphomes-bootloader-plain-package)) |
| Nothing happens at all, device silent, no Wi-Fi, no AP | Power-cycle 30 s; then UART log ([page](recovery-uart.md)) |
| Device in a boot loop | UART ([page](recovery-uart.md)) |

Rules for a failure:

- **Do not send again and again.** Read the log first. A second send on a half-written device can make it worse.
- **Do not push the official app through ESPHome OTA** as a way back; it does not boot ([why](recovery-uart.md#not-a-way-back-pushing-the-official-app-over-esphome-ota)).
- If the device was dead after an update, a **UART log** says what runs. Read it before you write anything.

## 11. The way back to Shelly OS

| Situation | What to do |
| --- | --- |
| The Shelly firmware still runs (the update has not happened yet, or the old app is back) | `python ota.py restore <Profile> --ip <IP>`: sends the cached official package. NVS is reset, Wi-Fi is gone. |
| ESPHome runs with ESPHome's bootloader | **UART only**: [Recovery over UART](recovery-uart.md). Back up first, check the eFuses, erase NVS, write all parts from the official package. Do not write the `shelly` and `aux` partitions. |
| ESPHome runs, but you only want the stock slot again | [Select slot 1 with a hand-made otadata](troubleshooting.md#select-slot-1-with-a-hand-made-otadata) (UART) |
| You have a flash backup | `esptool write-flash 0x0 backup.bin` restores your device exactly as it was. |

A device brought back this way reports Shelly OS loader 1.0.3. The profile's `boot_min_version: 1.0.9` makes a later install replace it again.

## 12. Tell us how it went

Also when it worked. This is how 🧪 devices turn into ✅.

1. Run `python ota.py --version` and keep the output.
2. Attach the `--log-file` file, **after removing** Wi-Fi passwords, keys, the cloud key and MAC addresses.
3. [Open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml), or a [bug report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=bug.yml)
   if the tool misbehaved.
4. **Never attach** flash dumps, built ZIPs or DevKit images: they hold your credentials and per-device secrets.
5. Say what you checked and what you did not (relay under load, meter, button, a second OTA). The tables use exactly that.

## Special cases

### A device without a profile

A profile is made from the official package and takes minutes. [Request it](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=new-device.yml) (offer to test it),
or make it yourself with `python ota.py add-device <official.zip>` and follow [Device profiles](../devices/README.md#adding-a-profile) and the [Developer guide](guide-developers.md#6-add-a-new-device).
Nobody can say it works until someone flashed one; treat it as 🧪.

### A device with no Wi-Fi (Zigbee firmware)

Some Zigbee firmware has no network and opens no access point. Give it a Wi-Fi over Bluetooth, then use the printed address:

```
pip install bleak
python ota.py ble scan
python ota.py ble wifi MyNetwork -
python ota.py send <Profile> out/<file>.zip --ip <printed address> --dry-run
```

`-` asks for the password without echoing. Seen on a dev board only, not yet on a real device ([`ble`](commands.md#ble)).

### Battery device (H&T Gen3)

Charge or replace the battery (30 % or more) and keep the device awake. The stock updater answers `Battery below 30 percent` otherwise, and `send` does not retry.
The official H&T package may not be listed for current firmware; use `fetch HTG3 --from-version 1.4.4` ([`fetch`](commands.md#fetch)). Its page: [HTG3](devices/HTG3.md).

### Classic ESP32 (Gen2) and ESP32-C6 (Gen4)

The steps are the same; the differences are in the profile: partition table at `0x8000` for Gen2, an 8 MB layout on Gen4. The bootloader header must match Shelly's
(flash frequency 80 MHz on classic ESP32 and C6, see the [fix table](troubleshooting.md#build-refuses-to-replace-the-bootloader)). Gen4 packages may be verified with a signature on some firmware; if the
device rejects the package, check the log and use UART ([disputed](troubleshooting.md#gen4-signature-check-disputed)).

### Beta firmware

Do not send a package of the wrong layout. Check [Beta firmware with another flash layout](bootloader-and-slots.md#beta-firmware-with-another-flash-layout). Shelly can pull a beta, so cache the package with `fetch` before you need it.

### Devices that measure only

The Plug PM Gen3 and PM Mini Gen3 have no relay. A config for them must not have one.

### Settings you want to keep

The package wipes NVS. `--drop nvs` leaves it out of the package, but it is **untested on devices**; only use it if you know why.

### Password on the Shelly

`--user admin --password '<pw>'` for `send`, `restore` and `log`. A password on the command line stays in the shell history.

### Several devices

Repeat steps 5 to 9 per device, with its own profile, its own CSV and its own YAML. A package built for one model is refused by another.

## Cheat sheet

```
python ota.py list                                        # profiles and cached firmware
python ota.py fetch <Profile> --insecure                  # get the official package
python ota.py build <Profile> --compile my.yaml           # compile and build (or use app.ota.bin ...)
python ota.py inspect out/<file>.zip --device <Profile>   # look inside
python ota.py send <Profile> out/<file>.zip --ip <IP> --dry-run
python ota.py send <Profile> out/<file>.zip --ip <IP> --log-file
python ota.py restore <Profile> --ip <IP>                 # official firmware back (Shelly still running)
python ota.py log --ip <IP> --seconds 30                  # live device log
python ota.py clean --keep 3 --yes                        # remove old ZIPs
```

Every option: [Commands](commands.md).

## Checklist

Before you send:

- [ ] Exact model known, profile chosen, device page read
- [ ] Device runs Shelly firmware (version noted, beta ruled out)
- [ ] UART adapter ready; backup made if you opened the device
- [ ] Config uses the stock partition CSV, the right offset, `esp-idf`, `allow_partition_access: true`, has Wi-Fi and a fallback access point
- [ ] Same compile for the app and the factory image (or `--compile`)
- [ ] Package built with ESPHome's bootloader; `inspect` is clean
- [ ] ZIP not shared, not committed
- [ ] Device awake for 2+ minutes, battery OK, reachable
- [ ] Ports 8000 (TCP) and 9514 (UDP) open on this PC
- [ ] `send --dry-run` says slot 0, reachable, model matches (or `restore` run)
- [ ] Power will stay on for ten minutes

After:

- [ ] ESPHome joined the network (power-cycled if needed)
- [ ] Relay, button, LED, meter checked
- [ ] A second OTA with a visible change took effect
- [ ] Old ZIPs cleaned, `fw/` kept
- [ ] Report written

---

> [!TIP]
> **Stuck anywhere?** Keep the `--log-file` file and [open a report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml). Both forms ask for the log without passwords, keys and MAC addresses.

[Developer guide](guide-developers.md) · [Contributing](../CONTRIBUTING.md) · [Commands](commands.md) · [Bootloader and slots](bootloader-and-slots.md) · [Troubleshooting](troubleshooting.md) · [Recovery over UART](recovery-uart.md)
