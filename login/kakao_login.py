import os
import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from typing import Optional, List

router = APIRouter()

# .env 파일 로드
load_dotenv()

# 환경 변수 설정
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_ADMIN_KEY = os.getenv("KAKAO_ADMIN_KEY")  # Admin Key 추가
KAKAO_REDIRECT_URI = "https://api.mapda.site/login/kakao/auth"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"
KAKAO_UNREGISTER_URL = "https://kapi.kakao.com/v1/user/unlink"  # Unlink URL 추가

# 카카오 로그인 리다이렉트 엔드포인트
@router.get('/login/kakao')
def kakao_login():
    url = f"https://kauth.kakao.com/oauth/authorize?client_id={KAKAO_REST_API_KEY}&response_type=code&redirect_uri={KAKAO_REDIRECT_URI}"
    return RedirectResponse(url)

# 사용자 정보를 가져오는 함수
def kakao_user_info(access_token: str):
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    user_info_response = requests.get(KAKAO_USER_INFO_URL, headers=headers)
    
    if user_info_response.status_code != 200:
        raise HTTPException(status_code=user_info_response.status_code, detail="카카오 사용자 정보 가져오기 실패")
    
    return user_info_response.json()

# 카카오 인증 후 액세스 토큰을 발급받고, 사용자 정보를 가져오는 엔드포인트
@router.get('/login/kakao/auth')
async def kakao_auth(code: Optional[str] = None):
    if code is None:
        raise HTTPException(status_code=400, detail="카카오 인증 코드가 제공되지 않았습니다.")
    
    # 토큰 요청을 위한 데이터
    token_data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": code
    }

    # POST 요청으로 토큰 발급
    token_response = requests.post(KAKAO_TOKEN_URL, data=token_data)
    
    if token_response.status_code != 200:
        raise HTTPException(status_code=token_response.status_code, detail="카카오 토큰 발급 실패")
    
    # JSON 형식의 응답 파싱
    token_json = token_response.json()
    access_token = token_json.get("access_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="액세스 토큰이 없습니다.")

    # 사용자 정보 가져오기
    user_info = kakao_user_info(access_token)

    return {
        "token_data": token_json,
        "user_info": user_info
    }

# 카카오 연결 해제 (unlink) 메소드
@router.post('/login/kakao/unregister')
async def kakao_unregister(target_id: str):
    if not KAKAO_ADMIN_KEY:
        raise HTTPException(status_code=500, detail="KAKAO_ADMIN_KEY가 설정되지 않았습니다.")

    # Admin Key 기반으로 카카오 사용자 연결 해제 API 호출
    headers = {
        "Authorization": f"KakaoAK {KAKAO_ADMIN_KEY}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    # 연결 해제 요청 데이터
    unregister_data = {
        "target_id_type": "user_id",
        "target_id": target_id
    }

    # POST 요청으로 연결 해제
    unregister_response = requests.post(KAKAO_UNREGISTER_URL, headers=headers, data=unregister_data)
    
    if unregister_response.status_code != 200:
        raise HTTPException(status_code=unregister_response.status_code, detail="카카오 사용자 연결 해제 실패")

    return {"message": "카카오 사용자 연결이 성공적으로 해제되었습니다."}
