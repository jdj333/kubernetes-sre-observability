"""Small instrumented API. Faults affect only the requesting caller."""
import atexit
import json
import logging
import os
import time

from flask import Flask, Response, jsonify, request
from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST, generate_latest

LOG = logging.getLogger("sre.requests")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def create_app(*, fault_enabled=None, provider=None):
    app = Flask(__name__)
    enabled = (os.getenv("ENABLE_FAULT_INJECTION", "false").lower() == "true"
               if fault_enabled is None else fault_enabled)
    if provider is None:
        provider = TracerProvider(resource=Resource.create({
            "service.name": "sre-api", "service.version": "1.0.0",
            "deployment.environment.name": os.getenv("ENVIRONMENT", "local"),
        }))
        if os.getenv("OTEL_SDK_DISABLED", "false").lower() != "true":
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        atexit.register(provider.shutdown)
    tracer = provider.get_tracer("sre-api")
    registry = CollectorRegistry()
    requests = Counter("sre_http_requests_total", "Completed API requests",
                       ["route", "method", "status_code"], registry=registry)
    duration = Histogram("sre_http_request_duration_seconds", "API request duration",
                         ["route", "method", "status_code"], registry=registry,
                         buckets=(.01, .025, .05, .1, .2, .3, .5, 1, 2, 5))
    inflight = Gauge("sre_http_requests_in_flight", "API requests executing",
                     registry=registry)
    # Initialize bounded label sets, including zero errors before the first failure.
    for code in ("200", "400", "503"):
        requests.labels("/api/work", "GET", code)
        duration.labels("/api/work", "GET", code)
    app.extensions["metrics"] = registry

    @app.get("/healthz")
    @app.get("/readyz")
    def health():
        return jsonify(status="ok")

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(registry), content_type=CONTENT_TYPE_LATEST)

    @app.get("/api/work")
    def work():
        started = time.perf_counter()
        code, latency_ms, injected = 200, 0, False
        inflight.inc()
        with tracer.start_as_current_span(
            "GET /api/work", kind=SpanKind.SERVER, context=propagate.extract(request.headers),
            attributes={"http.request.method": "GET", "http.route": "/api/work"},
        ) as span:
            trace_id = format(span.get_span_context().trace_id, "032x")
            try:
                if enabled:
                    try:
                        latency_ms = int(request.headers.get("X-Demo-Latency-Ms", "0"))
                        error = request.headers.get("X-Demo-Error", "false").lower()
                        if not 0 <= latency_ms <= 2000 or error not in ("true", "false"):
                            raise ValueError
                    except ValueError:
                        code = 400
                        return jsonify(error="Expected latency 0..2000 ms and error true/false"), code
                    injected = latency_ms > 0 or error == "true"
                else:
                    error = "false"
                with tracer.start_as_current_span("simulated_dependency") as dependency:
                    dependency.set_attribute("demo.latency_ms", latency_ms)
                    time.sleep((10 + latency_ms) / 1000)
                    if error == "true":
                        code = 503
                        dependency.set_status(Status(StatusCode.ERROR, "Injected failure"))
                response = jsonify(status="unavailable" if code == 503 else "ok",
                                   trace_id=trace_id, fault_injected=injected)
                response.headers["X-Trace-Id"] = trace_id
                return response, code
            finally:
                elapsed = time.perf_counter() - started
                span.set_attribute("http.response.status_code", code)
                span.set_attribute("demo.fault_injected", injected)
                if code >= 500:
                    span.set_status(Status(StatusCode.ERROR, "Service unavailable"))
                exemplar = {"trace_id": trace_id} if span.get_span_context().trace_flags.sampled else None
                requests.labels("/api/work", "GET", str(code)).inc(exemplar=exemplar)
                duration.labels("/api/work", "GET", str(code)).observe(elapsed, exemplar=exemplar)
                inflight.dec()
                LOG.info(json.dumps({"event": "request", "route": "/api/work", "status": code,
                                     "duration_ms": round(elapsed * 1000, 2), "trace_id": trace_id,
                                     "fault_injected": injected}))
    return app
