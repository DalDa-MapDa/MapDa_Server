import os
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from models import SessionLocal, UserObject, User  # User 모델 임포트
from dotenv import load_dotenv
from datetime import datetime
import boto3

load_dotenv()

# S3 클라이언트 설정
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)
S3_BUCKET = os.getenv('S3_BUCKET_NAME')

router = APIRouter()

@router.post("api/v1/register", tags=["Object"])
async def register_object(
    request: Request,  # Request 추가
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

        # 사용자 ID 가져오기
        user_id = user.id

        # S3에 이미지 업로드
        file_extension = imageData.filename.split('.')[-1]
        s3_filename = f"{uuid.uuid4()}.{file_extension}"
        imageData.file.seek(0)  # 파일 포인터를 시작 위치로 재설정
        s3_client.upload_fileobj(
            imageData.file, 
            S3_BUCKET, 
            s3_filename,
            ExtraArgs={
                'ContentType': f'image/{file_extension}',  # 적절한 MIME 타입 설정
            }
        )
        image_url = f"https://{S3_BUCKET}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{s3_filename}"

        # UserObject 객체 생성
        db_object = UserObject(
            user_id=user_id,
            created_uuid=user_uuid,
            latitude=latitude,
            longitude=longitude,
            object_name=objectName,
            place_name=placeName,
            image_url=image_url
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
