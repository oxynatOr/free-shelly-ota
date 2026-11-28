"""Say which official packages the firmware cache lacks: tests that need them are skipped or check less.

Run from the checkout. It only reads the cache; it never downloads anything.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelly_ota import firmware, profile  # noqa: E402


def missing() -> list[str]:
    lines = []
    for name in profile.list_devices():
        p = profile.load_profile(name)
        for variant in p.variants():
            if p.channel == "beta":
                found = firmware.cached_zip(p.package_name, prerelease=True)
            else:
                found = firmware.zip_for_layout(variant)
            if found is None:
                layout = f"layout since {variant.layout_since}" if variant.base else "first layout"
                lines.append(f"{name}: no cached package ({layout}, app slot 0x{variant.app_slot_size:x})")
    return lines


if __name__ == "__main__":
    gaps = missing()
    if gaps:
        print(f"Firmware cache: {len(gaps)} package(s) missing (get one with `python ota.py fetch <profile>`, then --sync):")
        print("\n".join(f"  {line}" for line in gaps))
    else:
        print("Firmware cache: a package for every profile and layout.")
