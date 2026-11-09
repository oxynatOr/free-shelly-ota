# Shelly AZ Plug

[← README](../../README.md) · [All devices](README.md) · [Commands](../commands.md)

![State: partly checked](https://img.shields.io/badge/state-partly%20checked-yellow.svg?style=flat-square)
![Generation: 3](https://img.shields.io/badge/gen-3-lightgrey.svg?style=flat-square)
![Chip: ESP32-C3](https://img.shields.io/badge/chip-ESP32--C3-blue.svg?style=flat-square)

| Fact | Value |
| --- | --- |
| Profile | `PlugAZ` |
| Model | `S3PL-10112EU` |
| Flash | 8 MB |
| Official package | 2.0.3, build `20261026-122214/2.0.3-g4601943` |
| Partition table | `0xf000` |
| App slot size | `0x280000` (2,621,440 bytes) |
| ESPHome device page | [Plug S Gen3 reference, not AZ confirmation](https://devices.esphome.io/devices/shelly-plug-s-gen3/) |

**Partly checked:** Tilen reported a successful OTA conversion on one AZ Plug
on 2026-11-08, from stock 2.0.3 to minimal ESPHome 2026.6.5 (Wi-Fi, encrypted
API, OTA, captive portal). Later ESPHome OTA updates were confirmed through
the native API: the same unit subsequently ran ESPHome 2026.10.2 with the
full GPIO config and then its Bluetooth-proxy revision. The owner confirmed
on 2026-11-09 that the relay works after a complete power cycle. GPIO4 is
active high. Voltage, frequency and internal temperature readings were
received, but metering under a known load and NTC calibration are not
checked. The button and LED behavior are not individually confirmed.
No UART was used for this installation.

## Before you start

Check first:

- [ ] the device runs Shelly's own firmware, not ESPHome yet
- [ ] you know its IP address (`--ip`), or this PC is on the device's own access point
- [ ] the device can reach this PC: same network, port 8000 not blocked
- [ ] your ESPHome config uses the partition table below and is compiled
- [ ] a UART adapter is available for recovery ([Recovery over UART](../recovery-uart.md))

## ESPHome config

Copy `partitions/PlugAZ-stock.csv` next to your YAML. Keep your own Wi-Fi,
API and OTA credentials; no credentials or ready-made firmware are shipped here.

```yaml
esp32:
  variant: ESP32C3
  board: esp32-c3-devkitm-1
  flash_size: 8MB
  flash_mode: dio
  flash_frequency: 80MHz
  partitions: PlugAZ-stock.csv
  framework:
    type: esp-idf
    sdkconfig_options:
      CONFIG_PARTITION_TABLE_OFFSET: "0xf000"
    advanced:
      enable_ota_rollback: false

ota:
  - platform: esphome
    allow_partition_access: true
```

These flash settings match the official AZ image header. The reported build
used ESPHome 2026.6.5, ESP-IDF 5.5.4, PlatformIO platform 55.03.39 and esptool 5.3.0.
That PlatformIO exporter omitted chip revision arguments even though the
compiled SDK configuration requires revisions 0.3–1.99. Both the legacy and
full revision fields were re-exported from the **same compiled ELFs** using
esptool, then checked without changing any code/data segments. The stock
minimum is 3, full minimum 3, full maximum 199. Do not bypass the bootloader
header check or patch arbitrary firmware headers. See the explicit local-only
[export recipe](#image-export-for-the-reported-toolchain) if your build has
that mismatch. No re-export is needed if `build` already accepts the headers.

## Pins

| Function | Pin | Evidence on AZ |
| --- | --- | --- |
| Relay | GPIO4, active high | Stock firmware analysis and owner-confirmed switching after a power cycle |
| Button, pull-up, inverted | GPIO18 | Plug S Gen3 reference; not individually checked |
| BL0942 UART, 9600 baud | ESP RX GPIO6, ESP TX GPIO7 | Voltage/frequency readings received; load calibration not checked |
| NTC | GPIO3 | Temperature reading received; calibration not checked |
| WS2812 ring, four pixels, GRB | GPIO5 | Plug S Gen3 reference; not individually checked |

The reference is the ESPHome device page linked above. The AZ relay mapping
also agrees with stock 2.0.3: initialization at `0x42008eac–0x42008eb8`
passes pin 4 and active level 1 to the output constructor at `0x420a4840`;
the write routine at `0x420a4720` uses that level for ON and its complement
for OFF. These are addresses in the stock image, not device identifiers.
The reference NTC configuration uses 10 kΩ at
25 °C, B=3350 and a 10 kΩ downstream divider. Do not claim temperature
protection or metering accuracy on AZ until measured. Full device configs
belong in the separate `esphome-configs` project (see the [developer guide](../guide-developers.md#13-related-repositories-and-tools)).

## Flash it

```sh
python ota.py fetch PlugAZ --insecure
python ota.py build PlugAZ firmware.ota.bin --esphome-factory firmware.factory.bin --esphome-yaml plugaz.yaml
python ota.py send PlugAZ out/<package>.zip --ip <device-IP> --dry-run
python ota.py send PlugAZ out/<package>.zip --ip <device-IP> --log-file
```

Use the two binaries from the same build (or the exported pair below).
**Keep all the official parts, including `fs`:** a package with `fs` removed
was rejected by this AZ updater with `Missing a part`. Rebuilding with the
original filesystem part was followed by the successful report. It does not
mean ESPHome uses Shelly's filesystem. Do not pass `--drop-fs` or `--drop fs`.

## What to expect

The dry run must report `Update target slot: 0`. If it reports slot 1,
run `python ota.py restore PlugAZ --ip <device-IP>` first, wait for the
stock update to finish, then check again. An official reinstallation on the
reported unit moved its active slot from 0 to 1; the next target was 0.
`Shelly.GetDeviceInfo.slot` describes the active slot, not the target.

If UDP logging was left active through the reboot, re-enabling the same
address does not emit the startup target line. The log reader now toggles
that already-active destination before listening and restores it afterwards.
This fixed the slot check on the reported AZ Plug. If the target remains
unknown, stop and diagnose it rather than using `--ignore-slot`.

The stock restoration log reported installed loader 1.0.2; its normal
`min_version: 1.0.2` did not replace it (`update? 0`). The ESPHome package
requested 1.0.9. A final loader-write log is not available, but subsequent
ESPHome OTA updates and the resulting versions were confirmed. The state
stays 🟡 because full load testing and calibration are still outstanding.

**Relay does not click although the switch stays ON:** after the initial
conversion the owner saw exactly this behavior. Temperature was around
31 °C, power 0 W and the software protection was inactive. Disconnecting the
plug completely from mains and reconnecting it resolved the problem; the
owner confirmed relay operation on 2026-11-09. Do this only after the update
has finished. A retained GPIO state across the software reset is a working
explanation, not a measured cause. Releasing only GPIO4's pad hold in an
ESPHome boot hook has not been independently validated as a replacement
for that power cycle. Do not change the relay GPIO or disable protections
merely to work around this symptom.

## Notes for this device

- AZ identifies as **`PlugAZ`**, not `AZPlug` or `PlugSG3`. The official AZ
  package matches the device identity; renaming another model's manifest
  does not establish compatibility.
- Plug S Gen3 2.1.1 has its table at `0x10000` and app slots of `0x2a0000`;
  its app is 37,248 bytes larger than the AZ slot. Its bootloader also
  differs. Do not use that profile or firmware for AZ.
- On the reported unit, a first package without `fs` was rejected during
  backend validation; stock firmware continued to answer in active slot 1.
- No device addresses, credentials, compiled images or raw device logs are
  included in this repository. The evidence is the local report from Tilen.
- The source package was obtained from Shelly's update service with TLS
  verification disabled because the local CA chain failed; its internal
  hashes were checked. Those checks establish consistency, not authenticity.

### Image export for the reported toolchain

This optional recipe is specific to the ESP32-C3 AZ layout above. Run it in
an environment with esptool installed, using your own compiled build folder.
It does not contact or program the plug. Change `build_dir` and `official`
to your local paths. Keep the generated binaries private.

```python
from pathlib import Path
import re
import struct
import zipfile
from esptool.cmds import elf2image
from shelly_ota.bootswap import verify_image

build_dir = Path("<build-directory-containing-firmware.elf>")
official = Path("fw/shelly/PlugAZ/2.0.3/PlugAZ.zip")
out = Path("out/plugaz-export")
out.mkdir(parents=True, exist_ok=True)
sdk = (build_dir / "config/sdkconfig.h").read_text()
assert re.search(r"^#define CONFIG_ESP_REV_MIN_FULL 3$", sdk, re.M)
assert re.search(r"^#define CONFIG_ESP_REV_MAX_FULL 199$", sdk, re.M)
with zipfile.ZipFile(official) as z:
    header = z.read("bootloader.bin")[:24]
assert header[12:19] == bytes.fromhex("0500030300c700")

def segments(image):
    pos, result = 24, []
    for _ in range(image[1]):
        address, size = struct.unpack_from("<II", image, pos)
        result.append((address, image[pos + 8:pos + 8 + size]))
        pos += 8 + size
    return result

for elf, original, target, extra in (
    ("bootloader.elf", "bootloader.bin", "bootloader.bin", {}),
    ("firmware.elf", "firmware.ota.bin", "firmware.ota.bin",
     {"elf_sha256_offset": 0xb0}),
):
    elf2image(str(build_dir / elf), chip="esp32c3", output=str(out / target),
              flash_mode="dio", flash_freq="80m", flash_size="8MB",
              min_rev=3, min_rev_full=3, max_rev_full=199, **extra)
    image = (out / target).read_bytes()
    verify_image(image, target)
    assert segments(image) == segments((build_dir / original).read_bytes())
    assert image[2:4] == header[2:4] and image[12:19] == header[12:19]

factory = bytearray((build_dir / "firmware.factory.bin").read_bytes())
boot = (out / "bootloader.bin").read_bytes()
app = (out / "firmware.ota.bin").read_bytes()
assert len(boot) == (build_dir / "bootloader.bin").stat().st_size
assert len(app) == (build_dir / "firmware.ota.bin").stat().st_size
factory[:len(boot)] = boot
factory[0x20000:0x20000 + len(app)] = app
(out / "firmware.factory.bin").write_bytes(factory)
```

Pass `out/plugaz-export/firmware.ota.bin` and
`out/plugaz-export/firmware.factory.bin` to `build`. Its existing bootloader,
partition, slot-size and factory/app checks still run unchanged.

## Way back

`python ota.py restore PlugAZ` reinstalls the official package **while stock
firmware still runs**. Once ESPHome is installed, use normal ESPHome OTA
for future app updates, retaining the AZ partition CSV and table offset.
Restoring Shelly afterwards requires UART recovery.

---

> [!WARNING]
> - **Wipes Wi-Fi and settings.** ESPHome opens its own access point or joins the Wi-Fi from your config; if nothing comes up, power-cycle the device ([help](../troubleshooting.md#esphome-does-not-start-after-the-update)).
> - **No way back over the network** once ESPHome's bootloader runs: `restore` gets no answer, only UART brings Shelly OS back ([Recovery over UART](../recovery-uart.md)). Take a flash backup first if you can.
> - **Flashed it? Tell us,** also when it worked: [open a device report](https://github.com/oxynatOr/free-shelly-ota/issues/new?template=device-report.yml).

[Bootloader and slots](../bootloader-and-slots.md) · [Troubleshooting](../troubleshooting.md) · [Recovery over UART](../recovery-uart.md)
