from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middleware import authentication_middleware, add_utf8_encoding
from openapi_config import custom_openapi
from router_config import register_routers
from api.admin.redis_manage import flush_cache_on_startup

app = FastAPI()

# CORS 정책 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 미들웨어 등록
app.middleware("http")(authentication_middleware)
app.middleware("http")(add_utf8_encoding)

# 라우터 등록
register_routers(app)

# OpenAPI 스키마 커스터마이징
app.openapi = lambda: custom_openapi(app)

# 앱 시작 시 Redis 캐시 플러시
flush_cache_on_startup()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
