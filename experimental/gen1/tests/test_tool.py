"""Host-side tests for tools/gen1_ota.py: image conversion, structure check, and the wire protocol against a fake device."""
import hashlib
import hmac
import os
import socket
import struct
import sys
import threading
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import gen1_ota  # noqa: E402


def fake_sketch() -> bytes:
    irom = bytes(range(256)) * 8
    out = struct.pack("<BBBBI", 0xE9, 3, 0, 0, 0x40100000)
    for addr, seg in ((0x40208010, irom), (0x3FFE8000, b"\x11" * 5), (0x40100000, b"\x22" * 12)):  # 5 bytes: must be padded
        out += struct.pack("<II", addr, len(seg)) + seg
    return out + b"\x00"


def test_convert_pads_and_checks():
    img = gen1_ota.convert(fake_sketch())
    assert img[:2] == b"\xEA\x04"
    assert gen1_ota.check(img) is None
    # firmware.bin variant (eboot in front) gives the same image
    eboot = struct.pack("<BBBBI", 0xE9, 1, 0, 0, 0x40100000) + struct.pack("<II", 0x40100000, 4) + b"\x00" * 4
    assert gen1_ota.convert(eboot + b"\xFF" * (0x1000 - len(eboot)) + fake_sketch()) == img


def test_check_rejects_damage():
    img = bytearray(gen1_ota.convert(fake_sketch()))
    bad = bytearray(img)
    bad[bytes(img).index(b"\x22\x22")] ^= 1  # inside the inner image; the irom segment is not covered by rBoot's checksum (the transfer CRC is)
    assert gen1_ota.check(bytes(bad)) == "checksum"
    assert gen1_ota.check(bytes(img[:-1])) is not None
    assert gen1_ota.check(b"\xE9" + bytes(img[1:])) == "not an rboot image"


def device(password: bytes, result: dict):
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def run():
        c, _ = srv.accept()
        nonce = os.urandom(16)
        c.sendall(nonce)
        buf = b""
        while len(buf) < 44:
            buf += c.recv(44 - len(buf))
        hdr, mac = buf[:12], buf[12:]
        if not hmac.compare_digest(mac, hmac.new(password, nonce + hdr, hashlib.sha256).digest()):
            c.sendall(b"ERR auth\n")
            return
        if hdr[:4] == b"G1RV":
            result["revert"] = True
            c.sendall(b"OK\n")
            return
        size, crc = struct.unpack("<II", hdr[4:])
        c.sendall(b"READY\n")
        data = b""
        while len(data) < size:
            data += c.recv(size - len(data))
        result["ok"] = zlib.crc32(data) == crc and len(data) == size
        c.sendall(b"OK\n")

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return srv.getsockname()[1], t


def test_send_right_and_wrong_password():
    img = gen1_ota.convert(fake_sketch())
    res = {}
    port, t = device(b"correct horse", res)
    assert gen1_ota.send(img, "127.0.0.1", port, b"correct horse") == "OK"
    t.join(2)
    assert res["ok"]
    port, t = device(b"correct horse", {})
    assert gen1_ota.send(img, "127.0.0.1", port, b"wrong") == "ERR auth"


def test_revert_right_and_wrong_password():
    res = {}
    port, t = device(b"correct horse", res)
    assert gen1_ota.revert("127.0.0.1", port, b"correct horse") == "OK"
    t.join(2)
    assert res.get("revert") is True
    res = {}
    port, t = device(b"correct horse", res)
    assert gen1_ota.revert("127.0.0.1", port, b"wrong") == "ERR auth"
    t.join(2)
    assert "revert" not in res
