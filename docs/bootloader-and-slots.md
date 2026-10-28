# Bootloader and slots

[← README](../README.md) · [Documentation](README.md) · [Device pages](devices/README.md) · [Troubleshooting](troubleshooting.md)

[✅ Recommended](#recommended-ship-esphomes-bootloader) · [🔢 min_version](#is-the-new-bootloader-really-written-min_version) · [🎯 Slot 0](#the-app-must-land-in-slot-0) · [📦 Plain package](#without-esphomes-bootloader-plain-package) · [🧩 Beta layout](#beta-firmware-with-another-flash-layout)

Two things decide whether an ESPHome image started from a Shelly package keeps working: whose **bootloader** runs, and which
**slot** the installer writes the app to. Every [device page](devices/README.md) repeats the commands; this page explains the why.

| Question | Short answer |
| --- | --- |
| Whose bootloader should run? | ESPHome's: build with `--esphome-factory` |
| Does the installer write it? | Only if the package's `min_version` is higher than the loader it considers installed |
| Which slot does the app land in? | It has to be slot 0, otherwise the old app starts again; `send` refuses if it is not |
| What if Shelly's loader stays? | ESPHome runs for three starts; only an ESPHome OTA during that time can keep it, and only once. After that only UART helps. `send` stops before it sends such a package (`--force` overrides) |

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
`boot_min_version: 1.0.9`. The Plug M Gen3 profile sets it too: the official 2.0.1 package carries loader 1.0.3, so a Plug M restored
from it (for example over UART) reports 1.0.3 and would skip a package with 1.0.3. The Plug S Gen3 package carries the same bootloader
(byte-identical), so its profile sets 1.0.9 as well. Hardware-confirmed for 1.0.9 on a Plug M Gen3 from factory firmware 1.8.99 (installed loader 1.0.2): `Boot: cur 010002ff, ..., min 010009ff, update? 1`, then `Installing BL ... -> boot(0)`.

- **Check it:** the update log (`send --log-file` keeps it, `--log-level raw` shows it as it arrives) shows `Boot: cur ... min ... update? 0/1` and, when written,
  `Installing BL ... -> boot(0)`. Shelly's loader prints only ROM lines over UART on some models (the Multicolor Bulb prints
  `Shelly OS loader 1.0.2`); ESPHome's prints `ESP-IDF ... 2nd stage bootloader`.
- **`update? 0`:** `send --watch` (and `restore --watch`) now prints a WARNING when the package carries ESPHome's bootloader and
  the log says `update? 0` (cur and min shown as versions, `010003ff` = 1.0.3) and leaves out the "no separate bootloader update
  is needed" note. Build again with a higher `--boot-min-version` (for example `1.0.9`) or set `boot_min_version:` in the
  profile.
- **Wrong value already installed:** a UART fix (back up first): write ESPHome's bootloader to `0x0` (ESP32-C3, ESP32-C6) or `0x1000`
  (classic ESP32: Plus Plug S, Plus Uni, Pro 3EM) and a clean (all `0xFF`) `otadata` to the `otadata` partition, both taken from the
  package. Simpler: flash the `.factory.bin` of an ESPHome build that uses the device's stock partition CSV at `0x0`; it carries both.
- **Untested:** a later `restore` of the official package, whose `min_version` is lower than 1.0.9, may leave ESPHome's
  bootloader in place.

## The app must land in slot 0

After the update the installer writes its own boot state into `otadata`, which ESPHome's bootloader cannot read
(`ota data partition invalid and no factory, will try all partitions`). It then starts the first valid app in the table,
`app_0`. So the app only runs if the installer wrote it to slot 0 (shown as `Device: The installer writes to slot 0`; raw log: `Will write to slot 0`).

The installer writes to the slot the stock firmware is **not** running from. Seen on the Power Strip 4 Gen4 on stock 1.7.99:
the installer wrote to slot 1, the old stock app in `app_0` started again although the update reported success and ESPHome's
bootloader was in place (UART log: `Loaded app from partition at offset 0x20000`, `PowerStrip 1.7.99`). After one official
update to 2.0.1 and a new `send`, ESPHome started.

**How `send` helps:** right after the debug log is switched on, the device prints `Storing core dumps to app_N`, and N was the
same as the later `Will write to slot N` in all runs so far. When the package replaces the bootloader, `send` reads that line
first (briefly switching on the UDP log, so allow UDP port 9514) and **refuses to send if N is not 0**, telling you to run
`ota.py restore <Device>` first. `--ignore-slot` sends anyway. The `slot=` value in the first output line is not a reliable
predictor, so the check uses the log line. (On the Mini 1PM Gen4 Zigbee firmware on a dev board it was the running slot, and the update went to the other one: slot 0 running, target 1; after `restore` slot 1 running, target 0. One board only.)

> [!NOTE]
> Not every firmware prints an app slot there. The Plug M Gen3 on stock 1.8.99 logs `Storing core dumps to scratch (0x720000)`,
> which names no slot. `send` then prints `this firmware does not reveal the update target slot before the update` and goes on
> (it does not refuse, and it does not blame the firewall: the log did arrive). With `--watch`, look for `Will write to slot N`
> yourself. That device ran from slot 1 and the installer wrote to slot 0, as the rule above says; with N = 1 the old app starts
> again and the cure below applies.

