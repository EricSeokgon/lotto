"""SPEC-LOTTO-043: GET /patterns/consecutive 페이지 + 네비게이션 링크 테스트.

정상 렌더링 → 200, recent_n 파라미터 → 200, 데이터 부재에도 200,
인덱스 페이지에 /patterns/consecutive 네비 링크 노출을 검증한다.
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
# AC-14: 정상 렌더링 → 200 HTML
# ---------------------------------------------------------------------------


def test_consecutive_page_returns_200() -> None:
    """GET /patterns/consecutive → 200 HTML."""
    from lotto.web import data as wd
    from lotto.web.app import app

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 18, 33, 40], 12),
        _mk(2, date(2023, 1, 14), [7, 8, 19, 20, 41, 45], 3),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/patterns/consecutive")

    assert response.status_code == 200, response.text
    assert "연속 번호" in response.text


# ---------------------------------------------------------------------------
# AC-15: recent_n 파라미터 → 200 HTML
# ---------------------------------------------------------------------------


def test_consecutive_page_with_recent_n() -> None:
    """GET /patterns/consecutive?recent_n=100 → 200 HTML."""
    from lotto.web import data as wd
    from lotto.web.app import app

    draws = [_mk(1, date(2023, 1, 7), [1, 2, 3, 18, 33, 40], 12)]
    with patch.object(wd, "get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/patterns/consecutive?recent_n=100")

    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# AC-16: 데이터 부재에도 200 (빈 상태)
# ---------------------------------------------------------------------------


def test_consecutive_page_no_data_returns_200() -> None:
    """get_draws가 None이어도 /patterns/consecutive는 200을 반환한다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    with patch.object(wd, "get_draws", return_value=None):
        c = TestClient(app)
        response = c.get("/patterns/consecutive")

    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# AC-17: 인덱스 네비게이션 링크
# ---------------------------------------------------------------------------


def test_index_has_consecutive_nav_link() -> None:
    """GET / 응답 HTML에 /patterns/consecutive 네비게이션 링크가 포함된다."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.get("/")
    assert response.status_code == 200
    assert 'href="/patterns/consecutive"' in response.text
