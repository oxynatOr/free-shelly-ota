# Recovery over UART

[← README](../README.md) · [Documentation](README.md) · [Commands](commands.md#restore) · [Troubleshooting](troubleshooting.md)

[🪜 Steps](#steps) · [🚫 Not a way back](#not-a-way-back-pushing-the-official-app-over-esphome-ota)

The official package is also a way back for a device that no longer boots (or runs something else). Its `manifest.json` says
where every part goes; the parts can be written over UART with `esptool`. This brought a Shelly Plus Plug S (V2 hardware,
ESP32) that ran ESPHome back to Shelly OS. It was done by hand as described here; the log was not reviewed by this project.
It also brought a Plug M Gen3 (ESP32-C3) back from ESPHome; that boot log was reviewed: Shelly OS loader 1.0.3, `Booting app 0`,
app 2.0.1 up with its access point, factory data intact.

> [!WARNING]
> Disconnect the device from mains and power it from the adapter (3.3 V). Never connect UART to a device that is on mains.

No adapter yet? [Build one](#build-your-own-uart-adapter) from an ESP32 dev board.

> [!TIP]
> Try it on a dev board first: `ota.py devkit` writes the same parts as one image ([Test the update on a dev board](devkit.md)).

## Steps

1. **Download mode:** put the chip into download mode (GPIO0 to GND at reset; on an ESP32-C3 it is GPIO9).
2. **Back up the whole flash first:** `esptool read-flash 0x0 <size> backup.bin` (size from `esptool flash-id`). Writing it
   back (`write-flash 0x0 backup.bin`) restores the previous state.
3. **Read the eFuses, do not burn anything:** `espefuse summary`. Continue only if flash encryption is off
   (`FLASH_CRYPT_CNT = 0`) and secure boot is off (`ABS_DONE_0`/`ABS_DONE_1 = False`); otherwise a plain image will not boot.
4. **Get the addresses:** take the official ZIP (`ota.py fetch <Device>`), unpack it and read `manifest.json`: `boot` and `pt`
   have an `addr`, the other parts sit in the partition named by `ptn` (offsets in `partitions/<Profile>-stock.csv`).
5. **Erase NVS, then write all parts in one command.** Example for the Plus Plug S (classic ESP32):

   ```
   esptool --chip esp32 --port COM4 --baud 460800 erase-region 0x9000 0x4000
   esptool --chip esp32 --port COM4 --baud 460800 write-flash --flash-mode keep --flash-size keep --flash-freq keep 0x1000 bootloader.bin 0x8000 partition-table.bin 0xd000 boot_state.bin 0x10000 PlusPlugS.bin 0x1a0000 fs.img
   ```

   The same for the Plug M Gen3 (ESP32-C3, addresses from `partitions/PlugMG3-stock.csv` and the manifest):

   ```
   esptool --chip esp32c3 --port COM4 --baud 460800 erase-region 0x14000 0xc000
   esptool --chip esp32c3 --port COM4 --baud 460800 write-flash --flash-mode keep --flash-size keep --flash-freq keep 0x0 bootloader.bin 0x10000 partition-table.bin 0x11000 boot_state.bin 0x20000 PlugMG3.bin 0x2c0000 fs.img
   ```

   The official bootloader is Shelly OS loader 1.0.3, so a device restored like this reports 1.0.3 afterwards. The `PlugMG3`
   profile sets `boot_min_version: 1.0.9` for that reason ([why](bootloader-and-slots.md#is-the-new-bootloader-really-written-min_version)).
6. **Do not write the device-specific partitions** (`shelly`, and `aux` on Gen2): they hold the model name and per-device data,
   and no package contains them. If they are blank, the firmware may start without calibration or identity (the MAC lives in
   the eFuses).

> [!IMPORTANT]
> Other devices use other addresses, so take them from the manifest and the partition CSV, not from the examples.

## Build your own UART adapter

You do not need an FTDI stick. An ESP32 dev board with a USB port and a UART chip on board (CP2102 or CH340, as on the ESP32 DevKitC)
becomes a UART adapter with one extra wire: it holds the board's own ESP in reset, so only the USB-UART chip is active, and the `RX`
and `TX` pins of the board lead straight to the device. ESP8266 boards (NodeMCU, Wemos D1 mini) work the same way with `RST` instead
of `EN`. A dev board that talks over the chip's native USB (most ESP32-C3 and ESP32-C6 boards) cannot do this: there is no UART chip
on it.

### Parts

| Part | Notes |
| --- | --- |
| ESP32 dev board with a USB-UART chip | The one you already have is fine. |
| 6 jumper wires | One on the dev board from `EN` to `GND`; `3V3`, `GND`, `RX`, `TX` and one for download mode to the device. Female ends fit pin headers. |
| A contact for the pads | Pogo pins or test clips hold a bare pad while `esptool` runs; thin wires soldered to the pads are the most reliable. A wire held by hand is not: a lost contact during `write-flash` leaves a half-written flash. |
| Optional: push button or slide switch | In the download-mode wire, so that no wire has to be moved. |
| Optional: electrolytic capacitor, 100 to 470 µF | Across `3V3` and `GND` close to the device, if the chip resets while it writes. |

### Wiring

1. On the dev board: wire `EN` to `GND`. The ESP32 on the board stays in reset and lets go of its pins.
2. Dev board `3V3` and `GND` to `3V3` and `GND` of the device. Leave `5V`/`VIN` of the dev board unconnected: 5 V on a 3.3 V pad
   destroys the chip.
3. Dev board `RX` (`RX0`, GPIO3) to the device's `RX`, and dev board `TX` (`TX0`, GPIO1) to the device's `TX`. They are **not crossed**
   here: the pins of the dev board are named from the point of view of the ESP32 on it, which is in reset, so its pin `RX` carries
   what the USB-UART chip sends.

The pads of the device, by chip:

| Device pad | ESP32 | ESP32-C3 | ESP32-C6 |
| --- | --- | --- | --- |
| `RX` (UART0) | GPIO3 | GPIO20 | GPIO17 |
| `TX` (UART0) | GPIO1 | GPIO21 | GPIO16 |
| Boot pad, to `GND` only for download mode | GPIO0 | GPIO9 | GPIO9 |

- Boards usually label the pads (`TX`, `RX`, `IO0`/`IO9`, `3V3`, `GND`). If one is not labelled, look up the GPIO from the table in the
  datasheet of the ESP module and follow the trace.
- The device stays off mains, as in the warning above. Many Shelly devices have a non-isolated supply, so even the `GND` of the bare
  board can be live while it is plugged in.

### Check the adapter first

1. With nothing connected to the device, measure `3V3` to `GND` on the dev board with a multimeter: it must read about 3.3 V.
2. Loopback: with `EN` on `GND`, join `RX` and `TX` of the dev board with one wire and open a terminal
   (`python -m serial.tools.miniterm COM4 115200`; pyserial comes with `esptool`). What you type must appear again. Leave with
   Ctrl+], then remove the wire.

### Connect the device and enter download mode

1. Unplug the dev board from USB.
2. Connect `GND`, `RX` and `TX`, then `3V3`.
3. Connect the boot pad (`GPIO0`, on an ESP32-C3 or ESP32-C6 `GPIO9`) to `GND`, with a wire or by closing the switch.
4. Plug the dev board into USB. The device is powered and starts in download mode; the power-up is the reset, so the device needs no
   `EN` wire (the one on the dev board stays).
5. Test it: `esptool --port COM4 flash-id` must print the chip type and the flash size. Then go on with step 2 above (the backup).
6. After the last write: unplug USB, remove the boot-pad wire (open the switch) and plug in again. The device boots from flash. For the
   boot log open the terminal at 115200 baud.

### If it does not connect

| What you see | Likely cause and fix |
| --- | --- |
| `Failed to connect` or `Wrong boot mode detected` | The boot pad was not on `GND` when the power came on. Unplug USB, check the wire, plug in again. |
| `Connecting......` and nothing else | `RX` and `TX` swapped (on the dev board they are not crossed), `GND` missing, or a pad without contact. |
| Garbage or strange errors from the first byte | `EN` of the dev board is not on `GND`: its own ESP32 runs and talks on the same lines. |
| Garbage in the terminal | Wrong baud rate: the boot log is at 115200. |
| The chip resets while writing, a brown-out message | The 3.3 V supply of the dev board is too weak or the wires are too long. Add the capacitor, shorten the wires, write with `--baud 115200`. |
| `Write timeout` or CRC errors at 460800 | Wires too long or contacts poor: write with `--baud 115200`. |
| No COM port appears | The driver for the USB-UART chip (CP210x, CH340/CH343) is missing, or the USB cable only charges. |

### With a plain USB-to-UART module instead

If you have a module (CP2102, CH340, FT232RL, CH9102) the steps are the same, except: there is no `EN` wire; the module's `TX` goes to
the device's `RX` and its `RX` to the device's `TX` (crossed, because a module names its pins from its own point of view); and a 3.3 V
/ 5 V switch or solder jumper on the module must be on **3.3 V**. Leave `5V`/`VBUS` unconnected.

## Not a way back: pushing the official app over ESPHome OTA

> [!NOTE]
> One exception was seen: on an ESP32-C6 dev board (`S1PMG4`) the pushed official app started, committed its boot state after 90 s and then accepted `restore`. See [the way back over the network](bootloader-and-slots.md#the-way-back-over-the-network-seen-on-two-boards). The Plug M Gen3 case below did not.

A device that runs ESPHome accepts the official *app image* through ESPHome's own OTA and boots it, but that is no way back.
ESP-IDF's OTA writes `otadata` in its own format, and the Shelly app only reads its own (`SH0S`, the `boot_state.bin` of the
package). On a Plug M Gen3 it stops with `no valid boot state!` and `ShOS init failed: -32` and restarts in a loop (with
ESPHome's OTA rollback on, the bootloader returns to ESPHome after the first restart instead). `restore` never gets a chance to
run, so use the UART steps above.

---

> [!TIP]
> **Brought a device back this way?** Tell us how it went: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[`restore`](commands.md#restore) · [Bootloader and slots](bootloader-and-slots.md) · [Troubleshooting](troubleshooting.md)
