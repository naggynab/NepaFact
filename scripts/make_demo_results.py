from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nepafact.demo import make_demo_results  # noqa: E402
from nepafact.schema import load_questions, write_jsonl  # noqa: E402


if __name__ == "__main__":
    questions_path = ROOT / "data" / "questions.jsonl"
    if not questions_path.exists():
        raise SystemExit("Run scripts/build_dataset.py first.")
    responses = make_demo_results(load_questions(questions_path))
    write_jsonl(ROOT / "results" / "demo_results.jsonl", (r.__dict__ for r in responses))
    print(f"Wrote {len(responses)} demo responses for {len(set(r.model for r in responses))} models.")
