import os
from pydantic import BaseModel
import requests
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
from typing import Optional
from sqlalchemy.orm import Session
from models import SessionLocal
from login.login_token_manage import (
    get_user_by_provider, create_user, update_user, create_or_update_token,
    create_access_token, create_refresh_token
)

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
    isProfileImageDefault: Optional[bool] = None  # 추가된 필드
    thumbnailImage: Optional[str] = None
    connectedAt: Optional[str] = None

# 카카오 로그인 정보 받기 엔드포인트
@router.post('/login/kakao', tags=["Login"])
async def kakao_login(user_info: KakaoUserInfo):
    print("=== Kakao login 시작 ===")
    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        print("사용자 정보 추출 중...")
        # 사용자 정보를 받아서 저장하거나 처리
        user_data = {
            "id": user_info.id,
            "nickname": user_info.nickname if user_info.nickname else None,
            "email": user_info.email if user_info.email else None,
            "profileImage": user_info.profileImage if user_info.profileImage else None,
            "isProfileImageDefault": user_info.isProfileImageDefault if user_info.isProfileImageDefault is not None else True,
            "thumbnailImage": user_info.thumbnailImage if user_info.thumbnailImage else None,
            "connectedAt": user_info.connectedAt if user_info.connectedAt else None,
        }
        print(f"user_data: {user_data}")

        # provider_profile_image 설정
        if user_data['isProfileImageDefault']:
            provider_profile_image = None
        else:
            provider_profile_image = user_data['profileImage']
        print(f"provider_profile_image: {provider_profile_image}")

        # 사용자 존재 여부 확인
        print("사용자 존재 여부 확인 중...")
        user = get_user_by_provider(db, 'KAKAO', user_data['id'])
        print(f"조회된 사용자: {user}")

        if not user:
            print("사용자가 없으므로 새로 생성합니다.")
            # 새로운 유저 생성
            user = create_user(
                db,
                email=user_data['email'],
                provider_type='KAKAO',
                provider_id=user_data['id'],
                provider_profile_image=provider_profile_image,
                provider_user_name=user_data['nickname'],
                status='Need_Register'  # 상태를 Need_Register로 설정
            )
            print(f"새로운 사용자 생성 완료: {user}")
            message = "Need_Register"
            status_code = 201
        else:
            print("사용자가 존재합니다. 정보 업데이트를 진행합니다.")
            # 이메일, 프로필 이미지, 닉네임 업데이트
            updated_fields = {}
            if user_data['email'] is not None:
                updated_fields["email"] = user_data['email']
            if provider_profile_image is not None:
                updated_fields["provider_profile_image"] = provider_profile_image
            if user_data['nickname'] is not None:
                updated_fields["provider_user_name"] = user_data['nickname']

            print(f"업데이트할 필드: {updated_fields}")
            if updated_fields:
                user = update_user(db, user, **updated_fields)
                print(f"사용자 정보 업데이트 완료: {user}")

            if user.status == 'Need_Register':
                message = "Need_Register"
                status_code = 202
            elif user.status == 'Active':
                message = "로그인 성공"
                status_code = 200
            else:
                print(f"유효하지 않은 사용자 상태: {user.status}")
                db.close()
                raise HTTPException(status_code=400, detail="유효하지 않은 사용자 상태입니다.")

        # 서버에서 JWT 토큰 생성
        print("JWT 토큰 생성 중...")
        access_token = create_access_token(data={"uuid": user.uuid})
        refresh_token = create_refresh_token(data={"uuid": user.uuid})
        print(f"액세스 토큰: {access_token}")
        print(f"리프레시 토큰: {refresh_token}")

        # 토큰 업데이트
        print("토큰 정보를 데이터베이스에 저장 중...")
        create_or_update_token(
            db,
            user_uuid=user.uuid,
            refresh_token=refresh_token
        )
        print("토큰 저장 완료")

        db.close()
        print(f"응답 반환: 상태 코드 {status_code}, 메시지 '{message}'")
        print("=== Kakao login 종료 ===")
        return {
            "message": message,
            "access_token": access_token,
            "refresh_token": refresh_token
        }, status_code

    except Exception as e:
        print(f"예외 발생: {e}")
        db.close()
        raise HTTPException(status_code=500, detail=f"Error processing user info: {str(e)}")

# 카카오 연결 해제 (unlink) 메소드
@router.delete('/login/kakao/unregister', tags=["Login"])
async def kakao_unregister(user_id: str):
    if not KAKAO_ADMIN_KEY:
        raise HTTPException(status_code=500, detail="KAKAO_ADMIN_KEY가 설정되지 않았습니다.")

    headers = {
        "Authorization": f"KakaoAK {KAKAO_ADMIN_KEY}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    unregister_data = {
        "target_id_type": "user_id",
        "target_id": user_id
    }

    # POST 요청으로 연결 해제
    unregister_response = requests.post('https://kapi.kakao.com/v1/user/unlink', headers=headers, data=unregister_data)
    
    if unregister_response.status_code != 200:
        raise HTTPException(status_code=unregister_response.status_code, detail="카카오 사용자 연결 해제 실패")

    return {"message": "카카오 사용자 연결이 성공적으로 해제되었습니다."}