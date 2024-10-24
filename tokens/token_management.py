import jwt
from jwt import PyJWTError
import os
from dotenv import load_dotenv
import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from models import SessionLocal, Token

load_dotenv()

JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
JWT_ALGORITHM = 'HS256'

ACCESS_TOKEN_EXPIRE_SECONDS = 3600    # 1시간

router = APIRouter()

def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        uuid: str = payload.get("uuid")
        if uuid is None:
            return None
        return uuid
    except PyJWTError:
        return None

def verify_refresh_token(token: str):
    try:
        jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return True
    except PyJWTError:
        return False

def create_access_token(uuid: str):
    """액세스 토큰 생성, UUID 포함"""
    to_encode = {"uuid": uuid}
    expire = datetime.datetime.utcnow() + datetime.timedelta(seconds=ACCESS_TOKEN_EXPIRE_SECONDS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

class RefreshTokenRequest(BaseModel):
    refresh_token: str

@router.post('/auth/refresh', tags=['Authentication'])
async def refresh_access_token_endpoint(refresh_request: RefreshTokenRequest):
    refresh_token = refresh_request.refresh_token
    # 리프레시 토큰 유효성 검증
    if not verify_refresh_token(refresh_token):
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다.")
    # 데이터베이스 세션 생성
    db: Session = SessionLocal()
    try:
        # 리프레시 토큰으로 사용자 조회
        token_entry = db.query(Token).filter(Token.refresh_token == refresh_token).first()
        if not token_entry:
            raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다.")
        # 새로운 액세스 토큰 생성
        new_access_token = create_access_token(token_entry.uuid)
        return {"access_token": new_access_token}
    finally:
        db.close()
