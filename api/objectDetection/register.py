from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from models import SessionLocal, UserObject, User  # User 모델 임포트
from setting.storage import upload_file_to_storage

router = APIRouter()

@router.post("/api/v1/register", tags=["Object"])
async def register_object(
    request: Request,
    latitude: float = Form(...),
    longitude: float = Form(...),
    objectName: str = Form(...),
    placeName: str = Form(...),
    imageData: UploadFile = File(...)
):
    db = None
    try:
        # DB 세션 생성
        db: Session = SessionLocal()

        # 인증된 사용자 UUID 가져오기
        user_uuid = request.state.user_uuid

        # 사용자 정보 조회
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # 사용자 ID 및 대학 정보 가져오기
        user_id = user.id
        user_university = user.university  # university 데이터 가져오기

        stored_image = upload_file_to_storage(imageData, "objects")

        # UserObject 객체 생성
        db_object = UserObject(
            user_id=user_id,
            created_uuid=user_uuid,
            latitude=latitude,
            longitude=longitude,
            object_name=objectName,
            place_name=placeName,
            image_url=stored_image.url,
            university=user_university  # university 데이터 저장
        )
        db.add(db_object)
        db.commit()
        db.refresh(db_object)

        return {"id": db_object.id, "resource_id": db_object.resource_id}

    except Exception as e:
        if db:
            db.rollback()  # DB 롤백 추가
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")

    finally:
        if db:
            db.close()
