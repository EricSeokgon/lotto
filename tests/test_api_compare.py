"""SPEC-LOTTO-040: POST /api/compare API 통합 테스트.

유효 입력은 200 + 전체 키, 검증 실패는 422, 데이터 부재 시에도 200 + 빈 구조를
검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult

_COMPARE_KEYS = {
    "numbers",
    "total_draws_checked",
    "match_summary",
    "number_frequency",
    "grade",
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


# ---------------------------------------------------------------------------
# AC-1: 유효 POST → 200 + 전체 키
# ---------------------------------------------------------------------------


def test_compare_valid_returns_200_with_all_keys(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """유효 입력은 200과 5개 키 전체를 반환한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [1, 10, 20, 30, 40, 45], 5),
        _mk(2, date(2023, 1, 14), [1, 10, 15, 25, 35, 44], 3),
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    response = api_client.post("/api/compare", json={"numbers": [1, 10, 20, 30, 40, 45]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _COMPARE_KEYS
    assert body["numbers"] == [1, 10, 20, 30, 40, 45]
    assert body["total_draws_checked"] == 2
    assert body["match_summary"]["6"]["count"] == 1


# ---------------------------------------------------------------------------
# AC-8: 검증 실패 → 422
# ---------------------------------------------------------------------------


def test_compare_fewer_than_six_returns_422(api_client: TestClient) -> None:
    """6개 미만이면 422를 반환한다."""
    response = api_client.post("/api/compare", json={"numbers": [1, 2, 3, 4, 5]})
    assert response.status_code == 422, response.text


def test_compare_out_of_range_returns_422(api_client: TestClient) -> None:
    """범위(1~45)를 벗어난 번호는 422를 반환한다."""
    r_low = api_client.post("/api/compare", json={"numbers": [0, 2, 3, 4, 5, 6]})
    assert r_low.status_code == 422, r_low.text
    r_high = api_client.post("/api/compare", json={"numbers": [1, 2, 3, 4, 5, 46]})
    assert r_high.status_code == 422, r_high.text


def test_compare_duplicate_returns_422(api_client: TestClient) -> None:
    """중복 번호는 422를 반환한다."""
    response = api_client.post("/api/compare", json={"numbers": [1, 1, 3, 4, 5, 6]})
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# AC-9: 데이터 부재 → 200 + 빈 구조
# ---------------------------------------------------------------------------


def test_compare_no_data_returns_empty_structure(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_draws가 None이면 200 + 일관된 빈 구조를 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.post("/api/compare", json={"numbers": [1, 2, 3, 4, 5, 6]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _COMPARE_KEYS
    assert body["total_draws_checked"] == 0
    assert body["match_summary"]["6"]["count"] == 0
    assert all(item["count"] == 0 for item in body["number_frequency"])
