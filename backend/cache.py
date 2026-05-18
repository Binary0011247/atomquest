import json
import os
from collections.abc import Callable
from functools import wraps
from typing import Any

import redis
from fastapi import Response

redis_client = redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379"),
    decode_responses=True,
)


def get_cache(key: str) -> Any | None:
    try:
        data = redis_client.get(key)
        if data is None:
            return None
        return json.loads(data)
    except redis.RedisError:
        return None


def get_cache_ttl(key: str) -> int | None:
    try:
        ttl = redis_client.ttl(key)
        if ttl < 0:
            return None
        return ttl
    except redis.RedisError:
        return None


def set_cache(key: str, value: Any, expire_seconds: int) -> None:
    try:
        redis_client.setex(key, expire_seconds, json.dumps(value, default=str))
    except redis.RedisError:
        pass


def invalidate_cache(pattern: str) -> None:
    try:
        for key in redis_client.keys(pattern):
            redis_client.delete(key)
    except redis.RedisError:
        pass


def invalidate_mutation_caches(*, goals: bool = False, checkins: bool = False) -> None:
    invalidate_cache("admin:dashboard")
    invalidate_cache("admin:analytics:*")
    if goals:
        invalidate_cache("manager:team:*")
    if checkins:
        invalidate_cache("admin:reports:achievement")


def count_cached_keys() -> int:
    try:
        return redis_client.dbsize()
    except redis.RedisError:
        return 0


def ping_redis() -> bool:
    try:
        return redis_client.ping()
    except redis.RedisError:
        return False


def _serialize_result(result: Any) -> Any:
    if isinstance(result, list):
        return [_serialize_result(item) for item in result]
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    return result


def _set_cache_headers(response: Response | None, *, hit: bool, ttl: int) -> None:
    if response is None:
        return
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    response.headers["X-Cache-TTL"] = str(max(ttl, 0))


def cache_response(key: str | Callable[..., str], expire_seconds: int):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = key(**kwargs) if callable(key) else key
            response: Response | None = kwargs.get("response")

            cached = get_cache(cache_key)
            if cached is not None:
                ttl = get_cache_ttl(cache_key) or expire_seconds
                _set_cache_headers(response, hit=True, ttl=ttl)
                return cached

            result = func(*args, **kwargs)
            set_cache(cache_key, _serialize_result(result), expire_seconds)
            _set_cache_headers(response, hit=False, ttl=expire_seconds)
            return result

        return wrapper

    return decorator
