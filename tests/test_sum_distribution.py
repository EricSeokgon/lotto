"""SPEC-LOTTO-140 번호 합계 분포 분석 테스트."""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_sum_distribution_analysis

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
    # 합계: 1+2+3+4+5+6 = 21 (최솟값)
    _mk(1, [1, 2, 3, 4, 5, 6]),
    # 합계: 10+20+30+40+41+42 = 183
    _mk(2, [10, 20, 30, 40, 41, 42]),
    # 합계: 5+15+25+35+40+45 = 165
    _mk(3, [5, 15, 25, 35, 40, 45]),
    # 합계: 7+14+21+28+35+42 = 147
    _mk(4, [7, 14, 21, 28, 35, 42]),
    # 합계: 3+9+15+21+27+33 = 108
    _mk(5, [3, 9, 15, 21, 27, 33]),
]


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------

def test_returns_none_when_empty() -> None:
    """데이터 없을 때 None을 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=[]):
        result = get_sum_distribution_analysis()
    assert result is None


def test_returns_dict() -> None:
    """정상 데이터일 때 dict를 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_sum_distribution_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """필수 키를 모두 포함한다."""
    from lotto.web import data as wd

    required_keys = {
        "total", "actual_min", "actual_max", "actual_avg",
        "theoretical_avg", "avg_diff", "mode_sum", "mode_count",
        "peak_range", "bucket_list", "top_sums", "recent",
    }
    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_sum_distribution_analysis()
    assert result is not None
    assert required_keys.issubset(result.keys())


def test_theoretical_avg_is_138() -> None:
    """이론적 평균은 138.0이다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_sum_distribution_analysis()
    assert result is not None
    assert result["theoretical_avg"] == 138.0


def test_actual_min_gte_21() -> None:
    """실제 최솟값은 이론적 최솟값 21 이상이다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_sum_distribution_analysis()
    assert result is not None
    assert result["actual_min"] >= 21


def test_actual_max_lte_255() -> None:
    """실제 최댓값은 이론적 최댓값 255 이하이다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_sum_distribution_analysis()
    assert result is not None
    assert result["actual_max"] <= 255


def test_bucket_list_nonempty() -> None:
    """구간 목록이 비어있지 않다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_sum_distribution_analysis()
    assert result is not None
    assert len(result["bucket_list"]) > 0


def test_top_sums_lte_10() -> None:
    """최빈 합계 목록은 최대 10개이다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_sum_distribution_analysis()
    assert result is not None
    assert len(result["top_sums"]) <= 10


def test_recent_length_lte_20() -> None:
    """최근 회차 목록은 최대 20개이다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_sum_distribution_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_sum_distribution_page_200() -> None:
    """GET /stats/sum-distribution 응답이 200이다."""
    response = client.get("/stats/sum-distribution")
    assert response.status_code == 200
