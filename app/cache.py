import os
import redis

r = redis.Redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379"),
    decode_responses=True,   # return strings instead of bytes
)

VERSION_KEY = "search:version"


def search_version() -> str:
    return r.get(VERSION_KEY) or "0"


def invalidate_search_cache() -> None:
    r.incr(VERSION_KEY)     # bump the version → all old search keys are ignored