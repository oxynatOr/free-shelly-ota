# Shelly Multicolor Bulb E27 Gen3 (RGBCCT) - ESPHome notes and config skeleton

Status: **hardware notes and a skeleton only.** There is no working light yet; nothing in this folder has been compiled or run
on the bulb. The OTA side (`RGBCCTBulbG3` profile, `RGBCCTBulbG3-stock.csv`) is prepared but also not tested on hardware.

Files: `shelly-rgbcct-bulb-g3.yaml` (skeleton with the I2C bus), `RGBCCTBulbG3-stock.csv` (Shelly's partition table from the
official 2.0.1 package), `secrets.yaml.example`.

## What is known

| What | Value | Source |
|---|---|---|
| Chip | ESP32-C3, 8 MB flash, partition table at `0x10000` | boot log, official package |
| I2C bus | **SDA = GPIO4, SCL = GPIO5, 100 kHz** | the firmware's own boot log: `I2C0: init ok (SDA: 4, SCL: 5, freq: 100000)` |
| LED driver | **KP18068** (Kiwi Instruments, 5-channel I2C LED driver) | marking `KP18068ESP` read on the board by the owner; the frame below matches the KP18058 family |
| Light component in Shelly OS | `rgbcct:0` | boot log |

## The frame Shelly OS sends (read from the firmware code, not measured on the bus)

The firmware writes **13 bytes** over its hardware I2C bus to a 7-bit address that depends on the state:

- address **`0x70`** (wire byte `0xE0`) when at least one channel is on, **`0x40`** (wire byte `0x80`) when all channels are off
  (standby).

```
byte  0      0x00
byte  1      0x0A when on, 0x03 when off            = (RGB current 5 << 1) | parity, or the fixed standby value
byte  2      0x56                                    = bit 6 set | (CW current 11 << 1) | parity
bytes 3..12  five channels, two bytes each, in this order of bytes: high part, then low part
             high = ((v >> 5) & 0x1F) << 1 | parity      low = (v & 0x1F) << 1 | parity     (v = 10-bit value, 0..1023)
```

Every byte carries an even-parity bit in bit 0. Which of the five channels is R, G, B, cold white, warm white is not decoded
here. The 13-byte length, the standby bytes `0x00 0x03`, the parity bits and the 5-bit halves all match the KP18058/KP18068
protocol as implemented by the OpenBeken project (which sends the low half first and a slightly different third byte; the
differences may be a chip variant, they were not checked).

Correction of an earlier note: the I2C **addresses are `0x70` and `0x40`** (7-bit), not `0x38` and `0x20`.

## What is missing

- **No official ESPHome component.** There is no `kp18058` page in the ESPHome documentation; a pull request
  (esphome/esphome#7685) for KP18058/KP18068 was closed, and that driver bit-bangs two pins. This bulb uses the I2C
  peripheral, so a small external component (an `I2CDevice` that writes the frame above, with the address switched between
  `0x70` and `0x40`) would be the way. It does not exist here yet.
- The channel order, the current codes (5 for RGB and 11 for white were read from the constants) and the behaviour at full
  brightness are unverified.
- A Duo Bulb (`DuoBulbG3`) is a different design: its firmware has no I2C code, it uses PWM (LEDC).

## Installing

Use ShellyOTA as for the other devices: build with the partition table from `RGBCCTBulbG3-stock.csv` and
`CONFIG_PARTITION_TABLE_OFFSET: "0x10000"`, then `ota.py build RGBCCTBulbG3 ... --esphome-factory ...`, `ota.py send` (it
checks that the installer writes to slot 0 and tells you when to run `ota.py restore` first). Not tested on this device.
Keep UART or USB access as your way back.
