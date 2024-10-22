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
    nickname: Optional[str] = None  # Null 값 허용
    email: Optional[str] = None
    profileImage: Optional[str] = None
    thumbnailImage: Optional[str] = None
    connectedAt: Optional[str] = None

# 카카오 로그인 정보 받기 엔드포인트
@router.post('/login/kakao', tags=["Login"])
async def kakao_login(user_info: KakaoUserInfo):
    try:
        # id는 필수로 받음, 나머지는 Optional
        user_data = {
            "id": user_info.id,
            "nickname": user_info.nickname if user_info.nickname else "No Nickname",
            "email": user_info.email if user_info.email else "No Email",
            "profileImage": user_info.profileImage if user_info.profileImage else "No Profile Image",
            "thumbnailImage": user_info.thumbnailImage if user_info.thumbnailImage else "No Thumbnail Image",
            "connectedAt": user_info.connectedAt if user_info.connectedAt else "Not Connected Yet",
        }

        # 사용자 정보 출력 (필요시 다른 처리 가능)
        print(f"Processed Kakao user info: {user_data}")

        return {
            "message": "Kakao user info received successfully",
            "user_info": user_data
        }
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
