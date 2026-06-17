"""SPEC-LOTTO-031: 수집 이력 대시보드 — 요약 계산 + API + collect 페이지 테스트.

REQ: GET /api/collect/summary, /collect 페이지 요약 카드 + 누락 회차 표시.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import date

import pytest
from starlette.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """앱 클라이언트 — 모듈 단위 공유."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def gappy_draws() -> list[DrawResult]:
    """1~6회 중 2회, 4회가 누락된 데이터 (1,3,5,6회 존재).

    latest=6, oldest=1, total_collected=4, missing=[2, 4], coverage=4/6.
    """
    def mk(no: int, d: date) -> DrawResult:
        return DrawResult(drwNo=no, date=d, n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7)

    return [
        mk(1, date(2002, 12, 7)),
        mk(3, date(2002, 12, 21)),
        mk(5, date(2003, 1, 4)),
        mk(6, date(2003, 1, 11)),
    ]


@pytest.fixture(autouse=True)
def patch_draws(
    monkeypatch: pytest.MonkeyPatch,
    gappy_draws: list[DrawResult],
) -> None:
    """API/페이지가 gappy_draws를 사용하도록 패치.

    API 라우트는 lotto.web.data.get_draws 를 동적 호출하고,
    collect_page 는 pages 모듈에 임포트된 get_draws 심볼을 사용하므로 둘 다 패치한다.
    """
    from lotto.web import data as wd
    from lotto.web.routes import pages as pages_mod

    monkeypatch.setattr(wd, "get_draws", lambda: gappy_draws)
    monkeypatch.setattr(pages_mod, "get_draws", lambda: gappy_draws)


# ---------------------------------------------------------------------------
# 1. data.collect_summary 순수 계산 함수
# ---------------------------------------------------------------------------


def test_collect_summary_totals(gappy_draws: list[DrawResult]) -> None:
    """총 수집/최신/최오래된 회차 검증."""
    from lotto.web.data import collect_summary

    result = collect_summary(gappy_draws)
    assert result["total_collected"] == 4
    assert result["latest_drw_no"] == 6
    assert result["oldest_drw_no"] == 1


def test_collect_summary_missing(gappy_draws: list[DrawResult]) -> None:
    """누락 회차 = [2, 4], 누락 수 2."""
    from lotto.web.data import collect_summary

    result = collect_summary(gappy_draws)
    assert result["missing_drw_nos"] == [2, 4]
    assert result["missing_count"] == 2


def test_collect_summary_coverage(gappy_draws: list[DrawResult]) -> None:
    """커버리지 = 4/6 = 66.67%."""
    from lotto.web.data import collect_summary

    result = collect_summary(gappy_draws)
    assert result["coverage_pct"] == 66.67


def test_collect_summary_date_range(gappy_draws: list[DrawResult]) -> None:
    """날짜 범위 from=최오래된, to=최신."""
    from lotto.web.data import collect_summary

    result = collect_summary(gappy_draws)
    assert result["date_range"]["from"] == "2002-12-07"
    assert result["date_range"]["to"] == "2003-01-11"


def test_collect_summary_no_gaps() -> None:
    """누락 없는 연속 데이터 → missing 빈 리스트, coverage 100%."""
    from lotto.web.data import collect_summary

    draws = [
        DrawResult(drwNo=n, date=date(2002, 12, 7), n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7)
        for n in range(1, 4)
    ]
    result = collect_summary(draws)
    assert result["missing_drw_nos"] == []
    assert result["missing_count"] == 0
    assert result["coverage_pct"] == 100.0


def test_collect_summary_caps_missing_at_50() -> None:
    """누락 회차가 50개를 넘으면 최대 50개만 반환 (missing_count는 전체 개수)."""
    from lotto.web.data import collect_summary

    # 1회와 200회만 존재 → 2~199 누락 (198개)
    draws = [
        DrawResult(drwNo=1, date=date(2002, 12, 7), n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7),
        DrawResult(drwNo=200, date=date(2006, 9, 30), n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7),
    ]
    result = collect_summary(draws)
    assert len(result["missing_drw_nos"]) == 50
    assert result["missing_count"] == 198
    # 잘려도 앞에서부터 순서대로
    assert result["missing_drw_nos"][0] == 2


def test_collect_summary_empty() -> None:
    """빈 데이터 → 모든 값 0/None, 빈 리스트."""
    from lotto.web.data import collect_summary

    result = collect_summary([])
    assert result["total_collected"] == 0
    assert result["latest_drw_no"] == 0
    assert result["oldest_drw_no"] == 0
    assert result["missing_drw_nos"] == []
    assert result["missing_count"] == 0
    assert result["coverage_pct"] == 0.0
    assert result["date_range"]["from"] is None
    assert result["date_range"]["to"] is None


# ---------------------------------------------------------------------------
# 2. GET /api/collect/summary
# ---------------------------------------------------------------------------


def test_api_collect_summary_ok(client: TestClient) -> None:
    """수집 요약 API → 200 + 구조 검증."""
    resp = client.get("/api/collect/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_collected"] == 4
    assert body["latest_drw_no"] == 6
    assert body["missing_drw_nos"] == [2, 4]
    assert body["missing_count"] == 2
    assert body["coverage_pct"] == 66.67


def test_api_collect_summary_has_date_range(client: TestClient) -> None:
    """요약 응답에 date_range 포함."""
    resp = client.get("/api/collect/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "date_range" in body
    assert body["date_range"]["from"] == "2002-12-07"


# ---------------------------------------------------------------------------
# 3. /collect 페이지 요약 카드
# ---------------------------------------------------------------------------


def test_collect_page_has_summary(client: TestClient) -> None:
    """collect 페이지에 요약 카드 (총 회차/커버리지) 렌더링."""
    resp = client.get("/collect")
    assert resp.status_code == 200
    html = resp.text
    assert "커버리지" in html
    # 커버리지 66.67% 표시
    assert "66.67" in html


def test_collect_page_shows_missing(client: TestClient) -> None:
    """누락 회차가 있으면 목록 표시."""
    resp = client.get("/collect")
    assert resp.status_code == 200
    html = resp.text
    assert "누락" in html
    # 누락 회차 2, 4가 표시
    assert "2" in html
    assert "4" in html
