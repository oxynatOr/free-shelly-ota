# Shelly Power Strip 4 Gen4 - ESPHome config

Files: `shelly-power-strip-gen4.yaml` (the config), `PowerStrip-stock.csv` (Shelly's partition table, read from the official
2.0.1 package), `secrets.yaml.example` (copy to `secrets.yaml`).

Shelly's partition table is at **0x10000** on this model, so the config sets `CONFIG_PARTITION_TABLE_OFFSET: "0x10000"`.

| Function | Pin | Status |
|---|---|---|
| SPI MISO / MOSI / SCLK | GPIO12 / GPIO11 / GPIO13 | matches the stock firmware's boot log (`SPI2 init`) |
| ADE7953 chip select (outlets 1+2 / 3+4) | GPIO15 / GPIO10 | matches the stock boot log (`CS0/1/2: 15/10/-1`) |
| ADE7953 IRQ (chip 0 / chip 1) | GPIO6 / GPIO7 | in use on the author's device |
| Relays 1 to 4 | GPIO4 / GPIO2 / GPIO3 / GPIO1 | in use on the author's device |
| Buttons 1 to 4 | GPIO20 / GPIO22 / GPIO23 / GPIO21 | in use on the author's device (pull-up, inverted) |
| LED ring (WS2812, 12 LEDs, 3 per outlet) | GPIO18 | in use on the author's device |

Install with ShellyOTA:

```
python ota.py build PowerStrip app.ota.bin --esphome-factory app.factory.bin --esphome-yaml ../configs/shelly-power-strip-gen4/shelly-power-strip-gen4.yaml
python ota.py send PowerStrip out/<file>.zip --watch 60
```

Read the ShellyOTA README, "Notes & troubleshooting", first: on a Power Strip running stock **1.7.99** a direct `send` did not
work (the app landed in slot 1 and the old app started again). It worked after one official update to 2.0.1. With
`--watch`, the log line `Will write to slot 0` is the one you want.

After a successful install the UART log shows `ESP-IDF ... 2nd stage bootloader` (ESPHome's bootloader), `ota data partition
invalid and no factory, will try all partitions` (expected) and `Loaded app from partition at offset 0x20000`.

## What was changed from the author's config

The author's working config pulls Wi-Fi, API, safe mode and diagnostics from private include files. This published version
replaces them with plain blocks:

- Wi-Fi, API key and fallback AP password come from `!secret` (see `secrets.yaml.example`); the author's static IP is left as a
  commented example.
- `wifi:` options (hidden network, fast connect, no power save, 20 dB output, WPA2 minimum), the safe mode values (5 min, 10
  attempts, 60 s) and the Wi-Fi diagnostic entities were taken from the author's config and its boot log.
- The `WiFi Signal Percent` conversion is a generic dBm-to-percent filter written for this example; the author's original
  may differ.
- `ota:` has no `encryption:` entry here. The author's build requires OTA encryption (boot log: `Encryption: required`); add
  it yourself if you want that.

## Status

The author's config runs on a real Power Strip; ESPHome boots with ShellyOTA's package and joins Wi-Fi and Home Assistant
(UART log). This published file was cleaned up as described above and checked with `ota.py build --esphome-yaml` and a YAML
parse only. It has **not been compiled** in this exact form, and outlets, buttons, LEDs and metering were not checked by whoever
wrote this README.
