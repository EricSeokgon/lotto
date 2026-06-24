"""SPEC-LOTTO-127 배수 분석 테스트."""

from __future__ import annotations

import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_multiples_analysis

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


_DRAWS = [
    _mk(1, [3, 6, 10, 15, 21, 40]),   # 3의배수: 3,6,15,21 = 4개; 5의배수: 10,15,40 = 3개; 7의배수: 21 = 1개
    _mk(2, [5, 9, 14, 20, 27, 35]),   # 3의배수: 9,27 = 2개; 5의배수: 5,20,35 = 3개; 7의배수: 14,35 = 2개
    _mk(3, [2, 7, 12, 25, 33, 42]),   # 3의배수: 12,33,42 = 3개; 5의배수: 25 = 1개; 7의배수: 7,42 = 2개
    _mk(4, [1, 4, 8, 11, 16, 23]),    # 3의배수: 0개; 5의배수: 0개; 7의배수: 0개
    _mk(5, [15, 21, 28, 30, 35, 45]), # 3의배수: 15,21,30,45 = 4개; 5의배수: 15,35,45 = 3개; 7의배수: 21,28,35 = 3개
]


def test_returns_none_when_empty() -> None:
    """draws가 없으면 None 반환."""
    with patch("lotto.web.data.get_draws", return_value=[]):
        result = get_multiples_analysis()
    assert result is None


def test_returns_dict() -> None:
    """정상 데이터에서 dict 반환."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_multiples_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """total, mult3, mult5, mult7 키 존재."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_multiples_analysis()
    assert result is not None
    assert "total" in result
    assert "mult3" in result
    assert "mult5" in result
    assert "mult7" in result


def test_mult3_size_is_15() -> None:
    """3의 배수 집합 크기는 15."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_multiples_analysis()
    assert result is not None
    assert result["mult3"]["size"] == 15


def test_mult5_size_is_9() -> None:
    """5의 배수 집합 크기는 9."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_multiples_analysis()
    assert result is not None
    assert result["mult5"]["size"] == 9


def test_mult7_size_is_6() -> None:
    """7의 배수 집합 크기는 6."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_multiples_analysis()
    assert result is not None
    assert result["mult7"]["size"] == 6


def test_mult3_dist_sum_equals_total() -> None:
    """3의 배수 분포 합계는 전체 회차 수."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_multiples_analysis()
    assert result is not None
    total = result["total"]
    dist_sum = sum(item["freq"] for item in result["mult3"]["dist_list"])
    assert dist_sum == total


def test_mult5_dist_sum_equals_total() -> None:
    """5의 배수 분포 합계는 전체 회차 수."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_multiples_analysis()
    assert result is not None
    total = result["total"]
    dist_sum = sum(item["freq"] for item in result["mult5"]["dist_list"])
    assert dist_sum == total


def test_rate_range() -> None:
    """3의 배수 실제 출현율은 0~100 범위."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_multiples_analysis()
    assert result is not None
    rate = result["mult3"]["rate"]
    assert 0.0 <= rate <= 100.0


def test_multiples_page_200() -> None:
    """배수 분석 페이지 HTTP 200 반환."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        resp = client.get("/stats/multiples")
    assert resp.status_code == 200
