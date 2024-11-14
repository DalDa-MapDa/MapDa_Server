import datetime
import os
import jwt
from pydantic import BaseModel
import requests
from fastapi import APIRouter, HTTPException, Response, Request
from dotenv import load_dotenv
from typing import Optional
from sqlalchemy.orm import Session
from models import SessionLocal, User, Token
from api.login.login_token_manage import (
    get_user_by_provider, create_user, create_or_update_token,
    create_access_token, create_refresh_token
)
from sqlalchemy.future import select

router = APIRouter()

# .env 파일 로드
load_dotenv()

# 애플 관련 환경 변수 로드
APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID")
APPLE_KEY_ID = os.getenv("APPLE_KEY_ID")
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID")

# AuthKey 파일에서 비밀키를 읽어오기
auth_key_path = "/app/secrets/AuthKey_76ZFAC89DR.p8"  # 서버 경로
# auth_key_path = "secrets/AuthKey_76ZFAC89DR.p8"  # 로컬 경로

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
def apple_login(data: AppleLoginData, response: Response):
    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        # 1. 애플로부터 받은 authorizationCode로 토큰 요청
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
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail="애플 인증 요청 중 오류 발생")

    # 애플 인증 실패 시 오류 처리
    if token_response.status_code != 200:
        db.close()
        raise HTTPException(status_code=token_response.status_code, detail="애플 인증 실패")

    token_data = token_response.json()

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
        # 새로운 유저 생성
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
        message = "Need_Register"
        response.status_code = 201  # 상태 코드를 201로 설정

    elif user.status == 'Need_Register':
        message = "Need_Register"
        response.status_code = 202  # 상태 코드를 202로 설정

    elif user.status == 'Active':
        message = "로그인 성공"
        response.status_code = 200  # 상태 코드를 200으로 설정

    else:
        db.close()
        raise HTTPException(status_code=400, detail="유효하지 않은 사용자 상태입니다.")

    # 서버에서 JWT 토큰 생성
    access_token = create_access_token(uuid=user.uuid)
    refresh_token = create_refresh_token()

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
        "message": message,
        "access_token": access_token,
        "refresh_token": refresh_token
    }

# 클라이언트 시크릿 생성 함수
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

# identityToken 디코딩 및 검증 함수
def verify_and_decode_identity_token(identity_token: str) -> dict:
    try:
        decoded_token = jwt.decode(identity_token, options={"verify_signature": False})
        return decoded_token
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
