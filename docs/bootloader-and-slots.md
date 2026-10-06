# Bootloader and slots

[Back to the README](../README.md)

Two things decide whether an ESPHome image started from a Shelly package keeps working: whose **bootloader** runs, and which
**slot** the installer writes the app to. Every [device page](devices) repeats the commands; this page explains the why.

## Recommended: ship ESPHome's bootloader

Build with `--esphome-factory firmware.factory.bin`. The tool takes ESPHome's bootloader and a clean `otadata` out of the
factory image and puts them into the Shelly package instead of Shelly's; the partition table and everything else stay as
shipped. Confirmed on the Plug M Gen3, Plug S Gen3, H&T Gen3, Power Strip 4 Gen4, Plus Plug S and Multicolor Bulb Gen3. After it,
ESPHome OTAs take effect at once (on the Plug M Gen3 two in a row, 0.0.1 to 0.0.2 to 0.0.3), the UART log shows ESPHome's
bootloader, and no separate "Update bootloader" step or UART is needed.

Before building, the tool verifies that

- the bootloader's checksum and SHA-256 are intact and its header (flash mode, size/frequency, chip, minimum revision) equals
  Shelly's ([header errors](troubleshooting.md#build-refuses-to-replace-the-bootloader));
- the factory image's partition table has the same critical entries as the device (`otadata`, `nvs`, `app_0/1`, `fs_0/1`;
  differences in `scratch`/`shelly` only warn) and its `otadata` area is erased;
- the factory image contains exactly the app you are packing (same build).

> [!WARNING]
> A bootloader that does not suit the device can only be fixed with UART. It worked on the six confirmed devices; on other
> models the installer's rule may differ. The Plug US project advises against replacing the bootloader in the initial package;
> this goes beyond its findings. `send` warns again when a package replaces the bootloader.

### Is the new bootloader really written? `min_version`

The installer writes the bootloader only if the package's `min_version` is higher than what it considers installed. The tool
raises it by one patch level over the official one (1.0.2 to 1.0.3). That was enough on the Plug M Gen3, Plug S Gen3, Plus
Plug S and the Multicolor Bulb (installed loader 1.0.2), but **not** on the H&T Gen3, whose installed loader is 1.0.3: the
update log showed `Boot: cur 010003ff, ... min ..., update? 0`, ESPHome started, but later ESPHome OTAs silently did not take
effect and `otadata` stayed in Shelly's format (`SH0S`). The H&T and Power Strip profiles therefore set
`boot_min_version: 1.0.9`.

- **Check it:** the update log (`send --watch`) shows `Boot: cur ... min ... update? 0/1` and, when written,
  `Installing BL ... -> boot(0)`. Shelly's loader prints only ROM lines over UART on some models (the Multicolor Bulb prints
  `Shelly OS loader 1.0.2`); ESPHome's prints `ESP-IDF ... 2nd stage bootloader`.
- **`update? 0`:** build again with a higher `--boot-min-version` (for example `1.0.9`) or set `boot_min_version:` in the
  profile.
- **Wrong value already installed:** a UART fix (back up first): write ESPHome's bootloader to `0x0` and a clean (all `0xFF`)
  `otadata` to the `otadata` partition, both taken from the package.
- **Untested:** a later `restore` of the official package, whose `min_version` is lower than 1.0.9, may leave ESPHome's
  bootloader in place.

## The app must land in slot 0

After the update the installer writes its own boot state into `otadata`, which ESPHome's bootloader cannot read
(`ota data partition invalid and no factory, will try all partitions`). It then starts the first valid app in the table,
`app_0`. So the app only runs if the installer wrote it to slot 0 (`--watch` log: `Will write to slot 0`).

The installer writes to the slot the stock firmware is **not** running from. Seen on the Power Strip 4 Gen4 on stock 1.7.99:
the installer wrote to slot 1, the old stock app in `app_0` started again although the update reported success and ESPHome's
bootloader was in place (UART log: `Loaded app from partition at offset 0x20000`, `PowerStrip 1.7.99`). After one official
update to 2.0.1 and a new `send`, ESPHome started.

**How `send` helps:** right after the debug log is switched on, the device prints `Storing core dumps to app_N`, and N was the
same as the later `Will write to slot N` in all runs so far. When the package replaces the bootloader, `send` reads that line
first (briefly switching on the UDP log, so allow UDP port 9514) and **refuses to send if N is not 0**, telling you to run
`ota.py restore <Device>` first. `--ignore-slot` sends anyway. The `slot=` value in the first output line is not a reliable
predictor, so the check uses the log line.

Then the cure is: `python ota.py restore <Device>` (official firmware, Shelly's bootloader back), then `send` again; the
target is then slot 0. The Plus Plug S went through exactly this ([page](devices/PlusPlugS.md)).

Stuck anyway (ESPHome in `app_1`, old app in `app_0`, no way to run `restore`)? A UART step also works:
[Select slot 1 with a hand-made otadata](troubleshooting.md#select-slot-1-with-a-hand-made-otadata).

## Without ESPHome's bootloader (plain package)

Shelly's loader stays. A later ESPHome OTA writes the new image into the other slot, but the device keeps booting the old
one until Shelly's attempt counter runs out. The loader prints `Uncommitted boot of app 0 (attempts 1)` and counts down on
every start (about three restarts here); then the next start switches slot. ESPHome never commits, so the counter keeps
running; whether the loader later switches back has not been checked. The ESPHome log shows
`esp_ota_ops: ota data invalid, no current app. Assuming factory`; that is expected and does not stop ESPHome from booting.

The Plug US project handles this in two steps:

1. Build with `ota: - platform: esphome` and `allow_partition_access: true`, install once over the network. ESPHome then
   alternates between the stock `app_0` and `app_1` slots.
2. Run ESPHome Builder's **Update bootloader** action. It replaces the bootloader and keeps Shelly's partition table.

**Do not interrupt power while the bootloader updates.** If it fails you need UART. This step was documented for the Shelly
Plus Plug US (ESP32); it has **not been tested here on any device** (the package route above avoids it). Thanks to
[inventor7777](https://github.com/inventor7777/ESPHome-Shelly-Plus-Plug-US) for working this out.
