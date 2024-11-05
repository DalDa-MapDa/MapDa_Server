# 라우터 설정

from fastapi import FastAPI
from api import routers  # 모든 라우터가 포함된 리스트

def register_routers(app: FastAPI):
    for router in routers:
        app.include_router(router)
