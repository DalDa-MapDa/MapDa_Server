from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
import requests
import jwt  # PyJWT 라이브러리
import datetime
from dotenv import load_dotenv
import os

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
    # 1. 애플로부터 받은 identityToken 검증
    try:
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
        raise HTTPException(status_code=500, detail="애플 인증 요청 중 오류 발생")

    # 애플 인증 실패 시 오류 처리
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="애플 인증 실패")

    token_data = response.json()

    # 2. ID 토큰 디코딩 및 검증
    decoded_token = verify_and_decode_identity_token(token_data.get('id_token'))
    if decoded_token is None:
        raise HTTPException(status_code=400, detail="identityToken 검증 실패")

    # 3. id_token, refresh_token, userName, userEmail 반환
    return {
        "message": "애플 로그인 성공",
        "decoded_id_token": decoded_token,
        "refresh_token": token_data.get('refresh_token'),
        "userName": data.userName,  # userName 반환
        "userEmail": data.userEmail  # userEmail 반환
    }

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
