import json
import logging

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON
from opentelemetry.trace import StatusCode
from app.main import create_app


@pytest.fixture
def setup():
    exporter = InMemorySpanExporter()
    provider = TracerProvider(sampler=ALWAYS_ON)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    app = create_app(fault_enabled=True, provider=provider)
    yield app.test_client(), app.extensions["metrics"], exporter
    provider.shutdown()


def test_healthy_and_errors_are_counted(setup):
    client, registry, exporter = setup
    assert client.get("/api/work").status_code == 200
    response = client.get("/api/work", headers={"X-Demo-Error": "true"})
    assert response.status_code == 503
    labels = {"route": "/api/work", "method": "GET", "status_code": "503"}
    assert registry.get_sample_value("sre_http_requests_total", labels) == 1
    assert registry.get_sample_value("sre_http_requests_in_flight") == 0
    assert exporter.get_finished_spans()[-1].status.status_code == StatusCode.ERROR


def test_faults_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_FAULT_INJECTION", raising=False)
    provider = TracerProvider()
    client = create_app(provider=provider).test_client()
    response = client.get("/api/work", headers={"X-Demo-Error": "true", "X-Demo-Latency-Ms": "2000"})
    assert response.status_code == 200
    assert response.json["fault_injected"] is False
    provider.shutdown()


def test_latency_enters_slow_bucket(setup):
    client, registry, _ = setup
    assert client.get("/api/work", headers={"X-Demo-Latency-Ms": "350"}).status_code == 200
    labels = {"route": "/api/work", "method": "GET", "status_code": "200"}
    assert registry.get_sample_value("sre_http_request_duration_seconds_bucket", {**labels, "le": "0.3"}) == 0
    assert registry.get_sample_value("sre_http_request_duration_seconds_count", labels) == 1


@pytest.mark.parametrize("headers", [
    {"X-Demo-Latency-Ms": "-1"}, {"X-Demo-Latency-Ms": "2001"},
    {"X-Demo-Latency-Ms": "nan"}, {"X-Demo-Error": "maybe"},
])
def test_invalid_fault_input(setup, headers):
    client, registry, _ = setup
    assert client.get("/api/work", headers=headers).status_code == 400
    assert registry.get_sample_value("sre_http_requests_in_flight") == 0


def test_probes_and_unknown_routes_do_not_pollute_sli(setup):
    client, registry, _ = setup
    for path in ("/healthz", "/readyz", "/metrics", "/unknown/123"):
        client.get(path)
    for code in ("200", "400", "503"):
        assert registry.get_sample_value("sre_http_requests_total", {
            "route": "/api/work", "method": "GET", "status_code": code}) == 0


def test_trace_context_logs_and_exemplars(setup, caplog):
    client, _, exporter = setup
    trace_id = "1234567890abcdef1234567890abcdef"
    with caplog.at_level(logging.INFO, logger="sre.requests"):
        response = client.get("/api/work", headers={
            "traceparent": f"00-{trace_id}-1234567890abcdef-01"})
    assert response.headers["X-Trace-Id"] == trace_id
    server = exporter.get_finished_spans()[-1]
    assert server.parent.span_id == int("1234567890abcdef", 16)
    assert json.loads(caplog.records[-1].message)["trace_id"] == trace_id
    metrics = client.get("/metrics")
    assert "application/openmetrics-text" in metrics.content_type
    assert f'trace_id="{trace_id}"' in metrics.text


def test_fault_does_not_persist(setup):
    client, _, _ = setup
    assert client.get("/api/work", headers={"X-Demo-Error": "true"}).status_code == 503
    assert client.get("/api/work").status_code == 200
