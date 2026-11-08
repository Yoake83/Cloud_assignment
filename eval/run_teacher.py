"""Run the teacher (same prompt and settings as Task 1) on data/validation.jsonl."""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "worker"))
import teacher  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data/validation.jsonl")
ap.add_argument("--prompt", default="prompts/teacher_prompt.txt")
ap.add_argument("--out", default="results/teacher_predictions.jsonl")
a = ap.parse_args()

template = teacher.load_prompt(a.prompt)
os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
with open(a.data, encoding="utf-8") as f, open(a.out, "w", encoding="utf-8") as out:
    for line in f:
        if not line.strip():
            continue
        row = json.loads(line)
        raw = teacher.ask(template, row["text"])
        out.write(json.dumps({"id": row["id"], "prediction": raw}, ensure_ascii=False) + "\n")
        print(row["id"], raw, flush=True)
