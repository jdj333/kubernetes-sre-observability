#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for tool in docker kind kubectl python3; do
  command -v "$tool" >/dev/null || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done
cluster=sre-observability
context=kind-sre-observability
if ! kind get clusters | grep -Fxq "$cluster"; then
  kind create cluster --name "$cluster" --image kindest/node:v1.33.4
fi
docker build -t sre-api:local .
kind load docker-image sre-api:local --name "$cluster"
kubectl --context "$context" apply -f k8s/namespace.yml
if ! kubectl --context "$context" -n sre-lab get secret grafana-admin >/dev/null 2>&1; then
  # Pass the generated password via a protected file, never a command argument or log.
  password_file=$(mktemp)
  trap 'rm -f "$password_file"' EXIT
  python3 -c 'import secrets; print(secrets.token_urlsafe(32), end="")' > "$password_file"
  kubectl --context "$context" -n sre-lab create secret generic grafana-admin --from-file="password=$password_file"
fi
kubectl --context "$context" apply -k .
# A repeated build uses the same local image tag; force the API to load the new image.
kubectl --context "$context" -n sre-lab rollout restart deployment/sre-api
for deployment in sre-api prometheus grafana tempo otel-collector alertmanager; do
  kubectl --context "$context" -n sre-lab rollout status "deployment/$deployment" --timeout=180s
done
echo 'Ready. Run bash scripts/port-forward.sh in a separate terminal.'
