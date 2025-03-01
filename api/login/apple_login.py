import datetime
import os
import jwt
import requests
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Response
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from models import SessionLocal, User, Token
from api.login.login_token_manage import (
    get_user_by_provider, create_user, create_or_update_token,
    create_access_token, create_refresh_token
)

router = APIRouter()

# .env 파일 로드
load_dotenv()

# 애플 관련 환경변수 로드
APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID")
APPLE_KEY_ID = os.getenv("APPLE_KEY_ID")
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID")

# AuthKey 파일에서 비밀키를 읽어오기(이 부분은 로컬/서버 환경에 따라 경로가 다를 수 있음)
# 삭제 금지
auth_key_path = "/app/secrets/AuthKey_76ZFAC89DR.p8"  # 서버 경로
# auth_key_path = "secrets/AuthKey_76ZFAC89DR.p8"  # 로컬 경로


try:
    with open(auth_key_path, "r") as key_file:
        APPLE_PRIVATE_KEY = key_file.read()
except FileNotFoundError:
    raise HTTPException(status_code=500, detail=f"Private key file not found: {auth_key_path}")


class AppleLoginData(BaseModel):
    identityToken: str
    authorizationCode: str
    userEmail: str
    userName: str


@router.post('/login/apple', tags=["Login"])
def apple_login(data: AppleLoginData, response: Response):
    db: Session = SessionLocal()
    try:
        # Request token from Apple
        token_response = requests.post(
            'https://appleid.apple.com/auth/token',
            data={
                'client_id': APPLE_CLIENT_ID,
                'client_secret': create_client_secret(),
                'code': data.authorizationCode,
                'grant_type': 'authorization_code',
                'redirect_uri': 'https://api.mapda.site/login/apple'
            }
        )
        if token_response.status_code != 200:
            raise HTTPException(status_code=token_response.status_code, detail="Apple authentication failed")

        token_data = token_response.json()

        # Decode and verify identity token
        decoded_token = verify_and_decode_identity_token(token_data.get('id_token'))
        if not decoded_token:
            raise HTTPException(status_code=400, detail="Invalid identity token")

        provider_id = decoded_token.get('sub')
        if not provider_id:
            raise HTTPException(status_code=400, detail="Provider ID not found")

        # Check user existence using get_user_by_provider
        user = get_user_by_provider(db, 'APPLE', provider_id)

        if not user:
            # Create new user
            user = create_user(
                db,
                email=data.userEmail,
                provider_type='APPLE',
                provider_id=provider_id,
                provider_profile_image=None,
                provider_user_name=data.userName,
                apple_real_user_status=decoded_token.get('real_user_status'),
                status='Need_Register'
            )
            message = "Need_Register"
            response.status_code = 201
        elif user.status == 'Need_Register':
            message = "Need_Register"
            response.status_code = 202
        elif user.status == 'Active':
            message = "Login successful"
            response.status_code = 200
        else:
            raise HTTPException(status_code=400, detail="Invalid user status")

        # Generate and update tokens
        access_token = create_access_token(uuid=user.uuid)
        refresh_token = create_refresh_token()
        create_or_update_token(
            db,
            user_uuid=user.uuid,
            refresh_token=refresh_token,
            provider_type='APPLE',
            provider_refresh_token=token_data.get('refresh_token')
        )

        return {
            "message": message,
            "access_token": access_token,
            "refresh_token": refresh_token
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing Apple login: {str(e)}")
    finally:
        db.close()


def create_client_secret():
    headers = {
        "kid": APPLE_KEY_ID,
        "alg": "ES256"
    }
    payload = {
        "iss": APPLE_TEAM_ID,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=180),
        "aud": "https://appleid.apple.com",
        "sub": APPLE_CLIENT_ID,
    }
    try:
        return jwt.encode(payload, APPLE_PRIVATE_KEY, algorithm="ES256", headers=headers)
    except Exception:
        raise HTTPException(status_code=500, detail="Error generating client secret")


def verify_and_decode_identity_token(identity_token: str) -> dict:
    try:
        return jwt.decode(identity_token, options={"verify_signature": False})
    except jwt.InvalidTokenError:
        return None


# 회원 탈퇴 로직을 일반 함수로 변경
def apple_unregister_function(user_uuid: str):
    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        # 사용자의 토큰 항목 조회
        token_entry = db.query(Token).filter(Token.uuid == user_uuid).first()
        if not token_entry:
            db.close()
            raise HTTPException(status_code=404, detail="유효하지 않은 사용자입니다.")

        # provider_refresh_token 가져오기
        user_refresh_token = token_entry.provider_refresh_token

        # 애플에 회원 탈퇴 요청 보내기
        response = requests.post(
            'https://appleid.apple.com/auth/revoke',
            data={
                'client_id': APPLE_CLIENT_ID,
                'client_secret': create_client_secret(),
                'token': user_refresh_token,
                'token_type_hint': 'refresh_token'
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )

        if response.status_code != 200:
            db.close()
            raise HTTPException(status_code=response.status_code, detail="애플 회원 탈퇴 실패")

        # 사용자의 상태를 Deleted로 업데이트
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if user:
            user.status = 'Deleted'
            db.commit()

        # 토큰의 상태를 Deleted로 업데이트
        token_entry.status = 'Deleted'
        db.commit()

        db.close()
        return {"message": "애플 회원 탈퇴 성공"}

    except HTTPException as he:
        db.close()
        raise he
    except Exception as e:
        db.rollback()
        db.close()
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")