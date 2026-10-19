from __future__ import annotations

import argparse
import json
from pathlib import Path

from .metrics import evaluate
from .schema import load_questions, load_responses


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate NepaFact model responses")
    parser.add_argument("--questions", default="data/questions.jsonl")
    parser.add_argument("--responses", required=True)
    parser.add_argument("--out", default="results/metrics.json")
    args = parser.parse_args()

    rows, summary = evaluate(load_questions(args.questions), load_responses(args.responses))
    output = {"summary": summary, "rows": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
