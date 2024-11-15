import os
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from sqlalchemy.orm import Session
from models import SessionLocal, Token, User
from api.login.login_token_manage import (
    get_user_by_provider, create_user, update_user, create_or_update_token,
    create_access_token, create_refresh_token
)
import requests

router = APIRouter()

# Load environment variables
load_dotenv()

GOOGLE_CLIENT_IDS = os.getenv("GOOGLE_CLIENT_IDS", "").split(",")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")


class GoogleLoginData(BaseModel):
    idToken: str
    accessToken: str


# 구글 ID 토큰 검증
def verify_id_token(id_token_str: str) -> dict:
    try:
        return id_token.verify_oauth2_token(id_token_str, google_requests.Request(), None)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID Token")


@router.post("/login/google", tags=["Login"])
async def google_login(data: GoogleLoginData, response: Response):
    db: Session = SessionLocal()
    try:
        # Verify ID Token
        id_info = verify_id_token(data.idToken)

        # Check client ID
        if id_info['aud'] not in GOOGLE_CLIENT_IDS:
            raise HTTPException(status_code=400, detail="Invalid client ID")

        # Extract user information
        provider_id = id_info['sub']
        user_data = {
            "email": id_info.get('email'),
            "provider_profile_image": id_info.get('picture'),
            "provider_user_name": id_info.get('name')
        }

        # Check if user exists
        user = get_user_by_provider(db, 'GOOGLE', provider_id)

        if not user:
            # Create a new user
            user = create_user(
                db,
                email=user_data["email"],
                provider_type='GOOGLE',
                provider_id=provider_id,
                provider_profile_image=user_data["provider_profile_image"],
                provider_user_name=user_data["provider_user_name"],
                status='Need_Register'
            )
            message = "Need_Register"
            response.status_code = 201
        else:
            # Update user fields if changed
            updated_fields = {
                k: v for k, v in user_data.items() if v is not None and getattr(user, k) != v
            }
            if updated_fields:
                user = update_user(db, user, **updated_fields)

            if user.status == 'Need_Register':
                message = "Need_Register"
                response.status_code = 202
            elif user.status == 'Active':
                message = "로그인 성공"
                response.status_code = 200
            else:
                raise HTTPException(status_code=400, detail="유효하지 않은 사용자 상태입니다.")

        # Generate tokens
        access_token = create_access_token(uuid=user.uuid)
        refresh_token = create_refresh_token()

        # Update tokens in database
        create_or_update_token(
            db,
            user_uuid=user.uuid,
            refresh_token=refresh_token,
            provider_type='GOOGLE',
            provider_access_token=data.accessToken
        )

        return {
            "message": message,
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing user info: {str(e)}")
    finally:
        db.close()

# 구글 계정 연결 해제 (revoke) 함수를 일반 함수로 변경
def google_unregister_function(user_uuid: str):
    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        # 사용자의 토큰 항목 조회
        token_entry = db.query(Token).filter(Token.uuid == user_uuid).first()
        if not token_entry:
            db.close()
            raise HTTPException(status_code=404, detail="유효하지 않은 사용자입니다.")

        # provider_access_token 가져오기
        user_access_token = token_entry.provider_access_token

        # 구글에 연결 해제 요청 보내기
        revoke_url = f"https://accounts.google.com/o/oauth2/revoke?token={user_access_token}"
        revoke_response = requests.post(revoke_url)

        if revoke_response.status_code != 200:
            db.close()
            raise HTTPException(status_code=revoke_response.status_code, detail="구글 계정 연결 해제 실패")

        # 사용자의 상태를 Deleted로 업데이트
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if user:
            user.status = 'Deleted'
            db.commit()

        # 토큰의 상태를 Deleted로 업데이트
        token_entry.status = 'Deleted'
        db.commit()

        db.close()
        return {"message": "구글 계정 연결 해제 성공"}

    except HTTPException as he:
        db.close()
        raise he
    except Exception as e:
        db.rollback()
        db.close()
        raise HTTPException(status_code=500, detail=f"구글 연결 해제 중 오류 발생: {str(e)}")