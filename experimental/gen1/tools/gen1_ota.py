#!/usr/bin/env python3
"""Host tool for the gen1_ota component (ESPHome on a Shelly Gen1 with rBoot).

  gen1_ota.py partitions <manifest.json|official.zip> [-o x.csv]   partition CSV from an official Shelly Gen1 package
  gen1_ota.py convert <firmware.bin|firmware.ota.bin> <image.bin> [--partitions P]   ESPHome build -> rBoot image for the slot
  gen1_ota.py check <image.bin>                                     structure check of an rBoot image
  gen1_ota.py send <image.bin> --host H [--port 8267] [--password-file F]   push an image (password: G1OT_PASSWORD or file)
  gen1_ota.py push <firmware.bin> --host H ...                      convert + send

Exit status is 0 only if the device answered OK.
"""
import argparse
import hashlib
import hmac
import importlib.util
import io
import json
import os
import socket
import struct
import sys
import zipfile
import zlib

MAX_IMAGE = 0x70000 - 0x8000  # what the receiver accepts with the Shelly 1 layout


def _load_layout_module():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "components", "gen1_ota", "layout.py")
    spec = importlib.util.spec_from_file_location("gen1_ota_layout", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gen1_ota_layout"] = mod
    spec.loader.exec_module(mod)
    return mod


gen1_layout = _load_layout_module()


def load_layout(name_or_path: str):
    """A partition CSV: a path, or one of the files shipped in components/gen1_ota/partitions -> Layout."""
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "components", "gen1_ota", "partitions", name_or_path)
    path = name_or_path if os.path.isfile(name_or_path) else here
    with open(path, encoding="utf-8") as f:
        return gen1_layout.parse_csv(f.read())


