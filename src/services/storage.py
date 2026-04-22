import uuid
from pathlib import Path

import boto3
from botocore.client import Config

from src.config import settings

S3_TTL_HOURS = 24
PRESIGNED_URL_TTL_SECONDS = 3600  # 1 hour


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )


async def upload_file(local_path: Path, content_type: str = "text/plain") -> str:
    """Upload file to S3 and return the S3 key."""
    import asyncio

    key = f"transcriptions/{uuid.uuid4()}/{local_path.name}"
    client = _get_client()

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: client.upload_file(
            str(local_path),
            settings.S3_BUCKET,
            key,
            ExtraArgs={"ContentType": content_type},
        ),
    )
    return key


async def get_presigned_url(s3_key: str) -> str:
    """Generate a pre-signed URL valid for 1 hour."""
    import asyncio

    client = _get_client()
    loop = asyncio.get_event_loop()
    url = await loop.run_in_executor(
        None,
        lambda: client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.S3_BUCKET, "Key": s3_key},
            ExpiresIn=PRESIGNED_URL_TTL_SECONDS,
        ),
    )
    return url
