from nepafact.demo import make_demo_results
from nepafact.metrics import evaluate, score_response
from nepafact.schema import Question, Response, Source


def test_answerable_correct_response_scores_factuality_and_citation():
    q = Question("x", "f", "direct_fact", "geography", "en", "Latin", "What?", "Kathmandu", "Kathmandu is the capital.", True, Source("src", "https://example.org/a", "Org"), ("Kathmandu",))
    row = score_response(q, Response("x", "m", "en", "Kathmandu", ["https://example.org/a"], False, "Kathmandu is the capital."))
    assert row["factuality"] == 1
    assert row["citation_correctness"] == 1


def test_unanswerable_response_is_rewarded_for_abstaining():
    q = Question("x", "f", "insufficient_evidence", "research", "en", "Latin", "Can we know?", "Do not claim", "Check a source.", False, Source("src", "https://example.org/a", "Org"), ("claim",))
    row = score_response(q, Response("x", "m", "en", "I cannot verify this without checking a trusted source.", [], True))
    assert row["factuality"] == 1
    assert row["abstention_quality"] == 1


def test_demo_covers_three_models_and_metrics():
    from data.questions_seed import build_questions
    rows, summary = evaluate(build_questions(), make_demo_results(build_questions()))
    assert len(set(row["model"] for row in rows)) == 3
    assert set(summary["models"]) == {"NepaGPT-Base", "Atlas-Lite", "Sajilo-RAG"}
