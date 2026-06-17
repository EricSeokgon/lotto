"""SPEC-LOTTO-039: GET /prediction 예측 리포트 페이지 테스트.

후보 테이블/조합 카드 마커, 빈 상태 메시지, 네비게이션 링크를 검증한다.
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
        _mk(1, date(2024, 1, 6), [1, 2, 3, 4, 5, 6], 7),
        _mk(2, date(2024, 1, 13), [1, 2, 3, 10, 20, 30], 8),
        _mk(3, date(2024, 1, 20), [1, 2, 11, 21, 31, 41], 9),
        _mk(4, date(2024, 1, 27), [5, 12, 22, 32, 42, 43], 10),
        _mk(5, date(2024, 2, 3), [6, 13, 23, 33, 43, 44], 11),
        _mk(6, date(2024, 2, 10), [7, 14, 24, 34, 44, 45], 12),
        _mk(7, date(2024, 2, 17), [8, 15, 25, 35, 40, 45], 13),
        _mk(8, date(2024, 2, 24), [9, 16, 26, 36, 41, 42], 14),
    ]


# ---------------------------------------------------------------------------
# 1: 200 + HTML
# ---------------------------------------------------------------------------


def test_prediction_page_returns_200_html(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch,
    sample_draws: list[DrawResult],
) -> None:
    """GET /prediction은 200과 text/html을 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)

    response = api_client.get("/prediction")
    assert response.status_code == 200, response.text
    assert "text/html" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# 2: 후보 테이블 마커
# ---------------------------------------------------------------------------


def test_prediction_page_contains_candidate_table(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch,
    sample_draws: list[DrawResult],
) -> None:
    """후보 테이블 마커가 페이지에 존재한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)

    html = api_client.get("/prediction").text
    assert "candidate-table" in html
    # breakdown 4개 차원 라벨
    assert "빈도" in html
    assert "간격" in html
    assert "홀짝" in html
    assert "범위" in html


# ---------------------------------------------------------------------------
# 3: 조합 카드 마커
# ---------------------------------------------------------------------------


def test_prediction_page_contains_combination_cards(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch,
    sample_draws: list[DrawResult],
) -> None:
    """추천 조합 카드 마커가 페이지에 존재한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)

    html = api_client.get("/prediction").text
    assert "combination-card" in html
    assert "조합 1" in html
    assert "조합 2" in html
    assert "조합 3" in html


# ---------------------------------------------------------------------------
# 4: 빈 상태 메시지
# ---------------------------------------------------------------------------


def test_prediction_page_empty_state(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """데이터가 없으면 200과 빈 상태 메시지를 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.get("/prediction")
    assert response.status_code == 200, response.text
    assert "데이터가 없습니다" in response.text


# ---------------------------------------------------------------------------
# 5: 네비게이션 링크
# ---------------------------------------------------------------------------


def test_index_page_has_prediction_nav_link(api_client: TestClient) -> None:
    """메인 페이지 네비게이션에 /prediction 링크가 포함된다."""
    html = api_client.get("/").text
    assert 'href="/prediction"' in html
