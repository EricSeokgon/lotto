"""SPEC-LOTTO-126 번호 구간 조합(저/중/고) 분석 테스트."""

from __future__ import annotations

import datetime
import re
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_range_combo_analysis

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
    # 저:2 중:2 고:2 → 2-2-2
    _mk(1, [1, 10, 16, 25, 31, 40]),
    # 저:3 중:2 고:1 → 3-2-1
    _mk(2, [1, 5, 12, 16, 25, 33]),
    # 저:3 중:2 고:1 → 3-2-1
    _mk(3, [2, 6, 14, 17, 28, 35]),
    # 저:1 중:3 고:2 → 1-3-2
    _mk(4, [5, 16, 20, 29, 32, 44]),
    # 저:2 중:2 고:2 → 2-2-2
    _mk(5, [3, 12, 18, 27, 33, 42]),
]


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------

def test_returns_none_when_empty() -> None:
    """데이터 없을 때 None을 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=[]):
        result = get_range_combo_analysis()
    assert result is None


def test_returns_dict() -> None:
    """정상 데이터일 때 dict를 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_range_combo_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """필수 키가 모두 존재한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_range_combo_analysis()
    assert result is not None
    required = {
        "total", "best_combo", "best_combo_count", "best_combo_pct",
        "total_combos", "top_combos", "zone_data",
    }
    assert required <= result.keys()


def test_best_combo_format() -> None:
    """최빈 조합 형식이 '숫자-숫자-숫자' 패턴이다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_range_combo_analysis()
    assert result is not None
    assert re.fullmatch(r"\d+-\d+-\d+", result["best_combo"]) is not None


def test_top_combos_max_15() -> None:
    """top_combos는 최대 15개까지만 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_range_combo_analysis()
    assert result is not None
    assert len(result["top_combos"]) <= 15


def test_top_combos_sum_correct() -> None:
    """top_combos의 count 합은 total 이하다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_range_combo_analysis()
    assert result is not None
    total_count = sum(item["count"] for item in result["top_combos"])
    assert total_count <= result["total"]


def test_zone_data_keys() -> None:
    """zone_data에 'low', 'mid', 'high' 키가 존재한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_range_combo_analysis()
    assert result is not None
    assert set(result["zone_data"].keys()) == {"low", "mid", "high"}


def test_zone_data_each_has_7_entries() -> None:
    """각 구간 리스트는 0~6 총 7개 항목을 가진다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_range_combo_analysis()
    assert result is not None
    for zone_key in ("low", "mid", "high"):
        assert len(result["zone_data"][zone_key]) == 7


def test_zone_data_sum_equals_total() -> None:
    """각 구간의 freq 합은 전체 회차 수와 같다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_range_combo_analysis()
    assert result is not None
    total = result["total"]
    for zone_key in ("low", "mid", "high"):
        zone_sum = sum(item["freq"] for item in result["zone_data"][zone_key])
        assert zone_sum == total, f"{zone_key} zone freq sum {zone_sum} != total {total}"


def test_range_combo_page_200() -> None:
    """'/stats/range-combo' 페이지가 200을 반환한다."""
    response = client.get("/stats/range-combo")
    assert response.status_code == 200
