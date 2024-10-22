import os
from pydantic import BaseModel
import requests
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
from typing import Optional

router = APIRouter()

# .env 파일 로드
load_dotenv()

# 환경 변수 설정
KAKAO_ADMIN_KEY = os.getenv("KAKAO_ADMIN_KEY")  # Admin Key 추가

# 사용자 정보 모델 정의
class KakaoUserInfo(BaseModel):
    id: str
    nickname: Optional[str]
    email: Optional[str]

# 카카오 로그인 정보 받기 엔드포인트
@router.post('/login/kakao', tags=["Login"])
async def kakao_login(user_info: KakaoUserInfo):
    try:
        # 여기서 전달받은 사용자 정보를 처리합니다.
        print(f"Received Kakao user info: {user_info}")
        # 예시: 데이터베이스에 저장하거나 세션을 생성하는 등의 처리
        return {"message": "Kakao user info received successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing user info: {str(e)}")

# 카카오 연결 해제 (unlink) 메소드
@router.post('/login/kakao/unregister', tags=["Login"])
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
    unregister_response = requests.post('https://kapi.kakao.com/v1/user/unlink', headers=headers, data=unregister_data)
    
    if unregister_response.status_code != 200:
        raise HTTPException(status_code=unregister_response.status_code, detail="카카오 사용자 연결 해제 실패")

    return {"message": "카카오 사용자 연결이 성공적으로 해제되었습니다."}
