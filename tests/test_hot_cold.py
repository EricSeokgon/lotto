"""SPEC-LOTTO-128 핫/콜드 번호 분석 테스트."""

from __future__ import annotations

import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_hot_cold_analysis

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


# 15회 기준 draws — 최근 10회에서 1번이 5회 출현(hot), 45번은 미출현(cold)
_DRAWS = [
    _mk(1,  [2,  3,  4,  5,  6,  7]),
    _mk(2,  [2,  3,  4,  5,  6,  8]),
    _mk(3,  [2,  3,  4,  5,  6,  9]),
    _mk(4,  [2,  3,  4,  5,  6, 10]),
    _mk(5,  [2,  3,  4,  5,  6, 11]),
    # 최근 10회 시작
    _mk(6,  [1,  2,  3,  4,  5,  6]),
    _mk(7,  [1,  2,  3,  4,  5,  7]),
    _mk(8,  [1,  2,  3,  4,  5,  8]),
    _mk(9,  [1,  2,  3,  4,  5,  9]),
    _mk(10, [1,  2,  3,  4,  5, 10]),
    _mk(11, [1,  2,  3,  4,  5, 11]),
    _mk(12, [1,  2,  3,  4,  5, 12]),
    _mk(13, [1,  2,  3,  4,  5, 13]),
    _mk(14, [1,  2,  3,  4,  5, 14]),
    _mk(15, [1,  2,  3,  4,  5, 15]),
]


def test_returns_none_when_empty() -> None:
    """빈 draws일 때 None 반환."""
    with patch("lotto.web.data.get_draws", return_value=[]):
        result = get_hot_cold_analysis()
    assert result is None


def test_returns_dict() -> None:
    """정상 draws일 때 dict 반환."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_hot_cold_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """필수 키 존재 확인."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_hot_cold_analysis()
    assert result is not None
    required = {"total", "numbers", "hot_count", "cold_count", "top_hot", "top_cold", "expected_rate"}
    assert required <= result.keys()


def test_numbers_length_is_45() -> None:
    """numbers 리스트는 45개."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_hot_cold_analysis()
    assert result is not None
    assert len(result["numbers"]) == 45


def test_status_values() -> None:
    """모든 status 값이 'hot', 'warm', 'cold' 중 하나."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_hot_cold_analysis()
    assert result is not None
    valid = {"hot", "warm", "cold"}
    for item in result["numbers"]:
        assert item["status"] in valid


def test_hot_count_plus_cold_count_le_45() -> None:
    """hot_count + cold_count <= 45."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_hot_cold_analysis()
    assert result is not None
    assert result["hot_count"] + result["cold_count"] <= 45


def test_top_hot_max_10() -> None:
    """top_hot 최대 10개."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_hot_cold_analysis()
    assert result is not None
    assert len(result["top_hot"]) <= 10


def test_top_cold_max_10() -> None:
    """top_cold 최대 10개."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_hot_cold_analysis()
    assert result is not None
    assert len(result["top_cold"]) <= 10


def test_expected_rate_approx() -> None:
    """expected_rate ≈ 13.33."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        result = get_hot_cold_analysis()
    assert result is not None
    assert abs(result["expected_rate"] - 13.33) < 0.1


def test_hot_cold_page_200() -> None:
    """핫/콜드 페이지 HTTP 200."""
    with patch("lotto.web.data.get_draws", return_value=_DRAWS):
        resp = client.get("/stats/hot-cold")
    assert resp.status_code == 200
