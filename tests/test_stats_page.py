"""SPEC-LOTTO-038: GET /stats 통계 대시보드 페이지 테스트.

7개 통계 요소 마커, 빈 상태 메시지, 네비게이션 링크를 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult


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


@pytest.fixture
def sample_draws() -> list[DrawResult]:
    return [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7, 1_000_000_000),
        _mk(2, date(2024, 6, 3), [10, 20, 30, 40, 44, 45], 8, 2_000_000_000),
    ]


# ---------------------------------------------------------------------------
# AC-10: 200 + HTML content-type
# ---------------------------------------------------------------------------


def test_stats_page_returns_200_html(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch,
    sample_draws: list[DrawResult],
) -> None:
    """GET /stats는 200과 text/html을 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)

    response = api_client.get("/stats")
    assert response.status_code == 200, response.text
    assert "text/html" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# AC-11: 7개 통계 요소 마커 포함
# ---------------------------------------------------------------------------


def test_stats_page_contains_all_stat_markers(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch,
    sample_draws: list[DrawResult],
) -> None:
    """7개 통계 요소를 식별하는 마커가 모두 페이지에 존재한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)

    html = api_client.get("/stats").text
    # 1. 총 회차 수, 2. 1등 당첨금 합계
    assert "총 회차" in html
    assert "당첨금 합계" in html
    # 3. 번호 빈도 차트
    assert "numberFrequencyChart" in html
    # 4. 최고/최저 당첨금 회차
    assert "최고" in html
    assert "최저" in html
    # 5. 홀짝 분포
    assert "홀짝" in html
    # 6. 범위 분포
    assert "범위" in html or "구간" in html
    # 7. 연도별 평균 당첨금 차트
    assert "yearlyPrizeChart" in html


# ---------------------------------------------------------------------------
# AC-12: 빈 상태 메시지
# ---------------------------------------------------------------------------


def test_stats_page_empty_state(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """데이터가 없으면 200과 빈 상태 메시지를 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.get("/stats")
    assert response.status_code == 200, response.text
    html = response.text
    assert "데이터가 없습니다" in html


# ---------------------------------------------------------------------------
# AC-12 nav: 메인 페이지에 /stats 링크 노출
# ---------------------------------------------------------------------------


def test_index_page_has_stats_nav_link(api_client: TestClient) -> None:
    """메인 페이지 네비게이션에 /stats 링크가 포함된다."""
    html = api_client.get("/").text
    assert 'href="/stats"' in html
