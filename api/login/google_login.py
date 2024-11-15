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
import requests  # 동기화된 HTTP 요청을 위해 requests 사용
from sqlalchemy.future import select

router = APIRouter()

# .env 파일 로드
load_dotenv()

# 구글 관련 환경 변수 로드
GOOGLE_CLIENT_IDS = os.getenv("GOOGLE_CLIENT_IDS", "").split(",")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

class GoogleLoginData(BaseModel):
    idToken: str
    accessToken: str  # access token 추가


# 구글 로그인 메소드
@router.post("/login/google", tags=["Login"])
async def google_login(data: GoogleLoginData, response: Response):
    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        print("google_Step 1: Received data", data)  # 요청 데이터 출력

        # ID 토큰 검증
        try:
            id_info = id_token.verify_oauth2_token(
                data.idToken, google_requests.Request(), None
            )
            print("google_Step 2: ID Token verified successfully", id_info)  # 검증 결과 출력
        except Exception as e:
            print("google_Error verifying ID token:", e)  # 오류 메시지 출력
            db.close()
            raise HTTPException(status_code=400, detail="Invalid ID Token")

        # 클라이언트 ID 확인
        if id_info['aud'] not in GOOGLE_CLIENT_IDS:
            print("google_Step 3: Invalid client ID. Audience:", id_info['aud'])  # 잘못된 클라이언트 ID 출력
            db.close()
            raise HTTPException(status_code=400, detail="Invalid client ID")

        # 사용자 정보 추출
        provider_id = id_info['sub']
        email = id_info.get('email')
        provider_profile_image = id_info.get('picture')
        provider_user_name = id_info.get('name')

        print("google_Step 4: Extracted user information:", {
            "provider_id": provider_id,
            "email": email,
            "provider_profile_image": provider_profile_image,
            "provider_user_name": provider_user_name
        })  # 사용자 정보 출력

        # 사용자 존재 여부 확인
        user = db.query(User).filter(
            User.provider_type == 'GOOGLE',
            User.provider_id == provider_id,
            User.status != 'Deleted'  # Deleted 상태는 제외
        ).first()
        print("google_Step 5: User existence check:", user)  # 사용자 존재 여부 출력

        if not user:
            # Deleted 상태의 동일한 provider_id가 있을 수도 있으므로 중복 체크
            existing_deleted_user = db.query(User).filter(
                User.provider_type == 'GOOGLE',
                User.provider_id == provider_id,
                User.status == 'Deleted'
            ).first()

            if existing_deleted_user:
                print("google_Step 6: Found deleted user, creating new account")
            else:
                print("google_Step 6: No user found, creating new account")

            # 새로운 유저 생성
            user = create_user(
                db,
                email=email,
                provider_type='GOOGLE',
                provider_id=provider_id,
                provider_profile_image=provider_profile_image,
                provider_user_name=provider_user_name,
                status='Need_Register'
            )
            print("google_Step 7: New user created:", user)  # 생성된 사용자 정보 출력
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
                user = update_user(db, user, **updated_fields)
                print("google_Step 8: Updated user information:", updated_fields)  # 업데이트된 정보 출력

            if user.status == 'Need_Register':
                message = "Need_Register"
                response.status_code = 202  # 상태 코드를 202로 설정
            elif user.status == 'Active':
                message = "로그인 성공"
                response.status_code = 200  # 상태 코드를 200으로 설정
            else:
                print("google_Step 9: Invalid user status:", user.status)  # 유효하지 않은 상태 출력
                db.close()
                raise HTTPException(status_code=400, detail="유효하지 않은 사용자 상태입니다.")

        # 서버에서 JWT 토큰 생성
        access_token = create_access_token(uuid=user.uuid)
        refresh_token = create_refresh_token()
        print("google_Step 10: Tokens created. Access:", access_token, "Refresh:", refresh_token)  # 생성된 토큰 출력

        # 토큰 업데이트
        create_or_update_token(
            db,
            user_uuid=user.uuid,
            refresh_token=refresh_token,
            provider_type='GOOGLE',
            provider_access_token=data.accessToken
        )
        print("google_Step 11: Token updated in database")  # 토큰 업데이트 완료 메시지

        db.close()
        return {
            "message": message,
            "access_token": access_token,
            "refresh_token": refresh_token
        }

    except ValueError as ve:
        print("google_General value error:", ve)  # 일반적인 값 오류 출력
        db.close()
        raise HTTPException(status_code=400, detail="구글 인증 실패")
    except Exception as e:
        print("google_Unexpected error occurred:", e)  # 예기치 않은 오류 출력
        db.close()
        raise HTTPException(status_code=500, detail=f"Error processing user info: {str(e)}")



# 구글 계정 연결 해제 (revoke) 함수를 일반 함수로 변경
def google_unregister_function(user_uuid: str):
    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        # 사용자의 토큰 항목 조회
        token_entry = db.query(Token).filter(Token.uuid == user_uuid).first()
        if not token_entry:
            db.close()
            raise HTTPException(status_code=404, detail="유효하지 않은 사용자입니다.")

        # provider_access_token 가져오기
        user_access_token = token_entry.provider_access_token

        # 구글에 연결 해제 요청 보내기
        revoke_url = f"https://accounts.google.com/o/oauth2/revoke?token={user_access_token}"
        revoke_response = requests.post(revoke_url)

        if revoke_response.status_code != 200:
            db.close()
            raise HTTPException(status_code=revoke_response.status_code, detail="구글 계정 연결 해제 실패")

        # 사용자의 상태를 Deleted로 업데이트
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if user:
            user.status = 'Deleted'
            db.commit()

        # 토큰의 상태를 Deleted로 업데이트
        token_entry.status = 'Deleted'
        db.commit()

        db.close()
        return {"message": "구글 계정 연결 해제 성공"}

    except HTTPException as he:
        db.close()
        raise he
    except Exception as e:
        db.rollback()
        db.close()
        raise HTTPException(status_code=500, detail=f"구글 연결 해제 중 오류 발생: {str(e)}")