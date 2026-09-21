"""Allowlisted operational telemetry; never inspect bodies, headers or exceptions."""
from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from functools import wraps
from uuid import uuid4

request_id = ContextVar("tender_request_id", default=None)
LOGGER = logging.getLogger("tender.operations")
OPERATIONS = {"http", "ted", "tool", "retrieval", "agent"}
OUTCOMES = {"success", "failure", "MODEL_ANSWERED", "MODEL_UNAVAILABLE", "EMPTY_CLAIMS",
            "MODEL_OUTPUT_REJECTED", "INSUFFICIENT_EVIDENCE", "DETERMINISTIC_FALLBACK"}
ROUTES = {"/live", "/ready", "/health", "/ask", "/ingest"}


class Telemetry:
    def __init__(self, tracer=None, meter=None):
        self.tracer = tracer
        self.counter = meter.create_counter("tender.operations", unit="1") if meter else None
        self.duration = meter.create_histogram("tender.operation.duration", unit="s") if meter else None

    @contextmanager
    def operation(self, operation, route="other"):
        operation = operation if operation in OPERATIONS else "other"
        route = route if route in ROUTES else "other"
        attributes = {"operation": operation, "route": route}
        result = {"outcome": "success", "status_code": 0}
        started = time.perf_counter()
        span_context = self.tracer.start_as_current_span(
            operation, attributes=attributes, record_exception=False, set_status_on_exception=False
        ) if self.tracer else nullcontext(None)
        with span_context as span:
            try:
                yield result
            except BaseException:
                result["outcome"] = "failure"
                raise
            finally:
                elapsed = time.perf_counter() - started
                outcome = result["outcome"] if result["outcome"] in OUTCOMES else "failure"
                status = result["status_code"]
                status = status if isinstance(status, int) and 100 <= status <= 599 else 0
                labels = {**attributes, "outcome": outcome, "status_class": f"{status // 100}xx"}
                # Instrumentation must not turn successful work into a failure.
                try:
                    if span:
                        span.set_attributes(labels)
                        if outcome in {"failure", "MODEL_UNAVAILABLE"}:
                            from opentelemetry.trace import StatusCode
                            span.set_status(StatusCode.ERROR)
                    if self.counter:
                        self.counter.add(1, labels)
                        self.duration.record(elapsed, labels)
                    event = {"schema_version": 1, **labels, "status_code": status,
                             "duration_ms": round(elapsed * 1000, 3), "request_id": request_id.get()}
                    if span and span.get_span_context().is_valid:
                        event["trace_id"] = format(span.get_span_context().trace_id, "032x")
                    LOGGER.info(json.dumps(event, separators=(",", ":")))
                except Exception:
                    # No recursive telemetry, raw exception text or user data.
                    pass


telemetry = Telemetry()


def instrument(operation):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with telemetry.operation(operation) as event:
                result = function(*args, **kwargs)
                if operation == "agent":
                    event["outcome"] = result.answer_status
                return result
        return wrapped
    return decorate


def configure():
    """Called at app lifespan startup. OTLP is opt-in, local JSON is always on."""
    global telemetry
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False
    providers = []
    endpoint = os.environ.get("TENDER_OTLP_ENDPOINT")
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Explicit resource avoids automatic host/process/environment collection.
        resource = Resource({"service.name": "tender-ai", "service.version": "2.1.0"})
        traces = TracerProvider(resource=resource)
        traces.add_span_processor(BatchSpanProcessor(
            OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces", timeout=3),
            max_queue_size=512, max_export_batch_size=64,
        ))
        meters = MeterProvider(resource=resource, metric_readers=[PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=endpoint.rstrip("/") + "/v1/metrics", timeout=3),
            export_interval_millis=60000,
        )])
        providers = [meters, traces]
        telemetry = Telemetry(traces.get_tracer("tender-ai"), meters.get_meter("tender-ai"))

    def shutdown():
        global telemetry
        for provider in providers:
            provider.shutdown()
        telemetry = Telemetry()
        LOGGER.removeHandler(handler)
        handler.close()
    return shutdown


class RequestTelemetry:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        # Generate server-owned IDs: never echo attacker-controlled header values.
        identifier = uuid4().hex
        token = request_id.set(identifier)
        try:
            with telemetry.operation("http", scope.get("path")) as event:
                async def send_response(message):
                    if message["type"] == "http.response.start":
                        event["status_code"] = message["status"]
                        if message["status"] >= 500:
                            event["outcome"] = "failure"
                        message["headers"] = [*message.get("headers", []),
                                              (b"x-request-id", identifier.encode()),
                                              (b"cache-control", b"no-store")]
                    await send(message)
                try:
                    await self.app(scope, receive, send_response)
                except Exception:
                    if not event["status_code"]:
                        await send_response({"type": "http.response.start", "status": 500,
                                             "headers": [(b"content-type", b"application/json")]})
                        await send({"type": "http.response.body", "body": b'{"detail":"Request failed"}'})
                    else:
                        raise
        finally:
            request_id.reset(token)
