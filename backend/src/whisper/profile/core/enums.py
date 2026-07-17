"""Enum di dominio del profilo."""

from enum import StrEnum


class ProfileRevealStage(StrEnum):
    concealed = "concealed"  # mistero totale
    hinted = "hinted"  # qualche indizio svelato
    unmasked = "unmasked"  # identità di gioco rivelata pubblicamente
