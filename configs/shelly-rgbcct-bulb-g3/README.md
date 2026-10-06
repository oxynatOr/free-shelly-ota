# Shelly Multicolor Bulb E27 Gen3 (RGBCCT) - ESPHome notes and config

Status: **the OTA works, the light is unconfirmed.** `ota.py send` with `--esphome-factory` ran through on a real bulb and ESPHome runs
(reported by the owner, 2026-10-06). The LED driver component, the channel order and the colours have not been checked yet. 

Files: `shelly-rgbcct-bulb-g3.yaml` (config with an RGBW light and per-channel test lights), the LED driver component lives in its own repository, https://github.com/oxynatOr/esphome-kp18058 (pinned in the YAML), `RGBCCTBulbG3-stock.csv` (Shelly's partition table from the
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

Every byte carries an even-parity bit in bit 0.

**Channel order** (read from two places in the firmware: the function that builds the frame from the colour parameters, and
the start-up routine that lights the three colours one after the other; both put the first colour value on OUT2, the second on
OUT3 and the third on OUT1): **OUT1 = blue, OUT2 = red, OUT3 = green.** That the three values are R, G, B in this order is
inferred from the start-up order, not proven. In the colour-temperature path **OUT4 and OUT5 get the same value**, so the bulb
looks like RGB plus one white level (colour temperature is mixed from the RGB channels). The config therefore uses an `rgbw` light
that drives OUT4 and OUT5 together. It also contains one test light per channel to confirm this on the bulb. The 13-byte length, the standby bytes `0x00 0x03`, the parity bits and the 5-bit halves all match the KP18058/KP18068
protocol as implemented by the OpenBeken project (which sends the low half first and a slightly different third byte; the
differences may be a chip variant, they were not checked).

Correction of an earlier note: the I2C **addresses are `0x70` and `0x40`** (7-bit), not `0x38` and `0x20`.

## What is missing

- **No official ESPHome component.** There is no `kp18058` page in the ESPHome documentation; the pull request
  (esphome/esphome#7685) was closed. The config uses the separate component
  [oxynatOr/esphome-kp18058](https://github.com/oxynatOr/esphome-kp18058) (2-wire bit-bang on two pins, frame as above), pinned to a
  commit. Differences to the Shelly firmware: it sends the address byte `0xE1` (Shelly's I2C hardware sends `0xE0`), and it needs
  an ACK for every byte unless `ignore_ack: true` is set (the chip may not send one). If the light stays dark, try `ignore_ack`
  first. The first build on the bulb used an earlier version of the component than the pinned one.
- The current codes (5 for RGB and 11 for white, read from the constants), the channel order and the behaviour at full
  brightness are unverified.
- A Duo Bulb (`DuoBulbG3`) is a different design: its firmware has no I2C code, it uses PWM (LEDC).

## Installing

Use ShellyOTA as for the other devices: build with the partition table from `RGBCCTBulbG3-stock.csv` and
`CONFIG_PARTITION_TABLE_OFFSET: "0x10000"`, then `ota.py build RGBCCTBulbG3 ... --esphome-factory ...`, `ota.py send` (it
checks that the installer writes to slot 0 and tells you when to run `ota.py restore` first). Confirmed on this device (the first build used the config of this folder).
Keep UART or USB access as your way back.

## Duo Bulb

The owner reports that the Duo Bulb has the same main board with a different lamp module. Its stock firmware has no I2C code and drives
PWM (LEDC), so this config's LED driver does not apply to it. The OTA part (`DuoBulbG3` profile) should work the same way but has not been run.
