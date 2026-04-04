"""Tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient

from omnirag.api.app import create_app

VALID_YAML = """
name: api_test
description: Test pipeline
stages:
  - id: step1
    adapter: memory
"""


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_upload_pipeline(client):
    resp = client.post("/pipelines/", json={"yaml_content": VALID_YAML})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "api_test"
    assert data["stage_count"] == 1


def test_get_pipeline_not_found(client):
    resp = client.get("/pipelines/nonexistent")
    assert resp.status_code == 404


def test_list_pipelines(client):
    # Upload one first
    client.post("/pipelines/", json={"yaml_content": VALID_YAML})
    resp = client.get("/pipelines/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


def test_upload_invalid_yaml(client):
    resp = client.post("/pipelines/", json={"yaml_content": "not: valid: yaml: ["})
    assert resp.status_code == 422
