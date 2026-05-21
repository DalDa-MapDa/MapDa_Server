# 미들웨어 설정

from fastapi import Request, Response
from api.tokens import token_management
from config import PUBLIC_PATHS, PUBLIC_PATH_PREFIXES  # config에서 import

async def authentication_middleware(request: Request, call_next):
    path = request.url.path
    if path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
        return await call_next(request)
    
    auth_header = request.headers.get("Authorization")
    if auth_header:
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer":
            return Response(content="인증 스킴이 잘못되었습니다.", status_code=401)
    else:
        return Response(content="인증 정보가 필요합니다.", status_code=401)
    
    user_uuid = token_management.verify_access_token(token)
    if not user_uuid:
        return Response(content="유효하지 않은 토큰입니다.", status_code=401)

    request.state.user_uuid = user_uuid
    return await call_next(request)

async def add_utf8_encoding(request: Request, call_next):
    response = await call_next(request)
    if "text" in response.headers.get("content-type", ""):
        response.headers["Content-Type"] = "text/html; charset=utf-8"
    elif "application/json" in response.headers.get("content-type", ""):
        response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

