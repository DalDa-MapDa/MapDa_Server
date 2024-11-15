import datetime
import os
import jwt
from pydantic import BaseModel
import requests
from fastapi import APIRouter, HTTPException, Response, Request
from dotenv import load_dotenv
from typing import Optional
from sqlalchemy.orm import Session
from models import SessionLocal, User, Token
from api.login.login_token_manage import (
    get_user_by_provider, create_user, create_or_update_token,
    create_access_token, create_refresh_token
)
from sqlalchemy.future import select

router = APIRouter()

# .env 파일 로드
load_dotenv()

# 애플 관련 환경 변수 로드
APPLE_CLIENT_ID = os.getenv("APPLE_CLIENT_ID")
APPLE_KEY_ID = os.getenv("APPLE_KEY_ID")
APPLE_TEAM_ID = os.getenv("APPLE_TEAM_ID")

# AuthKey 파일에서 비밀키를 읽어오기(이 부분은 로컬/서버 환경에 따라 경로가 다를 수 있음)
# 삭제 금지
auth_key_path = "/app/secrets/AuthKey_76ZFAC89DR.p8"  # 서버 경로
# auth_key_path = "secrets/AuthKey_76ZFAC89DR.p8"  # 로컬 경로

try:
    with open(auth_key_path, "r") as key_file:
        APPLE_PRIVATE_KEY = key_file.read()
except FileNotFoundError:
    raise HTTPException(status_code=500, detail=f"비밀키 파일을 찾을 수 없습니다: {auth_key_path}")

# 입력 데이터 모델 정의
class AppleLoginData(BaseModel):
    identityToken: str
    authorizationCode: str
    userEmail: str  # 새로운 필드 추가
    userName: str   # 새로운 필드 추가


# 애플 로그인 메소드
@router.post('/login/apple', tags=["Login"])
def apple_login(data: AppleLoginData, response: Response):
    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        print("apple_Step 1: Received data", data)  # 요청 데이터 출력

        # 1. 애플로부터 받은 authorizationCode로 토큰 요청
        try:
            token_response = requests.post(
                'https://appleid.apple.com/auth/token',
                data={
                    'client_id': APPLE_CLIENT_ID,
                    'client_secret': create_client_secret(),
                    'code': data.authorizationCode,
                    'grant_type': 'authorization_code',
                    'redirect_uri': 'https://api.mapda.site/login/apple'
                }
            )
            print("apple_Step 2: Token response received from Apple")  # 애플의 응답 수신 확인
        except Exception as e:
            print("apple_Error requesting token from Apple:", e)  # 오류 메시지 출력
            db.close()
            raise HTTPException(status_code=500, detail="애플 인증 요청 중 오류 발생")

        # 애플 인증 실패 시 오류 처리
        if token_response.status_code != 200:
            print("apple_Step 3: Apple token response error", token_response.status_code, token_response.text)  # 애플 응답 에러 출력
            db.close()
            raise HTTPException(status_code=token_response.status_code, detail="애플 인증 실패")

        token_data = token_response.json()
        print("apple_Step 4: Token data from Apple", token_data)  # 토큰 데이터 출력

        # 2. ID 토큰 디코딩 및 검증
        decoded_token = verify_and_decode_identity_token(token_data.get('id_token'))
        if decoded_token is None:
            print("apple_Step 5: Identity token verification failed")  # 검증 실패 메시지 출력
            db.close()
            raise HTTPException(status_code=400, detail="identityToken 검증 실패")

        print("apple_Step 6: Decoded identity token", decoded_token)  # 디코딩된 토큰 출력

        # 3. provider_id 추출
        provider_id = decoded_token.get('sub')
        if not provider_id:
            print("apple_Step 7: Provider ID not found in decoded token")  # provider_id 누락 출력
            db.close()
            raise HTTPException(status_code=400, detail="provider_id를 가져올 수 없습니다.")

        print("apple_Step 8: Extracted provider_id", provider_id)  # provider_id 출력

        # 4. 사용자 존재 여부 확인
        user = db.query(User).filter(
            User.provider_type == 'APPLE',
            User.provider_id == provider_id,
            User.status != 'Deleted'  # Deleted 상태는 제외
        ).first()
        print("apple_Step 9: User existence check:", user)  # 사용자 존재 여부 출력

        if not user:
            # Deleted 상태의 동일한 provider_id가 있을 수도 있으므로 중복 체크
            existing_deleted_user = db.query(User).filter(
                User.provider_type == 'APPLE',
                User.provider_id == provider_id,
                User.status == 'Deleted'
            ).first()

            if existing_deleted_user:
                print("apple_Step 10: Found deleted user, creating new account")
            else:
                print("apple_Step 10: No user found, creating new account")

            # 새로운 유저 생성
            user = create_user(
                db,
                email=data.userEmail if data.userEmail else None,
                provider_type='APPLE',
                provider_id=provider_id,
                provider_profile_image=None,
                provider_user_name=data.userName if data.userName else None,
                apple_real_user_status=decoded_token.get('real_user_status'),
                status='Need_Register'  # 상태를 Need_Register로 설정
            )
            print("apple_Step 11: New user created", user)  # 생성된 사용자 정보 출력
            message = "Need_Register"
            response.status_code = 201  # 상태 코드를 201로 설정

        elif user.status == 'Need_Register':
            print("apple_Step 12: User already in Need_Register status")  # Need_Register 상태 메시지 출력
            message = "Need_Register"
            response.status_code = 202  # 상태 코드를 202로 설정

        elif user.status == 'Active':
            print("apple_Step 13: User is Active")  # Active 상태 메시지 출력
            message = "로그인 성공"
            response.status_code = 200  # 상태 코드를 200으로 설정

        else:
            print("apple_Step 14: Invalid user status", user.status)  # 유효하지 않은 상태 출력
            db.close()
            raise HTTPException(status_code=400, detail="유효하지 않은 사용자 상태입니다.")

        # 서버에서 JWT 토큰 생성
        access_token = create_access_token(uuid=user.uuid)
        refresh_token = create_refresh_token()
        print("apple_Step 15: Tokens created. Access:", access_token, "Refresh:", refresh_token)  # 생성된 토큰 출력

        # 토큰 업데이트
        create_or_update_token(
            db,
            user_uuid=user.uuid,
            refresh_token=refresh_token,
            provider_type='APPLE',
            provider_refresh_token=token_data.get('refresh_token')
        )
        print("apple_Step 16: Token updated in database")  # 토큰 업데이트 완료 메시지

        db.close()
        return {
            "message": message,
            "access_token": access_token,
            "refresh_token": refresh_token
        }

    except HTTPException as he:
        print("apple_HTTP exception occurred:", he.detail)  # HTTP 예외 메시지 출력
        db.close()
        raise he
    except Exception as e:
        print("apple_Unexpected error occurred:", e)  # 예기치 않은 오류 출력
        db.close()
        raise HTTPException(status_code=500, detail=f"Error processing user info: {str(e)}")



