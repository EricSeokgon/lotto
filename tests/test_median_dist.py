"""SPEC-LOTTO-141 번호 중앙값 분포 분석 테스트."""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_median_dist_analysis

client = TestClient(app)


def _mk(no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """DrawResult 헬퍼."""
    return DrawResult(
        drwNo=no,
        date=datetime.date(2020, 1, 1) + datetime.timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2],
        n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# ---------------------------------------------------------------------------
# 샘플 데이터
# ---------------------------------------------------------------------------

_DRAWS = [
    # median = (3+4)/2 = 3.5 (정수 아님)
    _mk(1, [1, 2, 3, 4, 5, 6]),
    # median = (20+30)/2 = 25.0 (정수)
    _mk(2, [10, 15, 20, 30, 40, 45]),
    # median = (15+20)/2 = 17.5 (정수 아님)
    _mk(3, [5, 10, 15, 20, 25, 30]),
    # median = (21+28)/2 = 24.5 (정수 아님)
    _mk(4, [7, 14, 21, 28, 35, 42]),
    # median = (15+21)/2 = 18.0 (정수)
    _mk(5, [3, 9, 15, 21, 27, 33]),
]


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------

class TestGetMedianDistAnalysis:
    """get_median_dist_analysis() 단위 테스트."""

    def test_returns_none_when_empty(self) -> None:
        """빈 draws 목록이면 None 반환."""
        with patch("lotto.web.data.get_draws", return_value=[]):
            result = get_median_dist_analysis()
        assert result is None

    def test_returns_dict(self) -> None:
        """정상 데이터이면 dict 반환."""
        with patch("lotto.web.data.get_draws", return_value=_DRAWS):
            result = get_median_dist_analysis()
        assert isinstance(result, dict)

    def test_required_keys(self) -> None:
        """필수 키 모두 존재."""
        required = {
            "total", "actual_avg", "theoretical_avg", "avg_diff",
            "actual_min", "actual_max", "int_count", "half_count",
            "bucket_list", "top_medians", "recent",
        }
        with patch("lotto.web.data.get_draws", return_value=_DRAWS):
            result = get_median_dist_analysis()
        assert result is not None
        assert required.issubset(result.keys())

    def test_theoretical_avg_is_23(self) -> None:
        """이론적 중앙값은 23.0."""
        with patch("lotto.web.data.get_draws", return_value=_DRAWS):
            result = get_median_dist_analysis()
        assert result is not None
        assert result["theoretical_avg"] == 23.0

    def test_int_plus_half_equals_total(self) -> None:
        """int_count + half_count == total."""
        with patch("lotto.web.data.get_draws", return_value=_DRAWS):
            result = get_median_dist_analysis()
        assert result is not None
        assert result["int_count"] + result["half_count"] == result["total"]

    def test_bucket_list_length_is_9(self) -> None:
        """bucket_list 길이는 9 (1~5, 6~10, ..., 41~45)."""
        with patch("lotto.web.data.get_draws", return_value=_DRAWS):
            result = get_median_dist_analysis()
        assert result is not None
        assert len(result["bucket_list"]) == 9

    def test_median_calculation(self) -> None:
        """[5,10,15,20,25,30] → median = (15+20)/2 = 17.5."""
        draws = [_mk(1, [5, 10, 15, 20, 25, 30])]
        with patch("lotto.web.data.get_draws", return_value=draws):
            result = get_median_dist_analysis()
        assert result is not None
        # actual_min == actual_max == 17.5
        assert result["actual_min"] == 17.5
        assert result["actual_max"] == 17.5

    def test_top_medians_lte_10(self) -> None:
        """top_medians 최대 10개."""
        with patch("lotto.web.data.get_draws", return_value=_DRAWS):
            result = get_median_dist_analysis()
        assert result is not None
        assert len(result["top_medians"]) <= 10

    def test_recent_length_lte_20(self) -> None:
        """recent 최대 20개."""
        many_draws = [_mk(i, [1, 2, 3, 4, 5, i % 39 + 6]) for i in range(1, 31)]
        with patch("lotto.web.data.get_draws", return_value=many_draws):
            result = get_median_dist_analysis()
        assert result is not None
        assert len(result["recent"]) <= 20


# ---------------------------------------------------------------------------
# HTTP 통합 테스트
# ---------------------------------------------------------------------------

class TestMedianDistPage:
    """GET /stats/median-dist 통합 테스트."""

    def test_median_dist_page_200(self) -> None:
        """GET /stats/median-dist → 200 OK."""
        response = client.get("/stats/median-dist")
        assert response.status_code == 200
