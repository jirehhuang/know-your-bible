"""In-process TTL cache for user settings (L1 in front of SQLite)."""

from threading import Lock

from cachetools import TTLCache

## Caches per user_id with 1-hour TTL
user_cache: TTLCache = TTLCache(maxsize=1000, ttl=3600)
cache_lock = Lock()


def get_cached_user_settings(user_id: str):
    """Return cached settings for a user, or None on miss/expiry."""
    with cache_lock:
        return user_cache.get(user_id)


def set_cached_user_settings(user_id: str, settings: dict):
    """Cache settings for a user (None evicts the entry)."""
    with cache_lock:
        user_cache[user_id] = settings
