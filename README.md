# NepaFact

NepaFact is a reproducible benchmark for multilingual factuality and robustness in Nepal-focused AI answers. It evaluates English, Nepali, and Romanized Nepali questions across direct facts, false assumptions, pressure to conform, and evidence-insufficiency cases.

The repository includes:

- a deterministic seed set of 100 original benchmark items, each with English, Nepali, and Romanized Nepali forms;
- trusted-source and expected-evidence metadata for every item;
- an evaluator with factuality, citation, abstention, and evidence-grounding metrics;
- a synthetic three-model result set for testing the complete workflow without API keys;
- a Streamlit dashboard for filtering questions, inspecting answers, and comparing models;
- a report scaffold and tests.

## Quick start

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dashboard]"
python scripts\build_dataset.py
python scripts\make_demo_results.py
streamlit run dashboard\app.py
```

Run the evaluator directly:

```powershell
python -m nepafact.evaluate --questions data\questions.jsonl --responses results\demo_results.jsonl --out results\demo_metrics.json
pytest
```

The demo results are intentionally imperfect. They exercise citation errors, over-confident answers to abstention items, and performance differences across language forms. Replace them with real model outputs using the same JSONL schema.

## Response schema

Each line in a response file is one model answer:

```json
{"item_id":"NF-001-direct_fact","model":"my-model","language":"ne","answer":"...","citations":["https://..."],"abstained":false,"evidence_quote":"..."}
```

The benchmark does not claim that string matching is a complete factuality judge. Automatic scores are screening metrics. Human review should be used for the final reported sample; the dashboard supports a `human_label` and `human_notes` field in response files.

## Research protocol

1. Build the benchmark with `python scripts/build_dataset.py` and commit the resulting `data/questions.jsonl`.
2. Run each model with the same prompt wrapper and temperature policy.
3. Save one JSONL response file per run or combine them in one file.
4. Evaluate with `python -m nepafact.evaluate`.
5. Inspect the dashboard and sample at least 20% of responses for human agreement.
6. Record model versions, retrieval settings, evaluator version, and date in the report.

## Scope and safety

Sources are intentionally drawn from public institutional material and stable reference pages. Health, law, and education questions are benchmark claims, not personal advice. A model should defer or recommend checking an authoritative source when the benchmark marks an item `answerable: false`.

## Project layout

```text
data/questions_seed.py     Curated facts and language variants
data/questions.jsonl       Generated, reviewable benchmark file
nepafact/                  Loading, scoring, and demo generation
dashboard/app.py           Streamlit dashboard
scripts/                   Reproducible data/result commands
reports/research_report.md Research write-up scaffold
tests/                     Unit tests
```