# 클라이언트 시크릿 생성 함수
def create_client_secret():
    headers = {
        "kid": APPLE_KEY_ID,
        "alg": "ES256"
    }
    payload = {
        "iss": APPLE_TEAM_ID,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=180),
        "aud": "https://appleid.apple.com",
        "sub": APPLE_CLIENT_ID,
    }
    try:
        client_secret = jwt.encode(payload, APPLE_PRIVATE_KEY, algorithm="ES256", headers=headers)
        return client_secret
    except Exception:
        raise HTTPException(status_code=500, detail="클라이언트 시크릿 생성 중 오류 발생")

# identityToken 디코딩 및 검증 함수
def verify_and_decode_identity_token(identity_token: str) -> dict:
    try:
        decoded_token = jwt.decode(identity_token, options={"verify_signature": False})
        return decoded_token
    except jwt.InvalidTokenError:
        return None

# 회원 탈퇴 로직을 일반 함수로 변경
def apple_unregister_function(user_uuid: str):
    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        # 사용자의 토큰 항목 조회
        token_entry = db.query(Token).filter(Token.uuid == user_uuid).first()
        if not token_entry:
            db.close()
            raise HTTPException(status_code=404, detail="유효하지 않은 사용자입니다.")

        # provider_refresh_token 가져오기
        user_refresh_token = token_entry.provider_refresh_token

        # 애플에 회원 탈퇴 요청 보내기
        response = requests.post(
            'https://appleid.apple.com/auth/revoke',
            data={
                'client_id': APPLE_CLIENT_ID,
                'client_secret': create_client_secret(),
                'token': user_refresh_token,
                'token_type_hint': 'refresh_token'
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )

        if response.status_code != 200:
            db.close()
            raise HTTPException(status_code=response.status_code, detail="애플 회원 탈퇴 실패")

        # 사용자의 상태를 Deleted로 업데이트
        user = db.query(User).filter(User.uuid == user_uuid).first()
        if user:
            user.status = 'Deleted'
            db.commit()

        # 토큰의 상태를 Deleted로 업데이트
        token_entry.status = 'Deleted'
        db.commit()

        db.close()
        return {"message": "애플 회원 탈퇴 성공"}

    except HTTPException as he:
        db.close()
        raise he
    except Exception as e:
        db.rollback()
        db.close()
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")
