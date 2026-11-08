# Command parser: sequence-level distillation + local Kubernetes deployment

Cloud Computing (CS3081) mini project.
Author: Arunima Das, roll number 230101011.

Teacher: phi3.5 (Ollama, temperature 0, seed 42). Student: EleutherAI/pythia-70m.
Replace `Yoake83/cloud-mini-project` (Makefile, `GITHUB_REPO`) with your real repository name.

## What the project does
- The parser reads one short English command and returns one JSON object with the keys `intent`, `date`, `time` and `place`.
  `intent` is one of eight fixed values. Each slot is copied exactly from the command, or it is `null`. It is never converted or invented.
- **Sequence-level distillation:** the small model is trained on the teacher's written reply (`teacher_raw`), not on the teacher's probabilities.
  Logit distillation does not fit, because Ollama returns text only and phi3.5 and Pythia-70M do not share a tokenizer.
- **Sharding:** two workers split the 3,000-command pool by line number. Line number (from 0) mod shard count picks the shard,
  so every command is labelled exactly once. Output: `datasets/teacher/shard-N.jsonl`.
- **Weights** live in object storage (bucket `models`) and in GitHub Release assets (`model-<version>.tar.gz`).
  They are never committed to Git and never baked into the image. `models/<v>/model.sha256` is the SHA-256 of the Release asset.
- **Network rules** (`network/nacl.json`, `network/subnets.md`): a NACL is stateless, so replies need their own rules.
  The deny for 198.51.100.0/24 is rule 100, lower than the allows for ports 80 and 443 (rules 200 and 210), so it matches first.

## Prerequisites
Ubuntu (run in WSL on Windows; the Makefile is bash and does not run in PowerShell), Docker (Docker Desktop with WSL integration),
k3d, kubectl, Python 3.11, Ollama, GitHub CLI (`gh`), make, zstd (the Ollama installer fails without it), openssl, curl.

```bash
sudo apt update
sudo apt install -y make zstd curl openssl python3-venv python3-pip
```

Keep the project on the Linux file system, for example `~/230101011`, not under `/mnt/c`. Creating the virtual environment on the Windows drive is very slow.

## Quick start (fresh clone, needs the model release to exist)
```
make up        # cluster, SeaweedFS, images, models from the GitHub Release, app behind Traefik on :8080
make test      # unit tests          (make lint for ruff)
make down      # delete the cluster
```
Try it: `curl -s -XPOST localhost:8080/parse -H 'content-type: application/json' -d '{"text":"what is the weather in london"}'`

## Full workflow (how the artefacts were produced)
1. Install and start the teacher:
   ```
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull phi3.5
   curl http://127.0.0.1:11434/api/tags      # Ollama must answer here (run `ollama serve` if it is not running)
   ```
2. `make venv` for the dev tools, then `make test` and `make lint`.
   `make venv-train` installs the pinned CPU-only torch wheel (torch 2.4.1) used for training and evaluation.
3. `make cluster storage` starts the k3d cluster and SeaweedFS, creates the buckets `datasets` and `models`, uploads the pool,
   and writes the S3 credentials to `.secrets/s3.env`.
4. **Teacher labelling with two shard workers, one per terminal.** Run this in both terminals and change only `SHARD_INDEX`
   (0 in the first, 1 in the second):
   ```
   cd ~/230101011
   source .venv/bin/activate
   set -a; source .secrets/s3.env; set +a
   export S3_ENDPOINT=http://localhost:8333
   export OLLAMA_URL=http://127.0.0.1:11434
   export PROMPT_FILE=$PWD/prompts/teacher_prompt.txt
   export SHARD_COUNT=2
   export SHARD_INDEX=0                      # 1 in the second terminal
   python worker/worker.py
   ```
   Temperature 0 and seed 42 are fixed in `worker/teacher.py`. Each worker labels 1500 commands, checkpoints every 25 commands,
   and resumes from its own shard file if it is started again. Labelling 3000 commands on CPU takes a long time.
   (The same step also runs inside the cluster as an Indexed Job with `make images`, `make label SHARDS=2` and `make label-status`;
   the manual route above is the one used for the results below.)
5. `make clean-data` writes `data/train.jsonl`, `data/train.sha256` and `results/clean_report.json` (the counts table).
   It stops if any command is missing or repeated across the shards.
6. `make train SUBSET=50` (smoke test), `make train` (v1), `make train-v2` (v2). Losses go to `training/loss*.csv`.
7. `make package VERSION=v1 && make package VERSION=v2` (checksum + upload to bucket `models`), then `make release VERSION=v1` and `VERSION=v2`
   (needs `gh auth login`).
8. `make eval-all` (teacher, untrained Pythia-70M, student v1; outputs and score reports in `results/`).
   The untrained model is expected to fail the validity gate; `make eval-base` ignores that failure on purpose.
9. `make deploy`, `make loadtest` (Locust, results in `results/`).

## Checks and results measured so far
| Item | Result |
|---|---|
| Command pool / validation file | 3000 lines / 100 lines (SHA-256 checksums saved) |
| Unit tests | 18 passed, 1 warning |
| Ruff | all checks passed |
| Sample network rules (`tools/nacl_sim.py --check`) | 6 of 6 correct (100 percent) |
| Untrained Pythia-70M on the 100 validation commands | 0.0 for JSON validity, intent, date, time, place and full frame (right-looking JSON, wrong keys) |
| `score.py --min-validity 95` on that file | exit status 1 (local run, not a GitHub Actions run) |
| One local generation, 64 tokens | 0.6 s after a 3.1 s model load (not the service latency) |

Training, packaging, the Actions run and the load test are not listed here until they have been measured.

## Layout
`cluster/` k3d config, `k8s/` manifests, `worker/` shard worker + `clean.py`, `training/`, `service/` (FastAPI + Dockerfile),
`eval/`, `network/` (subnets, NACL), `tests/`, `.github/workflows/ci.yml`, `results/` (evidence), `report/`.

Model weights are never committed: they live in object storage and in GitHub Release assets.
`models/<v>/model.sha256` is the SHA-256 of the Release asset `model-<v>.tar.gz`.