from api.objectDetection import register, objectList
from api.placeRegister import place_register, placeList
from api.proxy import proxy_server
from api.login import kakao_login, apple_login, google_login
from api.timeTable import timeTable_register, timeTable_list
from api.tokens import token_management
from api.userInfo import manage_userinfo

# 라우터 리스트 정의
routers = [
    register.router,
    objectList.router,
    place_register.router,
    placeList.router,
    proxy_server.router,
    kakao_login.router,
    apple_login.router,
    google_login.router,
    token_management.router,
    timeTable_register.router,
    timeTable_list.router,
    manage_userinfo.router,
]
