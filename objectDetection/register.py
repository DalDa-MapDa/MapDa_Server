import os
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import boto3
from sqlalchemy.orm import Session
from models import SessionLocal, UserObject
from dotenv import load_dotenv

load_dotenv()

# S3 클라이언트 설정
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')  # S3 리전 명시
)
S3_BUCKET = os.getenv('S3_BUCKET_NAME')

router = APIRouter()

class ObjectData(BaseModel):
    userID: int = Form(...)
    latitude: float = Form(...)
    longitude: float = Form(...)
    objectName: str = Form(...)
    placeName: str = Form(...)
    imageData: UploadFile = File(...)

@router.post("/register")
async def register_object(userID: int = Form(...), latitude: float = Form(...),
                          longitude: float = Form(...), objectName: str = Form(...),
                          placeName: str = Form(...), imageData: UploadFile = File(...)):
    db = None
    try:
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

        # DB에 정보 저장
        db: Session = SessionLocal()
        db_object = UserObject(
            user_id=userID,
            latitude=latitude,
            longitude=longitude,
            object_name=objectName,
            place_name=placeName,
            image_url=image_url
        )
        db.add(db_object)
        db.commit()
        db.refresh(db_object)

        return {"id": db_object.id}

    except Exception as e:
        if db:
            db.rollback()  # DB 롤백 추가
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
