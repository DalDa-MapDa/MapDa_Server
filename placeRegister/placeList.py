from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import SessionLocal, Place

router = APIRouter()

@router.get("/get_place_list")
async def get_place_list():
    try:
        # DB 세션 생성
        db: Session = SessionLocal()

        # 최신순으로 최대 25개의 장소 데이터를 DB에서 가져옴
        places = db.query(Place).order_by(desc(Place.created_at)).limit(25).all()

        # 장소 리스트 반환
        return places

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

    finally:
        db.close()
