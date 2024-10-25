from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi  # OpenAPI 스키마 커스터마이징을 위해 추가
from objectDetection import register, objectList
from placeRegister import place_register, placeList
from proxy import proxy_server
from login import kakao_login, apple_login, google_login
import uvicorn
from tokens import token_management

app = FastAPI()

# CORS 정책 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(register.router)
app.include_router(objectList.router)
app.include_router(place_register.router)
app.include_router(placeList.router)
app.include_router(proxy_server.router)
app.include_router(kakao_login.router)
app.include_router(apple_login.router)
app.include_router(google_login.router)
app.include_router(token_management.router)

# 인증이 필요하지 않은 경로 목록
PUBLIC_PATHS = [
    "/login/kakao",
    "/login/google",
    "/login/apple",
    # 기타 인증이 필요 없는 경로 추가
]

# 인증이 필요하지 않은 경로 패턴 목록
PUBLIC_PATH_PREFIXES = [
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static",
    "/auth",  # '/auth'로 시작하는 모든 경로
    "/proxy",
]

# 인증 미들웨어
@app.middleware("http")
async def authentication_middleware(request: Request, call_next):
    path = request.url.path

    # 인증이 필요 없는 경로는 미들웨어를 통과시킴
    if path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
        response = await call_next(request)
        return response

    # Authorization 헤더에서 토큰 추출
    auth_header = request.headers.get("Authorization")
    if auth_header:
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer":
            return Response(content="인증 스킴이 잘못되었습니다.", status_code=401)
    else:
        return Response(content="인증 정보가 필요합니다.", status_code=401)

    # 토큰 검증
    user_uuid = token_management.verify_access_token(token)
    if user_uuid in ["410", "411", "412"]:
        return Response(content="유효하지 않은 토큰입니다.", status_code=int(user_uuid))

    # 요청 상태에 사용자 UUID 저장
    request.state.user_uuid = user_uuid

    response = await call_next(request)
    return response

# # UTF-8 인코딩을 적용하는 미들웨어
# @app.middleware("http")
# async def add_utf8_encoding(request: Request, call_next):
#     response = await call_next(request)
#     # 모든 응답에 Content-Type을 설정하여 UTF-8 인코딩을 적용
#     if "text" in response.headers.get("content-type", ""):
#         response.headers["Content-Type"] = "text/html; charset=utf-8"
#     elif "application/json" in response.headers.get("content-type", ""):
#         response.headers["Content-Type"] = "application/json; charset=utf-8"
#     return response

# OpenAPI 스키마 커스터마이징
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="Map:Da API",
        version="1.0.0",
        description="Map:Da API 문서입니다.",
        routes=app.routes,
    )
    # 보안 스키마 추가
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    # 인증이 필요한 엔드포인트에 보안 스키마 적용
    for path, path_item in openapi_schema["paths"].items():
        if path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
            continue  # 인증이 필요 없는 경로는 보안 스키마를 적용하지 않음
        for method in path_item.keys():
            # 응답에 "security" 필드 추가
            if "security" not in openapi_schema["paths"][path][method]:
                openapi_schema["paths"][path][method]["security"] = [{"bearerAuth": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi  # 커스텀 OpenAPI 스키마 설정

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
