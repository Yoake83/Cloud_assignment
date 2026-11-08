"""Shard worker: label every command whose line number % SHARD_COUNT == SHARD_INDEX with the teacher.

Environment: SHARD_INDEX (from 0), SHARD_COUNT, S3_ENDPOINT, OLLAMA_URL (+ AWS_* credentials from a Secret).
Output: s3://datasets/teacher/shard-<SHARD_INDEX>.jsonl, one line per command:
        {"id": "...", "text": "...", "teacher_raw": "<the teacher's exact reply>"}
The worker checkpoints to object storage and resumes from its own shard object if it is restarted.
"""
import json
import os
import sys
import time

import s3util
import teacher

DATASET_BUCKET = os.environ.get("DATASET_BUCKET", "datasets")
POOL_KEY = os.environ.get("POOL_KEY", "commands_pool.jsonl")
OUT_PREFIX = os.environ.get("OUT_PREFIX", "teacher")
PROMPT_FILE = os.environ.get("PROMPT_FILE", "/app/prompts/teacher_prompt.txt")
CHECKPOINT_EVERY = int(os.environ.get("CHECKPOINT_EVERY", "25"))


def shard_items(lines, shard_index, shard_count):
    """Commands whose line number (counting from 0) leaves remainder shard_index modulo shard_count."""
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ValueError(f"bad shard settings: index={shard_index} count={shard_count}")
    items = []
    for n, line in enumerate(lines):
        if n % shard_count == shard_index and line.strip():
            items.append(json.loads(line))
    return items


def dump(records):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records).encode("utf-8")


def main():
    index = int(os.environ["SHARD_INDEX"])
    count = int(os.environ["SHARD_COUNT"])
    s3 = s3util.client()
    out_key = f"{OUT_PREFIX}/shard-{index}.jsonl"
    template = teacher.load_prompt(PROMPT_FILE)

    pool_lines = s3util.get_text(s3, DATASET_BUCKET, POOL_KEY).splitlines()
    items = shard_items(pool_lines, index, count)
    print(f"shard {index}/{count}: {len(items)} commands", flush=True)

    done = {}
    if s3util.exists(s3, DATASET_BUCKET, out_key):
        for line in s3util.get_text(s3, DATASET_BUCKET, out_key).splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec["id"]] = rec
        print(f"resuming: {len(done)} already labelled", flush=True)

    t0 = time.time()
    new = 0
    for item in items:
        if item["id"] in done:
            continue
        raw = teacher.ask(template, item["text"])
        done[item["id"]] = {"id": item["id"], "text": item["text"], "teacher_raw": raw}
        new += 1
        if new % CHECKPOINT_EVERY == 0:
            ordered = [done[i["id"]] for i in items if i["id"] in done]
            s3util.put_bytes(s3, DATASET_BUCKET, out_key, dump(ordered))
            rate = new / (time.time() - t0)
            print(f"checkpoint: {len(ordered)}/{len(items)} ({rate:.2f} cmds/s)", flush=True)

    ordered = [done[i["id"]] for i in items]
    s3util.put_bytes(s3, DATASET_BUCKET, out_key, dump(ordered))
    print(f"finished shard {index}: wrote s3://{DATASET_BUCKET}/{out_key} ({len(ordered)} records)", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyError as exc:
        sys.exit(f"missing environment variable {exc}")
