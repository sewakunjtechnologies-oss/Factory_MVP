from __future__ import annotations

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings


redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


async def close_redis() -> None:
    await redis_client.aclose()


async def ping_redis() -> bool:
    try:
        return bool(await redis_client.ping())
    except RedisError:
        return False
