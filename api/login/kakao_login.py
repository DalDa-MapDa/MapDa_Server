import os
from pydantic import BaseModel
import requests
from fastapi import APIRouter, HTTPException, Response, Request
from dotenv import load_dotenv
from typing import Optional
from sqlalchemy.orm import Session
from models import SessionLocal, Token, User
from api.login.login_token_manage import (
    get_user_by_provider, create_user, update_user, create_or_update_token,
    create_access_token, create_refresh_token
)
from sqlalchemy.future import select

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
def kakao_login(user_info: KakaoUserInfo, response: Response):
    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        print("kakao_Step 1: Received user_info", user_info)  # 요청 데이터 출력

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
        print("kakao_Step 2: Processed user data", user_data)  # 가공된 사용자 정보 출력

        # provider_profile_image 설정
        provider_profile_image = None if user_data['isProfileImageDefault'] else user_data['profileImage']
        print("kakao_Step 3: Determined provider_profile_image", provider_profile_image)  # 프로필 이미지 정보 출력

        # 사용자 존재 여부 확인
        user = db.query(User).filter(
            User.provider_type == 'KAKAO',
            User.provider_id == user_data['id'],
            User.status != 'Deleted'  # Deleted 상태는 제외
        ).first()
        print("kakao_Step 4: User existence check:", user)  # 사용자 존재 여부 출력

        if not user:
            # Deleted 상태의 동일한 provider_id가 있을 수도 있으므로 중복 체크
            existing_deleted_user = db.query(User).filter(
                User.provider_type == 'KAKAO',
                User.provider_id == user_data['id'],
                User.status == 'Deleted'
            ).first()

            if existing_deleted_user:
                print("kakao_Step 5: Found deleted user, creating new account")
            else:
                print("kakao_Step 5: No user found, creating new account")

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
            print("kakao_Step 6: New user created", user)  # 생성된 사용자 정보 출력
            message = "Need_Register"
            response.status_code = 201  # 상태 코드를 201로 설정
        else:
            # 이메일, 프로필 이미지, 닉네임 업데이트
            updated_fields = {}
            if user_data['email'] is not None:
                updated_fields["email"] = user_data['email']
            if provider_profile_image is not None:
                updated_fields["provider_profile_image"] = provider_profile_image
            if user_data['nickname'] is not None:
                updated_fields["provider_user_name"] = user_data["nickname"]

            if updated_fields:
                user = update_user(db, user, **updated_fields)
                print("kakao_Step 6: Updated user information", updated_fields)  # 업데이트된 정보 출력

            if user.status == 'Need_Register':
                print("kakao_Step 7: User in Need_Register status")  # Need_Register 상태 출력
                message = "Need_Register"
                response.status_code = 202  # 상태 코드를 202로 설정
            elif user.status == 'Active':
                print("kakao_Step 8: User is Active")  # Active 상태 출력
                message = "로그인 성공"
                response.status_code = 200  # 상태 코드를 200으로 설정
            else:
                print("kakao_Step 9: Invalid user status", user.status)  # 유효하지 않은 상태 출력
                db.close()
                raise HTTPException(status_code=400, detail="유효하지 않은 사용자 상태입니다.")

        # 서버에서 JWT 토큰 생성
        access_token = create_access_token(uuid=user.uuid)
        refresh_token = create_refresh_token()
        print("kakao_Step 10: Tokens created. Access:", access_token, "Refresh:", refresh_token)  # 생성된 토큰 출력

        # 토큰 업데이트
        create_or_update_token(
            db,
            user_uuid=user.uuid,
            provider_type='KAKAO',
            refresh_token=refresh_token
        )
        print("kakao_Step 11: Token updated in database")  # 토큰 업데이트 완료 메시지

        db.close()
        return {
            "message": message,
            "access_token": access_token,
            "refresh_token": refresh_token
        }

    except Exception as e:
        print("kakao_Unexpected error occurred:", e)  # 예기치 않은 오류 출력
        db.close()
        raise HTTPException(status_code=500, detail=f"Error processing user info: {str(e)}")



# 카카오 연결 해제 (unlink) 함수를 일반 함수로 변경
def kakao_unregister_function(user_uuid: str):
    if not KAKAO_ADMIN_KEY:
        raise HTTPException(status_code=500, detail="KAKAO_ADMIN_KEY가 설정되지 않았습니다.")

    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        # 사용자의 provider_id 조회
        user_result = db.execute(select(User).filter(User.uuid == user_uuid))
        user = user_result.scalars().first()
        if not user:
            db.close()
            raise HTTPException(status_code=404, detail="유효하지 않은 사용자입니다.")

        provider_id = user.provider_id

        headers = {
            "Authorization": f"KakaoAK {KAKAO_ADMIN_KEY}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        unregister_data = {
            "target_id_type": "user_id",
            "target_id": provider_id
        }

        # POST 요청으로 연결 해제
        unregister_response = requests.post(
            'https://kapi.kakao.com/v1/user/unlink',
            headers=headers,
            data=unregister_data
        )

        if unregister_response.status_code != 200:
            db.close()
            raise HTTPException(status_code=unregister_response.status_code, detail="카카오 사용자 연결 해제 실패")

        # 사용자의 상태를 Deleted로 업데이트
        user.status = 'Deleted'
        db.commit()

        # 토큰의 상태를 Deleted로 업데이트
        token_entry = db.query(Token).filter(Token.uuid == user_uuid).first()
        if token_entry:
            token_entry.status = 'Deleted'
            db.commit()

        db.close()
        return {"message": "카카오 사용자 연결이 성공적으로 해제되었습니다."}

    except HTTPException as he:
        db.close()
        raise he
    except Exception as e:
        db.rollback()
        db.close()
        raise HTTPException(status_code=500, detail=f"카카오 연결 해제 중 오류 발생: {str(e)}")
