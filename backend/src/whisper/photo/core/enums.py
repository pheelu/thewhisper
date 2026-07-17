"""Enum di dominio delle Foto Whisper."""

from enum import StrEnum


class PhotoStatus(StrEnum):
    draft = "draft"  # creata, in attesa di upload+publish
    published = "published"  # visibile nel feed
    under_review = "under_review"  # nascosta per moderazione
    removed = "removed"  # terminale, oggetto S3 purgato
    archived = "archived"  # a fine evento


class PhotoRemovalReason(StrEnum):
    subject_request = "subject_request"  # il Soggetto ritratto la rimuove
    hunter_deleted = "hunter_deleted"  # il Cacciatore la elimina
    consent_revoked = "consent_revoked"  # il Soggetto ha revocato il consenso
    host_action = "host_action"  # l'organizzatore la rimuove
    moderation = "moderation"  # rimozione a valle di moderazione
