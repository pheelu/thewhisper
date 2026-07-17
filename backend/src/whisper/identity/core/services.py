"""Servizi/regole pure del dominio identity."""

import secrets

# Alfabeto senza caratteri ambigui (niente 0/O/1/I/L) per i codici stampati sul QR.
_JOIN_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
JOIN_CODE_LENGTH = 8


def generate_join_code(length: int = JOIN_CODE_LENGTH) -> str:
    return "".join(secrets.choice(_JOIN_CODE_ALPHABET) for _ in range(length))
