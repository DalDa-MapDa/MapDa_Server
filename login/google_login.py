import os
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

router = APIRouter()

# .env 파일 로드
load_dotenv()

# 구글 관련 환경 변수 로드
GOOGLE_CLIENT_IDS = os.getenv("GOOGLE_CLIENT_IDS", "").split(",")

class GoogleLoginData(BaseModel):
    idToken: str

@router.post("/login/google")
async def google_login(data: GoogleLoginData, request: Request):
    # 최적화된 Google 로그인 처리
    try:
        # ID 토큰 검증
        id_info = id_token.verify_oauth2_token(
            data.idToken, google_requests.Request(), None
        )

        # 클라이언트 ID 확인
        if id_info['aud'] not in GOOGLE_CLIENT_IDS:
            raise ValueError("Invalid client ID")

        # 사용자 정보 반환
        return {"message": "구글 로그인 성공", "user_info": id_info}

    except ValueError:
        raise HTTPException(status_code=400, detail="구글 인증 실패")
