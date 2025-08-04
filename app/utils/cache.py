from cachetools import TTLCache
from threading import Lock

## Caches per user_id with 1-hour TTL
user_cache = TTLCache(maxsize=1000, ttl=3600)
cache_lock = Lock()

def get_cached_user_settings(user_id: str):
    with cache_lock:
        return user_cache.get(user_id)

def set_cached_user_settings(user_id: str, settings: dict):
    with cache_lock:
        user_cache[user_id] = settings