"""Client S3/MinIO: presigned PUT/GET e purge per prefisso (retention/erase GDPR).

Bucket privato; le foto sono accessibili solo via URL presigned a scadenza breve.
Le chiavi sono namespaced per evento (`events/{event_id}/...`) così il purge di
retention/erase raggiunge tutti gli oggetti dell'evento con un solo prefisso.
"""

from __future__ import annotations

import aioboto3
from aiobotocore.config import AioConfig

from whisper.settings import Settings

# Supabase Storage (e S3 moderno in generale) accetta solo firme SigV4 in
# path-style: senza questa config boto può ripiegare su SigV2 → "Missing signature".
_S3_CONFIG = AioConfig(signature_version="s3v4", s3={"addressing_style": "path"})


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.s3_bucket
        self._endpoint = settings.s3_endpoint_url
        self._region = settings.s3_region
        self._access_key = settings.s3_access_key
        self._secret_key = settings.s3_secret_key
        self._session = aioboto3.Session()

    def _client(self):
        return self._session.client(
            "s3",
            endpoint_url=self._endpoint,
            region_name=self._region,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            config=_S3_CONFIG,
        )

    async def ensure_bucket(self) -> None:
        async with self._client() as s3:
            try:
                await s3.head_bucket(Bucket=self._bucket)
            except Exception:  # noqa: BLE001 — bucket assente: lo creiamo
                await s3.create_bucket(Bucket=self._bucket)

    async def presigned_put(self, key: str, *, content_type: str, expires: int = 900) -> str:
        async with self._client() as s3:
            return await s3.generate_presigned_url(
                "put_object",
                Params={"Bucket": self._bucket, "Key": key, "ContentType": content_type},
                ExpiresIn=expires,
            )

    async def presigned_get(self, key: str, *, expires: int = 900) -> str:
        async with self._client() as s3:
            return await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires,
            )

    async def presigned_get_many(self, keys: list[str], *, expires: int = 900) -> dict[str, str]:
        out: dict[str, str] = {}
        async with self._client() as s3:
            for key in keys:
                out[key] = await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self._bucket, "Key": key},
                    ExpiresIn=expires,
                )
        return out

    async def delete_object(self, key: str) -> None:
        async with self._client() as s3:
            await s3.delete_object(Bucket=self._bucket, Key=key)

    async def delete_prefix(self, prefix: str) -> None:
        async with self._client() as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
                if keys:
                    await s3.delete_objects(Bucket=self._bucket, Delete={"Objects": keys})
