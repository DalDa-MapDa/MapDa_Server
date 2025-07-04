from datetime import datetime
import random
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field # Pydantic 모델을 위해 추가
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func, distinct # distinct를 위해 추가
from models import SessionLocal, PlaceContribution, PlaceMaster, PlaceContributionImage, User
from typing import List, Optional # Pydantic 모델을 위해 추가

router = APIRouter()

# 최대 몇 개의 장소를 visible=True 로 표시할지 설정
MAX_VISIBLE = 4

@router.get("/api/v1/get_place_list", tags=["Place"])
async def get_place_list(request: Request):
    """
    특정 사용자가 속한 university의 place_master 목록을 최신순으로 가져온다.
    반환 데이터: [
      {
        id,
        place_name,
        latitude,
        longitude,
        contributor_count,   # 기여자 수
        display             # 화면에 보여줄지 여부 (True/False)
      },
      ...
    ]
    """
    db: Session = SessionLocal()
    try:
        # 1) 사용자 조회
        user_uuid = request.state.user_uuid
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        user_uni = user.university

        # 2) place_master + contributor_count 조회
        query = (
            db.query(
                PlaceMaster,
                func.count(PlaceContribution.id).label("contributor_count")
            )
            .outerjoin(
                PlaceContribution,
                PlaceContribution.place_master_id == PlaceMaster.id
            )
            .filter(PlaceMaster.university == user_uni)
            .group_by(PlaceMaster.id)
            .order_by(desc(PlaceMaster.created_at))
            .limit(25)
        )
        results = query.all()

        # 3) dict 형태로 변환
        items = []
        for pm, contrib_count in results:
            items.append({
                "id": pm.id,
                "place_name": pm.place_name,
                "latitude": pm.latitude,
                "longitude": pm.longitude,
                "contributor_count": contrib_count,
            })

        # 4) 현재 시간(hour) 기반으로 seed 설정 후 섞기
        now = datetime.now()
        rng = random.Random(now.hour)
        rng.shuffle(items)

        # 5) 앞에서부터 MAX_VISIBLE 개수만 display=True, 나머지 False
        for idx, item in enumerate(items):
            item["display"] = idx < MAX_VISIBLE

        return items

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {e}")

    finally:
        db.close()


@router.get("/api/v1/get_specfic_place/{place_master_id}", tags=["Place"])
async def get_specific_place(request: Request, place_master_id: int):
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
            if field_name == "wheele_chair_accessible":
                value_counts = {str(i): 0 for i in range(1, 4)}
            elif field_name in ["rest_room_exist", "elevator_accessible"]:
                value_counts = {str(i): 0 for i in range(3)}
            else:
                value_counts = {str(i): 0 for i in range(4)}
            for contrib in contributions:
                value = getattr(contrib, field_name, None)
                if value is not None:
                    str_value = str(value)
                    if str_value in value_counts:
                        value_counts[str_value] += 1
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


class UserPlaceResponseItem(BaseModel):
    place_id: int
    place_name: str
    contributor_count: int
    image_url: Optional[str] = None

# --- [신규] 추가된 API 엔드포인트 ---
@router.get(
    "/api/v1/user_place_list",
    response_model=List[UserPlaceResponseItem],
    tags=["Place"],
    summary="사용자가 기여한 장소 목록 조회"
)
async def user_place_list(request: Request):
    """
    현재 로그인한 사용자가 정보를 기여한 장소들의 목록을 반환합니다.
    """
    db: Session = SessionLocal()
    try:
        # 1. 현재 사용자 ID 조회
        user_uuid = request.state.user_uuid
        user = db.query(User.id).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        user_id = user.id

        # 2. 사용자가 기여한 모든 장소의 고유 ID (place_master_id) 목록 조회
        place_ids_query = db.query(distinct(PlaceContribution.place_master_id)).filter(PlaceContribution.user_id == user_id)
        place_ids = [pid for pid, in place_ids_query.all()]

        if not place_ids:
            return [] # 기여한 장소가 없으면 빈 리스트 반환

        # 3. 각 장소별 기여자 수(중복제거)를 계산하는 서브쿼리 생성
        contributor_count_subquery = (
            db.query(func.count(distinct(PlaceContribution.user_id)))
            .filter(PlaceContribution.place_master_id == PlaceMaster.id)
            .correlate(PlaceMaster) # 메인 쿼리의 PlaceMaster와 연결
            .as_scalar()
        )

        # 4. 각 장소별 가장 최신 이미지 URL을 가져오는 서브쿼리 생성
        image_url_subquery = (
            db.query(PlaceContributionImage.image_url)
            .join(PlaceContribution, PlaceContributionImage.place_contribution_id == PlaceContribution.id)
            .filter(PlaceContribution.place_master_id == PlaceMaster.id)
            .order_by(PlaceContributionImage.created_at.desc())
            .limit(1)
            .correlate(PlaceMaster)
            .as_scalar()
        )

        # 5. 메인 쿼리: 위에서 얻은 장소 ID 목록과 서브쿼리들을 사용하여 최종 데이터 조회
        results = (
            db.query(
                PlaceMaster.id.label("place_id"),
                PlaceMaster.place_name,
                contributor_count_subquery.label("contributor_count"),
                image_url_subquery.label("image_url")
            )
            .filter(PlaceMaster.id.in_(place_ids))
            .order_by(desc(PlaceMaster.created_at)) # 장소의 최신 등록 순으로 정렬
            .all()
        )

        return results

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {e}")
    finally:
        db.close()