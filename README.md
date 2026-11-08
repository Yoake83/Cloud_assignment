# Command parser: sequence-level distillation + local Kubernetes deployment

Cloud Computing (CS3081) mini project. Teacher: phi3.5 (Ollama, temperature 0, seed 42). Student: EleutherAI/pythia-70m.
Replace `Yoake83/cloud-mini-project` (Makefile, `GITHUB_REPO`) with your real repository name.

Prerequisites: Docker, k3d, kubectl, Python 3.11, Ollama, GitHub CLI (`gh`), make.

## Quick start (fresh clone, needs the model release to exist)
```
make up        # cluster, SeaweedFS, images, models from the GitHub Release, app behind Traefik on :8080
make test      # unit tests          (make lint for ruff)
make down      # delete the cluster
```
Try it: `curl -s -XPOST localhost:8080/parse -H 'content-type: application/json' -d '{"text":"what is the weather in london"}'`

## Full workflow (how the artefacts were produced)
1. `ollama pull phi3.5`, then run Ollama so the cluster can reach it: `OLLAMA_HOST=0.0.0.0 ollama serve`
2. `make venv cluster images storage` (cluster, SeaweedFS in `data`, buckets `datasets` and `models`, pool uploaded)
3. `make label SHARDS=2` then `make label-status` (workers run in namespace `pipeline`, outputs `datasets/teacher/shard-N.jsonl`)
4. `make clean-data` writes `datasets/v1/train.jsonl` + `train.sha256` and `results/clean_report.json` (the counts table)
5. `make train SUBSET=50` (smoke test), `make train` (v1), `make train-v2` (v2), losses in `training/loss*.csv`
6. `make package VERSION=v1 && make package VERSION=v2` (checksum + upload to bucket `models`), then `make release VERSION=v1` and `VERSION=v2`
7. `make eval-all` (teacher, untrained Pythia-70M, student v1; outputs and score reports in `results/`)
8. `make deploy`, `make loadtest` (Locust, results in `results/`)

## Layout
`cluster/` k3d config, `k8s/` manifests, `worker/` shard worker + `clean.py`, `training/`, `service/` (FastAPI + Dockerfile),
`eval/`, `network/` (subnets, NACL), `tests/`, `.github/workflows/ci.yml`, `results/` (evidence), `report/`.

Model weights are never committed: they live in object storage and in GitHub Release assets.
`models/<v>/model.sha256` is the SHA-256 of the Release asset `model-<v>.tar.gz`.