def layout_from_package(path: str, name: str = "") -> str:
    """Partition CSV text from a manifest.json or an official package zip."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            member = next(n for n in z.namelist() if n.endswith("manifest.json"))
            manifest = json.loads(z.read(member))
    else:
        with open(path, encoding="utf-8") as f:
            manifest = json.load(f)
    return gen1_layout.partitions_from_manifest(manifest, name)


def set_cache_bank(img: bytes, bank: int) -> bytes:
    """Set the SDK cache-mapping byte (.data 0x3FFE84FC) in the inner image for a slot in the 1 MB window `bank` (0: untouched).
    EXPERIMENTAL: on a Shelly Plug 2 (slot at 0x100000) the sketch still crashes right after rBoot starts it, see README."""
    if bank == 0:
        return img
    if bank != 1:
        raise ValueError("only the second MB window (bank 1) can be set up this way")
    out = bytearray(img)
    pos = 8 + 8 + struct.unpack_from("<I", out, 12)[0]  # inner E9 image
    p = pos + 8
    for _ in range(out[pos + 1]):
        addr, length = struct.unpack_from("<II", out, p)
        if addr <= 0x3FFE84FC < addr + length:
            o = p + 8 + 0x3FFE84FC - addr
            out[-1] ^= out[o] ^ 1
            out[o] = 1
            return bytes(out)
        p += 8 + length
    raise ValueError("the SDK cache byte (0x3FFE84FC) is not in the image")


def convert(data: bytes) -> bytes:
    """ESPHome firmware.bin (eboot 4 kB + sketch) or firmware.ota.bin (sketch) -> rBoot image (0xEA 0x04 + irom segment + 0xE9 image)."""
    # firmware.bin starts with eboot (an E9 image linked for IRAM); the sketch's first segment is the irom one (>= 0x40200000)
    if data[:1] != b"\xE9" or struct.unpack_from("<I", data, 8)[0] < 0x40200000:
        data = data[0x1000:]
    magic, count, _mode, _szf, entry = struct.unpack_from("<BBBBI", data, 0)
    if magic != 0xE9:
        raise ValueError("not an ESP8266 sketch image (expected 0xE9 at offset 0 or 0x1000)")
    pos, segs = 8, []
    for _ in range(count):
        addr, length = struct.unpack_from("<II", data, pos)
        segs.append((addr, data[pos + 8:pos + 8 + length]))
        pos += 8 + length
    if segs[0][0] < 0x40200000:
        raise ValueError("first segment must be the irom one")
    irom, rest = segs[0][1], segs[1:]
    out = bytearray(struct.pack("<BBBBI", 0xEA, 0x04, 0xFF, 0xF0, entry))  # flash mode / size as in the stock app
    out += struct.pack("<II", 0, len(irom)) + irom
    out += struct.pack("<BBBBI", 0xE9, len(rest), 0xFF, 0xF0, entry)
    checksum = 0xEF
    for addr, seg in rest:
        seg = seg + bytes(-len(seg) % 4)  # rBoot's loader copies with the ROM memcpy: an odd length is a byte store into IRAM
        out += struct.pack("<II", addr, len(seg)) + seg
        for b in seg:
            checksum ^= b
    out += b"\x00" * ((-len(out) - 1) % 16) + bytes([checksum])
    return bytes(out)


def check(img: bytes, max_image: int = MAX_IMAGE):
    """Same checks as the receiver; returns None if the image is fine, else the reason."""
    if img[:2] != b"\xEA\x04":
        return "not an rboot image"
    off = 16 + struct.unpack_from("<I", img, 12)[0]
    if off + 8 > len(img) or img[off] != 0xE9 or not 1 <= img[off + 1] <= 8:
        return "no inner image"
    count, off, cs = img[off + 1], off + 8, 0xEF
    for _ in range(count):
        if off + 8 > len(img):
            return "segment header"
        length = struct.unpack_from("<I", img, off + 4)[0]
        off += 8
        if length % 4 or off + length > len(img):
            return "segment length"
        for b in img[off:off + length]:
            cs ^= b
        off += length
    pos = off + (16 - (off + 1) % 16) % 16
    if pos + 1 != len(img) or img[pos] != cs:
        return "checksum"
    if len(img) > max_image:
        return "image larger than the receiver accepts (%d bytes)" % max_image
    return None


def _line(s: socket.socket) -> str:
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = s.recv(64)
        if not chunk:
            break
        buf += chunk
    return buf.decode(errors="replace").strip()


def send(img: bytes, host: str, port: int, password: bytes, timeout: float = 30.0) -> str:
    s = socket.create_connection((host, port), timeout=10)
    try:
        nonce = b""
        while len(nonce) < 16:
            chunk = s.recv(16 - len(nonce))
            if not chunk:
                raise ConnectionError("connection closed: " + nonce.decode(errors="replace").strip())
            nonce += chunk
        hdr = b"G1OT" + struct.pack("<II", len(img), zlib.crc32(img))
        s.sendall(hdr + hmac.new(password, nonce + hdr, hashlib.sha256).digest())
        s.settimeout(timeout)
        first = _line(s)
        if first != "READY":
            return first  # ERR auth / size / layout, the device closes the connection
        s.sendall(img)
        return _line(s)
    finally:
        s.close()


def _password(args) -> bytes:
    if args.password_file:
        return open(args.password_file, "rb").read().strip()
    pw = os.environ.get("G1OT_PASSWORD")
    if not pw:
        sys.exit("password missing: set G1OT_PASSWORD or use --password-file")
    return pw.encode()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    lo = sub.add_parser("partitions")
    lo.add_argument("package", help="manifest.json or the official package zip")
    lo.add_argument("-o", "--output")
    lo.add_argument("--name", default="")
    c = sub.add_parser("convert")
    c.add_argument("firmware")
    c.add_argument("image")
    k = sub.add_parser("check")
    k.add_argument("image")
    for q in (c, k):
        q.add_argument("--partitions", help="partition CSV (path or a shipped file; default: the Shelly 1 layout)")
    for name in ("send", "push"):
        p = sub.add_parser(name)
        p.add_argument("image" if name == "send" else "firmware")
        p.add_argument("--host", required=True)
        p.add_argument("--port", type=int, default=8267)
        p.add_argument("--password-file")
        p.add_argument("--partitions", help="partition CSV (path or a shipped file; default: the Shelly 1 layout)")
    args = ap.parse_args(argv)
    if args.cmd == "partitions":
        text = layout_from_package(args.package, args.name)
        if args.output:
            with open(args.output, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        else:
            sys.stdout.write(text)
        return 0
    lay = load_layout(args.partitions) if getattr(args, "partitions", None) else None
    max_image = lay.max_image if lay else MAX_IMAGE
    if args.cmd == "convert":
        img = convert(open(args.firmware, "rb").read())
        if lay:
            img = set_cache_bank(img, lay.cache_bank)
        open(args.image, "wb").write(img)
        print("%s: %d bytes" % (args.image, len(img)))
        return 0
    if args.cmd == "check":
        why = check(open(args.image, "rb").read(), max_image)
        print("ok" if why is None else "bad: " + why)
        return 0 if why is None else 1
    img = open(args.image if args.cmd == "send" else args.firmware, "rb").read()
    if args.cmd == "push":
        img = convert(img)
        if lay:
            img = set_cache_bank(img, lay.cache_bank)
    why = check(img, max_image)
    if why:
        print("refusing to send: " + why)
        return 1
    try:
        reply = send(img, args.host, args.port, _password(args))
    except OSError as err:
        print("no answer from %s:%d (%s). Is the device up and on this network?" % (args.host, args.port, err))
        return 2
    print("%d bytes sent, reply: %s" % (len(img), reply))
    return 0 if reply == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
