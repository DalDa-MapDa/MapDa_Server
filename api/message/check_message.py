from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, case # [추가] func, case 임포트
from models import SessionLocal, User, Message
from typing import Optional, List
from datetime import datetime

router = APIRouter()

# --- 기존 Pydantic 응답 모델들 ---
class MessageDetailsResponse(BaseModel):
    id: int
    sender_uuid: str
    recipient_uuid: str 
    danger_obj_id: Optional[int]
    message_type_1: bool
    message_type_2: bool
    message_type_3: bool
    message_type_4: bool
    message_type_5: bool
    message_type_6: bool
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

class CheckMessageResponse(BaseModel):
    has_new_message: bool
    message: Optional[MessageDetailsResponse] = None

# --- [신규] check_my_mail을 위한 Pydantic 응답 모델 ---
class AllMessagesCountResponse(BaseModel):
    message_type_1: int
    message_type_2: int
    message_type_3: int
    message_type_4: int
    message_type_5: int
    message_type_6: int


# --- 데이터베이스 세션 의존성 ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 기존 API 엔드포인트 ---
@router.get(
    "/api/v1/message_check",
    response_model=CheckMessageResponse,
    tags=["Message"],
    summary="읽지 않은 새 메시지 확인"
)
async def check_for_new_message(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    현재 로그인한 사용자를 수신자로 하는 읽지 않은(is_read=False) 메시지가 있는지 확인합니다.
    - 읽지 않은 메시지가 있으면, 가장 최신 메시지 1개의 정보와 함께 `has_new_message: true`를 반환합니다.
    - 읽지 않은 메시지가 없으면, `has_new_message: false`를 반환합니다.
    """
    try:
        user_uuid = request.state.user_uuid
        current_user = db.query(User).filter(User.uuid == user_uuid).first()
        if not current_user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        latest_unread_message = db.query(Message)\
            .filter(Message.recipient_uuid == current_user.uuid)\
            .filter(Message.is_read == False)\
            .order_by(desc(Message.created_at))\
            .first()

        if latest_unread_message:
            return CheckMessageResponse(
                has_new_message=True,
                message=latest_unread_message
            )
        else:
            return CheckMessageResponse(
                has_new_message=False,
                message=None
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")


# --- [신규] 추가된 API 엔드포인트 ---
@router.get(
    "/api/v1/message/all",
    response_model=AllMessagesCountResponse,
    tags=["Message"],
    summary="수신한 모든 메시지 타입별 개수 확인"
)
async def check_my_mail(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    현재 로그인한 사용자가 수신한 모든 메시지에 대해,
    message_type 1부터 6까지 각각 몇 개인지 집계하여 반환합니다.
    """
    try:
        # 1. 현재 사용자 UUID 확인
        user_uuid = request.state.user_uuid

        # 2. SQLAlchemy의 func.sum과 case를 사용하여 DB에서 직접 개수 집계
        # 이 방법은 모든 메시지를 서버 메모리로 가져와서 루프를 돌리는 것보다 훨씬 효율적입니다.
        counts = db.query(
            func.sum(case((Message.message_type_1 == True, 1), else_=0)).label("count_1"),
            func.sum(case((Message.message_type_2 == True, 1), else_=0)).label("count_2"),
            func.sum(case((Message.message_type_3 == True, 1), else_=0)).label("count_3"),
            func.sum(case((Message.message_type_4 == True, 1), else_=0)).label("count_4"),
            func.sum(case((Message.message_type_5 == True, 1), else_=0)).label("count_5"),
            func.sum(case((Message.message_type_6 == True, 1), else_=0)).label("count_6")
        ).filter(Message.recipient_uuid == user_uuid).one()

        # 3. 쿼리 결과를 Pydantic 모델에 맞춰 반환
        return AllMessagesCountResponse(
            message_type_1=counts.count_1 or 0,
            message_type_2=counts.count_2 or 0,
            message_type_3=counts.count_3 or 0,
            message_type_4=counts.count_4 or 0,
            message_type_5=counts.count_5 or 0,
            message_type_6=counts.count_6 or 0
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")