# Background and open questions

[← README](../README.md) · [Documentation](README.md) · [Troubleshooting](troubleshooting.md) · [Bootloader and slots](bootloader-and-slots.md) · [Recovery over UART](recovery-uart.md)

Things that are not a fix for a symptom: why `send` works the way it does, and what is still disputed or unknown.

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
