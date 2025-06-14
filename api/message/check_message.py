from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import SessionLocal, User, Message
from typing import Optional, List
from datetime import datetime

router = APIRouter()

# --- Pydantic 응답 모델 정의 ---
# API가 반환할 메시지의 상세 구조를 정의합니다.
class MessageDetailsResponse(BaseModel):
    id: int
    sender_uuid: str
    recipient_id: int
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
        from_attributes = True # SQLAlchemy 모델을 Pydantic 모델로 변환 허용

# API의 최종 응답 구조를 정의합니다.
class CheckMessageResponse(BaseModel):
    has_new_message: bool
    message: Optional[MessageDetailsResponse] = None


# --- 데이터베이스 세션 의존성 ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- API 엔드포인트 ---
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
        # 1. 토큰에서 현재 사용자의 UUID 확인 (미들웨어 통해 주입됨)
        user_uuid = request.state.user_uuid
        
        # 2. UUID를 사용하여 사용자의 고유 ID (int) 조회
        current_user = db.query(User).filter(User.uuid == user_uuid).first()
        if not current_user:
            # 이 경우는 미들웨어에서 이미 처리되었겠지만, 안전을 위해 추가
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

        # 3. 현재 사용자를 수신자로 하고, is_read가 False인 메시지 중 가장 최신 1건 조회
        latest_unread_message = db.query(Message)\
            .filter(Message.recipient_id == current_user.id)\
            .filter(Message.is_read == False)\
            .order_by(desc(Message.created_at))\
            .first()

        # 4. 결과에 따라 응답 반환
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