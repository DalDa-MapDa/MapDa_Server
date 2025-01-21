from fastapi import APIRouter, HTTPException, Query, Request
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


@router.get("/api/v1/get_specfic_place", tags=["Place"])
async def get_specific_place(request: Request, place_master_id: int = Query(...)):
    """
    특정 place_master.id로 조회:
      - base_info: place_master의 기본 정보
      - aggregated_data: 각 편의시설 필드별 (값 -> 개수) 형태
      - contributor: 기여자 목록 [ { user_id, nickname, provider_profile_image }, ... ]
      - indoor_images, outdoor_images: 이미지 URL 모음
    """
    try:
        db: Session = SessionLocal()

        # 1) place_master 조회 (+ contributions 관계를 미리 joinedload)
        place_master = db.query(PlaceMaster)\
            .options(joinedload(PlaceMaster.contributions).joinedload(PlaceContribution.user))\
            .options(joinedload(PlaceMaster.contributions).joinedload(PlaceContribution.images))\
            .filter(PlaceMaster.id == place_master_id)\
            .first()

        if not place_master:
            raise HTTPException(status_code=404, detail="해당 place_master를 찾을 수 없습니다.")

        # 2) base_info: place_master의 기본 컬럼
        base_info = {
            "id": place_master.id,
            "place_name": place_master.place_name,
            "latitude": place_master.latitude,
            "longitude": place_master.longitude,
            "university": place_master.university,
            "created_at": place_master.created_at,
            "updated_at": place_master.updated_at
        }

        contributions = place_master.contributions  # 연관된 모든 PlaceContribution

        # 3) 편의시설 필드를 값별로 집계 (예: {"0": 2, "1": 3})
        fields_to_aggregate = [
            "wheele_chair_accessible",
            "rest_room_exist",
            "rest_room_floor",
            "elevator_accessible",
            "ramp_accessible"
        ]

        aggregated_data = {}
        for field_name in fields_to_aggregate:
            value_counts = {}
            for contrib in contributions:
                value = getattr(contrib, field_name, None)
                if value is not None:
                    str_value = str(value)
                    value_counts[str_value] = value_counts.get(str_value, 0) + 1
            aggregated_data[field_name] = value_counts

        # 4) contributor 목록 생성
        #   - 각 contribution.user에서 user_id, nickname, provider_profile_image를 가져옴
        #   - 중복 유저가 있을 수 있으니 dict로 중복 제거 후 list 변환
        contributor_dict = {}
        for contrib in contributions:
            if contrib.user:
                u = contrib.user
                if u.id not in contributor_dict:
                    contributor_dict[u.id] = {
                        "user_id": u.id,
                        "nickname": u.nickname,
                        "provider_profile_image": u.provider_profile_image
                    }

        contributor_list = list(contributor_dict.values())

        # 5) 이미지(indoor/outdoor) 전체 모으기
        indoor_images = []
        outdoor_images = []

        for contrib in contributions:
            for img in contrib.images:
                if img.image_type == "indoor":
                    indoor_images.append(img.image_url)
                elif img.image_type == "outdoor":
                    outdoor_images.append(img.image_url)

        # 6) 최종 응답
        return {
            "base_info": base_info,
            "aggregated_data": aggregated_data,
            "contributor": contributor_list,
            "indoor_images": indoor_images,
            "outdoor_images": outdoor_images
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")
    finally:
        db.close()
