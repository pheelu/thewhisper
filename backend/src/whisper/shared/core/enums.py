"""Enum condivisi, definiti una sola volta e importati dai domini (mai ridefiniti).

Gli enum specifici di un dominio vivono nel `core/` del dominio proprietario, ma
seguono le stesse convenzioni di naming (`snake_case`, prefisso semantico).
"""

from enum import StrEnum


class EventStatus(StrEnum):
    draft = "draft"
    open = "open"
    closed = "closed"
    archived = "archived"


class ParticipantRole(StrEnum):
    guest = "guest"
    host = "host"


class ParticipantNobleTitle(StrEnum):
    duca = "duca"
    duchessa = "duchessa"
    conte = "conte"
    contessa = "contessa"
    barone = "barone"
    baronessa = "baronessa"
    visconte = "visconte"
    viscontessa = "viscontessa"
    marchese = "marchese"
    marchesa = "marchesa"


class PointReason(StrEnum):
    """Enum canonico dei motivi di accredito punti (esteso in modo ADDITIVO)."""

    photo_created = "photo_created"
    subject_guessed = "subject_guessed"
    photo_solved = "photo_solved"
    hunter_guess_bonus = "hunter_guess_bonus"
    profile_completed = "profile_completed"
    missive_replied = "missive_replied"
    dialogue_opened = "dialogue_opened"
    dialogue_matched = "dialogue_matched"
    bet_staked = "bet_staked"
    bet_won = "bet_won"
    bet_refunded = "bet_refunded"
    badge_bonus = "badge_bonus"
    gazette_feature = "gazette_feature"
    moderation_penalty = "moderation_penalty"
    manual_host = "manual_host"
    reversal = "reversal"
