"""Aggrega i modelli ORM di TUTTI i domini su un'unica `Base.metadata`.

Importato da Alembic (`migrations/env.py`) e all'avvio dell'app, così ogni tabella
di dominio è registrata. Aggiungere qui l'import quando nasce un nuovo dominio.
"""

from whisper.dialogue.infrastructure import models as _dialogue_models  # noqa: F401
from whisper.discovery.infrastructure import models as _discovery_models  # noqa: F401
from whisper.gamification.infrastructure import models as _gamification_models  # noqa: F401

# Import per side-effect: registra le tabelle su Base.metadata.
from whisper.identity.infrastructure import models as _identity_models  # noqa: F401
from whisper.photo.infrastructure import models as _photo_models  # noqa: F401
from whisper.profile.infrastructure import models as _profile_models  # noqa: F401
from whisper.shared.infrastructure.db.base import Base

metadata = Base.metadata
