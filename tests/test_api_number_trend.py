"""SPEC-LOTTO-042: GET /api/numbers/trend API 통합 테스트.

유효 번호 → 200 + 키, 중복/범위 외/4개 → 422,
데이터 부재 → 200 + 빈 구조를 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult

_TOP_KEYS = {"recent_n", "draws_analyzed", "numbers"}


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


# ---------------------------------------------------------------------------
# AC-9: 정상 응답 — 200 + 키
# ---------------------------------------------------------------------------


def test_trend_returns_200_with_keys(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """유효 번호 2개 → 200과 최상위 키를 반환한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [7, 8, 9, 10, 11, 12], 1),
        _mk(2, date(2023, 1, 14), [14, 20, 30, 40, 44, 45], 2),
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    response = api_client.get("/api/numbers/trend?n=7&n=14")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _TOP_KEYS
    assert len(body["numbers"]) == 2
    assert {e["number"] for e in body["numbers"]} == {7, 14}


# ---------------------------------------------------------------------------
# AC-10: 중복 번호 → 422
# ---------------------------------------------------------------------------


def test_trend_duplicate_numbers_returns_422(api_client: TestClient) -> None:
    """동일 번호 중복 → 422."""
    response = api_client.get("/api/numbers/trend?n=7&n=7")
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# AC-11: 범위 외 번호 → 422
# ---------------------------------------------------------------------------


def test_trend_out_of_range_returns_422(api_client: TestClient) -> None:
    """1~45 범위 밖 번호 → 422."""
    response = api_client.get("/api/numbers/trend?n=0")
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# AC-12: 4개 번호 → 422
# ---------------------------------------------------------------------------


def test_trend_too_many_numbers_returns_422(api_client: TestClient) -> None:
    """번호 4개 → 422 (최대 3개)."""
    response = api_client.get("/api/numbers/trend?n=1&n=2&n=3&n=4")
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# AC-13: 데이터 부재 → 200 + 빈 구조
# ---------------------------------------------------------------------------


def test_trend_no_data_returns_empty_structure(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_draws가 None이면 200 + 빈 구조를 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.get("/api/numbers/trend?n=7")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _TOP_KEYS
    assert body["draws_analyzed"] == 0
    assert body["numbers"] == []
