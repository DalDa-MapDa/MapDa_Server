from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from objectDetection import register, objectList  # 새로 추가된 모듈 import
import uvicorn

app = FastAPI()

# CORS 정책 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인 허용, 필요에 따라 특정 도메인으로 제한 가능
    allow_credentials=True,
    allow_methods=["*"],  # 모든 메소드 허용 (GET, POST, etc)
    allow_headers=["*"],  # 모든 헤더 허용
)

# 라우터 등록
app.include_router(register.router)  # 위험 물체 등록
app.include_router(objectList.router)  # 위험 물체 리스트

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
