from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from datetime import datetime
from models import SessionLocal, User, UserObject, PlaceContribution, PlaceMaster

router = APIRouter()

@router.get("/api/v1/activity/user_barrierfree", tags=["Activity"])
async def get_barrierfree_activity(request: Request):
    """
    반환 포맷:
    {
      "day_since_registration": int,         # 가입 후 지난 일자
      "user_object_count": int,             # user_objects 총 개수 (동일 대학)
      "user_object_img_urls": [str, ...],   # 최대 3개의 최신 이미지 URL
      "user_place_count": int,              # place_contribution 중복 제거 개수 (동일 대학)
      "user_place_img_urls": [str, ...]     # place_contribution별 최신 이미지 URL 리스트
    }
    """
    db: Session = SessionLocal()
    try:
        # 1) 사용자 검증
        user_uuid = request.state.user_uuid
        user: User = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # 2) 가입 후 지난 일자 계산
        day_since_registration = (datetime.utcnow().date() - user.created_at.date()).days

        # 3) user_objects 관련
        #    - 동일 대학에 속한 전체 개수
        user_object_count = db.query(func.count(UserObject.id))\
            .filter(
                UserObject.created_uuid == user_uuid,
                UserObject.university == user.university
            ).scalar() or 0

        #    - 최신순 3건 이미지 URL
        recent_objs = db.query(UserObject)\
            .filter(
                UserObject.created_uuid == user_uuid,
                UserObject.university == user.university
            )\
            .order_by(desc(UserObject.created_at))\
            .limit(3)\
            .all()
        user_object_img_urls = [obj.image_url for obj in recent_objs]

        # 4) place_contribution 관련
        #    - 동일 대학에 속한 기여 전체 (중복된 place_master_id 제거)
        contribs = db.query(PlaceContribution)\
            .join(PlaceMaster, PlaceContribution.place_master_id == PlaceMaster.id)\
            .filter(
                PlaceContribution.user_id == user.id,
                PlaceMaster.university == user.university
            ).all()
        unique_place_ids = {c.place_master_id for c in contribs}
        user_place_count = len(unique_place_ids)

        #    - 각 기여마다 최신 이미지 URL 추출
        place_img_urls = []
        for c in contribs:
            if c.images:
                # 가장 최근에 등록된 이미지를 하나 골라서
                latest = max(c.images, key=lambda img: img.created_at)
                place_img_urls.append(latest.image_url)
        # 중복 제거
        user_place_img_urls = list(dict.fromkeys(place_img_urls))

        return {
            "day_since_registration": day_since_registration,
            "user_object_count": user_object_count,
            "user_object_img_urls": user_object_img_urls,
            "user_place_count": user_place_count,
            "user_place_img_urls": user_place_img_urls
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")
    finally:
        db.close()
