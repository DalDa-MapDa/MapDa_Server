# syntax=docker/dockerfile:1.7

# 베이스 이미지로 Python 3.12 사용
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ARG BUILDKIT_INLINE_CACHE=1
ENV UV_LINK_MODE=copy
LABEL app="mapda-server"

# 작업 디렉토리 설정
WORKDIR /app

# 로컬의 requirements.txt 파일을 컨테이너로 복사
COPY requirements.txt .

# 필요한 Python 패키지 설치
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r requirements.txt

# 애플리케이션 소스 코드 전체를 컨테이너로 복사
COPY . .

# 컨테이너가 시작될 때 실행할 명령어
EXPOSE 8000

# 컨테이너가 시작될 때 실행할 명령어
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
