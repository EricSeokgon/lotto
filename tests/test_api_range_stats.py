"""SPEC-LOTTO-041: GET /api/stats/range API 통합 테스트.

유효 구간 → 200 + 전체 키, 역전/누락 파라미터 → 422,
데이터 부재 → 200 + 빈 구조를 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult

_RANGE_KEYS = {
    "start_drw",
    "end_drw",
    "total_draws",
    "number_frequency",
    "odd_even",
    "range_distribution",
    "avg_prize1",
    "highest_prize1_draw",
    "lowest_prize1_draw",
}


def _mk(no: int, d: date, nums: list[int], bonus: int, prize1: int | None) -> DrawResult:
    return DrawResult(
        drwNo=no, date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus, prize1Amount=prize1,
    )


@pytest.fixture
def api_client() -> TestClient:
    """매 테스트 새 TestClient — 라우터는 모듈 공유."""
    from lotto.web.app import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# AC-9: 정상 응답 — 200 + 전체 키
# ---------------------------------------------------------------------------


def test_range_returns_200_with_all_keys(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """유효 구간 → 200과 전체 키를 반환한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7, 1_000_000_000),
        _mk(2, date(2024, 6, 3), [10, 20, 30, 40, 44, 45], 8, 2_000_000_000),
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    response = api_client.get("/api/stats/range?start_drw=1&end_drw=50")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _RANGE_KEYS
    assert body["start_drw"] == 1
    assert body["end_drw"] == 50
    assert len(body["number_frequency"]) == 45


# ---------------------------------------------------------------------------
# AC-13: total_draws 정확성
# ---------------------------------------------------------------------------


def test_range_total_draws_count(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """응답의 total_draws가 구간 내 회차 수와 일치한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7, 1_000_000_000),
        _mk(5, date(2023, 2, 4), [7, 8, 9, 10, 11, 12], 13, 2_000_000_000),
        _mk(10, date(2023, 3, 4), [13, 14, 15, 16, 17, 18], 19, None),
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    response = api_client.get("/api/stats/range?start_drw=1&end_drw=5")
    assert response.status_code == 200, response.text
    body = response.json()
    # 회차 1, 5 만 구간 1~5에 포함 (회차 10 제외)
    assert body["total_draws"] == 2


# ---------------------------------------------------------------------------
# AC-10: 역전 구간 → 422
# ---------------------------------------------------------------------------


def test_range_inverted_returns_422(api_client: TestClient) -> None:
    """start_drw > end_drw 이면 422를 반환한다."""
    response = api_client.get("/api/stats/range?start_drw=50&end_drw=1")
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# AC-11: 필수 파라미터 누락 → 422
# ---------------------------------------------------------------------------


def test_range_missing_start_returns_422(api_client: TestClient) -> None:
    """start_drw 누락 시 422를 반환한다."""
    response = api_client.get("/api/stats/range?end_drw=50")
    assert response.status_code == 422, response.text


def test_range_missing_end_returns_422(api_client: TestClient) -> None:
    """end_drw 누락 시 422를 반환한다."""
    response = api_client.get("/api/stats/range?start_drw=1")
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# AC-12: 데이터 부재 → 200 + 빈 구조
# ---------------------------------------------------------------------------


def test_range_no_data_returns_empty_structure(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_draws가 None이면 200 + 일관된 빈 구조를 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.get("/api/stats/range?start_drw=1&end_drw=50")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _RANGE_KEYS
    assert body["total_draws"] == 0
    assert body["avg_prize1"] is None
    assert body["highest_prize1_draw"] is None
    assert len(body["number_frequency"]) == 45
