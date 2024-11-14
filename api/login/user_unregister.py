import os
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from models import SessionLocal, Token, User
from api.login.login_token_manage import (
    get_user_by_provider, create_user, update_user, create_or_update_token,
    create_access_token, create_refresh_token
)
from sqlalchemy.future import select

# 개별 unregister 함수 임포트
from api.login.kakao_login import kakao_unregister_function
from api.login.apple_login import apple_unregister_function
from api.login.google_login import google_unregister_function

router = APIRouter()

# .env 파일 로드
load_dotenv()

class UnregisterResponse(BaseModel):
    message: str

@router.delete('/api/v1/unregister', response_model=UnregisterResponse, tags=["Unregister"])
def user_unregister(request: Request):
    # 사용자 UUID 가져오기
    user_uuid = request.state.user_uuid

    if not user_uuid:
        raise HTTPException(status_code=401, detail="인증되지 않은 사용자입니다.")

    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        # 사용자 조회
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if not user:
            db.close()
            raise HTTPException(status_code=404, detail="유효하지 않은 사용자입니다.")

        provider_type = user.provider_type

        if provider_type == 'KAKAO':
            # 카카오 연결 해제 함수 호출
            result = kakao_unregister_function(user_uuid)
        elif provider_type == 'APPLE':
            # 애플 연결 해제 함수 호출
            result = apple_unregister_function(user_uuid)
        elif provider_type == 'GOOGLE':
            # 구글 연결 해제 함수 호출
            result = google_unregister_function(user_uuid)
        else:
            db.close()
            raise HTTPException(status_code=400, detail="지원되지 않는 provider_type입니다.")

        db.close()
        return UnregisterResponse(message=result["message"])

    except HTTPException as he:
        db.close()
        raise he
    except Exception as e:
        db.rollback()
        db.close()
        raise HTTPException(status_code=500, detail=f"회원 탈퇴 중 오류 발생: {str(e)}")
