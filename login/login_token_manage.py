import jwt
import datetime
from sqlalchemy.orm import Session
from models import User, Token
from dotenv import load_dotenv
import os

load_dotenv()

# 시크릿 키와 알고리즘 설정
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')  # 직접 생성한 시크릿 키를 환경 변수로 설정
JWT_ALGORITHM = 'HS256'

# 액세스 토큰과 리프레시 토큰의 유효 기간 설정 (초 단위)
ACCESS_TOKEN_EXPIRE_SECONDS = 10    # 10초
REFRESH_TOKEN_EXPIRE_SECONDS = 604800  # 7일

def get_user_by_provider(db: Session, provider_type: str, provider_id: str):
    return db.query(User).filter(
        User.provider_type == provider_type,
        User.provider_id == provider_id,
        User.status != 'Deleted'  # Deleted 상태의 사용자는 제외
    ).first()

def create_user(db: Session, **kwargs):
    user = User(**kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update_user(db: Session, user: User, **kwargs):
    for key, value in kwargs.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user

def create_or_update_token(db: Session, user_uuid: str, **kwargs):
    token = db.query(Token).filter(Token.uuid == user_uuid).first()
    if token:
        for key, value in kwargs.items():
            setattr(token, key, value)
        db.commit()
        db.refresh(token)
    else:
        token = Token(uuid=user_uuid, **kwargs)
        db.add(token)
        db.commit()
        db.refresh(token)
    return token

def create_access_token(uuid: str):
    """액세스 토큰 생성, UUID 포함"""
    to_encode = {"uuid": uuid}
    expire = datetime.datetime.utcnow() + datetime.timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def create_refresh_token():
    """리프레시 토큰 생성, UUID 포함 안 함"""
    to_encode = {}
    expire = datetime.datetime.utcnow() + datetime.timedelta(seconds=REFRESH_TOKEN_EXPIRE_SECONDS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        uuid: str = payload.get("uuid")
        if uuid is None:
            return None
        return uuid
    except jwt.PyJWTError:
        return None

def verify_refresh_token(token: str):
    try:
        jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return True
    except jwt.PyJWTError:
        return False

def refresh_access_token(db: Session, refresh_token: str):
    # refresh_token의 유효성 확인
    if not verify_refresh_token(refresh_token):
        return None

    # tokens 테이블에서 해당 refresh_token을 가진 사용자 찾기
    token_entry = db.query(Token).filter(Token.refresh_token == refresh_token).first()
    if not token_entry:
        return None

    # 새로운 access token 생성
    new_access_token = create_access_token(uuid=token_entry.uuid)
    return new_access_token
