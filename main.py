from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from objectDetection import register, objectList
from placeRegister import place_register, placeList
from ocr_conversion import ocr_conversion
from proxy import proxy_server  # 프록시 라우터 import
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

# 기존 라우터 등록
app.include_router(register.router)
app.include_router(objectList.router)
app.include_router(place_register.router)
app.include_router(placeList.router)
app.include_router(ocr_conversion.router)

# 프록시 라우터 등록
app.include_router(proxy_server.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
