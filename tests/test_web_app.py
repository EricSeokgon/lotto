"""FastAPI 앱 인스턴스 및 /health 엔드포인트 테스트."""

from fastapi.testclient import TestClient


def test_app_instance_is_fastapi():
    """앱이 FastAPI 인스턴스인지 확인."""
    from fastapi import FastAPI

    from lotto.web.app import app

    assert isinstance(app, FastAPI)


def test_health_returns_200():
    """/health 가 200을 반환하는지 확인."""
    from lotto.web.app import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_has_status_field():
    """/health 응답에 필수 필드가 있는지 확인."""
    from lotto.web.app import app

    client = TestClient(app)
    response = client.get("/health")
    data = response.json()
    assert "status" in data
    assert "data_csv_exists" in data
    assert "stats_json_exists" in data


def test_health_status_is_string():
    """/health 의 status 필드가 문자열인지 확인."""
    from lotto.web.app import app

    client = TestClient(app)
    response = client.get("/health")
    data = response.json()
    assert data["status"] in ("ok", "degraded")
