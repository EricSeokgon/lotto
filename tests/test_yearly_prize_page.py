"""SPEC-LOTTO-046: GET /stats/yearly-prize 페이지 + 네비게이션 링크 테스트.

페이지 렌더링 → 200, 테이블/차트 마커 포함, 데이터 부재에도 200,
인덱스 페이지에 /stats/yearly-prize 네비 링크 노출을 검증한다.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult


def _mk(
    no: int, d: date, nums: list[int], bonus: int,
    prize: int | None = None, winners: int | None = None,
) -> DrawResult:
    return DrawResult(
        drwNo=no, date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus, prize1Amount=prize, prize1Winners=winners,
    )


# ---------------------------------------------------------------------------
# AC-14: 페이지 렌더링 → 200 HTML (결과 + 차트/테이블 마커)
# ---------------------------------------------------------------------------


def test_yearly_prize_page_returns_200_html() -> None:
    """GET /stats/yearly-prize → 200 HTML, 차트/테이블 마커 포함."""
    from lotto.web import data as wd
    from lotto.web.app import app

    nums = [1, 10, 20, 30, 40, 45]
    draws = [
        _mk(1, date(2022, 1, 1), nums, 5, prize=1000, winners=1),
        _mk(2, date(2023, 1, 1), nums, 5, prize=3000, winners=2),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/stats/yearly-prize")

    assert response.status_code == 200, response.text
    html = response.text
    # 차트 canvas + 연도별 테이블 마커
    assert "yearlyPrizeChart" in html
    assert "연도별" in html
    # 연도 라벨이 테이블에 노출
    assert "2022" in html
    assert "2023" in html


# ---------------------------------------------------------------------------
# AC-15: 데이터 부재에도 200 (빈 상태)
# ---------------------------------------------------------------------------


def test_yearly_prize_page_no_data_returns_200() -> None:
    """get_draws가 None이어도 /stats/yearly-prize는 200을 반환한다 (빈 상태)."""
    from lotto.web import data as wd
    from lotto.web.app import app

    with patch.object(wd, "get_draws", return_value=None):
        c = TestClient(app)
        response = c.get("/stats/yearly-prize")

    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# AC-16: 인덱스 네비게이션 링크
# ---------------------------------------------------------------------------


def test_index_has_yearly_prize_nav_link() -> None:
    """GET / 응답 HTML에 /stats/yearly-prize 네비게이션 링크가 포함된다."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.get("/")
    assert response.status_code == 200
    assert 'href="/stats/yearly-prize"' in response.text


# ---------------------------------------------------------------------------
# AC-17: 데이터 부재 시 빈 상태 메시지 노출
# ---------------------------------------------------------------------------


def test_yearly_prize_page_empty_state_message() -> None:
    """데이터 부재 시 빈 상태 안내 문구가 노출된다 (차트 미렌더)."""
    from lotto.web import data as wd
    from lotto.web.app import app

    with patch.object(wd, "get_draws", return_value=None):
        c = TestClient(app)
        response = c.get("/stats/yearly-prize")

    assert response.status_code == 200
    # 빈 상태에서는 데이터 없음 안내가 노출된다
    assert "데이터가 없습니다" in response.text
