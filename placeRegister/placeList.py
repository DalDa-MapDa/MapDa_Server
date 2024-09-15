from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import SessionLocal, Place

router = APIRouter()

@router.get("/get_place_list")
async def get_place_list():
    try:
        # DB 세션 생성
        db: Session = SessionLocal()

        # 최신순으로 최대 25개의 장소 데이터를 DB에서 가져옴
        places = db.query(Place).order_by(desc(Place.created_at)).limit(25).all()

        # 장소 리스트 반환
        place_list = []
        for place in places:
            indoor_images = [indoor.image_url for indoor in place.indoor_images]
            outdoor_images = [outdoor.image_url for outdoor in place.outdoor_images]
            place_list.append({
                "id": place.id,
                "uuid": place.uuid,
                "created_at": place.created_at,
                "user_id": place.user_id,
                "place_name": place.place_name,
                "latitude": place.latitude,
                "longitude": place.longitude,
                "wheele_chait_accessible": place.wheele_chait_accessible,
                "rest_room_exist": place.rest_room_exist,
                "rest_room_floor": place.rest_room_floor,
                "elevator_accessible": place.elevator_accessible,
                "ramp_accessible": place.ramp_accessible,
                "indoor_images": indoor_images,
                "outdoor_images": outdoor_images
            })

        return place_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

    finally:
        db.close()
