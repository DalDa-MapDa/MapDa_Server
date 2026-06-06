#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

cd "$ROOT_DIR"

COMPOSE="docker compose"
NGINX_CONTAINER="mapda-nginx"
UPSTREAM_FILE="/etc/nginx/active/upstream.inc"
CACHE_ROOT=".docker-build-cache"
CURRENT_CACHE_DIR="$CACHE_ROOT/current"
NEXT_CACHE_DIR="$CACHE_ROOT/next"

export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

cleanup_next_cache() {
  rm -rf "$NEXT_CACHE_DIR"
}

trap cleanup_next_cache EXIT

current="blue"
if docker ps --format '{{.Names}}' | grep -qx "$NGINX_CONTAINER"; then
  current=$(
    docker exec "$NGINX_CONTAINER" sh -c "cat $UPSTREAM_FILE 2>/dev/null || true" |
      sed -n 's/.*mapda-server-\(blue\|green\):8000.*/\1/p' |
      tail -n 1
  )
  current=${current:-blue}
fi

if [ "$current" = "blue" ]; then
  next="green"
else
  next="blue"
fi

echo "Current active color: $current"
echo "Next color: $next"

$COMPOSE up -d --build mapda-nginx

rm -rf "$NEXT_CACHE_DIR"
mkdir -p "$CACHE_ROOT"

if [ -d "$CURRENT_CACHE_DIR" ]; then
  echo "Building mapda-server:$next using cache from $CURRENT_CACHE_DIR..."
  docker buildx build \
    --load \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    --cache-from "type=local,src=$CURRENT_CACHE_DIR" \
    --cache-to "type=local,dest=$NEXT_CACHE_DIR,mode=max" \
    -t "mapda-server:$next" \
    .
else
  echo "Building mapda-server:$next without app build cache..."
  docker buildx build \
    --load \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    --cache-to "type=local,dest=$NEXT_CACHE_DIR,mode=max" \
    -t "mapda-server:$next" \
    .
fi

$COMPOSE up -d --no-build "mapda-server-$next"

echo "Waiting for mapda-server-$next health..."
attempt=1
while [ "$attempt" -le 60 ]; do
  if docker exec "$NGINX_CONTAINER" wget -qO- "http://mapda-server-$next:8000/health" >/dev/null 2>&1; then
    break
  fi

  if [ "$attempt" -eq 60 ]; then
    echo "mapda-server-$next did not become healthy in time." >&2
    exit 1
  fi

  attempt=$((attempt + 1))
  sleep 2
done

docker exec "$NGINX_CONTAINER" sh -c "printf 'set \$active_upstream mapda-server-$next:8000;\n' > $UPSTREAM_FILE && nginx -s reload"

if [ "$current" != "$next" ]; then
  $COMPOSE stop "mapda-server-$current" >/dev/null 2>&1 || true
  $COMPOSE rm -f "mapda-server-$current" >/dev/null 2>&1 || true
fi

rm -rf "$CURRENT_CACHE_DIR"
mv "$NEXT_CACHE_DIR" "$CURRENT_CACHE_DIR"

echo "Cleaning old mapda-server image cache..."
docker image rm "mapda-server:$current" >/dev/null 2>&1 || true
docker image prune -f --filter "label=app=mapda-server" >/dev/null 2>&1 || true
docker image prune -f >/dev/null 2>&1 || true
docker builder prune -af >/dev/null 2>&1 || true

echo "Switched active color to $next."
