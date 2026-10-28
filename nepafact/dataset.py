"""Data models and validation for the first NepaFact benchmark items."""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

from .source_registry import load_source_file


ITEM_COLUMNS = (
    "item_id", "base_fact_id", "source_id", "domain", "question_type",
    "language", "script", "question", "correct_answer", "acceptable_answers",
    "evidence_quote", "should_abstain", "difficulty", "reviewer_status", "notes",
)
ANNOTATION_COLUMNS = (
    "item_id", "reviewer_status", "translation_status", "source_check",
    "evidence_check", "answerability_check", "notes",
)
SUPPORTED_LANGUAGES = frozenset({"en", "ne", "ne_rom"})
EXPECTED_SCRIPTS = {"en": "Latin", "ne": "Devanagari", "ne_rom": "Latin"}
SUPPORTED_QUESTION_TYPES = frozenset({"direct", "false_premise", "unanswerable", "noisy"})
SUPPORTED_DOMAINS = frozenset({"geography_history", "government_public_services", "education_agriculture"})
SUPPORTED_DIFFICULTIES = frozenset({"easy", "medium", "hard"})
SUPPORTED_REVIEW_STATUSES = frozenset({"draft", "needs_review", "human_verified"})


@dataclass(frozen=True)
class BenchmarkItem:
    item_id: str
    base_fact_id: str
    source_id: str
    domain: str
    question_type: str
    language: str
    script: str
    question: str
    correct_answer: str
    acceptable_answers: tuple[str, ...]
    evidence_quote: str
    should_abstain: bool
    difficulty: str
    reviewer_status: str
    notes: str


@dataclass(frozen=True)
class Annotation:
    item_id: str
    reviewer_status: str
    translation_status: str
    source_check: str
    evidence_check: str
    answerability_check: str
    notes: str


@dataclass(frozen=True)
class ValidationIssue:
    file: str
    row_number: int
    code: str
    message: str


class DatasetValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = tuple(issues)
        detail = "; ".join(f"{i.file}:{i.row_number} {i.code} ({i.message})" for i in issues)
        super().__init__(detail)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _required_columns(fieldnames: list[str] | None, required: tuple[str, ...], file: str) -> list[ValidationIssue]:
    names = set(fieldnames or [])
    missing = [column for column in required if column not in names]
    return [ValidationIssue(file, 1, "missing_columns", ", ".join(missing))] if missing else []


def _parse_bool(value: str) -> bool | None:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return None


def validate_item_rows(rows: list[dict[str, str]], source_ids: set[str], file: str = "items.csv") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: dict[str, int] = {}
    for index, row in enumerate(rows, start=2):
        item_id = _clean(row.get("item_id"))
        if not item_id:
            issues.append(ValidationIssue(file, index, "missing_item_id", "item_id is required"))
        elif item_id in seen:
            issues.append(ValidationIssue(file, index, "duplicate_item_id", f"already used on row {seen[item_id]}"))
        else:
            seen[item_id] = index

        for column in ("base_fact_id", "question", "correct_answer", "evidence_quote", "notes"):
            if not _clean(row.get(column)):
                issues.append(ValidationIssue(file, index, f"missing_{column}", f"{column} is required"))

        source_id = _clean(row.get("source_id"))
        if source_id not in source_ids:
            issues.append(ValidationIssue(file, index, "unknown_source_id", f"source_id is not in source registry: {source_id}"))

        domain = _clean(row.get("domain"))
        if domain not in SUPPORTED_DOMAINS:
            issues.append(ValidationIssue(file, index, "unsupported_domain", domain))

        question_type = _clean(row.get("question_type"))
        if question_type not in SUPPORTED_QUESTION_TYPES:
            issues.append(ValidationIssue(file, index, "unsupported_question_type", question_type))

        language = _clean(row.get("language"))
        if language not in SUPPORTED_LANGUAGES:
            issues.append(ValidationIssue(file, index, "unsupported_language", language))
        elif _clean(row.get("script")) != EXPECTED_SCRIPTS[language]:
            issues.append(ValidationIssue(file, index, "script_language_mismatch", language))

        acceptable = [answer.strip() for answer in _clean(row.get("acceptable_answers")).split("|") if answer.strip()]
        if not acceptable:
            issues.append(ValidationIssue(file, index, "missing_acceptable_answers", "at least one answer is required"))

        should_abstain = _parse_bool(_clean(row.get("should_abstain")))
        if should_abstain is None:
            issues.append(ValidationIssue(file, index, "invalid_should_abstain", "use true or false"))
        elif question_type == "unanswerable" and not should_abstain:
            issues.append(ValidationIssue(file, index, "unanswerable_must_abstain", "unanswerable items must set should_abstain=true"))

        if _clean(row.get("difficulty")) not in SUPPORTED_DIFFICULTIES:
            issues.append(ValidationIssue(file, index, "unsupported_difficulty", _clean(row.get("difficulty"))))
        if _clean(row.get("reviewer_status")) not in SUPPORTED_REVIEW_STATUSES:
            issues.append(ValidationIssue(file, index, "unsupported_reviewer_status", _clean(row.get("reviewer_status"))))

    return issues


