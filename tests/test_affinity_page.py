"""SPEC-LOTTO-044: GET /numbers/affinity 페이지 + 네비게이션 링크 테스트.

폼 렌더링 → 200, target 파라미터 → 200 결과, 데이터 부재에도 200,
인덱스 페이지에 /numbers/affinity 네비 링크 노출을 검증한다.
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
# AC-15: 폼 렌더링 → 200 HTML
# ---------------------------------------------------------------------------


def test_affinity_page_form_returns_200() -> None:
    """GET /numbers/affinity (target 없음) → 200 HTML (폼)."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.get("/numbers/affinity")
    assert response.status_code == 200, response.text
    assert "번호 궁합" in response.text


# ---------------------------------------------------------------------------
# AC-16: target 파라미터 → 200 HTML (결과)
# ---------------------------------------------------------------------------


def test_affinity_page_with_target_returns_200() -> None:
    """GET /numbers/affinity?target=7 → 200 HTML (결과)."""
    from lotto.web import data as wd
    from lotto.web.app import app

    draws = [
        _mk(1, date(2023, 1, 7), [7, 13, 27, 30, 40, 45], 1),
        _mk(2, date(2023, 1, 14), [7, 18, 27, 33, 41, 44], 2),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/numbers/affinity?target=7")

    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# AC-17: 데이터 부재에도 200 (크래시 없음)
# ---------------------------------------------------------------------------


def test_affinity_page_no_data_returns_200() -> None:
    """get_draws가 None이어도 /numbers/affinity?target=7은 200을 반환한다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    with patch.object(wd, "get_draws", return_value=None):
        c = TestClient(app)
        response = c.get("/numbers/affinity?target=7")

    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# AC-18: 인덱스 네비게이션 링크
# ---------------------------------------------------------------------------


def test_index_has_affinity_nav_link() -> None:
    """GET / 응답 HTML에 /numbers/affinity 네비게이션 링크가 포함된다."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.get("/")
    assert response.status_code == 200
    assert 'href="/numbers/affinity"' in response.text
