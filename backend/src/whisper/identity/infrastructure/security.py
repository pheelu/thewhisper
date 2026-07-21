"""Hashing del segreto host (PBKDF2-HMAC-SHA256, stdlib)."""

import base64
import hashlib
import hmac
import os

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 200_000


def hash_secret(secret: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, _ITERATIONS)
    return (
        f"{_ALGO}${_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"
    )


def verify_secret(secret: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, iters_s, salt_b64, dk_b64 = stored.split("$")
        if algo != _ALGO:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
        candidate = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, int(iters_s))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, expected)
