import os
from pydantic import BaseModel
import requests
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
from typing import Optional
from sqlalchemy.orm import Session
from models import SessionLocal
from login.login_token_manage import (
    get_user_by_provider, create_user, create_or_update_token,
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
    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        # 사용자 정보를 받아서 저장하거나 처리
        user_data = {
            "id": user_info.id,
            "nickname": user_info.nickname if user_info.nickname else "No Nickname",
            "email": user_info.email if user_info.email else None,
            "profileImage": user_info.profileImage if user_info.profileImage else None,
            "isProfileImageDefault": user_info.isProfileImageDefault if user_info.isProfileImageDefault is not None else True,
            "thumbnailImage": user_info.thumbnailImage if user_info.thumbnailImage else None,
            "connectedAt": user_info.connectedAt if user_info.connectedAt else None,
        }

        # 카카오 사용자 검증 (생략 가능하거나 필요 시 구현)
        # verification_response = verify_kakao_user(user_info.id)
        # if verification_response.status_code != 200:
        #     raise HTTPException(status_code=400, detail="Kakao user verification failed")

        # 사용자 존재 여부 확인
        user = get_user_by_provider(db, 'KAKAO', user_data['id'])

        # provider_profile_image 설정
        if user_data['isProfileImageDefault']:
            provider_profile_image = None
        else:
            provider_profile_image = user_data['profileImage']

        if not user:
            # 새로운 유저 생성
            user = create_user(
                db,
                email=user_data['email'] if user_data['email'] else None,
                provider_type='KAKAO',
                provider_id=user_data['id'],
                provider_profile_image=provider_profile_image if provider_profile_image else None,
                provider_user_name=user_data['nickname'] if user_data['nickname'] else None,
                status='Need_Register'  # 상태를 Need_Register로 설정
            )

            # 서버에서 JWT 토큰 생성
            access_token = create_access_token(data={"uuid": user.uuid})
            refresh_token = create_refresh_token(data={"uuid": user.uuid})

            # 토큰 저장
            create_or_update_token(
                db,
                user_uuid=user.uuid,
                refresh_token=refresh_token,
                provider_type='KAKAO'
            )

            db.close()
            return {
                "message": "Need_Register",
                "access_token": access_token,
                "refresh_token": refresh_token
            }, 201

        elif user.status == 'Need_Register':
            # 이미 회원가입은 했으나 추가 정보가 필요한 상태

            # 서버에서 JWT 토큰 생성
            access_token = create_access_token(data={"uuid": user.uuid})
            refresh_token = create_refresh_token(data={"uuid": user.uuid})

            # 토큰 업데이트
            create_or_update_token(
                db,
                user_uuid=user.uuid,
                refresh_token=refresh_token,
                provider_type='KAKAO'
            )

            db.close()
            return {
                "message": "Need_Register",
                "access_token": access_token,
                "refresh_token": refresh_token
            }, 202

        elif user.status == 'Active':
            # 기존 유저이며 Active 상태

            # 서버에서 JWT 토큰 생성
            access_token = create_access_token(data={"uuid": user.uuid})
            refresh_token = create_refresh_token(data={"uuid": user.uuid})

            # 토큰 업데이트
            create_or_update_token(
                db,
                user_uuid=user.uuid,
                refresh_token=refresh_token,
                provider_type='KAKAO'
            )

            db.close()
            return {
                "message": "로그인 성공",
                "access_token": access_token,
                "refresh_token": refresh_token
            }, 200

        else:
            db.close()
            raise HTTPException(status_code=400, detail="유효하지 않은 사용자 상태입니다.")

    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Error processing user info: {str(e)}")
