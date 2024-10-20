import os
from fastapi import APIRouter, HTTPException, Request
import requests
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
    print(f"Received Google login request from {request.client.host}")
    print(f"Request data: {data}")

    try:
        # ID 토큰 검증
        id_info = id_token.verify_oauth2_token(
            data.idToken, google_requests.Request(), None
        )

        # 클라이언트 ID 확인
        if id_info['aud'] not in GOOGLE_CLIENT_IDS:
            raise ValueError(f"Token has wrong audience {id_info['aud']}")

        # 사용자 정보 출력
        print(f"Google user info: {id_info}")
        return {"message": "구글 로그인 성공", "user_info": id_info}
    except ValueError as e:
        print(f"Google token verification failed: {str(e)}")
        raise HTTPException(status_code=400, detail="구글 인증 실패")

