"""Shelly's root CA, taken out of an official package and checked against a fingerprint fixed in this file.

Shelly's servers use a private CA and send only the leaf certificate, so `--cafile` needs the root as a PEM file. The root is in the
`fs.img` of every package: as a DER certificate in the newer ones, as a PEM file (`shelly_cloud.pem`, next to a CA bundle) in old ones.
Nothing here parses the file system or the certificate. The bytes of every candidate are hashed and compared with
SHELLY_ROOT_SHA256, so what is written is exactly the certificate that was measured, whatever else the image holds.

The value was measured on 2026-11-03: 107 of 108 cached packages hold this DER certificate, one old package (MiniPMG3 1.3.3) the
same certificate as PEM. It is self-signed, X.509 v1 (no `CA:TRUE`) and verified updates.shelly.cloud with openssl.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import ssl
import zipfile
from datetime import date
from pathlib import Path

from .builder import OtaError, require_zip

SHELLY_ROOT_SHA256 = "5a7ee2faf82bd43beef6581f48bbd4a134456488a7904eec52a15c572f53093e"   # of the DER certificate, O=Allterco
SHELLY_ROOT_NOT_AFTER = date(2030, 8, 2)
DER_LENGTH = range(256, 4097)       # the root is 689 bytes; the scan hashes only slices of a plausible size
PEM_BLOCK = re.compile(rb"-----BEGIN CERTIFICATE-----(.*?)-----END CERTIFICATE-----", re.S)


def fingerprint(der: bytes) -> str:
    """SHA-256 of a DER certificate, lower case hex."""
    return hashlib.sha256(der).hexdigest()


def colon_hex(sha256: str) -> str:
    """The fingerprint the way openssl prints it: 5A:7E:..."""
    return ":".join(sha256[i:i + 2] for i in range(0, len(sha256), 2)).upper()


def find_root(data: bytes, expected_sha256: str | None = None) -> bytes | None:
    """The DER certificate in `data` whose SHA-256 is `expected_sha256`, or None.

    Looks for a DER SEQUENCE with a two-byte length (30 82 LL LL) and for PEM blocks; the text around a PEM block may be anything.
    Without `expected_sha256` it is SHELLY_ROOT_SHA256.
    """
    expected_sha256 = expected_sha256 or SHELLY_ROOT_SHA256
    start = data.find(b"\x30\x82")
    while start >= 0:
        length = 4 + int.from_bytes(data[start + 2:start + 4], "big")
        if length in DER_LENGTH and start + length <= len(data) and fingerprint(data[start:start + length]) == expected_sha256:
            return data[start:start + length]
        start = data.find(b"\x30\x82", start + 1)
    for block in PEM_BLOCK.finditer(data):
        try:
            der = base64.b64decode(re.sub(rb"\s+", b"", block.group(1)), validate=True)
        except binascii.Error:
            continue
        if fingerprint(der) == expected_sha256:
            return der
    return None


def extract_from_zip(path: Path, expected_sha256: str | None = None) -> bytes:
    """The root certificate (DER) of a package; an OtaError if the package has no `fs.img` or the certificate is not in it."""
    expected_sha256 = expected_sha256 or SHELLY_ROOT_SHA256
    path = require_zip(path, "package")
    with zipfile.ZipFile(path) as zf:
        if "fs.img" not in zf.namelist():
            raise OtaError(f"{path.name} has no fs.img, so there is no certificate to take out of it.")
        data = zf.read("fs.img")
    der = find_root(data, expected_sha256)
    if der is None:
        raise OtaError(f"No certificate with SHA-256 {colon_hex(expected_sha256)} in the fs.img of {path.name}. "
                       "Nothing was written: this package does not hold the root this tool knows, or Shelly changed it.")
    return der


def to_pem(der: bytes) -> bytes:
    """PEM text with Unix line ends on every platform (the file is read by OpenSSL, which accepts both, but diffs stay clean)."""
    return ssl.DER_cert_to_PEM_cert(der).encode("ascii")


def expired(today: date | None = None) -> bool:
    return (today or date.today()) > SHELLY_ROOT_NOT_AFTER
