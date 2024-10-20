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
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

class GoogleLoginData(BaseModel):
    idToken: str

@router.post("/login/google")
async def google_login(data: GoogleLoginData, request: Request):
    print(f"Received Google login request from {request.client.host}")
    print(f"Request data: {data}")

    try:
        # 1. Google ID Token 검증
        id_info = id_token.verify_oauth2_token(data.idToken, google_requests.Request(), GOOGLE_CLIENT_ID)

        if id_info['aud'] != GOOGLE_CLIENT_ID:
            raise HTTPException(status_code=400, detail="잘못된 클라이언트 ID입니다.")

        # 2. 사용자 정보 반환
        user_info = {
            'email': id_info.get('email'),
            'name': id_info.get('name'),
            'picture': id_info.get('picture')
        }

        print(f"Google user info response: {user_info}")
        return {"message": "구글 로그인 성공", "user_info": user_info}

    except ValueError as e:
        print(f"Google token verification failed: {e}")
        raise HTTPException(status_code=400, detail="ID 토큰 검증 실패")
