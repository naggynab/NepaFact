"""Conservative data-review checks and report generation for NepaFact."""

from __future__ import annotations

import csv
import re
import sys
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .dataset import EXPECTED_SCRIPTS, SUPPORTED_LANGUAGES, SUPPORTED_QUESTION_TYPES, validate_dataset
from .source_registry import load_source_file


STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"
STATUS_NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


@dataclass(frozen=True)
class ReviewRecord:
    item_id: str
    base_fact_id: str
    language: str
    review_status: str
    warning_codes: tuple[str, ...]
    warning_reasons: tuple[str, ...]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _normalized_question(question: str) -> str:
    return re.sub(r"[^\w]+", " ", question.casefold(), flags=re.UNICODE).strip()


def _has_devanagari(text: str) -> bool:
    return any("\u0900" <= char <= "\u097f" for char in text)


def _question_type_warnings(row: dict[str, str]) -> list[tuple[str, str]]:
    question_type = _clean(row.get("question_type"))
    question = _clean(row.get("question"))
    should_abstain = _clean(row.get("should_abstain")).lower()
    warnings: list[tuple[str, str]] = []
    if question_type not in SUPPORTED_QUESTION_TYPES:
        return [("wrong_question_type", f"Unsupported question_type: {question_type or '<empty>'}.")]
    if question_type == "false_premise":
        markers = ("monarchy", "राजतन्त्र", "rajtantra")
        if not any(marker.casefold() in question.casefold() for marker in markers):
            warnings.append(("wrong_question_type", "false_premise is not visibly framed with a false-premise marker."))
    if question_type == "noisy" and "??" not in question and "Rastrya" not in question:
        warnings.append(("wrong_question_type", "noisy item has no recorded punctuation or spelling-noise marker."))
    if question_type == "unanswerable" and should_abstain != "true":
        warnings.append(("incorrect_abstention", "unanswerable item must set should_abstain=true."))
    if question_type != "unanswerable" and should_abstain == "true":
        warnings.append(("incorrect_abstention", "answerable question type is marked should_abstain=true."))
    return warnings


def _script_warnings(row: dict[str, str]) -> list[tuple[str, str]]:
    language = _clean(row.get("language"))
    script = _clean(row.get("script"))
    question = _clean(row.get("question"))
    if language not in SUPPORTED_LANGUAGES:
        return [("incorrect_language_code", f"Unsupported language code: {language or '<empty>'}.")]
    warnings: list[tuple[str, str]] = []
    if script != EXPECTED_SCRIPTS[language]:
        warnings.append(("incorrect_language_code", f"Language {language} requires script {EXPECTED_SCRIPTS[language]}, found {script or '<empty>'}."))
    if language == "ne_rom" and _has_devanagari(question):
        warnings.append(("romanized_consistency", "Romanized Nepali question contains Devanagari characters."))
    return warnings


def _obvious_character_warnings(row: dict[str, str]) -> list[tuple[str, str]]:
    language = _clean(row.get("language"))
    text = " ".join((_clean(row.get("question")), _clean(row.get("correct_answer"))))
    allowed = set("āīūṛṅñḍṭḷśṣ’'-")
    suspicious = []
    for char in text:
        if char.isspace() or char.isalnum() or unicodedata.category(char)[0] in {"P", "S"} or char in allowed:
            continue
        if language in {"en", "ne_rom"} or not ("\u0900" <= char <= "\u097f"):
            suspicious.append(char)
    if suspicious:
        unique = "".join(dict.fromkeys(suspicious))
        return [("spelling_or_character_problem", f"Unexpected character(s) require review: {unique!r}.")]
    return []


