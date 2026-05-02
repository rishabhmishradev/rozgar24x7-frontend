"""Persist ATS uploads to S3 and DynamoDB with filesystem fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import importlib
import logging
import mimetypes
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import parse_qs, quote, urlparse
from uuid import uuid4


_DEFAULT_AWS_REGION = "ap-south-1"
_DEFAULT_DDB_TABLE = "resume-ats-submission"
_DEFAULT_S3_BUCKET = "rozgar-uploaded-resume"
_DEFAULT_S3_PREFIX = "uploads/ats-submissions"
_DEFAULT_LOCAL_STORAGE_DIR = "ats-local-storage"
_FILENAME_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoredSubmission:
    submission_id: str
    bucket_name: str
    object_key: str
    resume_link: str

    @property
    def document_link(self) -> str:
        return self.resume_link


@dataclass(frozen=True)
class LocalStoredSubmission:
    """Represents a locally stored submission when S3/DynamoDB isn't configured."""
    submission_id: str
    local_path: str
    resume_link: str  # Will be a local file path or placeholder

    @property
    def document_link(self) -> str:
        return self.resume_link


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


def _parse_s3_uri(value: str) -> tuple[str, str] | None:
    cleaned = value.strip()
    if not cleaned.startswith("s3://"):
        return None

    without_scheme = cleaned[5:]
    if "/" not in without_scheme:
        return None

    bucket_name, object_key = without_scheme.split("/", 1)
    bucket_name = bucket_name.strip()
    object_key = object_key.strip()
    if not bucket_name or not object_key:
        return None

    return bucket_name, object_key


def _extract_console_link_parts(value: str) -> tuple[str, str] | None:
    cleaned = value.strip()
    if not cleaned.startswith("https://s3.console.aws.amazon.com/s3/object/"):
        return None

    parsed = urlparse(cleaned)
    path = parsed.path.strip("/")
    parts = path.split("/", 3)
    if len(parts) < 4:
        return None

    bucket_name = parts[3].strip()
    prefix_values = parse_qs(parsed.query).get("prefix", [])
    object_key = prefix_values[0].strip() if prefix_values else ""
    if not bucket_name or not object_key:
        return None

    return bucket_name, object_key


def normalize_submission_item(item: dict[str, Any], aws_region: str | None = None) -> dict[str, Any]:
    submission_id = str(item.get("submission_id") or "").strip()
    if not submission_id:
        raise ValueError("submission_id is required to normalize ATS submission items")

    bucket_name = str(item.get("bucket_name") or "").strip()
    object_key = str(item.get("object_key") or "").strip()
    resume_link_value = str(item.get("resume_link") or "").strip()
    document_link_value = str(item.get("document_link") or "").strip()

    if not bucket_name or not object_key:
        s3_parts = _parse_s3_uri(resume_link_value) or _parse_s3_uri(document_link_value)
        console_parts = _extract_console_link_parts(resume_link_value) or _extract_console_link_parts(document_link_value)
        parsed_parts = s3_parts or console_parts
        if parsed_parts:
            bucket_name = bucket_name or parsed_parts[0]
            object_key = object_key or parsed_parts[1]

    if not bucket_name:
        bucket_name = _DEFAULT_S3_BUCKET

    if bucket_name and object_key:
        resume_link = _build_console_resume_link(bucket_name, object_key, aws_region)
    elif resume_link_value:
        resume_link = resume_link_value
    elif document_link_value:
        resume_link = document_link_value
    else:
        raise ValueError(f"Unable to derive resume_link for submission_id={submission_id}")

    job_description = str(item.get("job_description") or item.get("jd_text") or "").strip()
    job_role = str(item.get("job_role") or item.get("target_role") or "").strip()
    analysis_mode = str(item.get("analysis_mode") or "").strip()
    if not analysis_mode:
        analysis_mode = "jd" if job_description else "resume_only"

    source = str(item.get("source") or "ats_analysis").strip() or "ats_analysis"
    created_at = str(item.get("created_at") or "").strip()
    if not created_at:
        created_at = datetime.now(timezone.utc).isoformat()

    return {
        "submission_id": submission_id,
        "analysis_mode": analysis_mode,
        "bucket_name": bucket_name,
        "created_at": created_at,
        "job_description": job_description,
        "job_role": job_role,
        "resume_link": resume_link,
        "source": source,
    }


