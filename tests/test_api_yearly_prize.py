"""SPEC-LOTTO-046: GET /api/stats/yearly-prize API 통합 테스트.

정상 → 200 + 키, 연도 리스트 구조 검증, 데이터 부재 → 200 + 빈 구조, JSON 응답을 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult

_TOP_KEYS = {
    "total_years",
    "overall_avg_prize1",
    "highest_avg_year",
    "lowest_avg_year",
    "years",
}
_YEAR_KEYS = {
    "year",
    "total_draws",
    "prize_draws",
    "avg_prize1",
    "max_prize1",
    "min_prize1",
    "total_winners",
}


def _mk(
    no: int, d: date, nums: list[int], bonus: int,
    prize: int | None = None, winners: int | None = None,
) -> DrawResult:
    return DrawResult(
        drwNo=no, date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus, prize1Amount=prize, prize1Winners=winners,
    )


@pytest.fixture
def api_client() -> TestClient:
    """매 테스트 새 TestClient — 라우터는 모듈 공유."""
    from lotto.web.app import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# AC-10: 정상 응답 — 200 + 모든 키
# ---------------------------------------------------------------------------


def test_yearly_prize_returns_200_with_keys(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """데이터 있으면 200과 최상위 키를 반환한다."""
    from lotto.web import data as wd

    nums = [1, 10, 20, 30, 40, 45]
    draws = [
        _mk(1, date(2022, 1, 1), nums, 5, prize=1000, winners=1),
        _mk(2, date(2023, 1, 1), nums, 5, prize=3000, winners=2),
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    response = api_client.get("/api/stats/yearly-prize")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _TOP_KEYS
    assert body["total_years"] == 2


# ---------------------------------------------------------------------------
# AC-11: years 리스트 구조 정확
# ---------------------------------------------------------------------------


def test_yearly_prize_years_structure(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """years 항목이 모든 연도 키를 포함하고 연도 오름차순이다."""
    from lotto.web import data as wd

    nums = [1, 10, 20, 30, 40, 45]
    draws = [
        _mk(1, date(2022, 1, 1), nums, 5, prize=1000, winners=1),
        _mk(2, date(2023, 1, 1), nums, 5, prize=3000, winners=2),
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    body = api_client.get("/api/stats/yearly-prize").json()
    years = body["years"]
    assert len(years) == 2
    for y in years:
        assert set(y.keys()) == _YEAR_KEYS
    assert [y["year"] for y in years] == ["2022", "2023"]


# ---------------------------------------------------------------------------
# AC-12: 데이터 부재 → 200 + 빈 구조
# ---------------------------------------------------------------------------


def test_yearly_prize_no_data_returns_empty(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_draws가 None이면 200 + 빈 구조를 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.get("/api/stats/yearly-prize")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _TOP_KEYS
    assert body["total_years"] == 0
    assert body["highest_avg_year"] is None
    assert body["years"] == []


# ---------------------------------------------------------------------------
# AC-13: 응답은 JSON
# ---------------------------------------------------------------------------


def test_yearly_prize_response_is_json(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """응답 Content-Type이 application/json이다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.get("/api/stats/yearly-prize")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
