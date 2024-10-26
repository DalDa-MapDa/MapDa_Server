from fastapi import APIRouter, HTTPException, Request, Form
from sqlalchemy.orm import Session
from models import SessionLocal, UserTimetable, User  # 새로 추가한 UserTimetable 모델 임포트
from datetime import time

router = APIRouter()

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
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")


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
