"""SPEC-LOTTO-044: GET /api/numbers/affinity API 통합 테스트.

정상 → 200 + 키, 범위 위반/누락 → 422, 데이터 부재 → 200 + 빈 구조를 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult

_TOP_KEYS = {
    "target",
    "total_draws",
    "target_appearances",
    "partners",
    "recommended_combination",
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
# AC-10: 정상 응답 — 200 + 키
# ---------------------------------------------------------------------------


def test_affinity_returns_200_with_keys(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """target=7 데이터 → 200과 최상위 키를 반환한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [7, 13, 27, 30, 40, 45], 1),
        _mk(2, date(2023, 1, 14), [7, 18, 27, 33, 41, 44], 2),
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    response = api_client.get("/api/numbers/affinity?target=7")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _TOP_KEYS
    assert body["target"] == 7
    assert body["target_appearances"] == 2


# ---------------------------------------------------------------------------
# AC-11: target=0 → 422
# ---------------------------------------------------------------------------


def test_affinity_target_zero_returns_422(api_client: TestClient) -> None:
    """target=0 → 422 (ge=1 위반)."""
    response = api_client.get("/api/numbers/affinity?target=0")
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# AC-12: target=46 → 422
# ---------------------------------------------------------------------------


def test_affinity_target_over_range_returns_422(api_client: TestClient) -> None:
    """target=46 → 422 (le=45 위반)."""
    response = api_client.get("/api/numbers/affinity?target=46")
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# AC-13: target 누락 → 422
# ---------------------------------------------------------------------------


def test_affinity_missing_target_returns_422(api_client: TestClient) -> None:
    """target 미지정 → 422 (필수 파라미터)."""
    response = api_client.get("/api/numbers/affinity")
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# AC-14: 데이터 부재 → 200 + 빈 구조
# ---------------------------------------------------------------------------


def test_affinity_no_data_returns_empty_structure(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_draws가 None이면 200 + 빈 구조를 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.get("/api/numbers/affinity?target=7")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _TOP_KEYS
    assert body["target_appearances"] == 0
    assert body["partners"] == []
    assert body["recommended_combination"] == [7]
