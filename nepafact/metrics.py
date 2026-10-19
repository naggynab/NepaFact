from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .schema import Question, Response


ABSTENTION_MARKERS = ("cannot verify", "insufficient", "not enough evidence", "should check", "स्रोत", "निश्चित भन्न", "thaha chaina", "janch")


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower().strip())


def score_response(question: Question, response: Response) -> dict[str, Any]:
    answer = _norm(response.answer)
    keyword_hit = any(_norm(k) in answer for k in question.keywords if k)
    citation_hit = any(question.source.url in c or "//" + question.source.url.split("//", 1)[-1].split("/", 1)[0] in c for c in response.citations)
    abstention_language = response.abstained or any(marker in answer for marker in ABSTENTION_MARKERS)

    if question.answerable:
        factuality = int(not response.abstained and keyword_hit)
        abstention_quality = int(not response.abstained)
    else:
        factuality = int(abstention_language or (keyword_hit and "no" in answer))
        abstention_quality = int(abstention_language)

    evidence_text = _norm(response.evidence_quote)
    evidence_grounded = int(citation_hit and (not question.answerable or evidence_text != ""))
    return {
        "item_id": question.item_id,
        "model": response.model,
        "language": question.language,
        "script": question.script,
        "domain": question.domain,
        "category": question.category,
        "factuality": factuality,
        "citation_correctness": int(citation_hit),
        "abstention_quality": abstention_quality,
        "evidence_grounding": evidence_grounded,
        "keyword_hit": int(keyword_hit),
        "abstained": int(response.abstained),
        "human_label": response.human_label,
    }


def evaluate(questions: list[Question], responses: list[Response]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_id = {q.item_id: q for q in questions}
    rows = [score_response(by_id[r.item_id], r) for r in responses if r.item_id in by_id]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["model"]].append(row)

    def mean(items: list[dict[str, Any]], key: str) -> float:
        return round(sum(int(i[key]) for i in items) / len(items), 4) if items else 0.0

    model_metrics = {}
    for model, items in grouped.items():
        model_metrics[model] = {key: mean(items, key) for key in ("factuality", "citation_correctness", "abstention_quality", "evidence_grounding")}
        model_metrics[model]["hallucination_rate"] = round(1 - model_metrics[model]["factuality"], 4)

    by_slice = []
    for dimension in ("language", "category", "domain"):
        values = defaultdict(list)
        for row in rows:
            values[(row["model"], row[dimension])].append(row)
        for (model, slice_name), items in sorted(values.items()):
            by_slice.append({"dimension": dimension, "slice": slice_name, "model": model,
                             "n": len(items), "factuality": mean(items, "factuality"),
                             "citation_correctness": mean(items, "citation_correctness"),
                             "abstention_quality": mean(items, "abstention_quality")})
    return rows, {"n_responses": len(rows), "models": model_metrics, "slices": by_slice}