def validate_annotation_rows(rows: list[dict[str, str]], item_ids: set[str], file: str = "annotations.csv") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen: dict[str, int] = {}
    for index, row in enumerate(rows, start=2):
        item_id = _clean(row.get("item_id"))
        if not item_id:
            issues.append(ValidationIssue(file, index, "missing_annotation_item_id", "item_id is required"))
        elif item_id in seen:
            issues.append(ValidationIssue(file, index, "duplicate_annotation_item_id", f"already used on row {seen[item_id]}"))
        else:
            seen[item_id] = index
        if item_id and item_id not in item_ids:
            issues.append(ValidationIssue(file, index, "unknown_annotation_item_id", item_id))
        if _clean(row.get("reviewer_status")) not in SUPPORTED_REVIEW_STATUSES:
            issues.append(ValidationIssue(file, index, "unsupported_annotation_status", _clean(row.get("reviewer_status"))))
        for column in ("translation_status", "source_check", "evidence_check", "answerability_check", "notes"):
            if not _clean(row.get(column)):
                issues.append(ValidationIssue(file, index, f"missing_annotation_{column}", f"{column} is required"))
    missing = item_ids - set(seen)
    if missing:
        issues.append(ValidationIssue(file, 1, "missing_annotations", ", ".join(sorted(missing))))
    return issues


def validate_dataset(items_path: str | Path = "data/curated/items.csv", annotations_path: str | Path = "data/curated/annotations.csv", sources_path: str | Path = "data/curated/sources.csv") -> list[ValidationIssue]:
    """Validate items, annotations, and source references together."""
    source_records = load_source_file(sources_path)
    source_ids = {source.source_id for source in source_records}
    with Path(items_path).open("r", encoding="utf-8", newline="") as handle:
        item_reader = csv.DictReader(handle, skipinitialspace=True)
        issues = _required_columns(item_reader.fieldnames, ITEM_COLUMNS, "items.csv")
        item_rows = list(item_reader)
    if issues:
        return issues
    issues.extend(validate_item_rows(item_rows, source_ids))
    item_ids = {_clean(row.get("item_id")) for row in item_rows if _clean(row.get("item_id"))}

    with Path(annotations_path).open("r", encoding="utf-8", newline="") as handle:
        annotation_reader = csv.DictReader(handle, skipinitialspace=True)
        annotation_issues = _required_columns(annotation_reader.fieldnames, ANNOTATION_COLUMNS, "annotations.csv")
        annotation_rows = list(annotation_reader)
    issues.extend(annotation_issues)
    if not annotation_issues:
        issues.extend(validate_annotation_rows(annotation_rows, item_ids))
    return issues


def load_items_file(path: str | Path = "data/curated/items.csv", sources_path: str | Path = "data/curated/sources.csv") -> list[BenchmarkItem]:
    issues = validate_dataset(path, "data/curated/annotations.csv", sources_path)
    if issues:
        raise DatasetValidationError(issues)
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, skipinitialspace=True))
    return [
        BenchmarkItem(
            item_id=_clean(row["item_id"]), base_fact_id=_clean(row["base_fact_id"]),
            source_id=_clean(row["source_id"]), domain=_clean(row["domain"]),
            question_type=_clean(row["question_type"]), language=_clean(row["language"]),
            script=_clean(row["script"]), question=_clean(row["question"]),
            correct_answer=_clean(row["correct_answer"]),
            acceptable_answers=tuple(answer.strip() for answer in row["acceptable_answers"].split("|") if answer.strip()),
            evidence_quote=_clean(row["evidence_quote"]), should_abstain=_parse_bool(row["should_abstain"]) is True,
            difficulty=_clean(row["difficulty"]), reviewer_status=_clean(row["reviewer_status"]), notes=_clean(row["notes"]),
        )
        for row in rows
    ]


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    issues = validate_dataset(*(args + ["data/curated/items.csv", "data/curated/annotations.csv", "data/curated/sources.csv"])[:3])
    if issues:
        for issue in issues:
            print(f"{issue.file}:{issue.row_number}: {issue.code}: {issue.message}")
        return 1
    print("Valid five-item NepaFact dataset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
