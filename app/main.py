"""Skybyte greeting service."""
import os
import signal
import threading
from flask import Flask, jsonify, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

VERSION = "1.0.0"
API_TOKEN = os.environ.get("API_TOKEN", "")

# ── Observability ────────────────────────────────────────────
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)

# ── Graceful shutdown ────────────────────────────────────────
_shutdown_event = threading.Event()

def handle_sigterm(sig, frame):
    """Signal handler: stop accepting new requests and drain."""
    _shutdown_event.set()

signal.signal(signal.SIGTERM, handle_sigterm)

# ── Middleware ───────────────────────────────────────────────
@app.before_request
def check_shutdown():
    if _shutdown_event.is_set():
        return jsonify({"error": "server is shutting down"}), 503

# ── Routes ───────────────────────────────────────────────────
@app.route("/")
def hello():
    with REQUEST_DURATION.labels(method="GET", path="/").time():
        REQUEST_COUNT.labels(method="GET", path="/", status="200").inc()
        return jsonify({"message": "Hello, Candidate", "version": VERSION})

@app.route("/healthz")
def healthz():
    if _shutdown_event.is_set():
        return "shutting down", 503
    return "ok", 200

@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
