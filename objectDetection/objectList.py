from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import SessionLocal, UserObject

router = APIRouter()

@router.get("/get_object_list")
async def get_object_list():
    try:
        # DB 세션 생성
        db: Session = SessionLocal()

        # 최대 25개의 객체를 created_at을 기준으로 최신순으로 가져옴
        objects = db.query(UserObject).order_by(desc(UserObject.created_at)).limit(25).all()

        # 객체 리스트 반환
        return objects

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

    finally:
        db.close()

@router.get("/get_specific_object/{id}")
async def get_specific_object(id: int):
    try:
        # DB 세션 생성
        db: Session = SessionLocal()

        # 특정 ID에 해당하는 객체를 DB에서 가져옴
        obj = db.query(UserObject).filter(UserObject.id == id).first()

        if obj is None:
            raise HTTPException(status_code=404, detail="Object not found")

        # 객체 반환
        return obj

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

    finally:
        db.close()
