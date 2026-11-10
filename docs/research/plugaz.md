# Research: Shelly AZ Plug

[← AZ Plug](../devices/PlugAZ.md) · [Bootloader and slots](../bootloader-and-slots.md)

Details from the official PlugAZ 2.0.3 package, build
`20261026-122214/2.0.3-g4601943`, and the conversion reported by
[Tilen (tilenkranjc)](https://github.com/tilenkranjc) on 2026-11-08/09.
The [device page](../devices/PlugAZ.md) describes the checked behavior and
remaining limits. These notes preserve the analysis and the optional
workaround for the toolchain used in that report.

## Stock relay mapping

The AZ relay mapping agrees with stock 2.0.3: initialization at
`0x42008eac–0x42008eb8` passes pin 4 and active level 1 to the output
constructor at `0x420a4840`; the write routine at `0x420a4720` uses that
level for ON and its complement for OFF. These are addresses in the stock
image, not device identifiers. Tilen confirmed relay operation after a
complete power cycle on 2026-11-09. The firmware analysis alone does not
establish hardware behavior.

## Image export for the reported toolchain

The reported build used ESPHome 2026.6.5, ESP-IDF 5.5.4, PlatformIO
platform 55.03.39 and esptool 5.3.0. That PlatformIO exporter omitted chip
revision arguments even though the compiled SDK configuration requires
revisions 0.3–1.99. Both the legacy and full revision fields were re-exported
from the same compiled ELFs using esptool, then checked without changing
any code/data segments. The stock minimum is 3, full minimum 3, full
maximum 199. Do not bypass the bootloader header check or patch arbitrary
firmware headers.

This optional recipe is specific to the ESP32-C3 AZ layout on the device page. Run it in
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
