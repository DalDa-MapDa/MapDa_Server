# OpenAPI 설정

from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI
from config import PUBLIC_PATHS, PUBLIC_PATH_PREFIXES  # config에서 import

def custom_openapi(app: FastAPI):
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Map:Da API",
        version="1.0.0",
        description="Map:Da API 문서입니다.",
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    for path, path_item in openapi_schema["paths"].items():
        if path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
            continue
        for method in path_item.keys():
            if "security" not in openapi_schema["paths"][path][method]:
                openapi_schema["paths"][path][method]["security"] = [{"bearerAuth": []}]
                
    app.openapi_schema = openapi_schema
    return app.openapi_schema
