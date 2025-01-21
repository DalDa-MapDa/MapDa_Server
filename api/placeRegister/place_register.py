from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from models import SessionLocal, PlaceMaster, PlaceContribution, PlaceContributionImage, User

import uuid
import os
import boto3
from datetime import datetime
from typing import List
from dotenv import load_dotenv

load_dotenv()

s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)
S3_BUCKET = os.getenv('S3_PLACE_BUCKET_NAME')

router = APIRouter()

@router.post("/api/v1/register_moving_data", tags=["Place"])
async def register_moving_data(
    request: Request,
    placeName: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    wheeleChairAccessible: int = Form(...),
    restRoomExist: int = Form(None),
    restRoomFloor: int = Form(None),
    elevatorAccessible: int = Form(None),
    rampAccessible: int = Form(None),
    inDoorImages: List[UploadFile] = File(None),
    outDoorImages: List[UploadFile] = File(None)
):
    try:
        user_uuid = request.state.user_uuid

        db: Session = SessionLocal()

        # 1) 사용자 조회
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
        user_id = user.id
        user_university = user.university

        # 2) place_master 찾기 (university + placeName)
        #    같은 대학, 같은 이름이면 이미 존재한다고 간주
        place_master = db.query(PlaceMaster).filter(
            PlaceMaster.university == user_university,
            PlaceMaster.place_name == placeName
        ).first()

        # 같은 이름의 place_master가 없다면 새로 생성
        if not place_master:
            place_master = PlaceMaster(
                place_name=placeName,
                latitude=latitude,
                longitude=longitude,
                university=user_university
            )
            db.add(place_master)
            db.commit()
            db.refresh(place_master)

        # 3) place_contribution 생성
        db_contrib = PlaceContribution(
            place_master_id=place_master.id,
            user_id=user_id,
            wheele_chair_accessible=wheeleChairAccessible,
            rest_room_exist=restRoomExist,
            rest_room_floor=restRoomFloor,
            elevator_accessible=elevatorAccessible,
            ramp_accessible=rampAccessible
        )
        db.add(db_contrib)
        db.commit()
        db.refresh(db_contrib)

        # 4) 이미지 업로드 -> place_contribution_image 저장
        def upload_files(files, image_type):
            urls = []
            for file in files:
                ext = file.filename.split('.')[-1]
                s3_filename = f"{uuid.uuid4()}.{ext}"
                file.file.seek(0)
                s3_client.upload_fileobj(
                    file.file,
                    S3_BUCKET,
                    s3_filename,
                    ExtraArgs={'ContentType': f'image/{ext}'}
                )
                image_url = f"https://{S3_BUCKET}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{s3_filename}"
                # DB 저장
                db_image = PlaceContributionImage(
                    place_contribution_id=db_contrib.id,
                    image_url=image_url,
                    image_type=image_type
                )
                db.add(db_image)
                urls.append(image_url)
            return urls

        # (indoor)
        if inDoorImages:
            upload_files(inDoorImages, "indoor")

        # (outdoor)
        if outDoorImages:
            upload_files(outDoorImages, "outdoor")

        db.commit()

        return {
            "place_master_id": place_master.id,
            "place_contribution_id": db_contrib.id,
            "message": "등록 성공!"
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")
    finally:
        db.close()
