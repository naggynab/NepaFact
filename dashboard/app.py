from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nepafact.demo import make_demo_results  # noqa: E402
from nepafact.metrics import evaluate  # noqa: E402
from nepafact.schema import load_questions, load_responses, Response  # noqa: E402


st.set_page_config(page_title="NepaFact dashboard", page_icon="🇳🇵", layout="wide")
st.title("🇳🇵 NepaFact")
st.caption("Multilingual factuality and robustness benchmark for Nepal-focused AI")

questions_path = ROOT / "data" / "questions.jsonl"
if not questions_path.exists():
    st.error("Dataset not found. Run `python scripts/build_dataset.py` first.")
    st.stop()
questions = load_questions(questions_path)

uploaded = st.sidebar.file_uploader("Upload response JSONL", type=["jsonl", "json"])
if uploaded:
    temp = ROOT / ".streamlit_uploaded.jsonl"
    temp.write_bytes(uploaded.getvalue())
    responses = load_responses(temp)
    st.sidebar.success(f"Loaded {len(responses)} responses")
else:
    responses = make_demo_results(questions)
    st.sidebar.info("Showing deterministic demo results")

rows, summary = evaluate(questions, responses)

models = sorted({r["model"] for r in rows})
languages = sorted({r["language"] for r in rows})
categories = sorted({r["category"] for r in rows})
model_filter = st.sidebar.multiselect("Models", models, default=models)
language_filter = st.sidebar.multiselect("Language forms", languages, default=languages)
category_filter = st.sidebar.multiselect("Evaluation categories", categories, default=categories)

filtered_rows = [r for r in rows if r["model"] in model_filter and r["language"] in language_filter and r["category"] in category_filter]
filtered_ids = {r["item_id"] for r in filtered_rows}

cols = st.columns(5)
for col, label, key in zip(cols, ("Responses", "Factuality", "Citation correctness", "Abstention quality", "Hallucination rate"), ("n_responses", "factuality", "citation_correctness", "abstention_quality", "hallucination_rate")):
    if key == "n_responses":
        value = len(filtered_rows)
    else:
        value = round(sum(r[key] for r in filtered_rows) / len(filtered_rows) * 100, 1) if filtered_rows else 0
        value = f"{value}%"
    col.metric(label, value)

st.subheader("Model comparison")
if filtered_rows:
    import pandas as pd
    import plotly.express as px
    frame = pd.DataFrame(filtered_rows)
    compare = frame.groupby("model")[["factuality", "citation_correctness", "abstention_quality", "evidence_grounding"]].mean().reset_index()
    long = compare.melt(id_vars="model", var_name="metric", value_name="score")
    st.plotly_chart(px.bar(long, x="model", y="score", color="metric", barmode="group", range_y=[0, 1]), use_container_width=True)
    st.dataframe(compare.set_index("model").style.format("{:.1%}"), use_container_width=True)
else:
    st.info("No responses match the current filters.")

st.subheader("Inspect benchmark items and answers")
search = st.text_input("Search question, answer, or item id")
question_by_id = {q.item_id: q for q in questions}
response_by_id = {(r.item_id, r.model): r for r in responses}
shown = []
for row in filtered_rows:
    q = question_by_id[row["item_id"]]
    r = response_by_id.get((q.item_id, row["model"]))
    haystack = " ".join((q.item_id, q.question, r.answer if r else "")).lower()
    if search and search.lower() not in haystack:
        continue
    shown.append((q, r, row))
for q, r, row in shown[:100]:
    with st.expander(f"{q.item_id} · {q.language} · {q.category} · {row['model']}"):
        st.markdown(f"**Question:** {q.question}")
        st.markdown(f"**Model answer:** {r.answer if r else '—'}")
        st.markdown(f"**Gold answer:** {q.gold_answer}")
        st.markdown(f"**Expected evidence:** {q.expected_evidence}")
        st.markdown(f"**Trusted source:** [{q.source.title}]({q.source.url})")
        st.write({"factuality": row["factuality"], "citation_correctness": row["citation_correctness"], "abstention_quality": row["abstention_quality"], "evidence_grounding": row["evidence_grounding"]})

st.caption(f"Showing {min(len(shown), 100)} of {len(shown)} matching response rows. Automatic metrics are screening signals; use human review for publication.")
