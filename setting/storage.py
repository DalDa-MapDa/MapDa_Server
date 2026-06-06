import json
import mimetypes
import os
import threading
import uuid
from dataclasses import dataclass
from urllib.parse import quote

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

_bucket_ready = False
_bucket_lock = threading.Lock()


@dataclass(frozen=True)
class StoredFile:
    key: str
    url: str
    content_type: str


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def get_bucket_name() -> str:
    return _required_env("MINIO_BUCKET")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=_required_env("MINIO_ENDPOINT"),
        aws_access_key_id=_required_env("MINIO_ACCESS_KEY"),
        aws_secret_access_key=_required_env("MINIO_SECRET_KEY"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name=os.getenv("MINIO_REGION", "us-east-1"),
    )


def _public_url_for_key(key: str) -> str:
    public_base_url = _required_env("APP_PUBLIC_URL").rstrip("/")
    return f"{public_base_url}/media/{quote(key, safe='/')}"


def _content_type(filename: str, provided_type: str | None) -> str:
    if provided_type and provided_type != "application/octet-stream":
        return provided_type

    guessed_type, _ = mimetypes.guess_type(filename)
    return guessed_type or "application/octet-stream"


def _extension(filename: str, content_type: str) -> str:
    _, ext = os.path.splitext(filename or "")
    if ext:
        return ext.lstrip(".").lower()

    guessed_ext = mimetypes.guess_extension(content_type)
    return guessed_ext.lstrip(".") if guessed_ext else "bin"


def ensure_bucket() -> None:
    global _bucket_ready

    if _bucket_ready:
        return

    with _bucket_lock:
        if _bucket_ready:
            return

        client = get_s3_client()
        bucket = get_bucket_name()

        try:
            client.head_bucket(Bucket=bucket)
        except ClientError as error:
            status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            error_code = error.response.get("Error", {}).get("Code")
            if status_code == 404 or error_code in {"404", "NoSuchBucket", "NotFound"}:
                client.create_bucket(Bucket=bucket)
            else:
                raise

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket}/*"],
                }
            ],
        }
        client.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))
        _bucket_ready = True


def upload_file_to_storage(upload_file, prefix: str) -> StoredFile:
    ensure_bucket()

    content_type = _content_type(upload_file.filename, getattr(upload_file, "content_type", None))
    ext = _extension(upload_file.filename, content_type)
    key = f"{prefix.strip('/')}/{uuid.uuid4()}.{ext}"

    upload_file.file.seek(0)
    get_s3_client().upload_fileobj(
        upload_file.file,
        get_bucket_name(),
        key,
        ExtraArgs={"ContentType": content_type},
    )

    return StoredFile(key=key, url=_public_url_for_key(key), content_type=content_type)


def read_upload_as_data_url(upload_file, content_type: str) -> str:
    import base64

    upload_file.file.seek(0)
    encoded = base64.b64encode(upload_file.file.read()).decode("ascii")
    upload_file.file.seek(0)
    return f"data:{content_type};base64,{encoded}"
