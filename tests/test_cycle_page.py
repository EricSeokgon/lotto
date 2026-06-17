"""SPEC-LOTTO-047: GET /numbers/cycle 페이지 + 네비게이션 링크 테스트.

페이지 렌더링 → 200, 번호 테이블/상태 마커 포함, 데이터 부재에도 200(빈 상태),
인덱스 페이지에 /numbers/cycle 네비 링크 노출을 검증한다.
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


def _draws() -> list[DrawResult]:
    return [
        _mk(1, date(2020, 1, 1), [1, 2, 3, 4, 5, 6], 45),
        _mk(2, date(2020, 1, 8), [1, 2, 3, 7, 8, 9], 44),
        _mk(3, date(2020, 1, 15), [1, 10, 11, 12, 13, 14], 43),
    ]


# ---------------------------------------------------------------------------
# AC-15: 페이지 렌더링 → 200 HTML (번호 테이블 + 상태 마커)
# ---------------------------------------------------------------------------


def test_cycle_page_returns_200_html() -> None:
    """GET /numbers/cycle → 200 HTML, 번호 테이블/상태 마커 포함."""
    from lotto.web import data as wd
    from lotto.web.app import app

    with patch.object(wd, "get_draws", return_value=_draws()):
        c = TestClient(app)
        response = c.get("/numbers/cycle")

    assert response.status_code == 200, response.text
    html = response.text
    # 페이지 제목 + 상태 라벨 마커
    assert "당첨 주기" in html
    # 번호 테이블에 평균 주기 / 현재 간격 헤더 노출
    assert "평균 주기" in html
    assert "현재 간격" in html


# ---------------------------------------------------------------------------
# AC-16: 상태 배지 / 요약 카운트 노출
# ---------------------------------------------------------------------------


def test_cycle_page_contains_status_markers() -> None:
    """페이지에 상태(미출현 등) 마커와 요약 카운트가 노출된다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    with patch.object(wd, "get_draws", return_value=_draws()):
        c = TestClient(app)
        response = c.get("/numbers/cycle")

    assert response.status_code == 200
    html = response.text
    # 미출현 상태 라벨 (29개 이상 존재)
    assert "미출현" in html


# ---------------------------------------------------------------------------
# AC-17: 데이터 부재에도 200 (빈 상태)
# ---------------------------------------------------------------------------


def test_cycle_page_no_data_returns_200() -> None:
    """get_draws가 None이어도 /numbers/cycle는 200을 반환한다 (빈 상태)."""
    from lotto.web import data as wd
    from lotto.web.app import app

    with patch.object(wd, "get_draws", return_value=None):
        c = TestClient(app)
        response = c.get("/numbers/cycle")

    assert response.status_code == 200, response.text
    # 빈 상태 안내 문구
    assert "데이터가 없습니다" in response.text


# ---------------------------------------------------------------------------
# AC-18: 인덱스 네비게이션 링크
# ---------------------------------------------------------------------------


def test_index_has_cycle_nav_link() -> None:
    """GET / 응답 HTML에 /numbers/cycle 네비게이션 링크가 포함된다."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.get("/")
    assert response.status_code == 200
    assert 'href="/numbers/cycle"' in response.text
