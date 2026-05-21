"""SPEC-LOTTO-006: /api/draws 페이지네이션 및 회차 범위 필터 테스트.

REQ-PAGE-001/002/003/004 검증.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _make_mock_draws(start: int = 1, end: int = 100) -> list[MagicMock]:
    """드로 결과 mock 객체를 회차 범위로 생성합니다."""
    draws = []
    for i in range(start, end + 1):
        m = MagicMock()
        m.drwNo = i
        m.model_dump.return_value = {"drwNo": i, "date": "2024-01-01"}
        draws.append(m)
    return draws


def test_draws_default_pagination() -> None:
    """REQ-PAGE-002: 기본 호출 시 페이지네이션 래퍼 응답 구조."""
    from lotto.web.app import app

    with patch("lotto.web.routes.api.get_draws", return_value=_make_mock_draws(1, 100)):
        c = TestClient(app)
        response = c.get("/api/draws")

    assert response.status_code == 200
    body = response.json()
    assert "total" in body
    assert "limit" in body
    assert "offset" in body
    assert "items" in body
    assert body["limit"] == 50  # REQ-PAGE-001 기본값
    assert body["offset"] == 0
    assert isinstance(body["items"], list)


def test_draws_custom_limit() -> None:
    """REQ-PAGE-001: limit 파라미터 적용."""
    from lotto.web.app import app

    with patch("lotto.web.routes.api.get_draws", return_value=_make_mock_draws(1, 100)):
        c = TestClient(app)
        response = c.get("/api/draws?limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 10
    assert len(body["items"]) <= 10


def test_draws_offset() -> None:
    """REQ-PAGE-001: offset 파라미터 적용."""
    from lotto.web.app import app

    with patch("lotto.web.routes.api.get_draws", return_value=_make_mock_draws(1, 100)):
        c = TestClient(app)
        response = c.get("/api/draws?offset=5&limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 5
    # offset=5이면 6번째 회차(drwNo=6)부터 반환
    assert body["items"][0]["drwNo"] == 6


def test_draws_limit_exceeds_max_returns_422() -> None:
    """REQ-PAGE-001 + NFR-PAGE-002: limit 상한(200) 초과는 422."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.get("/api/draws?limit=999")
    assert response.status_code == 422


def test_draws_round_filter_both() -> None:
    """REQ-PAGE-003: from_round + to_round 범위 필터링."""
    from lotto.web.app import app

    with patch("lotto.web.routes.api.get_draws", return_value=_make_mock_draws(1, 100)):
        c = TestClient(app)
        response = c.get("/api/draws?from_round=10&to_round=20")

    assert response.status_code == 200
    body = response.json()
    for item in body["items"]:
        assert 10 <= item["drwNo"] <= 20
    assert body["total"] == 11  # 10..20 inclusive


def test_draws_from_round_only() -> None:
    """REQ-PAGE-003: from_round 단독 필터."""
    from lotto.web.app import app

    with patch("lotto.web.routes.api.get_draws", return_value=_make_mock_draws(1, 100)):
        c = TestClient(app)
        response = c.get("/api/draws?from_round=50&limit=200")

    assert response.status_code == 200
    body = response.json()
    for item in body["items"]:
        assert item["drwNo"] >= 50
    assert body["total"] == 51  # 50..100 inclusive


def test_draws_to_round_only() -> None:
    """REQ-PAGE-003: to_round 단독 필터."""
    from lotto.web.app import app

    with patch("lotto.web.routes.api.get_draws", return_value=_make_mock_draws(1, 100)):
        c = TestClient(app)
        response = c.get("/api/draws?to_round=30&limit=200")

    assert response.status_code == 200
    body = response.json()
    for item in body["items"]:
        assert item["drwNo"] <= 30
    assert body["total"] == 30  # 1..30 inclusive


def test_draws_empty_result() -> None:
    """REQ-PAGE-004: 데이터 범위 밖 필터는 빈 결과를 정상 반환."""
    from lotto.web.app import app

    with patch("lotto.web.routes.api.get_draws", return_value=_make_mock_draws(1, 100)):
        c = TestClient(app)
        response = c.get("/api/draws?from_round=9999")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []
