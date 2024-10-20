import os
from fastapi import APIRouter, HTTPException, Depends
import requests
from pydantic import BaseModel
from dotenv import load_dotenv

router = APIRouter()

# .env 파일 로드
load_dotenv()

# 구글 관련 환경 변수 로드
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

class GoogleLoginData(BaseModel):
    code: str

@router.post("/login/google")
async def google_login(data: GoogleLoginData):
    # 1. Google OAuth 2.0 서버로부터 Access Token 요청
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        'code': data.code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    
    token_response = requests.post(token_url, data=token_data)
    
    if token_response.status_code != 200:
        raise HTTPException(status_code=token_response.status_code, detail="구글 인증 실패")

    token_info = token_response.json()
    
    # 2. Access Token을 사용하여 사용자 정보 요청
    user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    user_info_response = requests.get(user_info_url, headers={"Authorization": f"Bearer {token_info['access_token']}"})
    
    if user_info_response.status_code != 200:
        raise HTTPException(status_code=user_info_response.status_code, detail="사용자 정보 요청 실패")

    user_info = user_info_response.json()
    
    # 3. 사용자 정보 반환
    return {"message": "구글 로그인 성공", "user_info": user_info}
