#!/usr/bin/env bash
set -euo pipefail
pids=()
cleanup() { for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT
trap 'exit 130' INT TERM
for mapping in app:8000 prometheus:9090 grafana:3000 alertmanager:9093; do
  service=${mapping%:*}
  port=${mapping#*:}
  kubectl --context kind-sre-observability -n sre-lab port-forward --address 127.0.0.1 "service/$service" "$port:$port" &
  pids+=("$!")
done
# Portable polling also exits if any port-forward process dies.
while true; do
  for pid in "${pids[@]}"; do kill -0 "$pid" 2>/dev/null || exit 1; done
  sleep 1
done
