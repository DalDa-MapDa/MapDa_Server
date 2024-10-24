from datetime import datetime
import os
import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel
from typing import List, Dict
import boto3
from sqlalchemy.orm import Session
from models import SessionLocal, Place, PlaceIndoor, PlaceOutdoor, User  # User 모델 임포트
from dotenv import load_dotenv
import json  # json 모듈 추가

load_dotenv()

# S3 클라이언트 설정
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)
S3_BUCKET = os.getenv('S3_PLACE_BUCKET_NAME')

router = APIRouter()

@router.post("/register_moving_data", tags=["Place"])
async def register_moving_data(
    request: Request,  # Request 추가
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
        # 인증된 사용자 UUID 가져오기
        user_uuid = request.state.user_uuid

        # 데이터베이스 세션 생성
        db: Session = SessionLocal()

        # 사용자 정보 조회
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # 사용자 ID 가져오기
        user_id = user.id

        # JSON 문자열을 파싱하여 위치 정보 추출
        try:
            location = json.loads(selectedLocation)
            latitude = location.get('latitude')
            longitude = location.get('longitude')
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="잘못된 위치 정보입니다.")

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

        # Place 객체 생성
        db_place = Place(
            user_id=user_id,
            created_uuid=user_uuid,
            place_name=placeName,
            latitude=latitude,
            longitude=longitude,
            wheele_chait_accessible=wheeleChaitAccessible,
            rest_room_exist=restRoomExist,
            rest_room_floor=restRoomFloor,
            elevator_accessible=elevatorAccessible,
            ramp_accessible=rampAccessible
        )
        db.add(db_place)
        db.commit()
        db.refresh(db_place)

        # 이미지 URL을 place_indoor 및 place_outdoor 테이블에 저장
        for url in in_door_image_urls:
            db_indoor = PlaceIndoor(place_id=db_place.id, image_url=url)
            db.add(db_indoor)
        
        for url in out_door_image_urls:
            db_outdoor = PlaceOutdoor(place_id=db_place.id, image_url=url)
            db.add(db_outdoor)
        
        db.commit()

        return {
            "id": db_place.id,
            "resource_id": db_place.resource_id,
            "place_name": db_place.place_name
        }

    except HTTPException as e:
        # 이미 발생한 HTTPException은 그대로 다시 발생시킵니다.
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")

    finally:
        db.close()
