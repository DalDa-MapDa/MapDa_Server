import redis
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# Redis 클라이언트 생성
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=0,
    decode_responses=True,
    socket_connect_timeout=5,  # 연결 타임아웃
    retry_on_timeout=True      # 타임아웃 시 재시도
)

# Redis 캐시 최대 크기 제한
MAX_CACHE_SIZE = int(os.getenv('REDIS_MAX_CACHE_SIZE', 1000))  # 기본값: 1000개
REDIS_EVICTION_POLICY = os.getenv('REDIS_EVICTION_POLICY', 'allkeys-lru')  # 기본값: LRU

# Redis 설정 적용
redis_client.config_set('maxmemory', f'{MAX_CACHE_SIZE}mb')  # 메모리 제한
redis_client.config_set('maxmemory-policy', REDIS_EVICTION_POLICY)  # 캐시 삭제 정책


