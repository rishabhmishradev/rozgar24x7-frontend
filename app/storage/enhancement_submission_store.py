"""Persist resume enhancement submissions to S3 and DynamoDB."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import importlib
import mimetypes
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote
from uuid import uuid4


_DEFAULT_AWS_REGION = "ap-south-1"
_DEFAULT_DDB_TABLE = "resume_enhancement_details"
_DEFAULT_S3_BUCKET = "rozgar-enhancement-resume"
_DEFAULT_S3_PREFIX = "uploads/resume-enhancement"
_FILENAME_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class StoredEnhancementSubmission:
    candidate_id: str
    bucket_name: str
    object_key: str
    resume_link: str
    candidate_submitted_date: str


def _sanitize_filename(filename: str) -> str:
    cleaned = _FILENAME_SANITIZE_RE.sub("_", Path(filename).name).strip("._")
    return cleaned or "resume"


def _guess_content_type(filename: str, fallback: str | None) -> str:
    if fallback and fallback.strip():
        return fallback.strip()
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _build_console_resume_link(bucket_name: str, object_key: str, aws_region: str | None) -> str:
    safe_region = (aws_region or _DEFAULT_AWS_REGION).strip() or _DEFAULT_AWS_REGION
    encoded_key = quote(object_key, safe="")
    return (
        f"https://s3.console.aws.amazon.com/s3/object/{bucket_name}"
        f"?region={safe_region}&bucketType=general&prefix={encoded_key}"
    )


class EnhancementSubmissionStore:
    """Uploads improve-form resumes to S3 and stores candidate metadata in DynamoDB."""

    def __init__(
        self,
        *,
        bucket_name: str | None,
        table_name: str | None,
        s3_prefix: str = _DEFAULT_S3_PREFIX,
        aws_region: str | None = None,
    ) -> None:
        self.bucket_name = (bucket_name or "").strip()
        self.table_name = (table_name or "").strip()
        self.s3_prefix = (s3_prefix or _DEFAULT_S3_PREFIX).strip().strip("/")
        self.aws_region = (aws_region or "").strip() or None

    @classmethod
    def from_env(cls) -> "EnhancementSubmissionStore":
        return cls(
            bucket_name=os.getenv("ENHANCEMENT_UPLOADS_S3_BUCKET", ""),
            table_name=os.getenv("ENHANCEMENT_UPLOADS_DDB_TABLE", ""),
            s3_prefix=os.getenv("ENHANCEMENT_UPLOADS_S3_PREFIX", _DEFAULT_S3_PREFIX),
            aws_region=os.getenv("AWS_REGION", _DEFAULT_AWS_REGION),
        )

    def is_configured(self) -> bool:
        return bool(self.bucket_name and self.table_name)

    def persist_submission(
        self,
        *,
        file_path: Path,
        original_filename: str,
        content_type: str | None,
        candidate_name: str,
        candidate_email_address: str,
        phone_number: str = "",
    ) -> StoredEnhancementSubmission | None:
        if not self.is_configured():
            return None

        timestamp = datetime.now(timezone.utc)
        candidate_id = uuid4().hex
        safe_filename = _sanitize_filename(original_filename)
        object_key = (
            f"{self.s3_prefix}/{timestamp:%Y-%m-%d}/"
            f"{candidate_id}-{safe_filename}"
        )
        resolved_content_type = _guess_content_type(safe_filename, content_type)

        s3_client = self._create_s3_client()
        with file_path.open("rb") as file_stream:
            s3_client.upload_fileobj(
                file_stream,
                self.bucket_name,
                object_key,
                ExtraArgs={
                    "ContentType": resolved_content_type,
                    "ServerSideEncryption": "AES256",
                },
            )

        resume_link = _build_console_resume_link(self.bucket_name, object_key, self.aws_region)
        table = self._create_dynamodb_resource().Table(self.table_name)
        table.put_item(
            Item={
                "candidate_id": candidate_id,
                "candidate_name": candidate_name.strip(),
                "candidate_email_address": candidate_email_address.strip(),
                "phone_number": phone_number.strip(),
                "candidate_resume_link": resume_link,
                "candidate_submitted_date": timestamp.isoformat(),
            }
        )

        return StoredEnhancementSubmission(
            candidate_id=candidate_id,
            bucket_name=self.bucket_name,
            object_key=object_key,
            resume_link=resume_link,
            candidate_submitted_date=timestamp.isoformat(),
        )

    def _create_s3_client(self) -> Any:
        boto3 = importlib.import_module("boto3")
        return boto3.client("s3", region_name=self.aws_region)

    def _create_dynamodb_resource(self) -> Any:
        boto3 = importlib.import_module("boto3")
        return boto3.resource("dynamodb", region_name=self.aws_region)
