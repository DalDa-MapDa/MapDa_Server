from fastapi import APIRouter, HTTPException, Request
import redis
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import SessionLocal, PlaceMaster, User  # 변경: Place -> PlaceMaster
from setting.redis_client import redis_client
import json
from typing import List
from difflib import SequenceMatcher

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
        # 인증된 사용자 UUID
        user_uuid = request.state.user_uuid
        
        db: Session = SessionLocal()
        
        # 사용자 조회
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        # 캐시 키
        cache_key = f"place_search:{user.university}:{keyword}"
        
        # 캐시 확인
        cached_result = redis_client.get(cache_key)
        if cached_result:
            return {
                "query": keyword,
                "items": json.loads(cached_result)
            }
        
        # DB에서 검색 - PlaceMaster 사용
        # status 컬럼이 없으므로, status=='Active' 조건 제거
        places_query = db.query(PlaceMaster.place_name)\
            .filter(
                PlaceMaster.university == user.university,
                func.lower(PlaceMaster.place_name).contains(func.lower(keyword))
            )\
            .distinct()
        
        places = places_query.all()  # [(place_name,), (place_name,)...] 형태
        
        # 유사도 정렬
        place_names = [p[0] for p in places]  # 실제 문자열 리스트
        sorted_places = sorted(
            place_names,
            key=lambda pname: calculate_similarity(keyword, pname),
            reverse=True
        )
        
        # 제한
        result = sorted_places[:limit]
        
        # 캐싱
        redis_client.setex(cache_key, CACHE_EXPIRATION, json.dumps(result))
        
        return {
            "query": keyword,
            "items": result
        }
    
    except redis.RedisError:
        # Redis 오류 시, DB 결과만
        places_query = db.query(PlaceMaster.place_name)\
            .filter(
                PlaceMaster.university == user.university,
                func.lower(PlaceMaster.place_name).contains(func.lower(keyword))
            )\
            .distinct()
        
        places = places_query.all()
        place_names = [p[0] for p in places]
        sorted_places = sorted(
            place_names,
            key=lambda pname: calculate_similarity(keyword, pname),
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


@router.get("/api/v1/search/place/coordinates", tags=["Search"])
async def search_places_coordinates(
    request: Request,
    keyword: str,
    limit: int = 10
):
    try:
        # 1) 인증된 사용자 UUID
        user_uuid = request.state.user_uuid
        db: Session = SessionLocal()

        # 2) 사용자 조회
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # 3) 캐시 키
        cache_key = f"place_search_coords:{user.university}:{keyword}"
        cached = redis_client.get(cache_key)
        if cached:
            return {
                "query": keyword,
                "items": json.loads(cached)
            }

        # 4) DB에서 place_name, latitude, longitude 함께 조회
        records = db.query(
            PlaceMaster.place_name,
            PlaceMaster.latitude,
            PlaceMaster.longitude
        ).filter(
            PlaceMaster.university == user.university,
            func.lower(PlaceMaster.place_name).contains(func.lower(keyword))
        ).distinct().all()

        # 5) 유사도 계산 후 정렬
        sorted_records = sorted(
            records,
            key=lambda x: calculate_similarity(keyword, x[0]),
            reverse=True
        )[:limit]

        # 6) dict 형태로 가공
        items = [
            {"place_name": name, "latitude": lat, "longitude": lon}
            for name, lat, lon in sorted_records
        ]

        # 7) 캐싱
        redis_client.setex(cache_key, CACHE_EXPIRATION, json.dumps(items))

        return {"query": keyword, "items": items}

    except redis.RedisError:
        # Redis 오류 발생 시 DB 결과만 반환
        records = db.query(
            PlaceMaster.place_name,
            PlaceMaster.latitude,
            PlaceMaster.longitude
        ).filter(
            PlaceMaster.university == user.university,
            func.lower(PlaceMaster.place_name).contains(func.lower(keyword))
        ).distinct().all()

        sorted_records = sorted(
            records,
            key=lambda x: calculate_similarity(keyword, x[0]),
            reverse=True
        )[:limit]

        items = [
            {"place_name": name, "latitude": lat, "longitude": lon}
            for name, lat, lon in sorted_records
        ]
        return {"query": keyword, "items": items}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {e}")

    finally:
        db.close()
