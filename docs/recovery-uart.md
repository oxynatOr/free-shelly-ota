# Recovery over UART

[Back to the README](../README.md)

The official package is also a way back for a device that no longer boots (or runs something else). Its `manifest.json` says
where every part goes; the parts can be written over UART with `esptool`. This brought a Shelly Plus Plug S (V2 hardware,
ESP32) that ran ESPHome back to Shelly OS. It was done by hand as described here; the log was not reviewed by this project.

> [!WARNING]
> Disconnect the device from mains and power it from the adapter (3.3 V). Never connect UART to a device that is on mains.

1. **Download mode:** put the chip into download mode (GPIO0 to GND at reset).
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

6. **Do not write the device-specific partitions** (`shelly`, and `aux` on Gen2): they hold the model name and per-device data,
   and no package contains them. If they are blank, the firmware may start without calibration or identity (the MAC lives in
   the eFuses).

Other devices use other addresses, so take them from the manifest and the partition CSV, not from the example.
