"""Generazione UUIDv7 (ordinabile temporalmente) senza dipendenze esterne.

Layout RFC 9562: 48 bit di timestamp Unix in millisecondi, 4 bit di versione (7),
12 bit random (rand_a), 2 bit di variant (10), 62 bit random (rand_b). Essendo
monotòno-ish nel tempo, migliora la località degli indici B-tree rispetto a UUIDv4
e rende gli id ordinabili per creazione.
"""

import os
import time
from uuid import UUID


def uuid7() -> UUID:
    unix_ms = time.time_ns() // 1_000_000
    ts = unix_ms & ((1 << 48) - 1)  # 48 bit timestamp
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF  # 12 bit
    rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)  # 62 bit

    value = (
        (ts << 80)
        | (0x7 << 76)  # version 7
        | (rand_a << 64)
        | (0b10 << 62)  # variant RFC 4122
        | rand_b
    )
    return UUID(int=value)
