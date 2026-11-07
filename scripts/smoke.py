#!/usr/bin/env python3
"""End-to-end checks against the loopback Compose or port-forwarded kind stack."""
import json
from http.client import HTTPException
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def get(url, headers=None):
    with urlopen(Request(url, headers=headers or {}), timeout=5) as response:
        return response.read()


def eventually(check, label, seconds=120):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            if check():
                print(f"PASS: {label}")
                return
        except (URLError, OSError, HTTPException, ValueError, KeyError) as error:
            last = error
        time.sleep(2)
    raise AssertionError(f"Timed out: {label}; last error: {last}")


def query(expr):
    return json.loads(get("http://127.0.0.1:9090/api/v1/query?" + urlencode({"query": expr})))["data"]["result"]


def main():
    eventually(lambda: get("http://127.0.0.1:8000/readyz"), "API ready")
    eventually(lambda: get("http://127.0.0.1:3000/api/health"), "Grafana ready")
    eventually(lambda: get("http://127.0.0.1:9093/-/ready"), "Alertmanager ready")
    response = json.loads(get("http://127.0.0.1:8000/api/work"))
    trace_id = response["trace_id"]
    try:
        get("http://127.0.0.1:8000/api/work", {"X-Demo-Error": "true"})
        raise AssertionError("Fault injection did not return 503")
    except HTTPError as error:
        assert error.code == 503, error.code
        error.close()
    get("http://127.0.0.1:8000/api/work", {"X-Demo-Latency-Ms": "350"})
    eventually(lambda: query('up{job="sre-api"} == 1'), "Prometheus scrapes API")
    # Generate a fresh failure after a scrape so the rate sees a counter increase.
    try:
        get("http://127.0.0.1:8000/api/work", {"X-Demo-Error": "true"})
    except HTTPError as error:
        assert error.code == 503
        error.close()
    eventually(lambda: query('sre_http_requests_total{status_code="503"} >= 2'), "Errors reach metrics")
    eventually(lambda: query('sre:availability:bad_ratio5m > 0'), "Recording rules evaluate")
    eventually(lambda: b"simulated_dependency" in get(
        f"http://127.0.0.1:3000/api/datasources/proxy/uid/tempo/api/traces/{trace_id}",
        {"Accept": "application/json"}), "App → Collector → Tempo → Grafana trace retrieval")
    dashboard = json.loads(get("http://127.0.0.1:3000/api/dashboards/uid/sre-overview"))
    assert len(dashboard["dashboard"]["panels"]) == 12
    print("PASS: provisioned 12-panel SRE dashboard")


if __name__ == "__main__":
    main()
