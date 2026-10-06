# Troubleshooting

[Back to the README](../README.md)

Device-specific problems are on the [device pages](devices); the slot and bootloader rules are in
[Bootloader and slots](bootloader-and-slots.md). Always run `send` with `--watch`: the log answers most questions.

## `send` refuses: update target slot is not 0

See [The app must land in slot 0](bootloader-and-slots.md#the-app-must-land-in-slot-0). Run `python ota.py restore <Device>`
first, then `send` again.

## Build refuses to replace the bootloader

`build` stops with "differs from Shelly's in ...": the ESPHome bootloader's header must match the one in the official package
in flash mode, size/frequency, chip and minimum chip revision, otherwise the device might not start. The message prints both
values and a `Fix:` line. Seen so far:

| Message | Fix |
| --- | --- |
| Flash frequency 40 MHz instead of 80 MHz | Classic ESP32: `CONFIG_ESPTOOLPY_FLASHFREQ_80M: "y"` under `sdkconfig_options`. ESP32-C6: `board_build.f_flash: 80000000L` under `platformio_options`. |
| `minimum_chip_revision` / `sram1_as_iram` | Remove them from the config for the package. They are fine for builds you only update with ESPHome OTA. |
| Partition table differs | Use the device's `partitions/<Profile>-stock.csv` and its `CONFIG_PARTITION_TABLE_OFFSET`. |
| `.factory.bin` from another build | Build `APP.bin` and the factory image from the same compile. |

## Empty `--watch` log

The log arrives as UDP datagrams on port 9514 (`--log-port`). A firewall that blocks incoming UDP on that port (on Windows,
the Python program in Windows Defender Firewall) leaves the log empty; the update itself still works. With the log you see
the installer's `ota_progress` events (0 to 95 %, then `ota_success`) and, for a package with ESPHome's bootloader, the line
`Boot: cur ... min ... update? 0/1`.

## Battery devices (H&T Gen3)

The stock updater refuses to start below 30 % battery: `Shelly.Update` answers HTTP 500 with
`{"code":-109,"message":"OTA not allowed (Battery below 30 percent. )"}`. `send` shows the device's answer after "HTTP 500".
Charge or replace the battery first. The device must also be awake.

## ESPHome does not start after the update

- Read the log of `send --watch`: did it say `Will write to slot 0`? If not, see [slot 0](bootloader-and-slots.md#the-app-must-land-in-slot-0).
- A real **power cycle** may be needed after the first boot (the cause is not understood; some state of the stock firmware
  seems to survive a soft reset). Disconnect the device from mains, wait at least 30 seconds so the capacitors can discharge
  (a rule of thumb, not measured), then reconnect. Do not open a device that is connected to mains. On the Plug M Gen3,
  ESPHome came up after a power-off of about 30 seconds.
- UART shows what runs: `ESP-IDF ... 2nd stage bootloader` and `Loaded app from partition at offset 0x20000` are good signs.

## ESPHome OTAs "work" but the version does not change

The installer skipped ESPHome's bootloader (`Boot: ... update? 0`) or the app landed in the wrong slot. See
[`min_version`](bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version).

## Select slot 1 with a hand-made otadata

If ESPHome sits in `app_1` while the old app in `app_0` starts (and `restore` is not possible), write an ESP-IDF `otadata`
entry that selects `app_1` (sequence number 2: partition `(2-1) % 2 = 1`) at the device's `otadata` offset (`0xd000` on the
Plus Plug S). The 8 KB file:

```
python -c "import struct,zlib;e=struct.pack('<I20sII',2,b'\xff'*20,0xFFFFFFFF,zlib.crc32(struct.pack('<I',2),0xFFFFFFFF));open('otadata_app1.bin','wb').write(e.ljust(4096,b'\xff')+b'\xff'*4096)"
esptool --chip esp32 --port COM4 write-flash 0xd000 otadata_app1.bin
```

Undo: `esptool erase-region 0xd000 0x2000` makes the bootloader start `app_0` again. After that, ESPHome's own OTA switches between
the two slots (confirmed for the OTA path on the Plus Plug S; not checked after this UART variant).

## URL update vs. upload

`send` uses `Shelly.Update?url=` with a local web server. This worked on the Plug M Gen3 (stock firmware 1.8.99, running from
slot 1). The Tasmota project advises against URL updates and uses the web UI file upload instead; if URL mode fails on your
device, that is why.

## Gen4 signature check (disputed)

The ESPHome device page for the Power Strip 4 Gen4 says stock OTA is not possible because Gen4 verifies OTA images with an
ECDSA signature, so it needs a UART flash. The Gen4 project in the [Credits](../README.md#credits) documents OTA installs for
other Gen4 models, and the Power Strip itself took the package from stock 2.0.1. Which is true may depend on model and
firmware version. A third-party report says Gen4 devices skip the app and stall at 87 % when updated from slot 0; that was not
seen here. If a Gen4 device rejects the package, check the log and fall back to UART.

## eFuse

A related project reports a permanent eFuse marker for non-official firmware (Plus Plug US). Unverified for Gen3. Observed on
the H&T Gen3 (stock 2.0.1, unsigned package): after the update the installer logged `FW signatures: want 07 got 00` followed
by `EFUSE write error bit[1]` and `bit[2]` with `Bits are not empty. Write operation is forbidden.` So it tries to write eFuse
bits for a package without the signature marks, and those writes were refused because the bits were already set. The update
still succeeded and ESPHome ran. What the bits mean is not known; this may be irreversible on a device where the bits were
still empty, so treat it as a possible permanent change.

## Safety

Nothing is downloaded unless you run `fetch` (or pass `--download`). Shelly firmware is not part of this repository (`fw/` and
`out/` are git-ignored; `out/` can contain credentials, see [Credential check](credential-check.md)).
