# Slot swap in the package (experimental)

[← README](../README.md) · [Documentation](README.md) · [Bootloader and slots](bootloader-and-slots.md) · [Commands](commands.md#send) · [Recovery over UART](recovery-uart.md)

How `send --slot-swap` and `build --pt-addr 0x8000` avoid the `restore` before a first install, what was seen on which board, and the way back. The background (why the app has to land in slot 0) is on [Bootloader and slots](bootloader-and-slots.md#the-app-must-land-in-slot-0).

> [!WARNING]
> **Experimental. Seen working on two dev boards (ESP32-C6 and ESP32-C3, 2026-11-05 to 2026-11-09). On a real device (a Shelly 2PM Gen3) only a plain `send` of a `--pt-addr` package was tried, `--slot-swap` itself was not run there (from the reporter's notes, no raw log).** The package moves the
> partition table and `send --slot-swap` changes it, and the installer writes it to flash. If that goes wrong, a serial
> connection and a flash dump of the device are needed to bring it back ([Recovery over UART](recovery-uart.md)). Going back to
> Shelly's firmware after such an install worked on two dev boards, over the network ([see below](#the-way-back-over-the-network-seen-on-two-boards)).

The installer and ESPHome's bootloader read different fields of the partition table. The installer finds the app slots by
label and address (`app_0`, `app_1`). ESPHome's bootloader, with an `otadata` it cannot read, starts the app partition whose
**subtype** is `ota_0`, and in Shelly's table that is `app_0`. That is why the app has to land in slot 0.

**Why the table has to move.** A `pt` part for the address where Shelly's table already is (`0x10000`, `0xf000` on some
devices) is not written there: the installer logs `Installing new PT1` and keeps the table in a journal that only Shelly's own
loader reads. ESPHome's bootloader reads the address it was built for, finds Shelly's old table and starts `app_0`, although the
update reports success. This was seen on a Gen4 dev board (stock 2.1.1) and on Gen3 dev boards (stock 2.0.1 and 2.1.0). A `pt`
part with another address is written there (log: `PT is being moved from 0x10000 to 0x8000`, `Installing PT ... -> pt(0x8000)`),
and Shelly's own table stays where it is, untouched. The idea and the first log of this come from
[WulffTech](https://github.com/WulffTech) ([#95](https://github.com/oxynatOr/free-shelly-ota/issues/95)).

**How it fits together.**

1. Build the ESPHome config **without** `CONFIG_PARTITION_TABLE_OFFSET` (ESP-IDF's default `0x8000`; keep `partitions:` with the
   stock CSV). Its bootloader then reads the table at `0x8000`.
2. `python ota.py build DEVICE --compile app.yaml --pt-addr 0x8000` (or `APP.bin --esphome-factory FACTORY.bin --pt-addr 0x8000`)
   ships that bootloader and Shelly's table with the address `0x8000`. `0x8000` is the only value for now: it is free on the
   Gen3/Gen4 flash maps. A profile whose table is at `0x8000` already has nothing to move.
3. `send DEVICE package.zip --slot-swap` reads the target slot as above (`Storing core dumps to app_N`). If it is 1, the device
   gets a copy of the package whose table has the two app subtypes swapped: `app_1` is `ota_0`, `app_0` is `ota_1`. Labels,
   addresses, sizes, flags and every other entry stay Shelly's; only the table's MD5 entry is recomputed. ESPHome's bootloader
   then starts slot 1, where the installer wrote the app: one `send`, no `restore` before it.

- Target slot 0: the table is not swapped, but it is still moved: the package goes out as built.
- Target slot unknown (no log line, or a firmware that names `scratch`): `send` stops. The table is only swapped for a slot the
  device has named.
- `send --slot-swap` refuses a package whose table was not moved, one without ESPHome's bootloader and a clean `otadata`, and
  `--ignore-slot`; it is not for `restore`.
- The swapped copy lives in a temporary folder for this one `send`; the package in `out/` stays as it is. `-v` shows the SHA-256
  of the table before and after.
- If the update log then says `Will write to slot N` for another slot than the one read before, or does not show the table being
  moved, `send` warns at once.

What was seen (2026-11-05/06, dev boards with the DevKit images, `build --compile ... --pt-addr 0x8000` and `send --slot-swap`):

| Board | Profile (stock) | Result |
| --- | --- | --- |
| ESP32-C6, 8 MB | `S1PMG4` (2.1.0) | Target slot 1. `PT is being moved from 0x10000 to 0x8000`, `Installing PT ... -> pt(0x8000)`. ESPHome's bootloader printed the swapped table, started `app_1`, the access point of the ESPHome config came up. A second ESPHome OTA (another build) took effect and the board then started from `app_0`. |
| ESP32-C3, 8 MB | `S1PMG3` (2.1.0) | Target slot 1. `PT is being moved from 0xf000 to 0x8000`, `Installing PT 4096@fs_1(0x660000) -> pt(0x8000)`. Bootloader started `app_1`, the access point of the ESPHome config came up. |

Repeat on 2026-11-09 (same two boards, stock 2.1.0 DevKit images, packages from `build --compile ... --pt-addr 0x8000`): swap send, way back, and a second send straight after the `restore` all worked on both. After the `restore` the installer's target was slot 0 on both boards (Shelly's app sits in slot 1 then), so the second send had nothing to swap and ESPHome started from `app_0`.

Reported on a real device (WulffTech, a Shelly 2PM Gen3 that had run ESPHome for a while, from their notes, not a raw log): the way back with the same steps, then a plain `send` (no `--slot-swap`) of a package built with `--pt-addr 0x8000`. ESPHome booted, Wi-Fi, mDNS, API and OTA came up, both relays and the power sensor were checked. Three earlier plain sends fell back to the old firmware: each time `send` could not read the target slot (the device's UDP log never arrived) and went ahead blind, and the unit reported slot 0, then 1, then 1 before them (the second try after only 96 s of uptime). After a `restore` and a proper wait the same plain send worked. `--slot-swap` itself was not run on the real device: seven dry runs all stopped with the slot "could not be read". Why no UDP log arrived on that unit is not known (a stale log destination after a restore is one candidate, see the open pull request #140).

Without the move (the table at Shelly's own address) the same boards, and a Gen3 board on stock 2.0.1, ended on the old app after
a reported success.

Not known yet:

- whether the way back below works on other models (it was seen on a C6 and a C3 board and, per the reporter's notes, on a real 2PM Gen3; a Plug M Gen3 once stopped with
  `no valid boot state!` after the same first step, see [Recovery over UART](recovery-uart.md));
- whether the installer chooses its target slot again after it has written the new table: in the runs above it did not;
- `--slot-swap` on a real device: it was never run there, because the slot could not be read (no UDP log from the unit);
- devices: apart from the one report above (a plain send, not `--slot-swap`), all of this was seen on dev boards only, not on a device in a wall or a socket.

## The way back over the network (seen on two boards)

Seen on the ESP32-C6 dev board (`S1PMG4`, stock 2.1.1, 2026-11-06), after a `--slot-swap` install, without UART:

1. Push **Shelly's own app image** (the `app` part of the official package, `S1PMG4.bin`) to the running ESPHome with its normal OTA
   (`esphome upload YOUR.yaml --device IP --file S1PMG4.bin`). ESPHome writes it to the other slot and restarts into it.
2. **Leave the board alone for at least 90 s.** Shelly's firmware starts under ESPHome's bootloader, writes a fresh boot state and
   commits it after 90 s (log: `Commit after 90 seconds`). A reset or power cycle before that sends the board back to ESPHome.
3. Join the board's Shelly access point and run `python ota.py restore DEVICE --ip 192.168.33.1`. The installer logs
   `The bootloader will be replaced (current 00000000, ...)`, writes Shelly's bootloader and firmware to the other slot, and the
   board then boots `Shelly OS loader 1.0.3` with the original table from `0x10000` and Shelly's app.

Do **not** use `esphome upload --bootloader` for this: it stages the bootloader in the other app slot and destroys the Shelly app
there; with Shelly's loader in place the board then loops (`slot 0 is not bootable`) and only UART helps.
After the way back, another `--slot-swap` install worked too (this time with target slot 0: the table moves, nothing to swap).

Tested on two dev boards (C6 `S1PMG4`, C3 `S1PMG3`, stock 2.1.0 images, Shelly's app 2.1.1) and, for the way back and a plain send of a `--pt-addr` package, once on a real 2PM Gen3. If `restore` says "Not committed", wait a minute or two and run it again.
