from __future__ import annotations

from sqlalchemy import text

from video_platform.config import settings
from video_platform.db import db_session


def check_db() -> tuple[bool, str | None]:
    try:
        with db_session() as session:
            session.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)


def check_qdrant() -> tuple[bool, str | None]:
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=settings.qdrant_url)
        _ = client.get_collections()
        return True, None
    except Exception as exc:
        return False, str(exc)


def check_minio() -> tuple[bool, str | None]:
    try:
        import boto3

        s3 = boto3.client(
            "s3",
            endpoint_url=f"http://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            region_name="us-east-1",
            use_ssl=settings.minio_secure,
        )
        _ = s3.list_buckets()
        return True, None
    except Exception as exc:
        return False, str(exc)
