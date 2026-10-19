from __future__ import annotations

from nepafact.schema import Question, Response


def make_demo_results(questions: list[Question]) -> list[Response]:
    """Create deterministic imperfect outputs so the dashboard works offline."""
    results = []
    for q in questions:
        for model in ("NepaGPT-Base", "Atlas-Lite", "Sajilo-RAG"):
            if model == "NepaGPT-Base":
                answer = q.gold_answer if q.answerable else "I cannot verify this without checking a trusted source."
                citations = [q.source.url]
                abstained = not q.answerable
                evidence = q.expected_evidence
            elif model == "Atlas-Lite":
                answer = q.gold_answer if q.answerable and q.language != "ro" else ("Yes, that is correct." if not q.answerable else "I am not sure; please check an official source.")
                citations = ["https://example.com/unsupported"] if q.category == "false_assumption" else []
                abstained = (not q.answerable and q.language == "ro") or (q.answerable and q.language == "ro")
                evidence = ""
            else:
                answer = q.gold_answer if q.answerable else "The claim should be verified against the official source."
                citations = [q.source.url] if q.category != "pressure_to_conform" else []
                abstained = not q.answerable
                evidence = q.expected_evidence if q.language != "ne" else ""
            results.append(Response(q.item_id, model, q.language, answer, citations, abstained, evidence))
    return results
