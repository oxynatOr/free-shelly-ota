# Shelly Plug S (Gen1, SHPLG-S): first test, draft

> **For testers only. This is not a supported way to flash a Plug S.** It has run on one real Plug S so far (first start only), and there is no Gen1 profile or
> `ota.py` command. A mistake can leave the plug without working firmware; the way back needs a UART connection and a flash backup.
> It switches mains power: open the case only with the plug unplugged. Do not try it on a device you cannot recover over UART.
>
> **Never connect a UART adapter to a plug that is connected to mains.** The ground of the plug's electronics can be at mains potential, and
> the adapter would carry it to your PC. UART is only for a plug that is unplugged with the case open. A plug powered by the UART adapter
> (3.3 V) runs the chip, but not the relay, and a flash write or WiFi on that supply can brown out. Everything that needs mains (relay, load,
> meter) is done with the case closed and without UART, over the plug's WiFi network.

Status: **draft.** On one real Plug S (2026-11-11, short case, stock already in slot 1) the test image started: the access point `plugs-test` came up and the button switched the relay. Reported in follow-ups: the rBoot config reads as confirmed (current slot 0, previous slot 1, flag 0, attempts 0), the plug comes back reliably after being unplugged several times, and the relay is off after plugging in and switched on by the button. Before that the sequence ran on a Wemos D1 mini with the Plug S flash layout and the
Plug S stock v1.14.0. The test image `example-plugs-test.yaml` (2026-11-10, D1 mini with the Plug S stock image) went through
ESPHome zip -> flip zip -> ESPHome zip: the stock moved to slot 1 (`Booting rom 1`), ESPHome landed in slot 0 and booted (AP `plugs-test`,
GPIO15 relay and GPIO13 button configured, `gen1_ota` listening on 8267). The rBoot config sector (0x7000) afterwards reads current rom 0,
previous rom 1, unconfirmed flag 0, attempts 0, roms 0x8000 / 0x108000 (boot confirmed). Relay and button were not exercised (no hardware
on the pins).

The one-update case (stock already running from slot 1) was rehearsed on the D1 mini on 2026-11-10: after `flip.zip` the stock ran from slot 1, one
`esphome.zip` landed in slot 0 and started (AP `plugs-test`, relay and button configured, `gen1_ota` listening). The image and packages for that run
were built with the commands of this guide in a clean folder. The rBoot config afterwards read the same as in the three-update run:
current rom 0, previous rom 1, unconfirmed flag 0, attempts 0 (boot confirmed), byte 9 is `01`.

## What the test image does

- Starts its own WiFi access point `plugs-test` (no WiFi credentials of yours are needed or stored).
- Runs the `gen1_ota` receiver on port 8267 (password from your `secrets.yaml`) and confirms the boot to rBoot after 10 s.
- Relay on GPIO15 (read from the stock firmware v1.14.0: hard-coded output). Starts OFF.
- Button on GPIO13 toggles the relay. GPIO13 comes from the ESPHome device page for the Plug S (its configuration is credited to a named tester) and worked on a real Plug S.
- Left out on purpose: LEDs (GPIO0/GPIO2) and power meter (GPIO12/5/14). They are documented on the same device page, but nobody has tried them on a plug in this project yet.

## What you need

- A 3.3 V UART adapter and the plug opened with **mains disconnected** (TX = GPIO1, RX = GPIO3, GND, GPIO0 to GND only for flash mode).
- `esptool` (for the backup and the config read).
- Python 3 (the tools in `tools/` use the standard library only).
- Docker, to build the image the same way it was built on the bench. (A local ESPHome 2026.10.0 install works too, then use `esphome compile`.)
- The plug and the PC in the same WiFi, and a firewall that lets the plug reach the PC on port 8000.
- Shelly's official firmware zip for the Plug S, which you download yourself: `http://firmware.shelly.cloud/gen1/SHPLG-S.zip`. Extract it to a
  folder (`<stock-dir>` below). These are Shelly's files, they are not part of this project and must not be posted.

## Before you start

1. Full flash backup: `esptool read-flash 0 0x200000 backup.bin`. Keep it private, it contains your settings.
2. Read the rBoot config (read-only): `esptool read-flash 0x7000 0x1000 cfg.bin`, then
   `python -c "print(open('cfg.bin','rb').read(16).hex(' '))"`. Expected: byte 0 is `e1`, byte 3 is the slot that runs now (0 or 1), byte 7 and 8 are `00`.
   If it looks different, stop and post it.
