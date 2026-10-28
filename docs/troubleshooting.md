# Troubleshooting

[← README](../README.md) · [Documentation](README.md) · [Bootloader and slots](bootloader-and-slots.md) · [Recovery over UART](recovery-uart.md)

[📤 Sending and building](#sending-and-building) · [🔌 After the update](#after-the-update) · [🧪 Background and open questions](#background-and-open-questions) · [🛡️ Safety](#safety)

Device-specific problems are on the [device pages](devices/README.md); the slot and bootloader rules are in
[Bootloader and slots](bootloader-and-slots.md).

> [!TIP]
> When something goes wrong, run `send` with `--log-file`: the file holds the whole device log and is what a bug report needs ([Log levels](commands.md#log-levels)).

## Sending and building

### `send` refuses: update target slot is not 0

See [The app must land in slot 0](bootloader-and-slots.md#the-app-must-land-in-slot-0). Run `python ota.py restore <Device>`
first, then `send` again.

### `send` stops with `Not committed`

```
The device refused the update: "Not committed". ...
```

The stock firmware does not accept `Shelly.Update` for a while after a start (HTTP 500, `{"code":-109,"message":"Not committed"}`).
Seen on the Multicolor Bulb Gen3 at an uptime of about 60 s; a device log showed a commit delay of about 90 s. These numbers are
observations, not a documented Shelly value.

`send` reads the uptime (`Sys.GetStatus`) before it asks you to confirm. If the device has been running for less than two minutes it
says so and offers to wait. If the device refuses anyway, `send` explains it, offers to wait `--wait` seconds (default 120) and asks
for a new confirmation before the next pass, at most three passes. With `--yes` it never waits or retries on its own: then keep the
device powered for a few minutes and run `send` again. A restart resets the uptime, so avoid power-cycling the device in between.

The same cause can be behind the warning "the update target slot could not be read": a device that has just started may not have
written the slot line to its log yet.

### Warning: the update target slot could not be read

The warning has two forms, and they point to different causes:

- **No UDP datagram arrived from the device:** the debug log does not reach this PC. Allow incoming UDP on port 9514 (on Windows
  the Python program in Windows Defender Firewall), or check `--log-port` and `--host`.
- **The device log arrives, but the slot line did not show up:** not a firewall problem. The device has probably just started;
  wait a minute and send again.

Without the slot the tool cannot tell whether the installer writes to slot 0. If it writes to slot 1 the old app starts again.

### `send` warns: this firmware does not reveal the update target slot

The debug log works, but the line `Storing core dumps to ...` names something other than `app_N` (the Plug M Gen3 on stock
1.8.99 logs `scratch`), so the slot check has nothing to read and cannot refuse in advance. This is not a firewall problem.
Send with `--watch` and look for `Will write to slot N`: 0 is right; 1 means the old app starts again, see
[The app must land in slot 0](bootloader-and-slots.md#the-app-must-land-in-slot-0). The other warning, `the update target slot
could not be read (UDP log blocked? ...)`, means no such line arrived at all: see [No progress, no device log](#no-progress-no-device-log).

### Build refuses to replace the bootloader

`build` stops with "differs from Shelly's in ...": the ESPHome bootloader's header must match the one in the official package
in flash mode, size/frequency, chip and minimum chip revision, otherwise the device might not start. The message prints both
values and a `Fix:` line. Seen so far:

| Message | Fix |
| --- | --- |
| Flash frequency 40 MHz instead of 80 MHz | Classic ESP32: `CONFIG_ESPTOOLPY_FLASHFREQ_80M: "y"` under `sdkconfig_options`. ESP32-C6: `board_build.f_flash: 80000000L` under `platformio_options`. |
| `minimum_chip_revision` / `sram1_as_iram` | Remove them from the config for the package. They are fine for builds you only update with ESPHome OTA. |
| Partition table differs | Use the device's `partitions/<Profile>-stock.csv` and its `CONFIG_PARTITION_TABLE_OFFSET`. |
| `.factory.bin` from another build | Build `APP.bin` and the factory image from the same compile. |

### `build --compile` is slow, or stops before the compile

The first compile with Docker downloads the toolchain and builds all of ESP-IDF; that takes many minutes. It is the only slow one: the toolchain stays in the Docker volume `free-shelly-esphome-cache` ([Compile](commands.md#compile)). If every compile is slow, the volume is gone or is not used.

| Message or symptom | Cause and fix |
| --- | --- |
| `Docker is installed but not running` | Start Docker Desktop (Windows) or the service (`sudo systemctl start docker`), then run `build` again. |
| `Neither 'esphome' nor 'docker' was found` | Install one of them; the message says how. |
| `ESPHome config check failed` (before the compile) | The YAML must have the `esp32:` block with the profile's partition table and offset, written out in the file itself: `!include` and `packages` are not followed ([Quick start](../README.md#quick-start)). |
| `... already exists. Use --tag ...` (before the compile) | A package with that name is in `out/`. Use `--tag LABEL`, `-o ZIP` or `--force`. |
| Every compile downloads ESP-IDF again | The volume was removed, or a different `--image` version is used. `docker volume ls` shows `free-shelly-esphome-cache`. |
| Very slow with the `esphome` command under WSL | The YAML is on `/mnt/c` or `/mnt/i`. Copy it into the Linux home and compile there. |
| `Could not prepare the Docker volume` or `Permission denied` (Linux) | The volume belongs to another user. `docker volume rm free-shelly-esphome-cache` and compile again. |
| `no firmware.ota.bin was found` | The compile did not produce one: the config needs `framework: type: esp-idf`. |
| Disk full | The volume is 3 GB and more; `docker system df -v` shows it, `docker volume rm free-shelly-esphome-cache` frees it. |

### No progress, no device log

`send` reads the device log (UDP datagrams on port 9514, `--log-port`) to show the progress and the device's own confirmation.
A firewall that blocks incoming UDP on that port (on Windows, the Python program in Windows Defender Firewall) leaves the log
empty; the update itself still works, and `send` then ends with "Done: the device downloaded the ZIP" instead of "Done: update
installed, the device confirmed it". With the log you see the progress (0 to 100 %), the confirmation (`ota_success`) and, for a
package with ESPHome's bootloader, the line `Boot: cur ... min ... update? 0/1`, shown as "The bootloader will be replaced" or
"will NOT be replaced". To see the raw log use `--log-level raw`, to keep all of it `--log-file`.

### `send` stops with an update error of the device

If the device's log reports an update error (an `ota_error` event or any event with "error" in its message), `send` stops with
the device's text and prints the last lines of the device log, whatever the log level. The event name `ota_error` is assumed, not
seen yet: if a device fails differently, the `--log-file` file shows how. Please report it.

### The device has no Wi-Fi and opens no access point

Seen on the Zigbee firmware of the Mini 1PM Gen4 on a dev board: the log said `WiFi mode: off`, `Shelly.GetDeviceInfo` said `"provision": "pending"`, no access point appeared, and only Bluetooth was on.
`send` needs an address, so give the device a Wi-Fi over Bluetooth first (needs `pip install bleak` and a Bluetooth LE adapter in this PC):

```
python ota.py ble scan
python ota.py ble wifi MyNetwork -
```

The second command asks for the password, waits for the address and prints it; use it as `--ip`. Nothing is found by `scan`: the device must be powered and within a few metres, and
BLE RPC must be on. `restore` and the ESPHome package wipe NVS, so the Wi-Fi is gone afterwards and `ble wifi` sets it again ([`ble`](commands.md#ble)). Not tried on a real device yet.

### The device does not download the ZIP

`send` ends with "did not download the ZIP within ..." when the Shelly cannot reach this PC. The usual cause is a network
rule: the Shelly sits in an IoT VLAN or guest network that may not connect to this PC (the other direction works: this PC
reaches the Shelly, so `send` can talk to it). `send --dry-run` asks the device to fetch `http://<this PC>:8000/` itself and fails with
`Connection error` if it cannot; the same check by hand:

```
http://<Shelly IP>/rpc/HTTP.GET?url="http://<PC IP>:8000/"
```

Any HTTP status in the answer (a 404 is fine) means the way is open. Allow TCP port 8000 (or your `--port`) from the Shelly's
network to this PC, or put the PC in the same network for the update. If `send` picked the wrong PC address, set `--host`.

A device with a **weak Wi-Fi signal** can reach this PC and still be too slow: at -68 dBm a Mini 1 Gen3 downloaded about 1 % per 5 s and `send` stopped after the default 300 s at 28 %. The device kept its old firmware. `send` now says it when the signal is -67 dBm or weaker and asks how long to wait ([Wi-Fi signal](commands.md#wi-fi-signal)); with `--yes` run it again with `--timeout 1200`, or move the device or the access point closer.

### Battery devices (H&T Gen3)

The stock updater refuses to start below 30 % battery: `Shelly.Update` answers HTTP 500 with
`{"code":-109,"message":"OTA not allowed (Battery below 30 percent. )"}`. `send` shows the device's message and tells you to
charge the battery; it does not retry. Charge or replace the battery first. The device must also be awake. The code `-109` is
shared with `Not committed` (above), so `send` tells them apart by the message text.

> [!NOTE]
> Charge or replace the battery first. The device must also be awake.

## After the update

### ESPHome does not start after the update

- Read the output of `send` (or the `--log-file` file): did it say `The installer writes to slot 0` (raw log: `Will write to slot 0`)? If not,
  see [slot 0](bootloader-and-slots.md#the-app-must-land-in-slot-0).
- A real **power cycle** may be needed after the first boot (the cause is not understood; some state of the stock firmware
  seems to survive a soft reset). Disconnect the device from mains, wait at least 30 seconds so the capacitors can discharge
  (a rule of thumb, not measured), then reconnect. Do not open a device that is connected to mains. On the Plug M Gen3,
  ESPHome came up after a power-off of about 30 seconds; on a second Plug M it ran at once (Wi-Fi, API, sensors), but the relay and the LED
  reacted only after such a power-off.
- UART shows what runs: `ESP-IDF ... 2nd stage bootloader` and `Loaded app from partition at offset 0x20000` are good signs.

### ESPHome OTAs "work" but the version does not change

The installer skipped ESPHome's bootloader (`Boot: ... update? 0`) or the app landed in the wrong slot. See
[`min_version`](bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version).

### Select slot 1 with a hand-made otadata

> [!WARNING]
> This is a UART step: read the safety note in [Recovery over UART](recovery-uart.md) first.

If ESPHome sits in `app_1` while the old app in `app_0` starts (and `restore` is not possible), write an ESP-IDF `otadata`
entry that selects `app_1` (sequence number 2: partition `(2-1) % 2 = 1`) at the device's `otadata` offset (`0xd000` on the
Plus Plug S). The 8 KB file:

```
python -c "import struct,zlib;e=struct.pack('<I20sII',2,b'\xff'*20,0xFFFFFFFF,zlib.crc32(struct.pack('<I',2),0xFFFFFFFF));open('otadata_app1.bin','wb').write(e.ljust(4096,b'\xff')+b'\xff'*4096)"
esptool --chip esp32 --port COM4 write-flash 0xd000 otadata_app1.bin
```

Undo: `esptool erase-region 0xd000 0x2000` makes the bootloader start `app_0` again. After that, ESPHome's own OTA switches between
the two slots (confirmed for the OTA path on the Plus Plug S; not checked after this UART variant).

## Background and open questions

### URL update vs. upload

`send` uses `Shelly.Update?url=` with a local web server. This worked on the Plug M Gen3 (stock firmware 1.8.99, running from
slot 1). The Tasmota project advises against URL updates and uses the web UI file upload instead; if URL mode fails on your
device, that is why.

### Gen4 signature check (disputed)

The ESPHome device page for the Power Strip 4 Gen4 says stock OTA is not possible because Gen4 verifies OTA images with an
ECDSA signature, so it needs a UART flash. The Gen4 project in the [Credits](../README.md#credits) documents OTA installs for
other Gen4 models, and the Power Strip itself took the package from stock 2.0.1. Which is true may depend on model and
firmware version. A third-party report says Gen4 devices skip the app and stall at 87 % when updated from slot 0; that was not
seen here. If a Gen4 device rejects the package, check the log and fall back to UART.

### eFuse

A related project reports a permanent eFuse marker for non-official firmware (Plus Plug US). Unverified for Gen3. Observed on
the H&T Gen3 (stock 2.0.1, unsigned package): after the update the installer logged `FW signatures: want 07 got 00` followed
by `EFUSE write error bit[1]` and `bit[2]` with `Bits are not empty. Write operation is forbidden.` So it tries to write eFuse
bits for a package without the signature marks, and those writes were refused because the bits were already set. The update
still succeeded and ESPHome ran. What the bits mean is not known.

> [!WARNING]
> This may be irreversible on a device where the bits were still empty, so treat it as a possible permanent change.

The same marker appeared on a PM Mini Gen3 (stock 2.0.1, package with ESPHome's bootloader): `Incoming fw signatures: 00`, then
`EFUSE write error bit[1]: 5636`, then a normal reboot. The update succeeded and ESPHome ran.

A Plug M Gen3 (stock 1.8.99, official 2.1.0 package with ESPHome's bootloader) logged `FW signatures: want 07 got 00` but no
`EFUSE write error`; the update succeeded and ESPHome ran. Whether the bits were written silently or not touched is not known (this
plug's eFuses were not read back with `espefuse summary`).

A Plus Uni (classic ESP32, stock 2.0.1) logged `FW signatures: want 07 got 00` and then, twice, `BURN BLOCK3` followed by
`BURN BLOCK3 - OK (all write block bits are set)`: no error this time. Whether the eFuse changed was not checked (no
`espefuse summary` before and after). On the Plus Plug S unit that was brought back over UART, `BLOCK3` had a byte `0x07` set.

The Multicolor Bulb Gen3 logged the same (`EFUSE write error bit[0]` and `bit[1]`, `Bits are not empty`) in an update on 2026-10-15
and the device confirmed the update. At the default log level `send` shows these lines as one note ("The installer logs refused
eFuse writes"); the full lines are in `--log-level raw` and in the `--log-file` file.

## Safety

Nothing is downloaded unless you run `fetch` (or pass `--download`). Shelly firmware is not part of this repository (`fw/` and
`out/` are git-ignored; `out/` can contain credentials, see [Credential check](credential-check.md)).

---

> [!TIP]
> **Still stuck?** If a flash went wrong, [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml);
> if the tool crashed or a message is wrong, [report a bug](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=bug.yml).
> Both forms ask for the log, without Wi-Fi passwords, keys, the cloud key or MAC addresses.

[Bootloader and slots](bootloader-and-slots.md) · [Recovery over UART](recovery-uart.md) · [Credential check](credential-check.md)
