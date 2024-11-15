import os
import select
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional
from sqlalchemy.orm import Session
from models import SessionLocal, Token, User
from api.login.login_token_manage import (
    get_user_by_provider, create_user, update_user, create_or_update_token,
    create_access_token, create_refresh_token
)
import requests

router = APIRouter()

# .env 파일 로드
load_dotenv()

KAKAO_ADMIN_KEY = os.getenv("KAKAO_ADMIN_KEY")


class KakaoUserInfo(BaseModel):
    id: str
    nickname: Optional[str] = None
    email: Optional[str] = None
    profileImage: Optional[str] = None
    isProfileImageDefault: Optional[bool] = None
    thumbnailImage: Optional[str] = None
    connectedAt: Optional[str] = None


@router.post('/login/kakao', tags=["Login"])
def kakao_login(user_info: KakaoUserInfo, response: Response):
    db: Session = SessionLocal()
    try:
        # Determine profile image
        provider_profile_image = None if user_info.isProfileImageDefault else user_info.profileImage

        # Check for existing user
        user = get_user_by_provider(db, 'KAKAO', user_info.id)

        if not user:
            # Create new user if not exists
            user = create_user(
                db,
                email=user_info.email,
                provider_type='KAKAO',
                provider_id=user_info.id,
                provider_profile_image=provider_profile_image,
                provider_user_name=user_info.nickname,
                status='Need_Register'
            )
            message = "Need_Register"
            response.status_code = 201
        else:
            # Update existing user fields if needed
            updated_fields = {
                "email": user_info.email,
                "provider_profile_image": provider_profile_image,
                "provider_user_name": user_info.nickname
            }
            updated_fields = {k: v for k, v in updated_fields.items() if v is not None and getattr(user, k, None) != v}
            if updated_fields:
                user = update_user(db, user, **updated_fields)

            # Handle user status
            if user.status == 'Need_Register':
                message = "Need_Register"
                response.status_code = 202
            elif user.status == 'Active':
                message = "로그인 성공"
                response.status_code = 200
            else:
                raise HTTPException(status_code=400, detail="유효하지 않은 사용자 상태입니다.")

        # Generate tokens
        access_token = create_access_token(uuid=user.uuid)
        refresh_token = create_refresh_token()

        # Update tokens in database
        create_or_update_token(db, user_uuid=user.uuid, provider_type='KAKAO', refresh_token=refresh_token)

        return {
            "message": message,
            "access_token": access_token,
            "refresh_token": refresh_token
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing user info: {str(e)}")
    finally:
        db.close()


@router.delete('/unregister/kakao', tags=["Login"])
def kakao_unregister_function(user_uuid: str):
    if not KAKAO_ADMIN_KEY:
        raise HTTPException(status_code=500, detail="KAKAO_ADMIN_KEY가 설정되지 않았습니다.")

    db: Session = SessionLocal()
    try:
        # Get user by UUID
        user = db.execute(select(User).filter(User.uuid == user_uuid)).scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="유효하지 않은 사용자입니다.")

        # Unlink user from Kakao
        response = requests.post(
            'https://kapi.kakao.com/v1/user/unlink',
            headers={
                "Authorization": f"KakaoAK {KAKAO_ADMIN_KEY}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={"target_id_type": "user_id", "target_id": user.provider_id}
        )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="카카오 사용자 연결 해제 실패")

        # Update user and token status to 'Deleted'
        user.status = 'Deleted'
        db.commit()

        token_entry = db.query(Token).filter(Token.uuid == user_uuid).first()
        if token_entry:
            token_entry.status = 'Deleted'
            db.commit()

        return {"message": "카카오 사용자 연결이 성공적으로 해제되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"카카오 연결 해제 중 오류 발생: {str(e)}")
    finally:
        db.close()