3. Check that the plug runs **v1.14.0**: `http://<plug-ip>/shelly` shows `20230913-113421/v1.14.0-gcb84623` in `fw`. If not, update it with the normal Shelly update first.
   The sequence is only tested with the v1.14.0 updater.

## Build the image and the packages

Run these in this folder (`experimental/gen1/`). In PowerShell; in cmd use `%cd%` instead of `${PWD}`.

1. `copy secrets.yaml.example secrets.yaml` and set `gen1_ota_password` (8 characters or more). That is the only secret the test image needs.
2. Compile (the first run downloads the toolchain and takes several minutes, later runs take seconds; ESPHome writes a `.esphome` folder next to the config, so the folder is mounted writable):
   ```
   docker run --rm -v "${PWD}:/config" -v esphome-gen1:/cache -e ESPHOME_DATA_DIR=/cache/data -e HOME=/cache/home ghcr.io/esphome/esphome:2026.10.0 compile /config/example-plugs-test.yaml
   mkdir out
   docker run --rm -v "${PWD}/out:/out" -v esphome-gen1:/cache --entrypoint sh ghcr.io/esphome/esphome:2026.10.0 -c "cp /cache/data/build/plugs-test/.pioenvs/plugs-test/firmware.bin /out/firmware.bin"
   ```
3. Convert it to an rBoot image and check it:
   ```
   python tools/gen1_ota.py convert --partitions SHPLG-S-stock.csv out/firmware.bin out/plugs-test-slot.bin
   python tools/gen1_ota.py check --partitions SHPLG-S-stock.csv out/plugs-test-slot.bin
   ```
   `check` has to print `ok`.
4. Build the packages for Shelly's updater (stored zips):
   ```
   python tools/make_stock_pkg.py <stock-dir> --image out/plugs-test-slot.bin --out out/esphome.zip
   python tools/make_stock_pkg.py <stock-dir> --flip --out out/flip.zip
   ```
5. Serve them from the folder with the zips: `cd out`, then `python -m http.server 8000`. Allow port 8000 in the firewall for the plug.

## Update through the stock updater

Open each URL in a browser or with curl; the answer is `{"status":"updating",...}`. Wait about a minute after each one. The plug
restarts and may be unreachable for a short time. `<pc-ip>` is the address of your PC in the WiFi.

- **If the plug runs from slot 1** (config byte 3 is `01`): one update is enough.
  `http://<plug-ip>/ota?url=http://<pc-ip>:8000/esphome.zip` -> the image lands in slot 0, starts, and a WiFi network `plugs-test` appears. Done.
- **If the plug runs from slot 0** (config byte 3 is `00`): three updates, in this order.
  1. `.../ota?url=http://<pc-ip>:8000/esphome.zip` -> the image lands in slot 1, does not start, the plug falls back to the stock firmware. Expected.
  2. `.../ota?url=http://<pc-ip>:8000/flip.zip` -> the stock firmware moves to slot 1.
  3. `.../ota?url=http://<pc-ip>:8000/esphome.zip` again -> lands in slot 0, starts, `plugs-test` appears.

If `plugs-test` does not appear after the last update, or the plug does not answer after the first one: stop, do not repeat in a loop, and
post the serial log (115200 baud).

## Report

- The serial log (remove WiFi names and MAC addresses).
- Whether `plugs-test` appeared and whether the plug kept running for a few minutes.
- Whether the relay clicks when you press the button, and whether the button needs another pin.
- The rBoot config again (`esptool read-flash 0x7000 0x1000 cfg.bin`, first 16 bytes): afterwards byte 3 is `00` (ESPHome in slot 0), byte 6 `01`, bytes 7 and 8 `00`.

## If something goes wrong

- The stock firmware stays in the other slot; a failed ESPHome boot falls back to it by itself.
- If the plug does not come back at all: UART, write `backup.bin` back (`esptool write-flash 0 backup.bin`).
- If ESPHome runs and you want the stock firmware back without UART: see "Second update and the way back" below.

## Second update and the way back (optional, after the first test worked)

