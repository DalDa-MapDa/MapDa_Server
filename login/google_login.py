import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import requests
from sqlalchemy.orm import Session
from models import SessionLocal
from login.login_token_manage import (
    get_user_by_provider, create_user, update_user, create_or_update_token,
    create_access_token, create_refresh_token
)

router = APIRouter()

# .env 파일 로드
load_dotenv()

# 구글 관련 환경 변수 로드
GOOGLE_CLIENT_IDS = os.getenv("GOOGLE_CLIENT_IDS", "").split(",")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

class GoogleLoginData(BaseModel):
    idToken: str
    accessToken: str  # access token 추가

@router.post("/login/google", tags=["Login"])
async def google_login(data: GoogleLoginData):
    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        # ID 토큰 검증
        id_info = id_token.verify_oauth2_token(
            data.idToken, google_requests.Request(), None
        )

        # 클라이언트 ID 확인 (GOOGLE_CLIENT_IDS 중 하나와 일치하는지 확인)
        if id_info['aud'] not in GOOGLE_CLIENT_IDS:
            db.close()
            raise HTTPException(status_code=400, detail="Invalid client ID")

        # 사용자 정보 추출
        provider_id = id_info['sub']
        email = id_info.get('email')
        provider_profile_image = id_info.get('picture')
        provider_user_name = id_info.get('name')

        # 사용자 존재 여부 확인
        user = get_user_by_provider(db, 'GOOGLE', provider_id)

        if not user:
            # 새로운 유저 생성
            user = create_user(
                db,
                email=email,
                provider_type='GOOGLE',
                provider_id=provider_id,
                provider_profile_image=provider_profile_image,
                provider_user_name=provider_user_name,
                status='Need_Register'
            )
            message = "Need_Register"
            status_code = 201
        else:
            # 이메일, 프로필 이미지, 사용자 이름 업데이트
            updated_fields = {}
            if email is not None:
                updated_fields["email"] = email
            if provider_profile_image is not None:
                updated_fields["provider_profile_image"] = provider_profile_image
            if provider_user_name is not None:
                updated_fields["provider_user_name"] = provider_user_name

            if updated_fields:
                user = update_user(db, user, **updated_fields)

            if user.status == 'Need_Register':
                message = "Need_Register"
                status_code = 202
            elif user.status == 'Active':
                message = "로그인 성공"
                status_code = 200
            else:
                db.close()
                raise HTTPException(status_code=400, detail="유효하지 않은 사용자 상태입니다.")

        # 서버에서 JWT 토큰 생성
        access_token = create_access_token(data={"uuid": user.uuid})
        refresh_token = create_refresh_token(data={"uuid": user.uuid})

        # 토큰 업데이트
        create_or_update_token(
            db,
            user_uuid=user.uuid,
            refresh_token=refresh_token,
            provider_type='GOOGLE',
            provider_access_token=data.accessToken
        )

        db.close()
        return {
            "message": message,
            "access_token": access_token,
            "refresh_token": refresh_token
        }, status_code

    except ValueError:
        db.close()
        raise HTTPException(status_code=400, detail="구글 인증 실패")
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Error processing user info: {str(e)}")

# 구글 계정 연결 해제 (revoke) 메소드
@router.delete("/login/google/unregister", tags=["Login"])
async def google_unregister(user_access_token: str):
    try:
        # 구글 revoke URL
        revoke_url = f"https://accounts.google.com/o/oauth2/revoke?token={user_access_token}"

        # 구글 revoke 요청
        revoke_response = requests.post(revoke_url)

        if revoke_response.status_code == 200:
            return {"message": "구글 계정 연결 해제 성공"}
        else:
            raise HTTPException(
                status_code=revoke_response.status_code,
                detail="구글 계정 연결 해제 실패"
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"구글 연결 해제 중 오류 발생: {str(e)}")