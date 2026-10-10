"""Push an app image to a device that runs ESPHome, with ESPHome's own OTA protocol (TCP port 3232).

This is the way back from ESPHome to the official Shelly firmware: a device that runs ESPHome does not answer
Shelly.Update, but it accepts an app image over ESPHome OTA. Only the plain app upload is implemented (no compression,
no Noise encryption, no bootloader or partition table upload). Written after the protocol of ESPHome's own client
(esphome/espota2.py); thanks to the ESPHome project.

Not used by any command yet. It was meant for a "to-stock" command (push the official Shelly app to a device that runs ESPHome,
then run `restore`). That does not work: the upload itself is accepted and the image boots, but ESP-IDF's OTA writes `otadata`
in its own format, and the Shelly app only reads its own (`SH0S`, `boot_state.bin` of the official package). On a Plug M Gen3 it
stops with "no valid boot state" and restarts in a loop (ShOS init failed: -32). Only code that rewrites `otadata` on the device,
or UART, gets such a device back to Shelly OS. Tested against a simulated ESPHome device only, never against an ESPHome release.
"""

from __future__ import annotations

import hashlib
import secrets
import socket
import struct
from dataclasses import dataclass
from typing import Callable

from .builder import OtaError

DEFAULT_PORT = 3232
MAGIC = bytes([0x6C, 0x26, 0xF7, 0x5C, 0x45])
BLOCK_SIZE = 8192

# client feature bits; only SHA-256 authentication is offered (current ESPHome devices accept nothing else)
FEATURE_SHA256_AUTH = 0x02

# device answers
RESPONSE_OK = 0x00
RESPONSE_REQUEST_AUTH = 0x01          # MD5 (older ESPHome)
RESPONSE_REQUEST_SHA256_AUTH = 0x02
RESPONSE_HEADER_OK = 0x40
RESPONSE_AUTH_OK = 0x41
RESPONSE_UPDATE_PREPARE_OK = 0x42
RESPONSE_BIN_MD5_OK = 0x43
RESPONSE_RECEIVE_OK = 0x44
RESPONSE_UPDATE_END_OK = 0x45
RESPONSE_SUPPORTS_COMPRESSION = 0x46
RESPONSE_CHUNK_OK = 0x47
RESPONSE_FEATURE_FLAGS = 0x48

# Every byte from 0x80 up is an error code.
ERRORS = {
    0x80: "the device did not accept the protocol header (magic bytes)",
    0x81: "the device cannot prepare the update",
    0x82: "wrong OTA password (or the device wants a password and none was given)",
    0x83: "the device failed to write the flash",
    0x84: "the device failed to finish the update (checksum or image check failed)",
    0x85: "the device is still starting up, try again in a minute",
    0x86: "flash configuration error on the device",
    0x87: "flash configuration error on the device",
    0x88: "not enough space for the image on the device",
    0x89: "the device found no partition for the update",
    0x8A: "partition problem on the device",
    0x8B: "the MD5 of the received image does not match",
    0x8C: "not enough space for the image on the device",
    0x8D: "the device rejected the image signature",
    0x8E: "the device does not support this OTA type",
    0x8F: "partition table error on the device",
    0x90: "partition table error on the device",
    0x91: "bootloader error on the device",
    0x92: "bootloader error on the device",
    0x93: "the device refused the image (downgrade check)",
    0x94: "the device requires an encrypted OTA connection (Noise); this tool cannot do that, use the esphome command line",
    0xFF: "unknown error on the device",
}


@dataclass
class Session:
    """What the handshake told us about the device."""
    ota_version: int
    server_flags: int | None   # feature byte of newer ESPHome (None: older device)
    auth: str                  # "none", "sha256" or "md5"


def _describe(code: int) -> str:
    return ERRORS.get(code, f"error code 0x{code:02x}")


def _read(sock: socket.socket, n: int, what: str) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except socket.timeout:
            raise OtaError(f"Timeout while waiting for the device ({what}).") from None
        except OSError as e:
            raise OtaError(f"Connection to the device failed while waiting for {what}: {e}") from e
        if not chunk:
            raise OtaError(f"The device closed the connection while waiting for {what}.")
        buf += chunk
    return bytes(buf)


def _expect(sock: socket.socket, ok: tuple[int, ...], what: str) -> int:
    """Read one answer byte; error codes and unexpected values raise."""
    b = _read(sock, 1, what)[0]
    if b >= 0x80:
        raise OtaError(f"The device refused the update at '{what}': {_describe(b)}.")
    if b not in ok:
        raise OtaError(f"Unexpected answer 0x{b:02x} from the device at '{what}'. Is this really an ESPHome device "
                       f"(ota: platform: esphome)?")
    return b


