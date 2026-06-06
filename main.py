import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from middleware import authentication_middleware, add_utf8_encoding
from openapi_config import custom_openapi
from router_config import register_routers
from api.admin.redis_manage import flush_cache_on_startup
from api.admin.admin_login import AdminTokenManager
from models import engine
from setting.redis_client import redis_client
from setting.storage import ensure_bucket


class HealthCheckAccessLogFilter(logging.Filter):
    def filter(self, record):
        return "/health" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(HealthCheckAccessLogFilter())

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


@app.get("/health", tags=["Health"])
async def health():
    checks = {"app": "ok"}

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as error:
        checks["database"] = f"error: {error}"

    try:
        redis_client.ping()
        checks["redis"] = "ok"
    except Exception as error:
        checks["redis"] = f"error: {error}"

    try:
        ensure_bucket()
        checks["minio"] = "ok"
    except Exception as error:
        checks["minio"] = f"error: {error}"

    healthy = all(value == "ok" for value in checks.values())
    status_code = 200 if healthy else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )

# 앱 시작 시 Redis 캐시 플러시
flush_cache_on_startup()

# # AdminTokenManager 초기화
# AdminTokenManager()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True)
