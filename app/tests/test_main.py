"""Unit tests for the Skybyte greeting service."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_hello_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200


def test_hello_returns_json(client):
    response = client.get("/")
    data = response.get_json()
    assert data["message"] == "Hello, Candidate"
    assert data["version"] == "1.0.0"


def test_healthz_returns_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.data == b"ok"


def test_metrics_endpoint_exists(client):
    response = client.get("/metrics")
    assert response.status_code == 200


def test_metrics_contains_request_counter(client):
    client.get("/")
    response = client.get("/metrics")
    assert b"http_requests_total" in response.data


def test_metrics_contains_duration_histogram(client):
    client.get("/")
    response = client.get("/metrics")
    assert b"http_request_duration_seconds" in response.data
