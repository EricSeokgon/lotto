"""SPEC-LOTTO-040: GET /compare 번호 비교 분석기 페이지 테스트.

200 HTML, 입력 폼 마커, 네비게이션 링크, 데이터 부재 동작을 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult


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


@pytest.fixture
def sample_draws() -> list[DrawResult]:
    return [
        _mk(1, date(2024, 1, 6), [1, 10, 20, 30, 40, 45], 7),
        _mk(2, date(2024, 1, 13), [1, 10, 15, 25, 35, 44], 8),
    ]


# ---------------------------------------------------------------------------
# 1: 200 + HTML
# ---------------------------------------------------------------------------


def test_compare_page_returns_200_html(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch,
    sample_draws: list[DrawResult],
) -> None:
    """GET /compare는 200과 text/html을 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)

    response = api_client.get("/compare")
    assert response.status_code == 200, response.text
    assert "text/html" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# 2: 네비게이션 링크
# ---------------------------------------------------------------------------


def test_index_page_has_compare_nav_link(api_client: TestClient) -> None:
    """메인 페이지 네비게이션에 /compare 링크가 포함된다."""
    html = api_client.get("/").text
    assert 'href="/compare"' in html


# ---------------------------------------------------------------------------
# 3: 입력 폼 마커
# ---------------------------------------------------------------------------


def test_compare_page_contains_number_form(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch,
    sample_draws: list[DrawResult],
) -> None:
    """페이지에 6개 번호 입력 폼 마커와 비교 버튼이 존재한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)

    html = api_client.get("/compare").text
    assert "compare-num" in html
    assert "compare-submit" in html


# ---------------------------------------------------------------------------
# 4: 데이터 부재 시에도 200
# ---------------------------------------------------------------------------


def test_compare_page_no_data(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """데이터가 없어도 200을 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.get("/compare")
    assert response.status_code == 200, response.text
