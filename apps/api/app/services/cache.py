from time import monotonic
from typing import Any, Callable, Dict, Optional, Tuple


class TTLCache:
    def __init__(
        self,
        ttl_seconds: int,
        now: Callable[[], float] = monotonic,
    ) -> None:
        self.ttl_seconds = max(ttl_seconds, 0)
        self.now = now
        self._items: Dict[str, Tuple[float, Any]] = {}

    @staticmethod
    def normalize_key(*parts: object) -> str:
        return ":".join(str(part).strip().upper() for part in parts)

    def get(self, key: str) -> Optional[Any]:
        if self.ttl_seconds <= 0:
            return None

        item = self._items.get(key)

        if item is None:
            return None

        expires_at, value = item

        if expires_at <= self.now():
            self._items.pop(key, None)
            return None

        return value

    def set(self, key: str, value: Any) -> None:
        if self.ttl_seconds <= 0:
            return

        self._items[key] = (self.now() + self.ttl_seconds, value)

    def clear(self) -> None:
        self._items.clear()
