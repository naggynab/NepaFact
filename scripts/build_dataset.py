from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nepafact.schema import question_to_dict, write_jsonl  # noqa: E402
from data.questions_seed import build_questions  # noqa: E402


if __name__ == "__main__":
    questions = build_questions()
    write_jsonl(ROOT / "data" / "questions.jsonl", (question_to_dict(q) for q in questions))
    print(f"Wrote {len(questions)} multilingual benchmark items from {len(questions) // 12} facts.")
