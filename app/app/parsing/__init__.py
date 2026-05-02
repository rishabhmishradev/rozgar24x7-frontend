"""Parsing layer package for resume processing."""

from .jd_parser import parse_job_description
from .resume_parser import ParsingError, ResumeParser, ResumeParseResult, SectionError
from .text_extractor import ExtractionError, UnsupportedFileTypeError

try:
	from .pipeline import LayoutAwareResumeParser
except Exception:  # pragma: no cover - optional heavy deps may be absent in lightweight envs
	LayoutAwareResumeParser = None  # type: ignore[assignment]

__all__ = [
	"ResumeParser",
	"ResumeParseResult",
	"LayoutAwareResumeParser",
	"ParsingError",
	"SectionError",
	"ExtractionError",
	"UnsupportedFileTypeError",
	"parse_job_description",
]