> [!TIP]
> **The cure:** `python ota.py restore <Device>` (official firmware, Shelly's bootloader back), then `send` again; the
> target is then slot 0. The Plus Plug S went through exactly this ([page](devices/PlusPlugS.md)).
>
> Stuck anyway (ESPHome in `app_1`, old app in `app_0`, no way to run `restore`)? A UART step also works:
> [Select slot 1 with a hand-made otadata](troubleshooting.md#select-slot-1-with-a-hand-made-otadata).

## Without ESPHome's bootloader (plain package)

> [!WARNING]
> A package built without `--esphome-factory` keeps Shelly's loader, and that does not give a lasting install (see below). `send` stops before it
> sends such a package; `--force` sends it anyway.

Shelly's loader stays. It keeps its own boot state in the `otadata` area and starts only the slot recorded there; it never
looks at the entry that an ESPHome OTA writes (`esp_ota_set_boot_partition`). After a Shelly-style install the state is
"uncommitted" with three attempts left: the loader prints `Uncommitted boot of app 0 (attempts 3)` (then 2, 1) on each start,
and on the next one `App 0 failed to boot, reverting to 1`. It then switches to the other slot (the rollback slot, where the old
firmware ran) and marks it **committed**. From then on it only prints `Booting app N` and never switches again. ESPHome does
not change that state and never commits.

What that means for a unit:

- ESPHome runs for three starts after the install. Then the old Shelly firmware comes back, unless an ESPHome OTA arrived in time.
- An ESPHome OTA writes its image into the other slot, which is the rollback slot. If it is there when the countdown ends (about three
  restarts after the install; the restart after the OTA counts), the switch lands on the new image and commits it. That works **once**.
- After that, further OTAs are written but never started: the unit keeps running the image it switched to. Restarts, safe mode and the
  web OTA do not change that. Only UART helps: ESPHome's bootloader and a clean `otadata` (see "Wrong value already installed" above).

This is read from the loader code (Plus Uni and Plug M Gen3, both loader 1.0.3). It was reproduced on a plain ESP32 test board that runs the
Plus Uni loader with the boot state of the Plus Uni report ([#46](https://github.com/oxynatOr/free-shelly-ota/issues/46), October 2026): the
countdown, the switch, the committed state and an ESPHome OTA that is written but never started. It was not repeated on a Plus Uni or a
Plug M with UART. The way without UART is the package with ESPHome's bootloader (`--esphome-factory`).
The ESPHome log shows `esp_ota_ops: ota data invalid, no current app. Assuming factory`; that is expected and does not stop ESPHome from booting.

The Plug US project handles this in two steps:

1. Build with `ota: - platform: esphome` and `allow_partition_access: true`, install once over the network. ESPHome then
   alternates between the stock `app_0` and `app_1` slots.
2. Run ESPHome Builder's **Update bootloader** action. It replaces the bootloader and keeps Shelly's partition table.

> [!WARNING]
> **Do not interrupt power while the bootloader updates.** If it fails you need UART.

This step was documented for the Shelly Plus Plug US (ESP32); it has **not been tested here on any device** (the package route
above avoids it). Thanks to [inventor7777](https://github.com/inventor7777/ESPHome-Shelly-Plus-Plug-US) for working this out.

## Beta firmware with another flash layout

Shelly's `2.2.0-beta2` (checked 2026-10-28, all profiles) changes the flash layout of 17 G3 devices to one common table with app slots of `0x300000` (the table the DimmerG3 already had): Dimmer0110VPMG3, DuoBulbG3, I4G3, Mini1G3, Mini1PMG3, MiniPMG3, OutdoorPlugSG3, Pill, PlugMG3, PlugPMG3, PlugSG3, RGBCCTBulbG3, S1G3, S1LG3, S1PMG3, S2LG3, S2PMG3. The BluGwG3 beta also has another table than its profile. Unchanged are all G4 devices, EMG3, S3EMG3, EMG4, MiniEMG4, Pro3EM, HTG3, PlusPlugIT, PlusUni and DimmerG3; PlusPlugS has no beta. The stable packages of the wave of 2026-10-26 (2.0.3, 2.1.1) kept bootloader and table (four samples checked).

- `fetch` and `inspect` warn about such a package, `build` refuses it, so no image for the wrong layout can be made.
- Only the Plug M Gen3 has a profile for it so far (`PlugMG3-beta`, [device page](devices/PlugMG3.md#beta-layout)). The others get one when someone needs the beta or when Shelly ships the layout as a stable release.
- The installer of Shelly 1.8.99 cannot change the layout (`Skipping app`), the one of 2.0.x can. The bootloaders in the beta differ between device groups; their `boot_min_version` has not been compared yet.

---

---

[Troubleshooting](troubleshooting.md) · [Recovery over UART](recovery-uart.md) · [`build` options](commands.md#build)
