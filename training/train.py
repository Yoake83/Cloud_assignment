"""Sequence-level distillation: fine-tune Pythia-70M on the teacher's replies (CPU, PyTorch + Transformers).

  python training/train.py --config training/config.yaml          (SUBSET=50 trains on the first 50 records only)
Every setting comes from the config file; SUBSET is the only other input.
"""
import argparse
import csv
import json
import os
import platform
import random
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "service"))
from promptfmt import build_prompt, build_target  # noqa: E402


def load_records(path, limit):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
            if len(rows) >= limit:
                break
    return rows


def encode(tok, record, max_len):
    """Command: <text>\\nJSON: <teacher JSON><eos>; the loss is computed on the JSON part only."""
    target = json.dumps(json.loads(record["teacher_raw"]), ensure_ascii=False)  # same object, one-line form
    prompt_ids = tok(build_prompt(record["text"]))["input_ids"]
    target_ids = tok(build_target(target))["input_ids"] + [tok.eos_token_id]
    ids = (prompt_ids + target_ids)[:max_len]
    labels = ([-100] * len(prompt_ids) + target_ids)[:max_len]
    return ids, labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="training/config.yaml")
    args = ap.parse_args()
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    import numpy as np
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer, get_linear_schedule_with_warmup

    subset = int(os.environ.get("SUBSET") or 0)
    seed = int(cfg["seed"])
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    transformers.set_seed(seed)
    torch.set_num_threads(max(1, os.cpu_count() or 1))

    for name, mod in (("torch", torch), ("transformers", transformers), ("numpy", np)):
        want = cfg["library_versions"][name]
        if not mod.__version__.startswith(want):
            print(f"WARNING: {name} {mod.__version__} installed, config.yaml says {want}")

    out_dir, loss_csv = cfg["output_dir"], cfg["loss_csv"]
    if subset:
        out_dir, loss_csv = "artifacts/subset-test", "training/loss_subset.csv"
    n = subset or int(cfg["max_train_examples"])
    records = load_records(cfg["train_file"], min(n, int(cfg["max_train_examples"])))
    if not records:
        sys.exit(f"no training records in {cfg['train_file']}; run `make clean-data` first")
    print(f"training {cfg['version']} on {len(records)} records, seed {seed}")

    tok = AutoTokenizer.from_pretrained(cfg["base_model"])
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(cfg["base_model"], torch_dtype=torch.float32)

    examples = [encode(tok, r, int(cfg["max_seq_length"])) for r in records]
    bs = int(cfg["batch_size"])
    steps = ((len(examples) + bs - 1) // bs) * int(cfg["epochs"])
    opt = torch.optim.AdamW(model.parameters(), lr=float(cfg["learning_rate"]), weight_decay=float(cfg["weight_decay"]))
    sched = get_linear_schedule_with_warmup(opt, int(steps * float(cfg["warmup_ratio"])), steps)
    gen = torch.Generator().manual_seed(seed)

    def collate(batch):
        width = max(len(i) for i, _ in batch)
        ids = torch.full((len(batch), width), tok.pad_token_id)
        lab = torch.full((len(batch), width), -100)
        att = torch.zeros((len(batch), width), dtype=torch.long)
        for r, (i, la) in enumerate(batch):
            ids[r, :len(i)] = torch.tensor(i)
            lab[r, :len(la)] = torch.tensor(la)
            att[r, :len(i)] = 1
        return ids, att, lab

    loader = torch.utils.data.DataLoader(examples, batch_size=bs, shuffle=True, generator=gen, collate_fn=collate)
    os.makedirs(os.path.dirname(loss_csv) or ".", exist_ok=True)
    losses = []
    model.train()
    for epoch in range(1, int(cfg["epochs"]) + 1):
        total, count = 0.0, 0
        for ids, att, lab in loader:
            loss = model(input_ids=ids, attention_mask=att, labels=lab).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
            total += loss.item()
            count += 1
        losses.append(total / count)
        print(f"epoch {epoch}/{cfg['epochs']}  train loss {losses[-1]:.4f}", flush=True)
    with open(loss_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["epoch", "train_loss"])
        for e, v in enumerate(losses, 1):
            w.writerow([e, f"{v:.6f}"])

    os.makedirs(out_dir, exist_ok=True)
    model.save_pretrained(out_dir)
    tok.save_pretrained(out_dir)
    info = {
        "version": cfg["version"], "base_model": cfg["base_model"], "seed": seed,
        "learning_rate": cfg["learning_rate"], "batch_size": bs, "epochs": cfg["epochs"],
        "max_seq_length": cfg["max_seq_length"], "training_records": len(records),
        "final_train_loss": round(losses[-1], 6),
        "libraries": {"python": platform.python_version(), "torch": torch.__version__,
                      "transformers": transformers.__version__, "numpy": np.__version__},
    }
    with open(os.path.join(out_dir, "version.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)
        f.write("\n")
    print("saved model to", out_dir)


if __name__ == "__main__":
    main()
