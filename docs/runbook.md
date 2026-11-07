# Incident diagnosis runbook

## Budget burn

**Trigger:** `AvailabilityBudgetBurnPage`, `AvailabilityBudgetBurnWarning`, `LatencyBudgetBurnPage`, or `LatencyBudgetBurnWarning`.

1. Confirm the alert's `service` and `slo`. Open the Grafana service dashboard and compare request rate, 5xx ratio, slow-request ratio, and the relevant burn rate. Do not infer customer impact solely from CPU or memory.
2. Inspect both alert windows in Prometheus. A high long-window value and healthy short-window value indicates recovery. An empty result indicates a telemetry problem, not success.
3. Compare latency and errors. HTTP 503 plus an error span points to the simulated dependency fault. Long dependency spans with HTTP 200 indicate injected latency. High active requests can explain queueing.
4. Inspect application logs for a matching time and trace ID. Do not record arbitrary headers or customer data in an incident report.
5. In Grafana Explore select Tempo, choose Trace ID, and paste the ID. The server span contains `http.response.status_code`; its child records `demo.latency_ms`. An exemplar can take you directly to that trace.
6. Stop the fault traffic or wait for its deadline, then run baseline traffic. Request-scoped faults leave no shared switch to reset.
7. Verify new requests return 200, ratios decline, short-window burn clears, and Alertmanager resolves the alert. Historical errors remain in the 30-day budget after recovery.

```bash
# Compose logs
docker compose logs --since=10m app otel-collector tempo

# Kubernetes logs and health
kubectl --context kind-sre-observability -n sre-lab get pods
kubectl --context kind-sre-observability -n sre-lab logs deployment/sre-api --since=10m
kubectl --context kind-sre-observability -n sre-lab describe deployment/sre-api
kubectl --context kind-sre-observability -n sre-lab get events --sort-by=.lastTimestamp

# Recovery traffic
python3 scripts/traffic.py baseline --duration 600
```

Useful PromQL:

```promql
sre:availability:bad_ratio5m / 0.001
sre:availability:bad_ratio1h / 0.001
sre:latency:bad_ratio5m / 0.01
sre:latency:bad_ratio1h / 0.01
sum by (status_code) (rate(sre_http_requests_total{job="sre-api"}[5m]))
```

## Missing telemetry

**Trigger:** `SreApiUnavailable` or `SreApiNoTraffic`.

- Check Prometheus Targets first. `up=0` means scrape failure; no series can mean discovery, relabeling, or deployment failure. Use pod events, DNS, endpoint ports, and the namespace Role to distinguish them.
- In Kubernetes, ensure discovery sees API pods with `app=sre-api` and a container port named `http`. Prometheus scrapes each pod directly, including unready running pods, so a readiness failure does not silently hide a failing target.
- If `up=1` and request counters are flat, start baseline traffic. The no-traffic alert intentionally fires after an idle lab remains idle; it has informational severity.
- If metrics work but traces are absent, inspect the Collector and Tempo logs, confirm the app's OTLP HTTP URL ends in `/v1/traces`, and confirm Tempo's gRPC receiver binds to `0.0.0.0:4317`. Traces expire after 24 hours.
- If Grafana is empty, confirm Prometheus/Tempo datasource health and dashboard provisioning. Wait for two scrapes before expecting rate queries to return useful values.

## Experiment protocol

Use only the dedicated local lab. Record the baseline, fault percentage, duration, expected outcome, start time, first symptom, alert time, mitigation, and recovery. Run one injector at a time when comparing percentages. Ctrl-C stops the generator; up to eight in-flight requests may finish within their timeout.

Do not mute alerts as the mitigation. Do not restart Prometheus to clear history. Preserve evidence and fill out [the postmortem template](postmortem-template.md). Real examples should include measured timings; this repository makes no invented claims about MTTR improvement or production results.