Only with the UART adapter ready and your backup safe. `send` and `revert` worked on one real plug (2026-11-11); putting ESPHome back through the stock updater afterwards did not work there: `revert` of the first image left byte 9 of the rBoot config at 1, and then the stock does not write a new package (see "The stock does not install after `revert`" below). Images built after 2026-11-12 clear it. After the one-time UART fix it worked on that plug (2026-11-13).

What you need:

- **Your PC in the plug's own network.** The test image does not know your WiFi. It runs its own network `plugs-test` (WPA2, password
  `change-me-please` from the example config), and the plug is at `192.168.4.1`. The tools talk to port 8267 there. While your PC is in
  that network, a PC with one WiFi adapter has no internet and no other WiFi: build the image first, then join `plugs-test`. A second
  adapter or a cable for the other network avoids this.
- **The same password as in the running image.** The plug accepts a command only with the `gen1_ota_password` that was in `secrets.yaml`
  when the running image was built. Give it to the tool through the environment (PowerShell: `$env:G1OT_PASSWORD = "..."`; Linux and macOS:
  `export G1OT_PASSWORD=...`) or with `--password-file`. A wrong password gives `ERR auth` after one second, the plug keeps running.
- **An image that knows `revert`.** The first test image has none. Build a new one from the current branch (same commands as in "Build the
  image and the packages", same password) and `send` it first.

Steps:

1. Send the newer image (this is the first update from ESPHome to ESPHome on a real plug):
   `python tools/gen1_ota.py send --partitions SHPLG-S-stock.csv out/plugs-test-slot.bin --host 192.168.4.1`. The answer has to be `OK`. The
   plug restarts and is gone for about 40 seconds; your PC may drop the network, join `plugs-test` again.
2. Way back to the stock firmware: `python tools/gen1_ota.py revert --host 192.168.4.1`. The answer has to be `OK`. The plug restarts as a
   Shelly again, with the settings it had before ESPHome, in your normal WiFi (if it was not set up, in its own network `shellyplug-s-...`).
   Check `http://<plug-ip>/shelly`.
3. Put ESPHome back (optional): the update URL of "Update through the stock updater" with `esphome.zip`; the stock runs from slot 1 now, so
   one update is enough.

Good to know: `revert` refuses (`ERR stock`) if the other slot holds no valid image, and `ERR state` if the plug does not run from slot 0.
After a `revert` there is no automatic fallback to ESPHome (the stock treats a set flag as a fresh update and drops it, see the README), so
if the stock does not come up, the way back is UART and your backup.

## The stock does not install after `revert`

Symptom: after `revert` you fire the update URL, the plug restarts after about ten seconds, and the stock firmware is back, no `plugs-test`.
The stock did download the package, but it did not write it. Cause: byte 9 of the rBoot config sector (`0x7000` on the Plug S) is `01`; the stock
sets it when it installs a package, and a `revert` from an image built before 2026-11-12 did not clear it. While it is `01` the stock does not write
a new package. How to see it: read the config (`esptool read-flash 0x7000 0x1000 cfg.bin`, the plug unplugged and powered by the adapter) and look at
the 10th byte (the first 16 bytes as hex: `e1 01 00 01 00 02 00 00 00 01 ...`). Clear it once:

```
esptool read-flash 0x7000 0x1000 cfg.bin
python -c "d=bytearray(open('cfg.bin','rb').read()); print(d[:16].hex(' ')); d[9]=0; open('cfg_fixed.bin','wb').write(d)"
esptool write-flash 0x7000 cfg_fixed.bin
```

The `print` shows the bytes before the change; it should start with `e1 01 00 01 00 02 00 00 00 01` (current slot 1, byte 9 is 1). Only that one
byte changes. Then the update URL works again. Build the next image with the current branch: its `revert` clears byte 9 itself, so this is needed only once.
Do not do it while the plug runs ESPHome from slot 0 and you do not know why; ask first.

## LEDs and power meter (optional third test, needs a load)

`example-plugs-meter.yaml` is the first test image plus both LEDs and the power meter. Only the relay is read from the firmware; the LED pins
(GPIO0 red, GPIO2 blue), the meter pins (GPIO12 select, GPIO5 CF, GPIO14 CF1) and the meter values (current resistor, voltage divider) come
from the ESPHome device page for the Plug S, which credits a named tester for the configuration. Nobody has tried them on a plug in this project yet. The readings are not calibrated, they only show whether the meter is
wired the way the device page says. On a real plug (2026-11-13) both LEDs and the meter pins worked; a 41 W lamp read 250.2 V, 0.24 A and 48.5 W (reference from another plug: 41 W, about 239 V), so the values need calibration. The image ran on the dev board (it starts and configures all of it); no signal was on the pins there.

- Build it like the first image, with `example-plugs-meter.yaml` instead (the Docker command compiles `/config/example-plugs-meter.yaml`, the
  firmware is in `/cache/data/build/plugs-meter/.pioenvs/plugs-meter/firmware.bin`), same password, and `send` it as a second update. Its own
  network is called `plugs-meter` (same password `change-me-please`), join that one afterwards.
- **Case closed, plug in the wall, no UART.** Join the network `plugs-meter` and read the values as JSON from `192.168.4.1` (user `admin`,
  password = your `gen1_ota_password`): `curl -u admin:PASSWORD http://192.168.4.1/sensor/Power`, also `/sensor/Voltage`, `/sensor/Current`,
  `/sensor/Energy`, `/switch/Relay` and `/binary_sensor/Button`. The names are case sensitive (capital first letter). The values update every
  10 seconds. The start page `http://192.168.4.1/` lists the entities, but it needs the internet to show values, so it stays empty in the
  plug's network. To switch the relay without the button: `curl -u admin:PASSWORD -X POST http://192.168.4.1/switch/Relay/toggle`.
- Press the button: the relay toggles, the **red LED follows the relay**, the **blue LED is lit while the button is held**.
- Put a known load on the relay (a lamp or a kettle, well below the plug's 10 A / 2300 W) and report the page values next to the real value of
  the load (a plug-in power meter, or the rated watts). A cut-off at 2400 W turns the relay off in this image; it is a test cut-off, not a
  protection, because the values are not calibrated. Anyone who knows the network password can switch the relay while this image runs.
- Report: which LED lights when, whether red and blue are the right way round, whether the load is really switched on when the page says
  `ON`, and the readings with and without load.

## The complete configuration

ESPHome's own wireless install (the dashboard's "Install wirelessly", `esphome upload`) does not work on a Gen1 yet: it needs the `eboot` bootloader, and
the plug keeps rBoot. Build the image in ESPHome (or the Docker command above), then send it with `tools/gen1_ota.py send`. Making the dashboard's
wireless install work is a goal, not started.

`plugs.yaml` is the configuration meant for daily use: your WiFi (with the plug's own network `shelly-plug-s` as fallback), the API, relay,
button, both LEDs, the meter with limits, daily energy and the temperature, and `gen1_ota` for updates. Use it after the first install and the
two small tests worked. Fill `secrets.yaml` (`wifi_ssid`, `wifi_password`, `ap_password`, `api_key`, `gen1_ota_password`), build it like the test
images (compile `/config/plugs.yaml`, firmware in `/cache/data/build/shelly-plug-s/.pioenvs/shelly-plug-s/firmware.bin`, convert, `send`). The
image is about 400 kB; the receiver accepts up to 425,984 bytes. The LED, meter and temperature parts are from the ESPHome device page and not
yet tried on a plug in this project; the meter is not calibrated. Keep the `wifi: ap:` block: if the WiFi fails, the plug opens its own network
and `send` and `revert` still reach it at `192.168.4.1`.

## Open points

- One real Plug S (short case) reported the first start, the config afterwards, restarts after power cuts and the relay, a second update (`send`) and `revert`. The three-update case is untested there. Installing again after `revert` failed there because of byte 9 (see below); after the one-time UART fix it worked there. `revert` with the fixed image and installing again without UART worked there too (2026-11-13).
- The `boot` part is never replaced (the stock updater marks it `update: false`).
- Power loss at other moments of the copy, repeated updates.
- Relay (`GPIO15`, read from the firmware) and button (`GPIO13`, device page) are confirmed on one real plug, including the relay level (a lamp on the plug lights when the relay is on). The LED pins (red `GPIO0`, blue `GPIO2`) and the meter pins (`GPIO12`, `GPIO5`, `GPIO14`) are confirmed on the same plug (2026-11-13); the meter values are not calibrated and the NTC temperature is not tried.
