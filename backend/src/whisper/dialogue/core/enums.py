"""Enum di dominio del dialogo (missive segrete e chat)."""

from enum import StrEnum


class ConversationOrigin(StrEnum):
    missive = "missive"  # aperta da una missiva segreta (mittente mascherato)
    direct = "direct"  # aperta apertamente (es. dopo un reveal)


class ConversationStatus(StrEnum):
    active = "active"
    closed = "closed"  # a chiusura evento (sola lettura)


class MessageKind(StrEnum):
    text = "text"
    system = "system"  # eventi di sistema (reveal, scambio contatti)


class ContactType(StrEnum):
    instagram = "instagram"
    phone = "phone"
    other = "other"
