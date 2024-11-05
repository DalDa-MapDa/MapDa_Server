# config.py
PUBLIC_PATHS = [
    "/login/kakao",
    "/login/google",
    "/login/apple",
    # 기타 인증이 필요 없는 경로 추가
]

PUBLIC_PATH_PREFIXES = [
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static",
    "/auth",  # '/auth'로 시작하는 모든 경로
    "/proxy",
]
