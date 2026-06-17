"""SPEC-LOTTO-047: GET /api/numbers/cycle API 통합 테스트.

정상 → 200 + 키, numbers 45개 구조 검증, 데이터 부재 → 200 + all-never 구조,
JSON 응답을 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult

_TOP_KEYS = {"total_draws", "numbers", "most_overdue", "summary"}


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


def _draws() -> list[DrawResult]:
    return [
        _mk(1, date(2020, 1, 1), [1, 2, 3, 4, 5, 6], 45),
        _mk(2, date(2020, 1, 8), [1, 2, 3, 7, 8, 9], 44),
        _mk(3, date(2020, 1, 15), [1, 10, 11, 12, 13, 14], 43),
    ]


# ---------------------------------------------------------------------------
# AC-11: 정상 응답 — 200 + 모든 키
# ---------------------------------------------------------------------------


def test_cycle_returns_200_with_keys(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """데이터 있으면 200과 최상위 키를 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: _draws())

    response = api_client.get("/api/numbers/cycle")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _TOP_KEYS
    assert body["total_draws"] == 3


# ---------------------------------------------------------------------------
# AC-12: numbers는 정확히 45개
# ---------------------------------------------------------------------------


def test_cycle_numbers_has_45_entries(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """numbers 항목이 정확히 45개이며 번호 오름차순이다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: _draws())

    body = api_client.get("/api/numbers/cycle").json()
    numbers = body["numbers"]
    assert len(numbers) == 45
    assert [n["number"] for n in numbers] == list(range(1, 46))


# ---------------------------------------------------------------------------
# AC-13: 데이터 부재(None) → 200 + all-never 구조
# ---------------------------------------------------------------------------


def test_cycle_no_data_returns_all_never(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_draws가 None이면 200 + 전부 never 구조를 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.get("/api/numbers/cycle")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_draws"] == 0
    assert len(body["numbers"]) == 45
    assert all(n["status"] == "never" for n in body["numbers"])
    assert body["most_overdue"] == []
    assert body["summary"]["never"] == 45


# ---------------------------------------------------------------------------
# AC-14: 응답은 JSON
# ---------------------------------------------------------------------------


def test_cycle_response_is_json(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """응답 Content-Type이 application/json이다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.get("/api/numbers/cycle")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
