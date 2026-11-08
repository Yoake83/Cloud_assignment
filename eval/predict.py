"""Run a Pythia model (trained student, or the untrained base model) on a labelled file.

  python eval/predict.py --model artifacts/v1 --out results/student_v1_predictions.jsonl
  python eval/predict.py --model EleutherAI/pythia-70m --out results/pythia_base_predictions.jsonl
Writes {"id": ..., "prediction": "<raw model output>"} lines for tools/score.py.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "service"))
from inference import Student  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True, help="local directory or Hugging Face model id")
ap.add_argument("--data", default="data/validation.jsonl")
ap.add_argument("--out", required=True)
ap.add_argument("--max-new-tokens", type=int, default=80)
a = ap.parse_args()

model = Student(a.model)
os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
with open(a.data, encoding="utf-8") as f, open(a.out, "w", encoding="utf-8") as out:
    for line in f:
        if not line.strip():
            continue
        row = json.loads(line)
        pred = model.generate(row["text"], a.max_new_tokens)
        out.write(json.dumps({"id": row["id"], "prediction": pred}, ensure_ascii=False) + "\n")
print("wrote", a.out)