def _send(sock: socket.socket, data: bytes, what: str) -> None:
    try:
        sock.sendall(data)
    except socket.timeout:
        raise OtaError(f"Timeout while sending {what} to the device.") from None
    except OSError as e:
        raise OtaError(f"Connection to the device failed while sending {what}: {e}") from e


def _authenticate(sock: socket.socket, kind: int, password: str | None) -> str:
    if not password:
        raise OtaError("The device asks for the OTA password: use --ota-password (the password under 'ota:' in the ESPHome config).")
    algo, name = (hashlib.sha256, "sha256") if kind == RESPONSE_REQUEST_SHA256_AUTH else (hashlib.md5, "md5")
    size = algo().digest_size * 2  # hex digits: the nonce has the length of the digest
    nonce = _read(sock, size, "authentication nonce").decode("ascii", "replace")
    cnonce = algo(secrets.token_bytes(16)).hexdigest()
    _send(sock, cnonce.encode(), "authentication")
    digest = algo((password + nonce + cnonce).encode()).hexdigest()
    _send(sock, digest.encode(), "authentication")
    _expect(sock, (RESPONSE_AUTH_OK,), "authentication result")
    return name


def push_app(host: str, image: bytes, *, port: int = DEFAULT_PORT, password: str | None = None,
             dry_run: bool = False, connect_timeout: float = 10.0, data_timeout: float = 120.0,
             progress: Callable[[int, int], None] | None = None) -> Session:
    """Upload an ESP app image over ESPHome OTA. With dry_run the connection ends after authentication, nothing is sent.

    The device writes the image to its inactive app slot and reboots into it once the checks pass.
    """
    try:
        sock = socket.create_connection((host, port), timeout=connect_timeout)
    except OSError as e:
        raise OtaError(f"Cannot connect to {host}:{port}: {e}\n"
                       f"  Is the device on ESPHome with 'ota: platform: esphome' (default port 3232), and reachable from this PC?") from e
    with sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(20)  # the device wants the handshake done within about 20 s
        _send(sock, MAGIC, "protocol header")
        status, version = _read(sock, 2, "protocol version")
        if status >= 0x80:
            raise OtaError(f"The device refused the connection: {_describe(status)}.")
        if status != RESPONSE_OK or version not in (1, 2):
            raise OtaError(f"This does not look like an ESPHome OTA port (answer 0x{status:02x} 0x{version:02x}). "
                           f"Does {host}:{port} belong to a device that runs ESPHome?")
        _send(sock, bytes([FEATURE_SHA256_AUTH]), "features")
        answer = _expect(sock, (RESPONSE_HEADER_OK, RESPONSE_SUPPORTS_COMPRESSION, RESPONSE_FEATURE_FLAGS), "features")
        flags = None
        if answer == RESPONSE_FEATURE_FLAGS:
            flags = _read(sock, 1, "feature flags")[0]
        elif answer == RESPONSE_SUPPORTS_COMPRESSION:
            raise OtaError("The device expects a compressed image, which this tool did not offer. Use the esphome command line.")
        auth_kind = _expect(sock, (RESPONSE_REQUEST_AUTH, RESPONSE_REQUEST_SHA256_AUTH, RESPONSE_AUTH_OK), "authentication")
        auth = "none" if auth_kind == RESPONSE_AUTH_OK else _authenticate(sock, auth_kind, password)
        session = Session(version, flags, auth)
        if dry_run:
            return session  # closing here ends the upload before anything is written

        sock.settimeout(data_timeout)
        _send(sock, struct.pack(">I", len(image)), "image size")
        _expect(sock, (RESPONSE_UPDATE_PREPARE_OK,), "update start (the device erases the slot)")
        _send(sock, hashlib.md5(image).hexdigest().encode(), "checksum")
        _expect(sock, (RESPONSE_BIN_MD5_OK,), "checksum")
        sent = 0
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 0)
        while sent < len(image):
            block = image[sent:sent + BLOCK_SIZE]
            _send(sock, block, "image data")
            sent += len(block)
            if version >= 2:
                _expect(sock, (RESPONSE_CHUNK_OK,), "image data")
            if progress:
                progress(sent, len(image))
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        _expect(sock, (RESPONSE_RECEIVE_OK,), "end of image data")
        _expect(sock, (RESPONSE_UPDATE_END_OK,), "image check (the device verifies the image)")
        try:
            sock.sendall(bytes([RESPONSE_OK]))  # end acknowledgement; the device reboots right after it
        except OSError:
            pass
        return session
