"""Data model and validation for the curated NepaFact source registry."""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


REQUIRED_COLUMNS = (
    "source_id",
    "title",
    "publisher",
    "url",
    "domain",
    "access_date",
    "source_type",
    "notes",
)

SUPPORTED_DOMAINS = frozenset(
    {
        "lawcommission.gov.np",
        "dos.gov.np",
        "nsonepal.gov.np",
        "whc.unesco.org",
        "narchives.gov.np",
        "election.gov.np",
        "donidcr.gov.np",
        "nepalpassport.gov.np",
        "mofaga.gov.np",
        "dotm.gov.np",
        "moest.gov.np",
        "neb.gov.np",
        "moecdc.gov.np",
        "ugcnepal.edu.np",
        "moald.gov.np",
        "narc.gov.np",
        "dhm.gov.np",
    }
)

SUPPORTED_RESEARCH_DOMAINS = frozenset(
    {"geography_history", "government_public_services", "education_agriculture"}
)
SUPPORTED_SOURCE_TYPES = frozenset({"government_website", "international_organization"})


@dataclass(frozen=True)
class SourceRecord:
    source_id: str
    title: str
    publisher: str
    url: str
    domain: str
    access_date: date
    source_type: str
    notes: str


@dataclass(frozen=True)
class ValidationIssue:
    row_number: int
    code: str
    message: str


class SourceRegistryError(ValueError):
    """Raised when a source registry cannot be loaded safely."""

    def __init__(self, issues: list[ValidationIssue]):
        self.issues = tuple(issues)
        detail = "; ".join(f"row {i.row_number}: {i.code} ({i.message})" for i in issues)
        super().__init__(detail)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _host_is_supported(url: str) -> bool:
    hostname = urlparse(url).hostname
    if not hostname:
        return False
    hostname = hostname.lower().rstrip(".")
    return any(hostname == domain or hostname.endswith("." + domain) for domain in SUPPORTED_DOMAINS)


def validate_rows(rows: list[dict[str, str]], start_row: int = 2) -> list[ValidationIssue]:
    """Validate parsed CSV rows and return all issues instead of failing early."""
    issues: list[ValidationIssue] = []
    seen_ids: dict[str, int] = {}

    for offset, row in enumerate(rows):
        row_number = start_row + offset
        source_id = _clean(row.get("source_id"))
        title = _clean(row.get("title"))
        publisher = _clean(row.get("publisher"))
        url = _clean(row.get("url"))
        domain = _clean(row.get("domain"))
        access_date = _clean(row.get("access_date"))
        source_type = _clean(row.get("source_type"))

        if not source_id:
            issues.append(ValidationIssue(row_number, "missing_source_id", "source_id is required"))
        elif source_id in seen_ids:
            issues.append(ValidationIssue(row_number, "duplicate_source_id", f"already used on row {seen_ids[source_id]}"))
        else:
            seen_ids[source_id] = row_number

        if not title:
            issues.append(ValidationIssue(row_number, "missing_title", "title is required"))
        if not publisher:
            issues.append(ValidationIssue(row_number, "missing_publisher", "publisher is required"))

        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            issues.append(ValidationIssue(row_number, "invalid_url", "url must be an absolute HTTPS URL"))
        elif not _host_is_supported(url):
            issues.append(ValidationIssue(row_number, "unsupported_domain", f"hostname is not approved: {parsed.hostname}"))

        try:
            date.fromisoformat(access_date)
        except ValueError:
            issues.append(ValidationIssue(row_number, "invalid_access_date", "access_date must be YYYY-MM-DD"))

        if domain not in SUPPORTED_RESEARCH_DOMAINS:
            issues.append(ValidationIssue(row_number, "unsupported_research_domain", f"unknown domain: {domain}"))
        if source_type not in SUPPORTED_SOURCE_TYPES:
            issues.append(ValidationIssue(row_number, "unsupported_source_type", f"unknown source_type: {source_type}"))

    return issues


def validate_source_file(path: str | Path) -> list[ValidationIssue]:
    """Validate a CSV registry without raising; useful for CI and editor feedback."""
    path = Path(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        missing_columns = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
        if missing_columns:
            return [ValidationIssue(1, "missing_columns", ", ".join(missing_columns))]
        return validate_rows(list(reader))


def load_source_file(path: str | Path) -> list[SourceRecord]:
    """Load a valid source registry into typed records."""
    issues = validate_source_file(path)
    if issues:
        raise SourceRegistryError(issues)

    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        SourceRecord(
            source_id=_clean(row["source_id"]),
            title=_clean(row["title"]),
            publisher=_clean(row["publisher"]),
            url=_clean(row["url"]),
            domain=_clean(row["domain"]),
            access_date=date.fromisoformat(_clean(row["access_date"])),
            source_type=_clean(row["source_type"]),
            notes=_clean(row["notes"]),
        )
        for row in rows
    ]


def main(argv: list[str] | None = None) -> int:
    """CLI validator: exit non-zero when the registry is invalid."""
    registry = Path((argv or sys.argv[1:] or ["data/curated/sources.csv"])[0])
    issues = validate_source_file(registry)
    if issues:
        for issue in issues:
            print(f"row {issue.row_number}: {issue.code}: {issue.message}")
        return 1
    print(f"Valid source registry: {registry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
