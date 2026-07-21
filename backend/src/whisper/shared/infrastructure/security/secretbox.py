"""Cifratura simmetrica (Fernet/AES) per i dati sensibili a riposo.

Usata dal dominio dialogue per i contatti reali: unico posto dove esistono,
cifrati con chiave derivata dal SECRET_KEY dell'app.
"""

import base64
import hashlib

from cryptography.fernet import Fernet


def _fernet(secret: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_text(plaintext: str, secret: str) -> bytes:
    return _fernet(secret).encrypt(plaintext.encode())


def decrypt_text(ciphertext: bytes, secret: str) -> str:
    return _fernet(secret).decrypt(bytes(ciphertext)).decode()
