from functools import lru_cache

from app.core.config import get_settings
from app.services.persistence.repository import SnapshotRepository
from app.services.persistence.sqlite_repository import SQLiteSnapshotRepository


@lru_cache
def get_snapshot_repository() -> SnapshotRepository:
    settings = get_settings()

    return SQLiteSnapshotRepository(settings.value_terminal_db_path)