class AtsSubmissionStore:
    """Uploads ATS submission files to S3 and stores metadata in DynamoDB."""

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
    def from_env(cls) -> "AtsSubmissionStore":
        return cls(
            bucket_name=os.getenv("ATS_UPLOADS_S3_BUCKET", ""),
            table_name=os.getenv("ATS_UPLOADS_DDB_TABLE", ""),
            s3_prefix=os.getenv("ATS_UPLOADS_S3_PREFIX", _DEFAULT_S3_PREFIX),
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
        target_role: str,
        jd_text: str,
        source: str = "ats_analysis",
    ) -> StoredSubmission | LocalStoredSubmission | None:
        # Fallback to local filesystem when S3/DynamoDB isn't configured
        if not self.is_configured():
            return self._persist_local_submission(
                file_path=file_path,
                original_filename=original_filename,
                target_role=target_role,
                jd_text=jd_text,
            )

        timestamp = datetime.now(timezone.utc)
        submission_id = uuid4().hex
        safe_filename = _sanitize_filename(original_filename)
        object_key = (
            f"{self.s3_prefix}/{timestamp:%Y-%m-%d}/"
            f"{submission_id}-{safe_filename}"
        )
        resolved_content_type = _guess_content_type(safe_filename, content_type)

        try:
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
                Item=normalize_submission_item(
                    {
                        "submission_id": submission_id,
                        "created_at": timestamp.isoformat(),
                        "analysis_mode": "jd" if jd_text.strip() else "resume_only",
                        "bucket_name": self.bucket_name,
                        "job_description": jd_text.strip(),
                        "job_role": target_role.strip(),
                        "resume_link": resume_link,
                        "source": source,
                    },
                    aws_region=self.aws_region,
                )
            )

            return StoredSubmission(
                submission_id=submission_id,
                bucket_name=self.bucket_name,
                object_key=object_key,
                resume_link=resume_link,
            )
        except Exception as e:
            logger.warning("Cloud storage upload failed (%s). Falling back to local storage.", e)
            return self._persist_local_submission(
                file_path=file_path,
                original_filename=original_filename,
                target_role=target_role,
                jd_text=jd_text,
            )

    def _persist_local_submission(
        self,
        *,
        file_path: Path,
        original_filename: str,
        target_role: str,
        jd_text: str,
    ) -> LocalStoredSubmission:
        """Save submission to local filesystem when cloud storage isn't configured."""
        timestamp = datetime.now(timezone.utc)
        submission_id = uuid4().hex
        safe_filename = _sanitize_filename(original_filename)

        # Determine storage directory (relative to app root)
        app_dir = Path(__file__).resolve().parent.parent
        storage_dir = app_dir / _DEFAULT_LOCAL_STORAGE_DIR / timestamp.strftime("%Y-%m-%d")
        storage_dir.mkdir(parents=True, exist_ok=True)

        # Create metadata file alongside the resume
        local_filename = f"{submission_id}-{safe_filename}"
        dest_path = storage_dir / local_filename

        # Copy the file to local storage
        import shutil
        shutil.copy2(file_path, dest_path)

        # Write metadata file for reference
        metadata_path = storage_dir / f"{submission_id}-metadata.txt"
        try:
            metadata_path.write_text(
                f"submission_id: {submission_id}\n"
                f"original_filename: {original_filename}\n"
                f"target_role: {target_role}\n"
                f"jd_text: {jd_text[:200]}\n"
                f"timestamp: {timestamp.isoformat()}\n"
                f"local_path: {dest_path}\n",
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Failed to write metadata file: %s", e)

        local_link = str(dest_path)
        logger.info(
            "ATS submission stored locally: submission_id=%s path=%s",
            submission_id,
            local_link,
        )

        return LocalStoredSubmission(
            submission_id=submission_id,
            local_path=str(dest_path),
            resume_link=local_link,
        )

    def _create_s3_client(self) -> Any:
        boto3 = importlib.import_module("boto3")
        return boto3.client("s3", region_name=self.aws_region)

    def _create_dynamodb_resource(self) -> Any:
        boto3 = importlib.import_module("boto3")
        return boto3.resource("dynamodb", region_name=self.aws_region)
