"""SPEC-LOTTO-043: GET /api/patterns/consecutive API 통합 테스트.

정상 → 200 + 키, recent_n 윈도, recent_n=0 → 422,
데이터 부재 → 200 + 빈 구조를 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult

_TOP_KEYS = {
    "total_draws",
    "draws_with_consecutive",
    "consecutive_ratio",
    "run_length_distribution",
    "max_run_length",
    "most_common_pairs",
    "draws_without_consecutive",
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


def test_consecutive_returns_200_with_keys(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_draws 데이터 → 200과 7개 최상위 키를 반환한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 18, 33, 40], 12),
        _mk(2, date(2023, 1, 14), [7, 8, 19, 20, 41, 45], 3),
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    response = api_client.get("/api/patterns/consecutive")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _TOP_KEYS
    assert body["total_draws"] == 2
    assert body["max_run_length"] == 3


# ---------------------------------------------------------------------------
# AC-11: recent_n 윈도
# ---------------------------------------------------------------------------


def test_consecutive_recent_n_window(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """recent_n=1 → 최신 1회차만 분석한다 (total_draws=1)."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 10, 20, 30, 40], 5),
        _mk(2, date(2023, 1, 14), [2, 5, 9, 14, 30, 44], 6),  # 연속 없음(최신)
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    response = api_client.get("/api/patterns/consecutive?recent_n=1")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_draws"] == 1
    assert body["draws_with_consecutive"] == 0


# ---------------------------------------------------------------------------
# AC-12: recent_n=0 → 422
# ---------------------------------------------------------------------------


def test_consecutive_recent_n_zero_returns_422(api_client: TestClient) -> None:
    """recent_n=0 → 422 (ge=1 위반)."""
    response = api_client.get("/api/patterns/consecutive?recent_n=0")
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# AC-13: 데이터 부재 → 200 + 빈 구조
# ---------------------------------------------------------------------------


def test_consecutive_no_data_returns_empty_structure(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_draws가 None이면 200 + 빈 구조를 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.get("/api/patterns/consecutive")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _TOP_KEYS
    assert body["total_draws"] == 0
    assert body["most_common_pairs"] == []
