# MapDa_Server
Team 달다(Dal:da) - 조은애/이지현/이유철

## Local Server Deployment

이 서버는 Docker Compose 기반으로 실행하며, `mapda-nginx` 컨테이너와 blue/green 앱 컨테이너를 사용합니다.

- `mapda-nginx`: Nginx, Redis, MinIO를 함께 실행합니다.
- `mapda-server-blue`: blue 앱 컨테이너입니다.
- `mapda-server-green`: green 앱 컨테이너입니다.
- 외부 요청은 호스트 `17200` 포트로 들어오고, Nginx가 현재 활성 앱 컨테이너로 라우팅합니다.

### Environment

`.env.example`을 참고해 `.env`를 작성합니다. `.env`는 Git에 포함하지 않습니다.

주요 값:

```env
DB_ENDPOINT=host.docker.internal
DB_PORT=3306
DB_NAME=mapda
DB_USER=<mysql-user>
DB_PASSWORD=<mysql-password>

MINIO_ENDPOINT=http://mapda-nginx:9000
MINIO_ACCESS_KEY=<minio-access-key>
MINIO_SECRET_KEY=<minio-secret-key>
MINIO_BUCKET=mapda-bucket

APP_PUBLIC_URL=http://<server-host>:17200
```

MySQL은 호스트 서버의 `3306` 포트에 떠 있는 `mapda` 데이터베이스를 사용합니다. Docker 컨테이너에서 접근하므로 MySQL 계정은 Docker bridge IP 대역의 접속을 허용해야 합니다.

### Initial Start

처음 실행할 때는 Nginx/Redis/MinIO 컨테이너와 blue 앱 컨테이너를 빌드하고 실행합니다.

```bash
docker compose up -d --build mapda-nginx mapda-server-blue
```

실행 후 상태를 확인합니다.

```bash
docker compose ps
curl http://localhost:17200/health
```

`/health`는 앱, MySQL, Redis, MinIO 연결 상태를 확인합니다.

### Blue-Green Deploy

배포는 아래 스크립트 하나로 진행합니다.

```bash
./deploy/blue-green-deploy.sh
```

스크립트 동작:

- 현재 활성 색상(blue 또는 green)을 확인합니다.
- 비활성 색상의 앱 이미지를 빌드합니다.
- 새 앱 컨테이너의 `/health`가 성공할 때까지 대기합니다.
- Nginx upstream을 새 컨테이너로 전환하고 reload합니다.
- 이전 앱 컨테이너와 이전 앱 이미지를 정리합니다.

배포가 실패하면 Nginx upstream은 기존 컨테이너를 유지합니다.

### Build Cache Policy

앱 이미지는 `uv`로 Python 패키지를 설치해 빌드 시간을 줄입니다.

Docker build cache는 `.docker-build-cache/current` 하나만 유지합니다. 배포 성공 후 새 캐시만 `current`로 승격하고, 이전 앱 이미지와 Docker builder cache는 정리합니다. 따라서 최신 성공 배포에 필요한 캐시만 남습니다.

### MinIO

MinIO는 별도 컨테이너로 실행하지 않고 `mapda:nginx` 이미지 안에서 함께 실행합니다. `mapda-nginx` 시작 시 `MINIO_BUCKET`이 없으면 생성하고, `/media/` 경로를 통해 Nginx가 MinIO 객체를 프록시합니다.

업로드된 파일 URL은 다음 형태로 저장됩니다.

```text
${APP_PUBLIC_URL}/media/{object_key}
```

## Convention
- [CHORE]: 프로덕션 코드가 바뀌지 않고 개발 로직과 상관 없는 가벼운 일들
- [DEPS]: Dependency와 관련 있는 내용
- [DOCS]: 도큐먼트/문서화 업데이트
- [FEAT]: 새로운 기능/특징
- [FIX]: 버그를 고침
- [HOTFIX]: 시급한 버그를 고침
- [REFACTOR]: production 코드를 리팩토링
- [STYLE]: Code의 스타일, 포맷 등이 바뀐 경우
- [TEST]: 테스트 코드 추가 및 업데이트
