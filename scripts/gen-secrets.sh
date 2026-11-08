#!/usr/bin/env bash
# Create random S3 credentials locally (.secrets/, git-ignored) and load them into the cluster as Secrets.
set -euo pipefail
mkdir -p .secrets
if [ ! -f .secrets/s3.env ]; then
  AK="ak$(openssl rand -hex 8)"; SK="$(openssl rand -hex 24)"
  printf 'AWS_ACCESS_KEY_ID=%s\nAWS_SECRET_ACCESS_KEY=%s\n' "$AK" "$SK" > .secrets/s3.env
  cat > .secrets/s3.json <<JSON
{"identities":[{"name":"admin","credentials":[{"accessKey":"$AK","secretKey":"$SK"}],"actions":["Admin","Read","Write","List","Tagging"]}]}
JSON
fi
# shellcheck disable=SC1091
set -a; . .secrets/s3.env; set +a
kubectl -n data create secret generic seaweedfs-s3-config --from-file=s3.json=.secrets/s3.json \
  --dry-run=client -o yaml | kubectl apply -f -
for ns in pipeline app; do
  kubectl -n "$ns" create secret generic s3-credentials \
    --from-literal=AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
    --from-literal=AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
    --dry-run=client -o yaml | kubectl apply -f -
done
