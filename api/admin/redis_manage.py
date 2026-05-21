from fastapi import APIRouter, HTTPException
from setting.redis_client import redis_client

router = APIRouter()

@router.delete("/admin/flush-redis", tags=["Admin"])
async def flush_redis_cache():
    """Redis 캐시를 플러시합니다."""
    try:
        redis_client.flushall()  # Redis 캐시 초기화
        return {"message": "Redis cache flushed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to flush Redis cache: {str(e)}")

def flush_cache_on_startup():
    """앱 시작 시 Redis 캐시를 플러시합니다."""
    try:
        redis_client.flushall()
        print("Redis cache flushed on startup")
    except Exception as e:
        print(f"Failed to flush Redis cache on startup: {str(e)}")
