"""SPEC-LOTTO-041: GET /stats/range 페이지 + 네비게이션 링크 테스트.

파라미터 없음 → 폼만, 유효 파라미터 → 통계 표시, 데이터 부재에도 200,
인덱스 페이지에 /stats/range 네비 링크 노출을 검증한다.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult


def _mk(no: int, d: date, nums: list[int], bonus: int, prize1: int | None = None) -> DrawResult:
    return DrawResult(
        drwNo=no, date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus, prize1Amount=prize1,
    )


# ---------------------------------------------------------------------------
# AC-14: 파라미터 없음 → 폼만 표시 (200)
# ---------------------------------------------------------------------------


def test_range_page_no_params_shows_form() -> None:
    """GET /stats/range (파라미터 없음) → 200 HTML, 입력 폼이 보인다."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.get("/stats/range")
    assert response.status_code == 200, response.text
    # 입력 폼 요소 (회차 입력 name 속성)
    assert 'name="start_drw"' in response.text
    assert 'name="end_drw"' in response.text


# ---------------------------------------------------------------------------
# AC-15: 유효 파라미터 → 통계 표시 (200)
# ---------------------------------------------------------------------------


def test_range_page_with_params_shows_stats() -> None:
    """GET /stats/range?start_drw=1&end_drw=10 → 200 HTML, 통계 결과가 보인다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7, 1_000_000_000),
        _mk(2, date(2023, 6, 3), [10, 20, 30, 40, 44, 45], 8, 2_000_000_000),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/stats/range?start_drw=1&end_drw=10")

    assert response.status_code == 200, response.text
    # 결과 영역 — 총 회차 수가 렌더링되어야 한다
    assert "구간 통계" in response.text


# ---------------------------------------------------------------------------
# AC-16: 데이터 부재에도 200
# ---------------------------------------------------------------------------


def test_range_page_no_data_returns_200() -> None:
    """get_draws가 None이어도 /stats/range는 200을 반환한다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    with patch.object(wd, "get_draws", return_value=None):
        c = TestClient(app)
        response = c.get("/stats/range?start_drw=1&end_drw=10")

    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# AC-17: 인덱스 네비게이션 링크
# ---------------------------------------------------------------------------


def test_index_has_range_nav_link() -> None:
    """GET / 응답 HTML에 /stats/range 네비게이션 링크가 포함된다."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.get("/")
    assert response.status_code == 200
    assert 'href="/stats/range"' in response.text
