FROM minio/minio:latest AS minio
FROM minio/mc:latest AS mc
FROM nginx:1.27-alpine

RUN apk add --no-cache redis

COPY --from=minio /usr/bin/minio /usr/bin/minio
COPY --from=mc /usr/bin/mc /usr/bin/mc
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 80 6379 9000 9001

ENTRYPOINT ["/entrypoint.sh"]
