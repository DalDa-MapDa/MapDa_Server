#!/bin/sh
set -eu

: "${ACTIVE_COLOR:=blue}"
: "${MINIO_ACCESS_KEY:?MINIO_ACCESS_KEY is required}"
: "${MINIO_SECRET_KEY:?MINIO_SECRET_KEY is required}"
: "${MINIO_BUCKET:=mapda-bucket}"

mkdir -p /etc/nginx/active
mkdir -p /data

if [ ! -s /etc/nginx/active/upstream.inc ]; then
  printf 'set $active_upstream mapda-server-%s:8000;\n' "$ACTIVE_COLOR" > /etc/nginx/active/upstream.inc
fi

redis-server --daemonize yes --bind 0.0.0.0 --protected-mode no
MINIO_ROOT_USER="$MINIO_ACCESS_KEY" \
MINIO_ROOT_PASSWORD="$MINIO_SECRET_KEY" \
  minio server /data --address 0.0.0.0:9000 --console-address 0.0.0.0:9001 >/var/log/minio.log 2>&1 &

until mc alias set local http://127.0.0.1:9000 "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" >/dev/null 2>&1; do
  sleep 1
done

mc mb -p "local/$MINIO_BUCKET" >/dev/null 2>&1 || true
mc anonymous set download "local/$MINIO_BUCKET" >/dev/null

exec nginx -g 'daemon off;'
