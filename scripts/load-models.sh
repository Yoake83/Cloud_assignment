#!/usr/bin/env bash
# Put model versions v1 and v2 into the `models` bucket. Uses artifacts/<v>/ if you trained locally,
# otherwise downloads the GitHub Release asset (public repo) and unpacks it.
set -euo pipefail
: "${GITHUB_REPO:?set GITHUB_REPO, e.g. Yoake83/cloud-mini-project}"
PY="${PY:-python}"
for v in v1 v2; do
  if [ ! -f "artifacts/$v/model.safetensors" ] && [ ! -f "artifacts/$v/pytorch_model.bin" ]; then
    mkdir -p "artifacts/$v"
    echo "downloading release $v from $GITHUB_REPO"
    curl -fL "https://github.com/$GITHUB_REPO/releases/download/$v/model-$v.tar.gz" -o "artifacts/model-$v.tar.gz"
    tar -xzf "artifacts/model-$v.tar.gz" -C "artifacts/$v"
    curl -fL "https://github.com/$GITHUB_REPO/releases/download/$v/model.sha256" -o "artifacts/$v/model.sha256"
  fi
  $PY worker/s3util.py put-dir models "$v" "artifacts/$v"
done
