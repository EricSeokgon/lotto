"""SPEC-LOTTO-042: GET /numbers/trend 페이지 + 네비게이션 링크 테스트.

파라미터 없음 → 폼만, 유효 파라미터 → 결과 표시, 데이터 부재에도 200,
인덱스 페이지에 /numbers/trend 네비 링크 노출을 검증한다.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult


def _mk(no: int, d: date, nums: list[int], bonus: int) -> DrawResult:
    return DrawResult(
        drwNo=no, date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# ---------------------------------------------------------------------------
# AC-14: 파라미터 없음 → 폼만 표시 (200)
# ---------------------------------------------------------------------------


def test_trend_page_no_params_shows_form() -> None:
    """GET /numbers/trend (파라미터 없음) → 200 HTML, 입력 폼이 보인다."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.get("/numbers/trend")
    assert response.status_code == 200, response.text
    # recent_n 입력 폼 요소
    assert 'name="recent_n"' in response.text


# ---------------------------------------------------------------------------
# AC-15: 유효 파라미터 → 결과 표시 (200)
# ---------------------------------------------------------------------------


def test_trend_page_with_params_shows_data() -> None:
    """GET /numbers/trend?n=7&recent_n=50 → 200 HTML, 결과가 렌더링된다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    draws = [
        _mk(1, date(2023, 1, 7), [7, 8, 9, 10, 11, 12], 1),
        _mk(2, date(2023, 1, 14), [1, 2, 3, 4, 5, 6], 7),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/numbers/trend?n=7&recent_n=50")

    assert response.status_code == 200, response.text
    assert "번호 추이" in response.text


# ---------------------------------------------------------------------------
# AC-16: 데이터 부재에도 200
# ---------------------------------------------------------------------------


def test_trend_page_no_data_returns_200() -> None:
    """get_draws가 None이어도 /numbers/trend는 200을 반환한다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    with patch.object(wd, "get_draws", return_value=None):
        c = TestClient(app)
        response = c.get("/numbers/trend")

    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# AC-17: 인덱스 네비게이션 링크
# ---------------------------------------------------------------------------


def test_index_has_trend_nav_link() -> None:
    """GET / 응답 HTML에 /numbers/trend 네비게이션 링크가 포함된다."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.get("/")
    assert response.status_code == 200
    assert 'href="/numbers/trend"' in response.text
