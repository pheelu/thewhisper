"""Enum di dominio della scoperta."""

from enum import StrEnum


class CommentStatus(StrEnum):
    visible = "visible"
    hidden = "hidden"  # nascosto da moderazione (reversibile)
    removed = "removed"  # rimosso (terminale)


class DiscoveryRevealState(StrEnum):
    hidden = "hidden"
    revealed = "revealed"
