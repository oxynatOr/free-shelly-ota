"""Run from ShellyOTA/: python -m unittest discover tests

The fake device below follows the ESPHome OTA protocol as the real device does it (plain app upload). It is NOT the real
thing: nothing here proves that a real ESPHome device accepts the upload.
"""

import hashlib
import socket
import struct
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelly_ota import builder, esphome_ota  # noqa: E402


class FakeEsphome:
    """One-connection-at-a-time ESPHome OTA server on a free local port."""

    def __init__(self, password=None, auth="sha256", version=2, flags=None, md5_error=False, drop_after_bytes=None,
                 magic_answer=None):
        self.password, self.auth, self.version, self.flags = password, auth, version, flags
        self.md5_error, self.drop_after_bytes, self.magic_answer = md5_error, drop_after_bytes, magic_answer
        self.received = bytearray()
        self.client_features = None
        self.finished = False   # the whole upload went through and the end acknowledgement arrived
        self.reached_size = False
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def close(self):
        self.sock.close()

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            conn.settimeout(5)
            try:
                self._handle(conn)
            except (OSError, EOFError):
                pass
            finally:
                conn.close()

    @staticmethod
    def _recv(conn, n):
        buf = b""
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise EOFError
            buf += chunk
        return buf

    def _handle(self, c):
        if self.magic_answer is not None:
            self._recv(c, 5)
            c.sendall(self.magic_answer)
            return
        if self._recv(c, 5) != esphome_ota.MAGIC:
            c.sendall(b"\x80")
            return
        c.sendall(bytes([0x00, self.version]))
        self.client_features = self._recv(c, 1)[0]
        c.sendall(b"\x40" if self.flags is None else bytes([0x48, self.flags]))
        if self.password is None:
            c.sendall(b"\x41")
        else:
            algo = hashlib.sha256 if self.auth == "sha256" else hashlib.md5
            if self.auth == "sha256" and not self.client_features & esphome_ota.FEATURE_SHA256_AUTH:
                c.sendall(b"\x82")  # current ESPHome: no SHA-256 feature bit, no access
                return
            nonce = algo(b"fake nonce").hexdigest()
            c.sendall(bytes([0x02 if self.auth == "sha256" else 0x01]) + nonce.encode())
            size = algo().digest_size * 2
            cnonce = self._recv(c, size).decode()
            answer = self._recv(c, size).decode()
            if answer != algo((self.password + nonce + cnonce).encode()).hexdigest():
                c.sendall(b"\x82")
                return
            c.sendall(b"\x41")
        size = struct.unpack(">I", self._recv(c, 4))[0]
        self.reached_size = True
        c.sendall(b"\x42")
        md5 = self._recv(c, 32).decode()
        c.sendall(b"\x43")
        while len(self.received) < size:
            block = self._recv(c, min(8192, size - len(self.received)))
            self.received += block
            if self.drop_after_bytes is not None and len(self.received) >= self.drop_after_bytes:
                return
            if self.version >= 2:
                c.sendall(b"\x47")
        c.sendall(b"\x44")
        if self.md5_error or hashlib.md5(self.received).hexdigest() != md5:
            c.sendall(b"\x8b")
            return
        c.sendall(b"\x45")
        self.finished = self._recv(c, 1) == b"\x00"


def image(size=20_000):
    return bytes((i * 7 + 3) % 251 for i in range(size))


class EsphomeOtaTests(unittest.TestCase):
    def dev(self, **kw):
        d = FakeEsphome(**kw)
        self.addCleanup(d.close)
        return d

    def push(self, d, data=None, **kw):
        return esphome_ota.push_app("127.0.0.1", data if data is not None else image(), port=d.port, **kw)

    def test_upload_without_password(self):
        d, data, seen = self.dev(), image(), []
        s = self.push(d, data, progress=lambda a, b: seen.append((a, b)))
        d.thread.join(0.2)
        self.assertEqual(bytes(d.received), data)
        self.assertEqual((s.ota_version, s.auth), (2, "none"))
        self.assertEqual(seen[-1], (len(data), len(data)))
        self.assertEqual(len(seen), -(-len(data) // 8192))   # one step per 8192-byte block
        self.assertEqual(d.client_features, esphome_ota.FEATURE_SHA256_AUTH)   # nothing else is offered

    def test_upload_with_sha256_password(self):
        d = self.dev(password="secret")
        s = self.push(d, password="secret")
        self.assertEqual(s.auth, "sha256")
        self.assertEqual(bytes(d.received), image())

    def test_upload_with_md5_password_on_an_older_device(self):
        d = self.dev(password="secret", auth="md5", version=1)
        s = self.push(d, password="secret")
        self.assertEqual((s.auth, s.ota_version), ("md5", 1))
        self.assertEqual(bytes(d.received), image())

    def test_feature_flags_of_newer_devices(self):
        d = self.dev(flags=0x02)
        self.assertEqual(self.push(d).server_flags, 0x02)

    def test_wrong_password(self):
        d = self.dev(password="secret")
        with self.assertRaises(builder.OtaError) as cm:
            self.push(d, password="nope")
        self.assertIn("password", str(cm.exception))
        self.assertFalse(d.reached_size)

    def test_password_needed_but_missing(self):
        d = self.dev(password="secret")
        with self.assertRaises(builder.OtaError) as cm:
            self.push(d)
        self.assertIn("--ota-password", str(cm.exception))
        self.assertFalse(d.reached_size)

    def test_dry_run_authenticates_and_sends_nothing(self):
        d = self.dev(password="secret")
        s = self.push(d, password="secret", dry_run=True)
        d.thread.join(0.3)
        self.assertEqual(s.auth, "sha256")
        self.assertEqual(bytes(d.received), b"")
        self.assertFalse(d.reached_size)

    def test_device_rejects_the_checksum(self):
        d = self.dev(md5_error=True)
        with self.assertRaises(builder.OtaError) as cm:
            self.push(d)
        self.assertIn("MD5", str(cm.exception))

    def test_connection_lost_during_upload(self):
        d = self.dev(drop_after_bytes=9000)
        with self.assertRaises(builder.OtaError):
            self.push(d)

    def test_port_without_esphome(self):
        d = self.dev(magic_answer=b"HTTP/1.1 400 Bad Request\r\n")
        with self.assertRaises(builder.OtaError) as cm:
            self.push(d)
        self.assertIn("ESPHome", str(cm.exception))

    def test_nothing_listens(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        with self.assertRaises(builder.OtaError) as cm:
            esphome_ota.push_app("127.0.0.1", image(), port=port, connect_timeout=2)
        self.assertIn("Cannot connect", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
