from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from models import SessionLocal, PlaceContribution, PlaceMaster, PlaceContributionImage, User

router = APIRouter()

@router.get("/api/v1/get_place_list", tags=["Place"])
async def get_place_list(request: Request):
    try:
        db: Session = SessionLocal()
        user_uuid = request.state.user_uuid

        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # university 기준으로 필터
        user_uni = user.university

        # 최신 Contribution 25개
        contributions = db.query(PlaceContribution)\
            .join(PlaceMaster, PlaceContribution.place_master_id == PlaceMaster.id)\
            .options(
                joinedload(PlaceContribution.place_master),
                joinedload(PlaceContribution.images),
                joinedload(PlaceContribution.user)
            )\
            .filter(PlaceMaster.university == user_uni)\
            .order_by(desc(PlaceContribution.created_at))\
            .limit(25)\
            .all()

        result_list = []
        for contrib in contributions:
            master = contrib.place_master
            images = contrib.images

            # indoor/outdoor 구분
            indoor_urls = [img.image_url for img in images if img.image_type == 'indoor']
            outdoor_urls = [img.image_url for img in images if img.image_type == 'outdoor']

            result_list.append({
                "contribution_id": contrib.id,
                "user_id": contrib.user_id,
                "place_master_id": master.id,
                "place_name": master.place_name,
                "latitude": master.latitude,
                "longitude": master.longitude,
                "university": master.university,
                # 편의시설 정보
                "wheelchair_accessible": contrib.wheele_chair_accessible,
                "rest_room_exist": contrib.rest_room_exist,
                "rest_room_floor": contrib.rest_room_floor,
                "elevator_accessible": contrib.elevator_accessible,
                "ramp_accessible": contrib.ramp_accessible,
                # 이미지
                "indoor_images": indoor_urls,
                "outdoor_images": outdoor_urls,
                # 기타 정보
                "created_at": contrib.created_at,
                "user_nickname": contrib.user.nickname if contrib.user else None
            })

        return result_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")
    finally:
        db.close()
