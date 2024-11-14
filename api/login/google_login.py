import os
from fastapi import APIRouter, HTTPException, Response, Request
from pydantic import BaseModel
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from sqlalchemy.orm import Session
from models import SessionLocal, Token, User
from api.login.login_token_manage import (
    get_user_by_provider, create_user, update_user, create_or_update_token,
    create_access_token, create_refresh_token
)
from sqlalchemy.future import select
import httpx

router = APIRouter()

# .env 파일 로드
load_dotenv()

# 구글 관련 환경 변수 로드
GOOGLE_CLIENT_IDS = os.getenv("GOOGLE_CLIENT_IDS", "").split(",")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

class GoogleLoginData(BaseModel):
    idToken: str
    accessToken: str  # access token 추가

@router.post("/login/google", tags=["Login"])
async def google_login(data: GoogleLoginData, response: Response):
    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        # ID 토큰 검증
        id_info = await id_token.verify_oauth2_token(
            data.idToken, google_requests.Request(), None
        )

        # 클라이언트 ID 확인
        if id_info['aud'] not in GOOGLE_CLIENT_IDS:
            await db.close()
            raise HTTPException(status_code=400, detail="Invalid client ID")

        # 사용자 정보 추출
        provider_id = id_info['sub']
        email = id_info.get('email')
        provider_profile_image = id_info.get('picture')
        provider_user_name = id_info.get('name')

        # 사용자 존재 여부 확인
        user = await get_user_by_provider(db, 'GOOGLE', provider_id)

        if not user:
            # 새로운 유저 생성
            user = await create_user(
                db,
                email=email,
                provider_type='GOOGLE',
                provider_id=provider_id,
                provider_profile_image=provider_profile_image,
                provider_user_name=provider_user_name,
                status='Need_Register'
            )
            message = "Need_Register"
            response.status_code = 201  # 상태 코드를 201로 설정
        else:
            # 이메일, 프로필 이미지, 사용자 이름 업데이트
            updated_fields = {}
            if email is not None:
                updated_fields["email"] = email
            if provider_profile_image is not None:
                updated_fields["provider_profile_image"] = provider_profile_image
            if provider_user_name is not None:
                updated_fields["provider_user_name"] = provider_user_name

            if updated_fields:
                user = await update_user(db, user, **updated_fields)

            if user.status == 'Need_Register':
                message = "Need_Register"
                response.status_code = 202  # 상태 코드를 202로 설정
            elif user.status == 'Active':
                message = "로그인 성공"
                response.status_code = 200  # 상태 코드를 200으로 설정
            else:
                db.close()
                raise HTTPException(status_code=400, detail="유효하지 않은 사용자 상태입니다.")

        # 서버에서 JWT 토큰 생성
        access_token = await create_access_token(uuid=user.uuid)
        refresh_token = await create_refresh_token()

        # 토큰 업데이트
        await create_or_update_token(
            db,
            user_uuid=user.uuid,
            refresh_token=refresh_token,
            provider_type='GOOGLE',
            provider_access_token=data.accessToken
        )

        await db.close()
        return {
            "message": message,
            "access_token": access_token,
            "refresh_token": refresh_token
        }

    except ValueError:
        db.close()
        raise HTTPException(status_code=400, detail="구글 인증 실패")
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"Error processing user info: {str(e)}")


# 구글 계정 연결 해제 (revoke) 메소드
@router.delete("/api/v1/login/google/unregister", tags=["Unregister"])
async def google_unregister(request: Request):
    # 사용자 UUID 가져오기
    user_uuid = request.state.user_uuid

    # 데이터베이스 세션 생성
    async with SessionLocal() as db:
        try:
            # 사용자의 토큰 항목 조회
            token_entry = await db.execute(select(Token).filter(Token.uuid == user_uuid))
            token_entry = token_entry.scalars().first()
            if not token_entry:
                raise HTTPException(status_code=404, detail="유효하지 않은 사용자입니다.")

            # provider_access_token 가져오기
            user_access_token = token_entry.provider_access_token

            # 구글에 연결 해제 요청 보내기
            async with httpx.AsyncClient() as client:
                revoke_url = f"https://accounts.google.com/o/oauth2/revoke?token={user_access_token}"
                revoke_response = await client.post(revoke_url)

            if revoke_response.status_code != 200:
                raise HTTPException(status_code=revoke_response.status_code, detail="구글 계정 연결 해제 실패")

            # 사용자의 상태를 Deleted로 업데이트
            user = await db.execute(select(User).filter(User.uuid == user_uuid))
            user = user.scalars().first()
            if user:
                user.status = 'Deleted'
                await db.commit()

            # 토큰의 상태를 Deleted로 업데이트
            token_entry.status = 'Deleted'
            await db.commit()

            return {"message": "구글 계정 연결 해제 성공"}

        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"구글 연결 해제 중 오류 발생: {str(e)}")
