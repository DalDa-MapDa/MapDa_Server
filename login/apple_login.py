from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
import requests
import jwt  # PyJWT 라이브러리
import datetime
from dotenv import load_dotenv
import os
from sqlalchemy.orm import Session
from models import SessionLocal
from login.login_token_manage import (
    get_user_by_provider, create_user, create_or_update_token,
    create_access_token, create_refresh_token
)

router = APIRouter()

# .env 파일 로드
load_dotenv()

# 애플 관련 환경 변수 로드
APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID")
APPLE_KEY_ID = os.getenv("APPLE_KEY_ID")
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID")

# AuthKey 파일에서 비밀키를 읽어오기
auth_key_path = "/app/secrets/AuthKey_76ZFAC89DR.p8"  # 서버 경로
# auth_key_path = "app/secrets/AuthKey_76ZFAC89DR.p8"  # 로컬 경로

try:
    with open(auth_key_path, "r") as key_file:
        APPLE_PRIVATE_KEY = key_file.read()
except FileNotFoundError:
    raise HTTPException(status_code=500, detail=f"비밀키 파일을 찾을 수 없습니다: {auth_key_path}")

# 입력 데이터 모델 정의
class AppleLoginData(BaseModel):
    identityToken: str
    authorizationCode: str
    userEmail: str  # 새로운 필드 추가
    userName: str   # 새로운 필드 추가

@router.post('/login/apple', tags=["Login"])
async def apple_login(data: AppleLoginData):
    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        # 1. 애플로부터 받은 authorizationCode로 토큰 요청
        response = requests.post(
            'https://appleid.apple.com/auth/token',
            data={
                'client_id': APPLE_CLIENT_ID,
                'client_secret': create_client_secret(),
                'code': data.authorizationCode,
                'grant_type': 'authorization_code',
                'redirect_uri': 'https://api.mapda.site/login/apple'
            }
        )
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail="애플 인증 요청 중 오류 발생")

    # 애플 인증 실패 시 오류 처리
    if response.status_code != 200:
        db.close()
        raise HTTPException(status_code=response.status_code, detail="애플 인증 실패")

    token_data = response.json()

    # 2. ID 토큰 디코딩 및 검증
    decoded_token = verify_and_decode_identity_token(token_data.get('id_token'))
    if decoded_token is None:
        db.close()
        raise HTTPException(status_code=400, detail="identityToken 검증 실패")

    # 3. provider_id 추출
    provider_id = decoded_token.get('sub')
    if not provider_id:
        db.close()
        raise HTTPException(status_code=400, detail="provider_id를 가져올 수 없습니다.")

    # 4. 사용자 존재 여부 확인
    user = get_user_by_provider(db, 'APPLE', provider_id)

    if not user:
        # 새로운 유저이므로 생성
        user = create_user(
            db,
            email=data.userEmail if data.userEmail else None,
            provider_type='APPLE',
            provider_id=provider_id,
            provider_profile_image=None,
            provider_user_name=data.userName if data.userName else None,
            apple_real_user_status=decoded_token.get('real_user_status'),
            status='Need_Register'  # 상태를 Need_Register로 설정
        )

        # 서버에서 JWT 토큰 생성
        access_token = create_access_token(data={"uuid": user.uuid})
        refresh_token = create_refresh_token(data={"uuid": user.uuid})

        # 토큰 저장
        create_or_update_token(
            db,
            user_uuid=user.uuid,
            refresh_token=refresh_token,
            provider_type='APPLE',
            provider_refresh_token=token_data.get('refresh_token')
        )

        db.close()
        return {
            "message": "Need_Register",
            "access_token": access_token,
            "refresh_token": refresh_token
        }, 201

    elif user.status == 'Need_Register':
        # 이미 회원가입은 했으나 추가 정보가 필요한 상태

        # 서버에서 JWT 토큰 생성
        access_token = create_access_token(data={"uuid": user.uuid})
        refresh_token = create_refresh_token(data={"uuid": user.uuid})

        # 토큰 업데이트
        create_or_update_token(
            db,
            user_uuid=user.uuid,
            refresh_token=refresh_token,
            provider_type='APPLE',
            provider_refresh_token=token_data.get('refresh_token')
        )

        db.close()
        return {
            "message": "Need_Register",
            "access_token": access_token,
            "refresh_token": refresh_token
        }, 202

    elif user.status == 'Active':
        # 기존 유저이며 Active 상태

        # 서버에서 JWT 토큰 생성
        access_token = create_access_token(data={"uuid": user.uuid})
        refresh_token = create_refresh_token(data={"uuid": user.uuid})

        # 토큰 업데이트
        create_or_update_token(
            db,
            user_uuid=user.uuid,
            refresh_token=refresh_token,
            provider_type='APPLE',
            provider_refresh_token=token_data.get('refresh_token')
        )

        db.close()
        return {
            "message": "로그인 성공",
            "access_token": access_token,
            "refresh_token": refresh_token
        }, 200

    else:
        db.close()
        raise HTTPException(status_code=400, detail="유효하지 않은 사용자 상태입니다.")

# 클라이언트 시크릿 생성 함수 (생략)
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
        client_secret = jwt.encode(payload, APPLE_PRIVATE_KEY, algorithm="ES256", headers=headers)
        return client_secret
    except Exception:
        raise HTTPException(status_code=500, detail="클라이언트 시크릿 생성 중 오류 발생")

# identityToken 디코딩 및 검증 함수 (생략)
def verify_and_decode_identity_token(identity_token: str) -> dict:
    try:
        decoded_token = jwt.decode(identity_token, options={"verify_signature": False})
        return decoded_token
    except jwt.InvalidTokenError:
        return None


# 회원 탈퇴 로직
@router.delete('/login/apple/unregister', tags=["Login"])
async def apple_unregister(user_refresh_token: str):
    # 저장된 refresh_token을 이용해 애플 회원 탈퇴 요청
    try:
        response = requests.post(
            'https://appleid.apple.com/auth/revoke',
            data={
                'client_id': APPLE_CLIENT_ID,
                'client_secret': create_client_secret(),
                'token': user_refresh_token,  # 저장된 refresh_token 사용
                'token_type_hint': 'refresh_token'
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="애플 회원 탈퇴 요청 중 오류 발생")

    # 탈퇴 요청 실패 시 처리
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="애플 회원 탈퇴 실패")

    return {"message": "애플 회원 탈퇴 성공"}