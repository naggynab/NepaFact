from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class Source:
    title: str
    url: str
    publisher: str


@dataclass(frozen=True)
class Question:
    item_id: str
    fact_id: str
    category: str
    domain: str
    language: str
    script: str
    question: str
    gold_answer: str
    expected_evidence: str
    answerable: bool
    source: Source
    keywords: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class Response:
    item_id: str
    model: str
    language: str
    answer: str
    citations: list[str] = field(default_factory=list)
    abstained: bool = False
    evidence_quote: str = ""
    human_label: str = ""
    human_notes: str = ""


def question_to_dict(question: Question) -> dict[str, Any]:
    record = asdict(question)
    record["source"] = asdict(question.source)
    record["keywords"] = list(question.keywords)
    return record


def question_from_dict(record: dict[str, Any]) -> Question:
    source = record["source"]
    return Question(
        item_id=record["item_id"], fact_id=record["fact_id"],
        category=record["category"], domain=record["domain"],
        language=record["language"], script=record["script"],
        question=record["question"], gold_answer=record["gold_answer"],
        expected_evidence=record["expected_evidence"],
        answerable=bool(record["answerable"]),
        source=Source(**source), keywords=tuple(record.get("keywords", [])),
    )


def response_from_dict(record: dict[str, Any]) -> Response:
    return Response(
        item_id=record["item_id"], model=record["model"],
        language=record.get("language", ""), answer=record.get("answer", ""),
        citations=list(record.get("citations", [])),
        abstained=bool(record.get("abstained", False)),
        evidence_quote=record.get("evidence_quote", ""),
        human_label=record.get("human_label", ""),
        human_notes=record.get("human_notes", ""),
    )


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_questions(path: str | Path) -> list[Question]:
    return [question_from_dict(row) for row in load_jsonl(path)]


def load_responses(path: str | Path) -> list[Response]:
    return [response_from_dict(row) for row in load_jsonl(path)]


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
