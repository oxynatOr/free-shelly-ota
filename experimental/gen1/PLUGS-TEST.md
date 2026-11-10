# Shelly Plug S (Gen1, SHPLG-S): first test, draft

> **For testers only. This is not a supported way to flash a Plug S.** It has never run on a real Plug S, and there is no Gen1 profile or
> `ota.py` command. A mistake can leave the plug without working firmware; the way back needs a UART connection and a flash backup.
> It switches mains power: open the case only with the plug unplugged. Do not try it on a device you cannot recover over UART.

Status: **draft, nothing here has run on a real Plug S.** The sequence ran on a Wemos D1 mini with the Plug S flash layout and the
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
- Button on GPIO13 toggles the relay. **GPIO13 is not confirmed**, it is a community value, not read from the firmware.
- Left out on purpose: LEDs (GPIO0/GPIO2), power meter (GPIO12/5/14), all unconfirmed.

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
- If the plug does not come back at all: UART, write `backup.bin` back (`esptool write-flash 0 backup.bin`). There is no way back without UART.

## Open points

- Not tested on a real Plug S.
- The `boot` part is never replaced (the stock updater marks it `update: false`).
- Power loss at other moments of the copy, repeated updates.
- Relay level and the pins of button, LEDs and meter are not confirmed.
