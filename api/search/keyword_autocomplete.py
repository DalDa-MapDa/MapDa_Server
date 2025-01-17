from fastapi import APIRouter, HTTPException, Request
import redis
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import SessionLocal, Place, User
from setting.redis_client import redis_client  # Redis 클라이언트 가져오기
import json
from typing import List
from difflib import SequenceMatcher  # 문자열 유사도 계산

CACHE_EXPIRATION = 3600  # 캐시 유효 시간 (1시간)

router = APIRouter()

def calculate_similarity(keyword: str, target: str) -> float:
    """두 문자열 간 유사도를 계산 (0~1 사이 값 반환)."""
    return SequenceMatcher(None, keyword.lower(), target.lower()).ratio()

@router.get("/api/v1/search/place", tags=["Search"])
async def search_places(
    request: Request,
    keyword: str,
    limit: int = 10
):
    try:
        # 인증된 사용자 UUID 가져오기
        user_uuid = request.state.user_uuid
        
        # DB 세션 생성
        db: Session = SessionLocal()
        
        # 사용자의 대학교 정보 조회
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
            
        # 캐시 키 생성 (대학교_키워드 형식)
        cache_key = f"place_search:{user.university}:{keyword}"
        
        # 캐시된 결과 확인
        cached_result = redis_client.get(cache_key)
        if cached_result:
            # 캐시된 데이터를 반환 (query와 items 포함)
            return {
                "query": keyword,
                "items": json.loads(cached_result)
            }
            
        # DB에서 검색
        places = db.query(Place.place_name)\
            .filter(
                Place.university == user.university,
                Place.status == 'Active',
                func.lower(Place.place_name).contains(func.lower(keyword))
            )\
            .distinct()\
            .all()
            
        # 유사도 기반 정렬
        sorted_places = sorted(
            [place[0] for place in places],  # 문자열 리스트로 변환
            key=lambda place_name: calculate_similarity(keyword, place_name),
            reverse=True  # 유사도가 높은 순으로 정렬
        )
        
        # 결과 제한 적용
        result = sorted_places[:limit]
        
        # 결과 캐싱
        redis_client.setex(
            cache_key,
            CACHE_EXPIRATION,
            json.dumps(result)
        )
        
        # 응답 데이터 반환
        return {
            "query": keyword,
            "items": result
        }
        
    except redis.RedisError as e:
        # Redis 에러 발생 시 DB 결과만 반환
        places = db.query(Place.place_name)\
            .filter(
                Place.university == user.university,
                Place.status == 'Active',
                func.lower(Place.place_name).contains(func.lower(keyword))
            )\
            .distinct()\
            .all()
        sorted_places = sorted(
            [place[0] for place in places],
            key=lambda place_name: calculate_similarity(keyword, place_name),
            reverse=True
        )
        return {
            "query": keyword,
            "items": sorted_places[:limit]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")
        
    finally:
        db.close()
