"""SPEC-LOTTO-130: 번호 범위(최대-최소) 분포 분석 테스트."""
from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_number_range_analysis

client = TestClient(app)


def make_draws(nums_list: list[list[int]]) -> list[DrawResult]:
    """번호 목록으로 DrawResult 리스트를 생성하는 헬퍼."""
    draws = []
    for i, nums in enumerate(nums_list, start=1):
        draws.append(DrawResult(
            drwNo=i,
            date=datetime.date(2020, 1, 1) + datetime.timedelta(days=i),
            n1=nums[0], n2=nums[1], n3=nums[2],
            n4=nums[3], n5=nums[4], n6=nums[5],
            bonus=7,
        ))
    return draws


SAMPLE = [
    [1, 5, 10, 20, 30, 40],
    [3, 8, 15, 25, 35, 42],
    [2, 6, 12, 22, 32, 44],
    [4, 9, 18, 28, 38, 45],
    [7, 11, 16, 24, 34, 43],
]


def test_returns_none_when_empty() -> None:
    """데이터 없으면 None 반환."""
    with patch("lotto.web.data.get_draws", return_value=[]):
        assert get_number_range_analysis() is None


def test_returns_dict() -> None:
    """정상 데이터 시 dict 반환."""
    draws = make_draws(SAMPLE)
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_number_range_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """필수 키 존재 검증."""
    draws = make_draws(SAMPLE)
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_number_range_analysis()
    assert result is not None
    for key in [
        "total", "avg_range", "min_range", "max_range",
        "min_draw", "max_draw", "best_bucket_label",
        "bucket_list", "top_min", "top_max", "recent",
    ]:
        assert key in result


def test_avg_range_in_bounds() -> None:
    """평균 범위는 5~44 사이."""
    draws = make_draws(SAMPLE)
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_number_range_analysis()
    assert result is not None
    assert 5 <= result["avg_range"] <= 44


def test_min_le_avg_le_max() -> None:
    """최소 범위 <= 평균 범위 <= 최대 범위."""
    draws = make_draws(SAMPLE)
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_number_range_analysis()
    assert result is not None
    assert result["min_range"] <= result["avg_range"] <= result["max_range"]


def test_bucket_list_length_is_7() -> None:
    """버킷 리스트 길이는 7."""
    draws = make_draws(SAMPLE)
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_number_range_analysis()
    assert result is not None
    assert len(result["bucket_list"]) == 7


def test_bucket_list_sum_equals_total() -> None:
    """버킷 count 합계 == total."""
    draws = make_draws(SAMPLE)
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_number_range_analysis()
    assert result is not None
    assert sum(b["count"] for b in result["bucket_list"]) == result["total"]


def test_top_min_max_10() -> None:
    """top_min, top_max는 최대 10개."""
    draws = make_draws(SAMPLE)
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_number_range_analysis()
    assert result is not None
    assert len(result["top_min"]) <= 10
    assert len(result["top_max"]) <= 10


def test_recent_length_lte_20() -> None:
    """recent 길이는 최대 20."""
    draws = make_draws(SAMPLE)
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_number_range_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_number_range_page_200() -> None:
    """번호 범위 분석 페이지 HTTP 200 응답."""
    response = client.get("/stats/number-range")
    assert response.status_code == 200
