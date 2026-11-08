"""Clean the teacher's raw replies and write datasets/v1/train.jsonl + train.sha256.

Rejection reasons (each record is counted under the FIRST reason that applies, so
input = a + b + c + d + duplicates + kept always holds):
  a  reply is not valid JSON
  b  reply is not an object with exactly the keys intent, date, time, place
  c  intent is not one of the eight
  d  a slot value is neither null nor (non-empty) text that appears in the command
  duplicates  same command text as an earlier valid record (the smallest id is kept)
Duplicates are looked for among valid records only, so a command is not lost because its
first copy happened to get a bad reply. Kept records are written in id order.

Usage
  python worker/clean.py                      read shards from s3://datasets/teacher/, upload v1/train.*
  python worker/clean.py --shards-dir DIR     read shard-*.jsonl from a local directory (no upload)
"""
import argparse
import glob
import hashlib
import json
import os
import sys

KEYS = ("intent", "date", "time", "place")
SLOTS = ("date", "time", "place")
INTENTS = {
    "alarm_set", "alarm_query", "calendar_set", "calendar_query",
    "calendar_remove", "weather_query", "datetime_query", "recommendation_events",
}


def reject_reason(rec):
    """Return 'a'..'d' for the first rule the record breaks, or None if it is good."""
    try:
        obj = json.loads(rec["teacher_raw"])
    except (ValueError, TypeError):
        return "a"
    if not isinstance(obj, dict) or sorted(obj.keys()) != sorted(KEYS):
        return "b"
    if not isinstance(obj["intent"], str) or obj["intent"] not in INTENTS:
        return "c"
    text = rec["text"].lower()
    for k in SLOTS:
        v = obj[k]
        if v is None:
            continue
        if not isinstance(v, str) or not v.strip() or v.lower() not in text:
            return "d"
    return None


def clean(records):
    counts = {"input": len(records), "a": 0, "b": 0, "c": 0, "d": 0, "duplicates": 0, "kept": 0}
    kept, seen = [], set()
    for rec in sorted(records, key=lambda r: r["id"]):
        why = reject_reason(rec)
        if why:
            counts[why] += 1
        elif rec["text"] in seen:
            counts["duplicates"] += 1
        else:
            seen.add(rec["text"])
            kept.append({"id": rec["id"], "text": rec["text"], "teacher_raw": rec["teacher_raw"]})
            counts["kept"] += 1
    total = sum(counts[k] for k in ("a", "b", "c", "d", "duplicates", "kept"))
    assert total == counts["input"], f"counts do not add up: {counts}"
    return kept, counts


def coverage(pool_ids, records):
    ids = [r["id"] for r in records]
    missing = sorted(set(pool_ids) - set(ids))
    repeated = sorted({i for i in ids if ids.count(i) > 1})
    return missing, repeated


def serialise(kept):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept).encode("utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--shards-dir", help="read shard-*.jsonl from this directory instead of object storage")
    ap.add_argument("--pool", default="data/commands_pool.jsonl", help="local pool file, used to check coverage")
    ap.add_argument("--out-dir", default="data", help="local copy of train.jsonl / train.sha256 goes here")
    ap.add_argument("--report", default="results/clean_report.json")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--allow-partial", action="store_true",
                    help="trial runs only: warn about unlabelled ids instead of stopping")
    a = ap.parse_args()

    records = []
    s3 = None
    if a.shards_dir:
        for path in sorted(glob.glob(os.path.join(a.shards_dir, "shard-*.jsonl"))):
            with open(path, encoding="utf-8") as f:
                records += [json.loads(line) for line in f if line.strip()]
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import s3util

        s3 = s3util.client()
        for key in s3util.list_keys(s3, "datasets", "teacher/"):
            if key.endswith(".jsonl"):
                records += [json.loads(x) for x in s3util.get_text(s3, "datasets", key).splitlines() if x.strip()]

    with open(a.pool, encoding="utf-8") as f:
        pool_ids = [json.loads(line)["id"] for line in f if line.strip()]
    missing, repeated = coverage(pool_ids, records)
    if repeated or (missing and not a.allow_partial):
        sys.exit(f"shard coverage problem: {len(missing)} missing ids (e.g. {missing[:3]}), "
                 f"{len(repeated)} repeated ids (e.g. {repeated[:3]})")

    if missing:
        print(f"WARNING: partial run, {len(missing)} commands not labelled yet (not valid for submission)")
    kept, counts = clean(records)
    data = serialise(kept)
    digest = hashlib.sha256(data).hexdigest()

    os.makedirs(a.out_dir, exist_ok=True)
    with open(os.path.join(a.out_dir, "train.jsonl"), "wb") as f:
        f.write(data)
    with open(os.path.join(a.out_dir, "train.sha256"), "w", encoding="utf-8") as f:
        f.write(f"{digest}  train.jsonl\n")
    os.makedirs(os.path.dirname(a.report) or ".", exist_ok=True)
    with open(a.report, "w", encoding="utf-8") as f:
        json.dump({**counts, "sha256": digest}, f, indent=2)
        f.write("\n")

    if s3 is not None and not a.no_upload:
        s3util.put_bytes(s3, "datasets", "v1/train.jsonl", data)
        s3util.put_bytes(s3, "datasets", "v1/train.sha256", f"{digest}  train.jsonl\n".encode())
        print("uploaded s3://datasets/v1/train.jsonl and train.sha256")

    print(json.dumps(counts, indent=2))
    print("sha256", digest)


if __name__ == "__main__":
    main()
