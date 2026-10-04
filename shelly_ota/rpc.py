"""Minimal Shelly RPC client over HTTP, with optional digest authentication (RFC 7616)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from .builder import OtaError

_PARAM = re.compile(r'(\w+)=(?:"([^"]*)"|([^,\s]+))')


def _digest_header(challenge: str, method: str, url: str, user: str, password: str) -> str:
    params = {k: (q or u) for k, q, u in _PARAM.findall(challenge)}
    algo = params.get("algorithm", "MD5").upper()
    hash_fn = {"SHA-256": hashlib.sha256, "MD5": hashlib.md5}.get(algo)
    if hash_fn is None:
        raise OtaError(f"Unsupported digest algorithm {algo!r}.")

    def h(text: str) -> str:
        return hash_fn(text.encode()).hexdigest()

    parts = urllib.parse.urlsplit(url)
    uri = parts.path + (f"?{parts.query}" if parts.query else "")
    nc, cnonce = "00000001", os.urandom(8).hex()
    ha1 = h(f"{user}:{params['realm']}:{password}")
    ha2 = h(f"{method}:{uri}")
    response = h(f"{ha1}:{params['nonce']}:{nc}:{cnonce}:auth:{ha2}")
    fields = [f'username="{user}"', f'realm="{params["realm"]}"', f'nonce="{params["nonce"]}"', f'uri="{uri}"',
              f"algorithm={algo}", f'response="{response}"', "qop=auth", f"nc={nc}", f'cnonce="{cnonce}"']
    if "opaque" in params:
        fields.append(f'opaque="{params["opaque"]}"')
    return "Digest " + ", ".join(fields)


def request(url: str, *, data: bytes | None = None, user: str | None = None, password: str | None = None,
            timeout: float = 10) -> bytes:
    """GET (or POST with data) and return the body. Answers a 401 digest challenge if credentials are given."""
    method = "POST" if data is not None else "GET"
    headers = {"Content-Type": "application/json"} if data is not None else {}
    try:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers),
                                        timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            challenge = e.headers.get("WWW-Authenticate", "")
            if e.code != 401 or not challenge.lower().startswith("digest"):
                raise
            if not (user and password):
                raise OtaError("The device requires a password: use --user and --password.") from e
            headers["Authorization"] = _digest_header(challenge, method, url, user, password)
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers),
                                        timeout=timeout) as resp:
                return resp.read()
    except urllib.error.HTTPError as e:
        raise OtaError(f"HTTP {e.code} from {url}") from e
    except OSError as e:
        raise OtaError(f"No answer from {url}: {e}") from e


def call(addr: str, method: str, params: dict | None = None, **auth) -> dict:
    """Call an RPC method (POST /rpc) and return its result."""
    body = json.dumps({"id": 1, "method": method, "params": params or {}}).encode()
    reply = json.loads(request(f"http://{addr}/rpc", data=body, **auth))
    if "error" in reply:
        raise OtaError(f"{method} failed: {reply['error']}")
    return reply.get("result", {})
