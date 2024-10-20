import os
import logging
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException, Request
import requests
import jwt  # PyJWT 라이브러리
import datetime
from dotenv import load_dotenv

router = APIRouter()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env 파일 로드
load_dotenv()

# 애플 관련 환경 변수 로드
APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID")  # 애플 클라이언트 ID
APPLE_KEY_ID = os.getenv("APPLE_KEY_ID")  # 애플 키 ID
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID")  # 애플 팀 ID

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

@router.post('/login/apple')
async def apple_login(data: AppleLoginData):
    # 클라이언트에서 받은 데이터 로그로 출력
    logger.info(f"Received request with identityToken: {data.identityToken[:10]}... and authorizationCode: {data.authorizationCode[:10]}...")

    # 1. 애플로부터 받은 identityToken 검증
    try:
        payload = {
            'client_id': APPLE_CLIENT_ID,
            'client_secret': create_client_secret(),
            'code': data.authorizationCode,
            'grant_type': 'authorization_code',
            'redirect_uri': 'https://api.mapda.site/login/apple'
        }
        logger.info(f"Sending request to Apple: {payload}")
        
        response = requests.post(
            'https://appleid.apple.com/auth/token',
            data=payload
        )
    except Exception as e:
        logger.error(f"Error during request to Apple: {e}")
        raise HTTPException(status_code=500, detail="애플 인증 요청 중 오류 발생")

    # 애플 인증 실패 시 오류 처리
    if response.status_code != 200:
        logger.error(f"Apple authentication failed with status code: {response.status_code}, response: {response.text}")
        raise HTTPException(status_code=response.status_code, detail="애플 인증 실패")

    token_data = response.json()

    # 애플로부터 받은 응답 로그 출력
    logger.info(f"Apple response token data: {token_data}")

    # 2. identityToken 검증
    if not verify_identity_token(data.identityToken):
        logger.error("identityToken 검증 실패")
        raise HTTPException(status_code=400, detail="identityToken 검증 실패")

    # 3. 사용자 정보 반환
    logger.info("애플 로그인 성공")
    return {"message": "애플 로그인 성공", "token_data": token_data}

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

    # 비밀키를 사용해 서명
    try:
        client_secret = jwt.encode(payload, APPLE_PRIVATE_KEY, algorithm="ES256", headers=headers)
        logger.info(f"Client secret created successfully: {client_secret[:10]}...")
        return client_secret
    except Exception as e:
        logger.error(f"Error during client secret creation: {e}")
        raise HTTPException(status_code=500, detail="클라이언트 시크릿 생성 중 오류 발생")

# identityToken 검증 함수
def verify_identity_token(identity_token: str) -> bool:
    try:
        jwt.decode(identity_token, options={"verify_signature": False})
        logger.info("identityToken 검증 성공")
        return True
    except jwt.InvalidTokenError:
        logger.error("identityToken 검증 실패")
        return False
