import json
import os
import uuid
import boto3
from dotenv import load_dotenv
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from openai import OpenAI
from sqlalchemy.orm import Session
from models import SessionLocal, UserTimetable
from datetime import time

router = APIRouter()

load_dotenv()

# S3 클라이언트 설정(유저 시간표 이미지를 저장할 버킷)
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION')
)
S3_BUCKET = os.getenv('S3_USER_TIMETABLE_BUCKET_NAME')

# OpenAI API 키 설정
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# OpenAI API 요청 시 사용할 프롬프트 (영어로 번역)
gpt_prompt = """
This image is a timetable image containing the class name, start time, end time, day of the week, and class location.
The class location is written in small text under the class name, but there may be cases where it is missing.
Please extract the timetable information from this image in JSON format.
The output format should be like this:
[{
    "lname": "Class name",
    "day": "Day of the week",
    "start_time": "HH:MM",
    "end_time": "HH:MM",
    "classroom": "Class location"
}]
If the classroom is missing, return null.
Only output in JSON format.
"""

# 시간표 데이터를 개별적으로 저장하는 함수
def save_timetable(db: Session, user_uuid: str, lname: str, day: str, start_time_obj: time, end_time_obj: time, classroom: str = None):
    """ 시간표 데이터를 DB에 저장하는 함수 """
    try:
        # 시간표 데이터 생성 및 저장
        new_timetable = UserTimetable(
            lname=lname,
            day=day,
            start_time=start_time_obj,
            end_time=end_time_obj,
            classroom=classroom,
            created_uuid=user_uuid
        )
        
        db.add(new_timetable)
        db.commit()
        db.refresh(new_timetable)

        return new_timetable

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"An error occurred while saving the timetable: {str(e)}")


@router.post("/api/v1/timetable/regByImage", tags=["Timetable"])
async def register_timetable_by_image(
    request: Request,
    timeTable_image: UploadFile = File(...)
):

    db = None  # Initialize db as None

    try:
        # 인증된 사용자 UUID 가져오기
        user_uuid = request.state.user_uuid
        if not user_uuid:
            raise HTTPException(status_code=401, detail="Invalid user.")

        # 이미지 파일을 S3에 업로드
        file_extension = timeTable_image.filename.split('.')[-1]
        s3_filename = f"{uuid.uuid4()}.{file_extension}"
        timeTable_image.file.seek(0)
        s3_client.upload_fileobj(
            timeTable_image.file,
            S3_BUCKET,
            s3_filename,
            ExtraArgs={
                'ContentType': f'image/{file_extension}'
            }
        )
        image_url = f"https://{S3_BUCKET}.s3.{os.getenv('AWS_REGION')}.amazonaws.com/{s3_filename}"

        # OpenAI API를 통해 이미지에서 시간표 정보 추출
        client = OpenAI(
            api_key=OPENAI_API_KEY
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": gpt_prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
        )

        # 응답에서 message 부분에 접근
        response_text = response.choices[0].message.content.strip()

        # JSON 응답 파싱
        try:
            timetable_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail=f"Error parsing OpenAI response: {str(e)}")

        # Check if 'timetable' key exists
        if 'timetable' not in timetable_data:
            raise HTTPException(status_code=500, detail="Invalid response format: 'timetable' key not found")

        # DB 세션 생성
        db = SessionLocal()

        # 각 수업 정보를 DB에 저장
        for entry in timetable_data['timetable']:
            lname = entry.get('lname')
            day = entry.get('day')
            start_time_str = entry.get('start_time')
            end_time_str = entry.get('end_time')
            classroom = entry.get('classroom')

            if not lname or not day or not start_time_str or not end_time_str:
                continue  # Skip entries with missing mandatory data

            # 시간을 time 객체로 변환
            try:
                start_time_obj = time.fromisoformat(start_time_str)
                end_time_obj = time.fromisoformat(end_time_str)
            except ValueError:
                continue  # Skip entries with invalid time format

            # 시간표 저장
            save_timetable(
                db=db,
                user_uuid=user_uuid,
                lname=lname,
                day=day,
                start_time_obj=start_time_obj,
                end_time_obj=end_time_obj,
                classroom=classroom
            )

        return {"message": "Timetable successfully registered."}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        if db is not None:
            try:
                db.close()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error closing DB session: {str(e)}")
