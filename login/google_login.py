import os
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import requests

router = APIRouter()

# .env 파일 로드
load_dotenv()

# 구글 관련 환경 변수 로드
GOOGLE_CLIENT_IDS = os.getenv("GOOGLE_CLIENT_IDS", "").split(",")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

class GoogleLoginData(BaseModel):
    idToken: str
    accessToken: str  # access token 추가

class GoogleUnregisterData(BaseModel):
    userId: str

class GoogleRefreshTokenData(BaseModel):
    refreshToken: str

@router.post("/login/google")
async def google_login(data: GoogleLoginData, request: Request):
    try:
        # ID 토큰 검증
        id_info = id_token.verify_oauth2_token(
            data.idToken, google_requests.Request(), None
        )

        # 클라이언트 ID 확인 (GOOGLE_CLIENT_IDS 중 하나와 일치하는지 확인)
        if id_info['aud'] not in GOOGLE_CLIENT_IDS:
            raise ValueError("Invalid client ID")

        # access token이 있다면 처리 (필요 시)
        if data.accessToken:
            print(f"Access Token: {data.accessToken}")

        # 사용자 정보 반환
        return {"message": "구글 로그인 성공", "user_info": id_info}

    except ValueError:
        raise HTTPException(status_code=400, detail="구글 인증 실패")

# 구글 계정 연결 해제 (revoke) 메소드
@router.post("/login/google/unregister")
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