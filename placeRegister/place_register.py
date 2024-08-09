import os
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Dict
import boto3
from sqlalchemy.orm import Session
from models import SessionLocal, Place
from dotenv import load_dotenv

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

class MovingData(BaseModel):
    placeName: str
    selectedLocation: Dict[str, float]
    wheeleChaitAccessible: int
    restRoomExist: int = None
    restRoomFloor: int = None
    elevatorAccessible: int = None
    rampAccessible: int = None
    inDoorImage: List[UploadFile] = None
    outDoorImage: List[UploadFile] = None

@router.post("/register_moving_data")
async def register_moving_data(
    userID: int = Form(...),
    placeName: str = Form(...),
    selectedLocation: str = Form(...),
    wheeleChaitAccessible: int = Form(...),
    restRoomExist: int = Form(None),
    restRoomFloor: int = Form(None),
    elevatorAccessible: int = Form(None),
    rampAccessible: int = Form(None),
    inDoorImage: List[UploadFile] = File(None),
    outDoorImage: List[UploadFile] = File(None)
):
    try:
        # DB 세션 생성
        db: Session = SessionLocal()

        # JSON 문자열을 파싱하여 위치 정보 추출
        location = eval(selectedLocation)
        latitude = location.get('latitude')
        longitude = location.get('longitude')

        # 이미지를 S3에 업로드하고 URL 리스트 생성
        def upload_files(files):
            urls = []
            for file in files:
                file_extension = file.filename.split('.')[-1]
                s3_filename = f"{uuid.uuid4()}.{file_extension}"
                file.file.seek(0)
                # ContentType을 설정하여 브라우저에서 바로 프리뷰 가능하도록 함
                s3_client.upload_fileobj(
                    file.file, 
                    S3_BUCKET, 
                    s3_filename,
                    ExtraArgs={
                        'ContentType': f'image/{file_extension}'
                    }
                )
                image_url = f"https://{S3_BUCKET}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{s3_filename}"
                urls.append(image_url)
            return urls

        in_door_image_urls = upload_files(inDoorImage) if inDoorImage else []
        out_door_image_urls = upload_files(outDoorImage) if outDoorImage else []

        # DB에 정보 저장
        db_place = Place(
            user_id=userID,
            place_name=placeName,
            latitude=latitude,
            longitude=longitude,
            wheele_chait_accessible=wheeleChaitAccessible,
            rest_room_exist=restRoomExist,
            rest_room_floor=restRoomFloor,
            elevator_accessible=elevatorAccessible,
            ramp_accessible=rampAccessible,
            in_door_image_urls=",".join(in_door_image_urls),
            out_door_image_urls=",".join(out_door_image_urls)
        )
        db.add(db_place)
        db.commit()
        db.refresh(db_place)

        return {"id": db_place.id, "place_name": db_place.place_name}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

    finally:
        db.close()
