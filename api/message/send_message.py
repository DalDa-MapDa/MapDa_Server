from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from models import SessionLocal, User, Message
from typing import List, Optional

router = APIRouter()

# --- Pydantic 모델 정의 ---
class MessageCreate(BaseModel):
    recipient_id: int = Field(..., description="메시지를 받을 사용자의 ID")
    message_types: List[int] = Field(..., description="메시지 종류 리스트 (1부터 6까지의 정수 배열)")
    danger_obj_id: Optional[int] = Field(None, description="연관된 위험 객체의 ID (정수, 선택 사항)")

# --- 데이터베이스 세션 의존성 ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- API 엔드포인트 ---
@router.post("/api/v1/message", tags=["Message"], summary="사용자에게 메시지 보내기")
async def send_user_message(
    request: Request,
    payload: MessageCreate,
    db: Session = Depends(get_db)
):
    """
    인증된 사용자가 다른 사용자에게 1~6번 타입의 메시지를 보냅니다.

    - **recipient_id**: 메시지를 받을 사용자의 고유 ID (int)
    - **message_types**: 보낼 메시지의 종류가 담긴 리스트 (예: [1, 3, 5])
    - **danger_obj_id**: 연관된 위험 객체의 ID (정수, 선택 사항)
    """
    # (API 로직 자체는 이전과 동일하게 작동합니다. 타입 힌트만 변경되었습니다.)
    try:
        sender_uuid = request.state.user_uuid
        sender = db.query(User).filter(User.uuid == sender_uuid).first()
        if not sender:
            raise HTTPException(status_code=404, detail="메시지를 보내는 사용자를 찾을 수 없습니다.")

        recipient = db.query(User).filter(User.id == payload.recipient_id).first()
        if not recipient:
            raise HTTPException(status_code=404, detail="메시지를 받는 사용자를 찾을 수 없습니다.")
        
        if sender.id == recipient.id:
            raise HTTPException(status_code=400, detail="자기 자신에게 메시지를 보낼 수 없습니다.")

        message_data = {
            "sender_uuid": sender.uuid,
            "recipient_id": recipient.id,
            "danger_obj_id": payload.danger_obj_id
        }
        
        for msg_type in payload.message_types:
            if not 1 <= msg_type <= 6:
                raise HTTPException(
                    status_code=400, 
                    detail=f"잘못된 message_type이 포함되어 있습니다: {msg_type}. 1과 6 사이의 값이어야 합니다."
                )
            message_data[f"message_type_{msg_type}"] = True

        new_message = Message(**message_data)
        
        db.add(new_message)
        db.commit()
        db.refresh(new_message)

        return {"status": "success", "message": f"성공적으로 메시지를 보냈습니다.", "message_id": new_message.id}

    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")