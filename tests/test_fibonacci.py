"""SPEC-LOTTO-142 피보나치 번호 분포 분석 테스트."""

from __future__ import annotations

import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_fibonacci_analysis

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
    # 피보나치 6개 포함: 1,2,3,5,8,13
    _mk(1, [1, 2, 3, 5, 8, 13]),
    # 피보나치 2개 포함: 1,2
    _mk(2, [1, 2, 10, 20, 30, 40]),
    # 피보나치 0개 포함
    _mk(3, [4, 6, 7, 9, 10, 11]),
    # 피보나치 1개 포함: 34
    _mk(4, [11, 15, 22, 29, 34, 43]),
    # 피보나치 3개 포함: 5,21,34
    _mk(5, [5, 12, 18, 21, 34, 44]),
]


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------

class TestGetFibonacciAnalysis:
    """get_fibonacci_analysis() 단위 테스트."""

    def test_returns_none_when_empty(self) -> None:
        """빈 draws 목록이면 None 반환."""
        with patch("lotto.web.data.get_draws", return_value=[]):
            result = get_fibonacci_analysis()
        assert result is None

    def test_returns_dict(self) -> None:
        """정상 데이터이면 dict 반환."""
        with patch("lotto.web.data.get_draws", return_value=_DRAWS):
            result = get_fibonacci_analysis()
        assert isinstance(result, dict)

    def test_required_keys(self) -> None:
        """필수 키 모두 존재."""
        required = {
            "total", "fib_count", "fib_numbers", "avg_fib", "expected",
            "diff", "best_count", "dist_list", "freq_list", "recent",
        }
        with patch("lotto.web.data.get_draws", return_value=_DRAWS):
            result = get_fibonacci_analysis()
        assert result is not None
        assert required.issubset(result.keys())

    def test_fib_count_is_8(self) -> None:
        """피보나치 수는 8개."""
        with patch("lotto.web.data.get_draws", return_value=_DRAWS):
            result = get_fibonacci_analysis()
        assert result is not None
        assert result["fib_count"] == 8

    def test_fib_numbers(self) -> None:
        """피보나치 수 집합이 {1,2,3,5,8,13,21,34}."""
        with patch("lotto.web.data.get_draws", return_value=_DRAWS):
            result = get_fibonacci_analysis()
        assert result is not None
        assert set(result["fib_numbers"]) == {1, 2, 3, 5, 8, 13, 21, 34}

    def test_dist_list_length_is_7(self) -> None:
        """dist_list 길이는 7 (0~6개)."""
        with patch("lotto.web.data.get_draws", return_value=_DRAWS):
            result = get_fibonacci_analysis()
        assert result is not None
        assert len(result["dist_list"]) == 7

    def test_freq_list_length_is_8(self) -> None:
        """freq_list 길이는 8 (피보나치 수 개수)."""
        with patch("lotto.web.data.get_draws", return_value=_DRAWS):
            result = get_fibonacci_analysis()
        assert result is not None
        assert len(result["freq_list"]) == 8

    def test_diff_calculation(self) -> None:
        """diff == round(avg_fib - expected, 3)."""
        with patch("lotto.web.data.get_draws", return_value=_DRAWS):
            result = get_fibonacci_analysis()
        assert result is not None
        assert round(result["avg_fib"] - result["expected"], 3) == result["diff"]

    def test_recent_length_lte_20(self) -> None:
        """recent 최대 20개."""
        many_draws = [_mk(i, [1, 2, 3, i % 40 + 4, i % 39 + 5, i % 38 + 6]) for i in range(1, 31)]
        with patch("lotto.web.data.get_draws", return_value=many_draws):
            result = get_fibonacci_analysis()
        assert result is not None
        assert len(result["recent"]) <= 20


# ---------------------------------------------------------------------------
# HTTP 통합 테스트
# ---------------------------------------------------------------------------

class TestFibonacciPage:
    """GET /stats/fibonacci 통합 테스트."""

    def test_fibonacci_page_200(self) -> None:
        """GET /stats/fibonacci → 200 OK."""
        response = client.get("/stats/fibonacci")
        assert response.status_code == 200
