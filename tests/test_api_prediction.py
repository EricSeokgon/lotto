"""SPEC-LOTTO-039: GET /api/prediction/report API 통합 테스트.

recent_n 범위 검증과 데이터 부재 시 빈 구조 응답을 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult

_REQUIRED_KEYS = {
    "recent_n",
    "draws_analyzed",
    "weights",
    "top_candidates",
    "recommended_combinations",
}


def _mk(no: int, d: date, nums: list[int], bonus: int) -> DrawResult:
    return DrawResult(
        drwNo=no, date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


@pytest.fixture
def api_client() -> TestClient:
    """매 테스트 새 TestClient — 라우터는 모듈 공유."""
    from lotto.web.app import app

    return TestClient(app)


@pytest.fixture
def sample_draws() -> list[DrawResult]:
    return [
        _mk(1, date(2024, 1, 6), [1, 2, 3, 4, 5, 6], 7),
        _mk(2, date(2024, 1, 13), [1, 2, 3, 10, 20, 30], 8),
        _mk(3, date(2024, 1, 20), [1, 2, 11, 21, 31, 41], 9),
        _mk(4, date(2024, 1, 27), [5, 12, 22, 32, 42, 43], 10),
        _mk(5, date(2024, 2, 3), [6, 13, 23, 33, 43, 44], 11),
        _mk(6, date(2024, 2, 10), [7, 14, 24, 34, 44, 45], 12),
        _mk(7, date(2024, 2, 17), [8, 15, 25, 35, 40, 45], 13),
        _mk(8, date(2024, 2, 24), [9, 16, 26, 36, 41, 42], 14),
    ]


# ---------------------------------------------------------------------------
# AC: 정상 200 + 필수 키
# ---------------------------------------------------------------------------


def test_prediction_report_returns_200_with_keys(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch,
    sample_draws: list[DrawResult],
) -> None:
    """GET /api/prediction/report는 200과 필수 키 전체를 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)

    response = api_client.get("/api/prediction/report")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _REQUIRED_KEYS
    assert len(body["top_candidates"]) == 10
    assert len(body["recommended_combinations"]) == 3


# ---------------------------------------------------------------------------
# AC: recent_n=10 → draws_analyzed <= 10
# ---------------------------------------------------------------------------


def test_prediction_report_recent_n_param(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch,
    sample_draws: list[DrawResult],
) -> None:
    """recent_n=10이면 draws_analyzed는 10 이하다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)

    response = api_client.get("/api/prediction/report?recent_n=10")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["recent_n"] == 10
    assert body["draws_analyzed"] <= 10


# ---------------------------------------------------------------------------
# AC: recent_n=0 → 422
# ---------------------------------------------------------------------------


def test_prediction_report_recent_n_zero_returns_422(
    api_client: TestClient,
) -> None:
    """recent_n=0은 ge=1 위반으로 422를 반환한다."""
    response = api_client.get("/api/prediction/report?recent_n=0")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# AC: recent_n=201 → 422
# ---------------------------------------------------------------------------


def test_prediction_report_recent_n_too_large_returns_422(
    api_client: TestClient,
) -> None:
    """recent_n=201은 le=200 위반으로 422를 반환한다."""
    response = api_client.get("/api/prediction/report?recent_n=201")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# AC: get_draws None → 200 + 빈 구조
# ---------------------------------------------------------------------------


def test_prediction_report_no_data_returns_empty(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_draws가 None이면 200 + 빈 구조를 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.get("/api/prediction/report")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _REQUIRED_KEYS
    assert body["draws_analyzed"] == 0
    assert body["top_candidates"] == []
    assert body["recommended_combinations"] == []
