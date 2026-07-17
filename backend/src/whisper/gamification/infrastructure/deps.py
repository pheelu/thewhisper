"""Factory della `PointsPort` per il resto dell'app (profile/photo/discovery...)."""

from whisper.gamification.infrastructure.points_service import PointsService
from whisper.shared.infrastructure.http.deps import DbSession


def get_points_service(db: DbSession) -> PointsService:
    return PointsService(db)
