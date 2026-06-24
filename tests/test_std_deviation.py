"""SPEC-LOTTO-125 번호 표준편차 분석 테스트."""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_std_deviation_analysis

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
    # 번호가 몰린 케이스 (낮은 표준편차)
    _mk(1, [1, 2, 3, 4, 5, 6]),
    # 번호가 고르게 퍼진 케이스 (높은 표준편차)
    _mk(2, [1, 10, 20, 30, 40, 45]),
    # 중간 케이스
    _mk(3, [5, 12, 20, 28, 36, 42]),
]


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------

def test_returns_none_when_empty() -> None:
    """데이터 없을 때 None을 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=[]):
        result = get_std_deviation_analysis()
    assert result is None


def test_returns_dict() -> None:
    """정상 데이터일 때 dict를 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_std_deviation_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """필수 키가 모두 존재한다."""
    from lotto.web import data as wd

    required = {
        "total", "avg_std", "min_std", "max_std",
        "min_draw", "max_draw", "best_bucket_label",
        "best_bucket_pct", "bucket_list", "recent",
    }
    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_std_deviation_analysis()
    assert result is not None
    assert required.issubset(result.keys())


def test_avg_std_positive() -> None:
    """avg_std는 0보다 크다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_std_deviation_analysis()
    assert result is not None
    assert result["avg_std"] > 0


def test_min_std_le_max_std() -> None:
    """min_std는 max_std 이하다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_std_deviation_analysis()
    assert result is not None
    assert result["min_std"] <= result["max_std"]


def test_bucket_list_length_is_6() -> None:
    """bucket_list 길이는 6이다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_std_deviation_analysis()
    assert result is not None
    assert len(result["bucket_list"]) == 6


def test_bucket_list_sum_equals_total() -> None:
    """bucket_list count 합계는 전체 회차 수와 같다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_std_deviation_analysis()
    assert result is not None
    total_from_buckets = sum(b["count"] for b in result["bucket_list"])
    assert total_from_buckets == result["total"]


def test_recent_length_lte_20() -> None:
    """recent 길이는 최대 20이다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_std_deviation_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_recent_has_std_key() -> None:
    """recent 각 항목에 std 키가 있다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_std_deviation_analysis()
    assert result is not None
    for item in result["recent"]:
        assert "std" in item
        assert item["std"] >= 0


def test_std_deviation_page_200() -> None:
    """표준편차 분석 페이지가 200 OK를 반환한다."""
    from lotto.web import data as wd

    mock_data = {
        "total": 3,
        "avg_std": 8.5,
        "min_std": 1.87,
        "min_draw": {"drwNo": 1, "numbers": [1, 2, 3, 4, 5, 6]},
        "max_std": 15.32,
        "max_draw": {"drwNo": 2, "numbers": [1, 10, 20, 30, 40, 45]},
        "best_bucket_label": "8~10",
        "best_bucket_pct": 33.3,
        "bucket_list": [
            {"label": "0~4", "count": 1, "pct": 33.3},
            {"label": "5~7", "count": 0, "pct": 0.0},
            {"label": "8~10", "count": 1, "pct": 33.3},
            {"label": "11~13", "count": 0, "pct": 0.0},
            {"label": "14~16", "count": 1, "pct": 33.3},
            {"label": "17+", "count": 0, "pct": 0.0},
        ],
        "recent": [
            {"drwNo": 3, "numbers": [5, 12, 20, 28, 36, 42], "std": 13.2},
        ],
    }
    with patch.object(wd, "get_std_deviation_analysis", return_value=mock_data):
        response = client.get("/stats/std-deviation")
    assert response.status_code == 200
    assert "번호 표준편차 분석" in response.text
