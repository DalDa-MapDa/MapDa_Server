from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import SessionLocal, Place, User  # User 모델 추가

router = APIRouter()

@router.get("/api/v1/get_place_list", tags=["Place"])
async def get_place_list(request: Request):  # Request 파라미터 추가
    try:
        # DB 세션 생성
        db: Session = SessionLocal()

        # 인증된 사용자 UUID 가져오기
        user_uuid = request.state.user_uuid

        # 사용자의 대학교 정보 조회
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # 사용자의 대학교와 일치하는 장소들을 최신순으로 최대 25개 조회
        places = db.query(Place)\
            .filter(Place.university == user.university)\
            .order_by(desc(Place.created_at))\
            .limit(25)\
            .all()

        # 장소 리스트 반환
        place_list = []
        for place in places:
            indoor_images = [indoor.image_url for indoor in place.indoor_images]
            outdoor_images = [outdoor.image_url for outdoor in place.outdoor_images]

            # 작성자 정보 가져오기
            user = db.query(User).filter(User.uuid == place.created_uuid).first()
            user_nickname = user.nickname if user else None

            place_list.append({
                "id": place.id,
                "resource_id": place.resource_id,
                "created_at": place.created_at,
                "user_id": place.user_id,
                "created_uuid": place.created_uuid,
                "user_nickname": user_nickname,
                "place_name": place.place_name,
                "latitude": place.latitude,
                "longitude": place.longitude,
                "wheelchair_accessible": place.wheele_chair_accessible,
                "rest_room_exist": place.rest_room_exist,
                "rest_room_floor": place.rest_room_floor,
                "elevator_accessible": place.elevator_accessible,
                "ramp_accessible": place.ramp_accessible,
                "indoor_images": indoor_images,
                "outdoor_images": outdoor_images
            })

        return place_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")

    finally:
        db.close()
