from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, case
from models import SessionLocal, User, Message
from typing import Optional, List
from datetime import datetime

router = APIRouter()

# --- Pydantic 응답 모델 정의 ---
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
    # (기존 코드와 동일)
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
    # (기존 코드와 동일)
    try:
        user_uuid = request.state.user_uuid
        counts = db.query(
            func.sum(case((Message.message_type_1 == True, 1), else_=0)).label("count_1"),
            func.sum(case((Message.message_type_2 == True, 1), else_=0)).label("count_2"),
            func.sum(case((Message.message_type_3 == True, 1), else_=0)).label("count_3"),
            func.sum(case((Message.message_type_4 == True, 1), else_=0)).label("count_4"),
            func.sum(case((Message.message_type_5 == True, 1), else_=0)).label("count_5"),
            func.sum(case((Message.message_type_6 == True, 1), else_=0)).label("count_6")
        ).filter(Message.recipient_uuid == user_uuid).one()

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


# --- [신규] 추가된 API 엔드포인트 ---
@router.get(
    "/api/v1/message/confirm",
    tags=["Message"],
    summary="수신한 모든 메시지를 읽음 처리"
)
async def confirm_all_messages(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    현재 로그인한 사용자가 받은 모든 '읽지 않은' 메시지를 '읽음' 상태로 변경하고,
    읽은 시간을 현재 시간으로 기록합니다.
    """
    try:
        user_uuid = request.state.user_uuid
        
        # 1. 업데이트할 대상 쿼리
        # 이미 읽은 메시지는 제외하여 불필요한 DB 쓰기를 방지합니다.
        messages_to_update = db.query(Message).filter(
            Message.recipient_uuid == user_uuid,
            Message.is_read == False
        )
        
        # 2. 대량 업데이트(bulk update) 실행
        # 이 방법은 메시지를 하나씩 불러와 수정하는 것보다 훨씬 효율적입니다.
        updated_count = messages_to_update.update({
            "is_read": True,
            "read_at": datetime.utcnow()
        }, synchronize_session=False) # 세션 동기화 전략 설정
        
        # 3. 변경사항 커밋
        db.commit()
        
        return {"status": "success", "updated_count": updated_count}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")