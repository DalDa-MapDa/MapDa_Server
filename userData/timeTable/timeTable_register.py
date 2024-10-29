import json, os, random, uuid, boto3, requests, xml.etree.ElementTree as ET
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
This image is a timetable that includes multiple course names, start times, end times, days, and classroom locations.
The classroom is shown in smaller text below the course name, but it may be missing in some cases.
The start time and end time are shown on the left side of the image, and you should use these times as a reference and follow the 24-hour format.
Please extract all the course information from this image and output it as a JSON object with the following structure:
{
    "timetable": [
        {
            "lname": "Course Name",
            "day": "Day",
            "start_time": "HH:MM",
            "end_time": "HH:MM",
            "classroom": "Classroom"
        },
        ...
    ]
}
If the classroom information is missing, set it to null. Ensure that all available course data is returned within the timetable array, following the format above.
"""

# 요일 변환 함수
def day_to_string(day_num):
    days = ["월", "화", "수", "목", "금", "토", "일"]
    return days[int(day_num)] if day_num.isdigit() and int(day_num) < len(days) else None

# 5분 단위 값을 HH:MM 형식으로 변환하는 함수
def convert_time(time_value):
    total_minutes = int(time_value) * 5
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"

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
    

@router.post("/api/v1/timetable/individual", tags=["Timetable"])
async def register_individual_timetable(
    request: Request,
    lname: str = Form(...),
    day: str = Form(...),
    startTime: str = Form(...),  # 시간을 문자열로 받고 나중에 time 객체로 변환
    endTime: str = Form(...),
    classroom: str = Form(None)
):
    try:
        # 인증된 사용자 UUID 가져오기 (미들웨어에서 이미 처리된 부분)
        user_uuid = request.state.user_uuid
        if not user_uuid:
            raise HTTPException(status_code=401, detail="유효하지 않은 사용자입니다.")

        # DB 세션 생성
        db: Session = SessionLocal()

        # 시간을 time 객체로 변환
        try:
            start_time_obj = time.fromisoformat(startTime)
            end_time_obj = time.fromisoformat(endTime)
        except ValueError:
            raise HTTPException(status_code=400, detail="시간 형식이 잘못되었습니다. HH:MM 형식이어야 합니다.")

        # 시간표를 저장하는 함수 호출
        new_timetable = save_timetable(
            db=db,
            user_uuid=user_uuid,
            lname=lname,
            day=day,
            start_time_obj=start_time_obj,
            end_time_obj=end_time_obj,
            classroom=classroom
        )

        return {
            "id": new_timetable.id,
            "lname": new_timetable.lname,
            "day": new_timetable.day,
            "start_time": new_timetable.start_time,
            "end_time": new_timetable.end_time,
            "classroom": new_timetable.classroom
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")
    finally:
        db.close()


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
            model="gpt-4o",
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


@router.post("/api/v1/timetable/regByUrl", tags=["Timetable"])
async def register_timetable_by_url(
    request: Request,
    url: str = Form(...)
):
    # 유저 액세스 토큰 검증
    user_uuid = request.state.user_uuid
    if not user_uuid:
        raise HTTPException(status_code=401, detail="유효하지 않은 사용자입니다.")

    # URL 검증
    if not url.startswith("https://everytime.kr/@"):
        raise HTTPException(status_code=400, detail="올바르지 않은 URL 형식입니다.")

    # identifier 추출
    try:
        identifier = url.split('@')[1]
    except IndexError:
        raise HTTPException(status_code=400, detail="identifier를 추출할 수 없습니다.")

    # API 요청을 위한 User-Agent 목록 설정
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 10; SM-G970F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Mobile Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:54.0) Gecko/20100101 Firefox/54.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.2 Safari/605.1.15",
        "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"
    ]

    # POST 요청 헤더 설정
    headers = {
        "User-Agent": random.choice(user_agents),
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://everytime.kr",
        "Referer": "https://everytime.kr"
    }

    # POST 요청의 페이로드
    payload = {
        "identifier": identifier,
        'friendInfo': 'true',
    }

    # 외부 API 요청 보내기
    response = requests.post("https://api.everytime.kr/find/timetable/table/friend", headers=headers, data=payload)

    # 응답 검증
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="API 요청 실패")

    # XML 응답 파싱
    xml_data = response.content
    root = ET.fromstring(xml_data)

    # DB 세션 생성
    db: Session = SessionLocal()

    try:
        # 각 subject 항목을 순회하며 데이터를 파싱 및 저장
        for subject in root.findall(".//subject"):
            lname = subject.find(".//name").attrib.get("value")
            professor = subject.find(".//professor").attrib.get("value")
            time_text = subject.find(".//time").attrib.get("value", "")
            credit = subject.find(".//credit").attrib.get("value")
            closed = subject.find(".//closed").attrib.get("value")

            # data 태그가 있는지 확인
            data_tag = subject.find(".//time/data")
            if data_tag is not None:
                day = day_to_string(data_tag.attrib.get("day", "0"))  # 요일 숫자를 변환
                starttime = convert_time(data_tag.attrib.get("starttime"))
                endtime = convert_time(data_tag.attrib.get("endtime"))
                place = data_tag.attrib.get("place", None)
            else:
                continue  # No time data available인 경우 저장하지 않음

            # 시간을 저장할 데이터가 없으면 건너뛰기
            if not day or not starttime or not endtime:
                continue

            # 시간표를 DB에 저장하는 함수 호출
            start_time_obj = time.fromisoformat(starttime)
            end_time_obj = time.fromisoformat(endtime)

            save_timetable(
                db=db,
                user_uuid=user_uuid,
                lname=lname,
                day=day,
                start_time_obj=start_time_obj,
                end_time_obj=end_time_obj,
                classroom=place
            )

        return {"message": "Timetable successfully registered."}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"서버 오류 발생: {str(e)}")
    finally:
        db.close()