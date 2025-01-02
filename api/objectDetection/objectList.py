from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import SessionLocal, UserObject, User

router = APIRouter()

@router.get("/api/v1/get_object_list", tags=["Object"])
async def get_object_list(request: Request):
    try:
        # DB 세션 생성
        db: Session = SessionLocal()

        # 인증된 사용자 UUID 가져오기
        user_uuid = request.state.user_uuid

        # 사용자의 대학교 정보 조회
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # 사용자의 대학교와 일치하는 객체들을 최신순으로 최대 25개 조회
        objects = db.query(UserObject)\
            .filter(UserObject.university == user.university)\
            .order_by(desc(UserObject.created_at))\
            .limit(25)\
            .all()

        # 객체 리스트 반환
        object_list = []
        for obj in objects:
            object_list.append({
                "id": obj.id,
                "resource_id": obj.resource_id,
                "created_at": obj.created_at,
                "user_id": obj.user_id,
                "created_uuid": obj.created_uuid,
                "latitude": obj.latitude,
                "longitude": obj.longitude,
                "object_name": obj.object_name,
                "place_name": obj.place_name,
                "image_url": obj.image_url
            })

        return object_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")

    finally:
        db.close()

@router.get("/api/v1/get_specific_object/{id}", tags=["Object"])
async def get_specific_object(id: int):
    try:
        # DB 세션 생성
        db: Session = SessionLocal()

        # 특정 ID에 해당하는 객체를 DB에서 가져옴
        obj = db.query(UserObject).filter(UserObject.id == id).first()

        if obj is None:
            raise HTTPException(status_code=404, detail="객체를 찾을 수 없습니다.")

        # 객체 반환
        return {
            "id": obj.id,
            "resource_id": obj.resource_id,
            "created_at": obj.created_at,
            "user_id": obj.user_id,
            "created_uuid": obj.created_uuid,
            "latitude": obj.latitude,
            "longitude": obj.longitude,
            "object_name": obj.object_name,
            "place_name": obj.place_name,
            "image_url": obj.image_url
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")

    finally:
        db.close()

@router.get("/api/v1/user_object_list", tags=["Object"])
async def get_user_object_list(request: Request):
    try:
        # DB 세션 생성
        db: Session = SessionLocal()

        # 인증된 사용자 UUID 가져오기
        user_uuid = request.state.user_uuid

        # 해당 사용자의 UUID로 등록된 객체들을 created_at 기준 최신순으로 가져옴
        objects = db.query(UserObject)\
            .filter(UserObject.created_uuid == user_uuid)\
            .order_by(desc(UserObject.created_at))\
            .all()

        # 객체 리스트 반환
        object_list = []
        for obj in objects:
            object_list.append({
                "id": obj.id,
                "resource_id": obj.resource_id,
                "created_at": obj.created_at,
                "user_id": obj.user_id,
                "created_uuid": obj.created_uuid,
                "latitude": obj.latitude,
                "longitude": obj.longitude,
                "object_name": obj.object_name,
                "place_name": obj.place_name,
                "image_url": obj.image_url
            })

        return object_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")

    finally:
        db.close()
