from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session
from models import SessionLocal, UserTimetable
from sqlalchemy import and_

router = APIRouter()

@router.get("/api/v1/timetable", tags=["Timetable"])
async def get_user_timetable(request: Request):
    """유저의 시간표 데이터를 조회하는 기능"""
    
    try:
        # 인증된 사용자 UUID 가져오기 (미들웨어에서 이미 처리된 부분)
        user_uuid = request.state.user_uuid
        if not user_uuid:
            raise HTTPException(status_code=401, detail="Invalid user.")

        # DB 세션 생성
        db: Session = SessionLocal()

        # 유저의 Active 상태의 시간표 데이터 조회
        timetables = db.query(UserTimetable).filter(
            and_(UserTimetable.created_uuid == user_uuid, UserTimetable.user_object_status == 'Active')
        ).order_by(UserTimetable.updated_at.desc(), UserTimetable.id.desc()).all()

        # 조회된 시간표 데이터에서 중복 시간 처리
        result = []
        time_slots = {}

        for timetable in timetables:
            day = timetable.day
            start_time = timetable.start_time
            end_time = timetable.end_time

            # 중복된 시간대가 있는지 확인
            is_overlapping = False
            for saved_timetable in time_slots.get(day, []):
                if (start_time < saved_timetable['end_time'] and end_time > saved_timetable['start_time']):
                    is_overlapping = True
                    break

            # 겹치는 시간이 없거나 가장 최신 데이터라면 저장
            if not is_overlapping:
                if day not in time_slots:
                    time_slots[day] = []
                
                time_slots[day].append({
                    "id": timetable.id,
                    "lname": timetable.lname,
                    "day": timetable.day,
                    "start_time": timetable.start_time,
                    "end_time": timetable.end_time,
                    "classroom": timetable.classroom,
                    "created_at": timetable.created_at,
                    "updated_at": timetable.updated_at,
                })

        # 시간대별로 최신 데이터를 result에 추가
        for day, schedules in time_slots.items():
            result.extend(schedules)

        return result if result else {"message": "No timetable data found for this user."}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        db.close()
