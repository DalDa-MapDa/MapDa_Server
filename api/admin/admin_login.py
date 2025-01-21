import datetime
import jwt
from sqlalchemy.orm import Session
from api.login.login_token_manage import JWT_ALGORITHM, JWT_SECRET_KEY, create_or_update_token
from models import SessionLocal

db: Session = SessionLocal()

# 30일(초 단위)
TOKEN_EXPIRE_SECONDS = 30 * 24 * 60 * 60  # 30일 = 30 * 24시간 * 60분 * 60초

def AdminTokenManager():
    ADMIN_UUID = "123456"

    # 실제 함수 호출
    access_token = create_admin_access_token(uuid=ADMIN_UUID)
    refresh_token = create_admin_refresh_token()

    # 토큰 출력
    print("Admin Access Token:", access_token)
    print("Admin Refresh Token:", refresh_token)

    # DB에 저장
    create_or_update_token(db, user_uuid=ADMIN_UUID, provider_type='KAKAO', refresh_token=refresh_token)


def create_admin_access_token(uuid: str):
    """액세스 토큰 생성, UUID 포함"""
    to_encode = {"uuid": uuid}
    expire = datetime.datetime.utcnow() + datetime.timedelta(seconds=TOKEN_EXPIRE_SECONDS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def create_admin_refresh_token():
    """리프레시 토큰 생성, UUID 포함 안 함"""
    to_encode = {}
    expire = datetime.datetime.utcnow() + datetime.timedelta(seconds=TOKEN_EXPIRE_SECONDS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt
