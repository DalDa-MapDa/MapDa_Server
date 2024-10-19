import os
import requests
import jwt  # PyJWT 라이브러리
import datetime
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv

router = APIRouter()

# .env 파일 로드
load_dotenv()

# 애플 관련 환경 변수 로드
APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID")  # 애플 클라이언트 ID
APPLE_KEY_ID = os.getenv("APPLE_KEY_ID")  # 애플 키 ID
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID")  # 애플 팀 ID

# AuthKey 파일에서 비밀키를 읽어오기 (경로 수정)
auth_key_path = "secrets/AuthKey_76ZFAC89DR.p8"
# auth_key_path = "/home/ec2-user/secrets/AuthKey_76ZFAC89DR.p8"  # 서버상의 실제 경로로 수정
try:
    with open(auth_key_path, "r") as key_file:
        APPLE_PRIVATE_KEY = key_file.read()
except FileNotFoundError:
    raise HTTPException(status_code=500, detail=f"비밀키 파일을 찾을 수 없습니다: {auth_key_path}")

@router.post('/login/apple')
async def apple_login(identityToken: str, authorizationCode: str):
    # 1. 애플로부터 받은 identityToken 검증
    response = requests.post(
        'https://appleid.apple.com/auth/token',
        data={
            'client_id': APPLE_CLIENT_ID,
            'client_secret': create_client_secret(),
            'code': authorizationCode,
            'grant_type': 'authorization_code',
            'redirect_uri': 'https://api.mapda.site/login/apple'  # 서버 주소에 맞춰서 수정
        }
    )

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="애플 인증 실패")

    token_data = response.json()

    # 2. identityToken 검증
    if not verify_identity_token(identityToken):
        raise HTTPException(status_code=400, detail="identityToken 검증 실패")

    # 3. 사용자 정보 반환
    return {"message": "애플 로그인 성공", "token_data": token_data}

# 클라이언트 시크릿 생성 함수
def create_client_secret():
    # 애플 클라이언트 시크릿을 생성 (JWT 사용)

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

    # 비밀키를 사용해 서명
    client_secret = jwt.encode(payload, APPLE_PRIVATE_KEY, algorithm="ES256", headers=headers)
    return client_secret

# identityToken 검증 함수
def verify_identity_token(identity_token: str) -> bool:
    # identityToken의 유효성을 검증하는 로직을 구현

    try:
        decoded_token = jwt.decode(identity_token, options={"verify_signature": False})
        # 애플에서 제공하는 공개키로 서명 검증 로직 추가 가능
        return True
    except jwt.InvalidTokenError:
        return False
