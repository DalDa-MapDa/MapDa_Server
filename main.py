from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from objectDetection import register, objectList
from placeRegister import place_register, placeList
from proxy import proxy_server  # 프록시 라우터 import
from login import kakao_login, apple_login, google_login, login_token_manage
import uvicorn

app = FastAPI()

# CORS 정책 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# UTF-8 인코딩을 적용하는 미들웨어
@app.middleware("http")
async def add_utf8_encoding(request: Request, call_next):
    response = await call_next(request)
    # 모든 응답에 Content-Type을 설정하여 UTF-8 인코딩을 적용
    if "text" in response.headers.get("content-type", ""):
        response.headers["Content-Type"] = "text/html; charset=utf-8"
    elif "application/json" in response.headers.get("content-type", ""):
        response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

# 라우터 등록
app.include_router(register.router)
app.include_router(objectList.router)
app.include_router(place_register.router)
app.include_router(placeList.router)
app.include_router(proxy_server.router)
app.include_router(kakao_login.router)
app.include_router(apple_login.router)
app.include_router(google_login.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