def review_item_rows(item_rows: list[dict[str, str]], annotation_rows: list[dict[str, str]], source_ids: set[str]) -> list[ReviewRecord]:
    warnings_by_item: dict[str, list[tuple[str, str]]] = {_clean(row.get("item_id")): [] for row in item_rows}
    row_by_id = {_clean(row.get("item_id")): row for row in item_rows}
    annotation_by_id = {_clean(row.get("item_id")): row for row in annotation_rows}

    by_base: dict[str, list[dict[str, str]]] = {}
    by_language: dict[str, list[dict[str, str]]] = {}
    for row in item_rows:
        item_id = _clean(row.get("item_id"))
        by_base.setdefault(_clean(row.get("base_fact_id")), []).append(row)
        by_language.setdefault(_clean(row.get("language")), []).append(row)
        warnings_by_item[item_id].extend(_script_warnings(row))
        warnings_by_item[item_id].extend(_obvious_character_warnings(row))
        warnings_by_item[item_id].extend(_question_type_warnings(row))
        if not _clean(row.get("evidence_quote")):
            warnings_by_item[item_id].append(("missing_evidence_quote", "Evidence quotation is empty."))
        if _clean(row.get("source_id")) not in source_ids:
            warnings_by_item[item_id].append(("unsupported_source_reference", "source_id is not present in the verified source registry."))
        annotation = annotation_by_id.get(item_id)
        if not annotation:
            warnings_by_item[item_id].append(("missing_review_annotation", "No review annotation row exists."))
        else:
            if _clean(annotation.get("translation_status")) != "human_verified":
                warnings_by_item[item_id].append(("meaning_requires_fluent_review", "English/Nepali meaning and translation naturalness have not been confirmed by a fluent Nepali speaker."))
            if _clean(annotation.get("spelling_check")) in {"", "pending", "not_checked"}:
                warnings_by_item[item_id].append(("spelling_requires_human_review", "Spelling, idiom, and cultural naturalness require fluent-speaker review; no approval is inferred."))
            warnings_by_item[item_id].append(("answer_support_requires_review", "Answer-to-evidence entailment has not been human-confirmed; source presence alone is not approval."))

    for base_fact_id, rows in by_base.items():
        languages = {_clean(row.get("language")) for row in rows}
        missing = sorted(SUPPORTED_LANGUAGES - languages)
        if missing:
            for row in rows:
                warnings_by_item[_clean(row.get("item_id"))].append(("missing_translation", f"Base fact {base_fact_id} is missing language form(s): {', '.join(missing)}."))

    for language, rows in by_language.items():
        for index, left in enumerate(rows):
            left_id = _clean(left.get("item_id"))
            left_question = _normalized_question(_clean(left.get("question")))
            for right in rows[index + 1:]:
                right_id = _clean(right.get("item_id"))
                right_question = _normalized_question(_clean(right.get("question")))
                if left_question and left_question == right_question:
                    reason = f"Exact duplicate question in language {language}: {right_id}."
                    warnings_by_item[left_id].append(("duplicate_question", reason))
                    warnings_by_item[right_id].append(("duplicate_question", f"Exact duplicate question in language {language}: {left_id}."))
                elif left_question and SequenceMatcher(None, left_question, right_question).ratio() >= 0.92:
                    reason = f"Near-duplicate question in language {language}: {right_id}."
                    warnings_by_item[left_id].append(("near_duplicate_question", reason))
                    warnings_by_item[right_id].append(("near_duplicate_question", f"Near-duplicate question in language {language}: {left_id}."))

    records: list[ReviewRecord] = []
    for item_id, row in row_by_id.items():
        warnings = warnings_by_item[item_id]
        hard_codes = {"incorrect_language_code", "unsupported_source_reference", "missing_evidence_quote", "wrong_question_type", "incorrect_abstention", "duplicate_question"}
        status = STATUS_REJECTED if any(code in hard_codes for code, _ in warnings) else STATUS_NEEDS_HUMAN_REVIEW
        if not warnings and _clean(row.get("reviewer_status")) == "human_verified":
            status = STATUS_APPROVED
        records.append(ReviewRecord(item_id, _clean(row.get("base_fact_id")), _clean(row.get("language")), status, tuple(code for code, _ in warnings), tuple(reason for _, reason in warnings)))
    return records


def review_files(items_path: str | Path = "data/curated/items.csv", annotations_path: str | Path = "data/curated/annotations.csv", sources_path: str | Path = "data/curated/sources.csv") -> list[ReviewRecord]:
    issues = validate_dataset(items_path, annotations_path, sources_path)
    if issues:
        raise ValueError("Dataset schema is invalid; run the dataset validator first: " + "; ".join(issue.code for issue in issues))
    with Path(items_path).open("r", encoding="utf-8", newline="") as handle:
        item_rows = list(csv.DictReader(handle, skipinitialspace=True))
    with Path(annotations_path).open("r", encoding="utf-8", newline="") as handle:
        annotation_rows = list(csv.DictReader(handle, skipinitialspace=True))
    source_ids = {source.source_id for source in load_source_file(sources_path)}
    return review_item_rows(item_rows, annotation_rows, source_ids)


def write_report(records: list[ReviewRecord], csv_path: str | Path = "data/curated/review_report.csv", markdown_path: str | Path = "docs/data_review_report.md") -> None:
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("item_id", "base_fact_id", "language", "review_status", "warning_codes", "warning_reasons"))
        for record in records:
            writer.writerow((record.item_id, record.base_fact_id, record.language, record.review_status, "; ".join(record.warning_codes), "; ".join(record.warning_reasons)))

    groups = {status: [record for record in records if record.review_status == status] for status in (STATUS_APPROVED, STATUS_REJECTED, STATUS_NEEDS_HUMAN_REVIEW)}
    lines = ["# NepaFact data-review report", "", "Generated by `python -m nepafact.review`.", "", f"Total items reviewed: {len(records)}", ""]
    for status, title in ((STATUS_APPROVED, "## Approved items"), (STATUS_REJECTED, "## Rejected items"), (STATUS_NEEDS_HUMAN_REVIEW, "## Items needing human review")):
        lines.extend([title, ""])
        if not groups[status]:
            lines.append("None.")
        else:
            for record in groups[status]:
                lines.append(f"- `{record.item_id}` ({record.language})")
                if record.warning_reasons:
                    for code, reason in zip(record.warning_codes, record.warning_reasons):
                        lines.append(f"  - `{code}`: {reason}")
        lines.append("")
    Path(markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(markdown_path).write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    records = review_files(*(args + ["data/curated/items.csv", "data/curated/annotations.csv", "data/curated/sources.csv"])[:3])
    write_report(records)
    counts = {status: sum(record.review_status == status for record in records) for status in (STATUS_APPROVED, STATUS_REJECTED, STATUS_NEEDS_HUMAN_REVIEW)}
    print(f"Review report written: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
