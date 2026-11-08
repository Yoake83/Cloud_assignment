# Usage: make up   (cluster + storage + images + models + app)   |   make down
SHELL := /bin/bash
CLUSTER   ?= cmdparser
SHARDS    ?= 2
VENV      ?= .venv
PY        := $(VENV)/bin/python
GITHUB_REPO ?= Yoake83/cloud-mini-project
SUBSET    ?=
VERSION   ?= v1
CONFIG    ?= training/config.yaml
export S3_ENDPOINT ?= http://localhost:8333
export GITHUB_REPO
-include .secrets/s3.env
export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY

.PHONY: up down venv venv-train cluster storage images label label-status clean-data fetch-data train train-v2 \
        package eval-teacher eval-base eval-student eval-all release deploy loadtest lint test

# ---------- one-command bring-up from a fresh clone ----------
up: venv cluster images storage models deploy
	@echo "ready: curl -s -XPOST localhost:8080/parse -H 'content-type: application/json' -d '{\"text\":\"what is the weather in london\"}'"

down:
	k3d cluster delete $(CLUSTER)

venv:
	test -d $(VENV) || python3 -m venv $(VENV)
	$(PY) -m pip install -q -r requirements-dev.txt

venv-train: venv
	$(PY) -m pip install -q -r requirements-train.txt

cluster:
	k3d cluster list $(CLUSTER) >/dev/null 2>&1 || k3d cluster create --config cluster/k3d.yaml
	kubectl apply -f k8s/00-namespaces.yaml

images:
	docker build -q -f worker/Dockerfile -t cmdparser-worker:1.0 .
	docker build -q -f service/Dockerfile -t cmdparser-service:1.0 .
	k3d image import -c $(CLUSTER) cmdparser-worker:1.0 cmdparser-service:1.0

storage:
	bash scripts/gen-secrets.sh
	kubectl apply -f k8s/seaweedfs.yaml
	kubectl -n data rollout status deploy/seaweedfs --timeout=300s
	@sleep 8
	$(PY) worker/s3util.py init-buckets
	$(PY) worker/s3util.py put datasets commands_pool.jsonl data/commands_pool.jsonl

models:
	PY=$(PY) bash scripts/load-models.sh

deploy:
	kubectl apply -f k8s/app/
	kubectl -n app rollout status deploy/cmdparser --timeout=600s

# ---------- Task 1: teacher labelling (Ollama must be running on the laptop: OLLAMA_HOST=0.0.0.0 ollama serve) ----------
label:
	sed 's/__SHARDS__/$(SHARDS)/g' k8s/pipeline/label-job.yaml | kubectl apply -f -
	@echo "follow with: make label-status"

label-status:
	kubectl -n pipeline get pods -o wide
	kubectl -n pipeline logs -l job-name=teacher-label --tail=3 --prefix=true

clean-data:
	$(PY) worker/clean.py --out-dir data
	mkdir -p data/teacher && $(PY) worker/s3util.py get-prefix datasets teacher/ data/teacher

# ---------- Task 2: training ----------
train: venv-train
	SUBSET=$(SUBSET) $(PY) training/train.py --config $(CONFIG)

train-v2:
	$(MAKE) train CONFIG=training/config_v2.yaml

package:
	$(PY) training/package.py $(VERSION)

release:
	gh release create $(VERSION) artifacts/model-$(VERSION).tar.gz models/$(VERSION)/model.sha256 \
	  models/$(VERSION)/version.json --title "model $(VERSION)" --notes "Distilled Pythia-70M $(VERSION)" \
	  || gh release upload $(VERSION) artifacts/model-$(VERSION).tar.gz --clobber

eval-teacher:
	$(PY) eval/run_teacher.py --out results/teacher_predictions.jsonl
	$(PY) tools/score.py results/teacher_predictions.jsonl data/validation.jsonl --out results/teacher_validation.json

eval-base:
	$(PY) eval/predict.py --model EleutherAI/pythia-70m --out results/pythia_base_predictions.jsonl
	-$(PY) tools/score.py results/pythia_base_predictions.jsonl data/validation.jsonl --out results/pythia_base_validation.json

eval-student:
	$(PY) eval/predict.py --model artifacts/$(VERSION) --out results/student_$(VERSION)_predictions.jsonl
	$(PY) tools/score.py results/student_$(VERSION)_predictions.jsonl data/validation.jsonl \
	  --out results/student_$(VERSION)_validation.json

eval-all: eval-teacher eval-base eval-student

# ---------- Task 7 ----------
loadtest:
	mkdir -p results
	$(PY) -m pip install -q locust
	$(VENV)/bin/locust -f tools/locustfile.py --headless --users 4 --spawn-rate 4 --run-time 2m \
	  --host http://localhost:8080 --csv results/loadtest

# ---------- quality ----------
lint:
	$(VENV)/bin/ruff check .

test:
	$(VENV)/bin/pytest -q
