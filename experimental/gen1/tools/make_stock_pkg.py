#!/usr/bin/env python3
"""Build update packages for the Shelly Gen1 stock updater (/ota?url=...), needed for the FIRST installation only.

  make_stock_pkg.py <stock-dir> --out esphome.zip --image <rboot image from gen1_ota.py convert>
      stock package with the stock app replaced by the ESPHome image (build id derived from the image)
  make_stock_pkg.py <stock-dir> --out flip.zip --flip
      the unchanged stock package with a different build id: the stock updater refuses a package with the build id it is
      running, but it accepts a changed one, so this moves the stock firmware into the other slot

<stock-dir> is the extracted official Shelly firmware zip (manifest.json, switch1.bin, fs.bin, rboot.bin, ...). Those files
belong to Shelly and are not part of this project. The stock updater needs a stored (uncompressed) zip with the full
manifest; nothing is signed.
"""
import argparse
import hashlib
import json
import os
import zipfile


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stock_dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--image", help="rBoot image of the ESPHome build (gen1_ota.py convert)")
    ap.add_argument("--flip", action="store_true", help="repack the stock firmware with a changed build id")
    ap.add_argument("--build-id", help="override the build id of the package")
    args = ap.parse_args()
    if bool(args.image) == bool(args.flip):
        ap.error("give either --image or --flip")

    stock = args.stock_dir
    with open(os.path.join(stock, "manifest.json")) as f:
        m = json.load(f)
    files = {}
    if args.image:
        data = open(args.image, "rb").read()
        fw = m["parts"]["fw"]
        fw.update(size=len(data), cs_sha1=hashlib.sha1(data).hexdigest(), cs_sha256=hashlib.sha256(data).hexdigest(), src="fw.bin")
        files["fw.bin"] = data
        m["build_id"] = args.build_id or "gen1-ota/" + hashlib.sha1(data).hexdigest()[:12]
    else:
        m["build_id"] = args.build_id or m["build_id"] + "-flip"
    for part in m["parts"].values():
        src = part.get("src")
        if src and src not in files:
            files[src] = open(os.path.join(stock, src), "rb").read()
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_STORED) as z:  # the stock updater rejects compressed zips
        z.writestr("manifest.json", json.dumps(m, indent=2))
        for name, data in files.items():
            z.writestr(name, data)
    print("%s: build id %s, %d files" % (args.out, m["build_id"], len(files) + 1))


if __name__ == "__main__":
    main()
