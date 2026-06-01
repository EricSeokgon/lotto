"""SPEC-LOTTO-038: GET /api/stats/overview API 통합 테스트.

데이터 부재 시에도 200 + 빈 구조로 응답하며, 호출이 data/ 디렉터리를
변경하지 않는(읽기 전용) 것을 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult

_OVERVIEW_KEYS = {
    "total_draws",
    "total_prize1_sum",
    "number_frequency",
    "highest_prize1_draw",
    "lowest_prize1_draw",
    "odd_even",
    "range_distribution",
    "yearly_avg_prize",
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
# AC-7: 정상 데이터 — 200 + 8개 키
# ---------------------------------------------------------------------------


def test_stats_overview_returns_200_with_all_keys(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """데이터가 있을 때 200과 8개 키 전체를 반환한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7, 1_000_000_000),
        _mk(2, date(2024, 6, 3), [10, 20, 30, 40, 44, 45], 8, 2_000_000_000),
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    response = api_client.get("/api/stats/overview")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _OVERVIEW_KEYS
    assert body["total_draws"] == 2
    assert body["total_prize1_sum"] == 3_000_000_000
    assert len(body["number_frequency"]) == 45


# ---------------------------------------------------------------------------
# AC-8: get_draws None → 200 + 빈 구조
# ---------------------------------------------------------------------------


def test_stats_overview_no_data_returns_empty_structure(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_draws가 None이면 200 + 일관된 빈 구조를 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.get("/api/stats/overview")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == _OVERVIEW_KEYS
    assert body["total_draws"] == 0
    assert body["total_prize1_sum"] == 0
    assert body["highest_prize1_draw"] is None
    assert body["lowest_prize1_draw"] is None
    assert body["yearly_avg_prize"] == []
    assert len(body["number_frequency"]) == 45


# ---------------------------------------------------------------------------
# AC-9: 호출이 data/ 디렉터리를 변경하지 않음 (읽기 전용)
# ---------------------------------------------------------------------------


def test_stats_overview_does_not_write_files(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """엔드포인트 호출 후 data/ 디렉터리에 파일이 생성/변경되지 않는다."""
    from lotto.web import data as wd

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.chdir(tmp_path)

    draws = [_mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7, 1_000_000_000)]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    before = sorted(p.name for p in data_dir.iterdir())
    response = api_client.get("/api/stats/overview")
    assert response.status_code == 200
    after = sorted(p.name for p in data_dir.iterdir())
    assert before == after == []
