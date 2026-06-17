"""SPEC-LOTTO-049: GET /stats/sum-range 페이지 + 네비게이션 링크 테스트.

차트/테이블 마커, 데이터 부재 빈 상태, 인덱스 네비 링크 노출을 검증한다.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult


def _mk(no: int, nums: list[int]) -> DrawResult:
    return DrawResult(
        drwNo=no, date=date(2020, 1, 1),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=10,
    )


def _draws() -> list[DrawResult]:
    return [
        _mk(1, [1, 2, 3, 4, 5, 15]),       # 30
        _mk(2, [1, 2, 3, 4, 20, 45]),      # 75
        _mk(3, [1, 2, 3, 43, 44, 45]),     # 138
    ]


def test_sum_range_page_returns_200_html() -> None:
    """GET /stats/sum-range → 200 HTML."""
    from lotto.web import data as wd
    from lotto.web.app import app

    with patch.object(wd, "get_draws", return_value=_draws()):
        response = TestClient(app).get("/stats/sum-range")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "합계" in response.text


def test_sum_range_page_contains_chart_and_table_markers() -> None:
    """차트 canvas 와 분포 테이블 마커가 포함된다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    with patch.object(wd, "get_draws", return_value=_draws()):
        response = TestClient(app).get("/stats/sum-range")
    assert "sumRangeChart" in response.text
    assert "<table" in response.text
    assert "121-140" in response.text  # 최빈 구간 라벨


def test_sum_range_page_no_data_returns_200() -> None:
    """get_draws None → 200 빈 상태."""
    from lotto.web import data as wd
    from lotto.web.app import app

    with patch.object(wd, "get_draws", return_value=None):
        response = TestClient(app).get("/stats/sum-range")
    assert response.status_code == 200
    assert "데이터가 없습니다" in response.text


def test_index_has_sum_range_nav_link() -> None:
    """GET / 응답 HTML에 /stats/sum-range 네비게이션 링크가 포함된다."""
    from lotto.web.app import app

    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert 'href="/stats/sum-range"' in response.text
