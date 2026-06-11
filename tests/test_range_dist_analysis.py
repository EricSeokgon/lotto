"""SPEC-LOTTO-068: 번호 구간별 분포 분석 테스트.

데이터 계층(get_range_dist_stats), 캐시, 페이지/API 라우트를
RED-GREEN-REFACTOR로 검증한다.

분석(회차별 본번호 6개, 보너스 제외):
- 각 번호를 5개 고정 구간 중 정확히 하나로 분류한다.
    "1-9"(<=9), "10-19"(<=19), "20-29"(<=29), "30-39"(<=39), "40-45"(>=40)
- 총합/소수합과 달리 한 회차가 여러 구간에 동시에 기여한다.
- range_stats: 5개 구간 키를 항상 포함하는 중첩 dict. 각 구간마다
    total_count / draw_count / avg_per_draw / pct_of_numbers / draw_pct.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd

if TYPE_CHECKING:
    from collections.abc import Iterator  # noqa: F401


_RANGE_KEYS = ["1-9", "10-19", "20-29", "30-39", "40-45"]


def _mk(no: int, nums: list[int], bonus: int = 1) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    bonus는 본번호 외 값을 사용해 구간 집계에 영향을 주지 않음을 검증할 수 있게 한다.
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# --------------------------------------------------------------------------- #
# 빈 데이터 / 일관된 빈 구조
# --------------------------------------------------------------------------- #


def test_empty_returns_zero_stats() -> None:
    """AC-068-001: 빈 리스트는 total_draws=0 과 5 구간 zero-fill 을 반환한다."""
    result = wd.get_range_dist_stats([])
    assert result["total_draws"] == 0
    assert result["most_covered_range"] == ""
    assert list(result["range_stats"].keys()) == _RANGE_KEYS
    for r in _RANGE_KEYS:
        rs = result["range_stats"][r]
        assert rs["total_count"] == 0
        assert rs["draw_count"] == 0
        assert rs["avg_per_draw"] == 0.0
        assert rs["pct_of_numbers"] == 0.0
        assert rs["draw_pct"] == 0.0


def test_empty_has_all_five_ranges() -> None:
    """빈 데이터에서도 5개 구간 키가 모두 존재한다."""
    result = wd.get_range_dist_stats([])
    assert list(result["range_stats"].keys()) == _RANGE_KEYS


def test_none_returns_zero_stats() -> None:
    """None 입력도 빈 데이터와 동일한 구조를 반환한다."""
    result = wd.get_range_dist_stats(None)
    assert result["total_draws"] == 0
    assert list(result["range_stats"].keys()) == _RANGE_KEYS


# --------------------------------------------------------------------------- #
# 구간 분류 / 집계
# --------------------------------------------------------------------------- #


def test_single_range_low() -> None:
    """AC-068-002: 6개 번호 [1..6] 전부 '1-9' 구간."""
    result = wd.get_range_dist_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert result["range_stats"]["1-9"]["total_count"] == 6
    for r in ["10-19", "20-29", "30-39", "40-45"]:
        assert result["range_stats"][r]["total_count"] == 0


def test_single_range_high() -> None:
    """AC-068-003: 6개 번호 [40..45] 전부 '40-45' 구간."""
    result = wd.get_range_dist_stats([_mk(1, [40, 41, 42, 43, 44, 45])])
    assert result["range_stats"]["40-45"]["total_count"] == 6
    for r in ["1-9", "10-19", "20-29", "30-39"]:
        assert result["range_stats"][r]["total_count"] == 0


def test_multi_range_spread() -> None:
    """AC-068-004: [5,15,25,35,42,43] 은 5개 구간에 분산된다."""
    result = wd.get_range_dist_stats([_mk(1, [5, 15, 25, 35, 42, 43])])
    rs = result["range_stats"]
    assert rs["1-9"]["total_count"] == 1
    assert rs["10-19"]["total_count"] == 1
    assert rs["20-29"]["total_count"] == 1
    assert rs["30-39"]["total_count"] == 1
    assert rs["40-45"]["total_count"] == 2


def test_bonus_excluded() -> None:
    """AC-068-005: 보너스 번호는 구간 집계에서 제외된다."""
    # bonus=1 ('1-9' 구간) 이지만 집계에 포함되면 안 됨
    result = wd.get_range_dist_stats([_mk(1, [5, 15, 25, 35, 42, 43], bonus=1)])
    assert result["range_stats"]["1-9"]["total_count"] == 1


def test_all_five_ranges_present_nonempty() -> None:
    """AC-068-006: 임의 비어 있지 않은 draws 에서도 5개 구간 키가 존재한다."""
    result = wd.get_range_dist_stats([_mk(1, [1, 11, 21, 31, 41, 45])])
    assert list(result["range_stats"].keys()) == _RANGE_KEYS


# --------------------------------------------------------------------------- #
# 수치 정확성
# --------------------------------------------------------------------------- #


def test_avg_per_draw_accuracy() -> None:
    """AC-068-007: 10회차에서 '1-9' 누적 15개 → avg_per_draw=1.5."""
    # 회차당 '1-9' 번호 개수를 조절: 5회는 2개, 5회는 1개 → 합 15
    draws = []
    for i in range(5):
        draws.append(_mk(i + 1, [1, 2, 11, 21, 31, 41]))  # '1-9' 2개
    for i in range(5):
        draws.append(_mk(i + 6, [1, 11, 12, 21, 31, 41]))  # '1-9' 1개
    result = wd.get_range_dist_stats(draws)
    assert result["range_stats"]["1-9"]["total_count"] == 15
    assert result["range_stats"]["1-9"]["avg_per_draw"] == 1.5


def test_pct_of_numbers_accuracy() -> None:
    """AC-068-008: 10회차에서 '1-9' 누적 15개 → pct_of_numbers=25.0."""
    draws = []
    for i in range(5):
        draws.append(_mk(i + 1, [1, 2, 11, 21, 31, 41]))
    for i in range(5):
        draws.append(_mk(i + 6, [1, 11, 12, 21, 31, 41]))
    result = wd.get_range_dist_stats(draws)
    # 15 / (10*6) * 100 = 25.0
    assert result["range_stats"]["1-9"]["pct_of_numbers"] == 25.0


def test_draw_count_accuracy() -> None:
    """AC-068-009: 3회차 중 2회차가 '40-45' 포함 → draw_count=2."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 40]),    # '40-45' 포함
        _mk(2, [10, 11, 12, 13, 14, 45]),  # '40-45' 포함
        _mk(3, [1, 11, 21, 31, 31, 32]),   # '40-45' 미포함
    ]
    result = wd.get_range_dist_stats(draws)
    assert result["range_stats"]["40-45"]["draw_count"] == 2


def test_draw_pct_accuracy() -> None:
    """AC-068-010: 3회차 중 2회차 포함 → draw_pct=66.67."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 40]),
        _mk(2, [10, 11, 12, 13, 14, 45]),
        _mk(3, [1, 11, 21, 31, 31, 32]),
    ]
    result = wd.get_range_dist_stats(draws)
    assert result["range_stats"]["40-45"]["draw_pct"] == 66.67


def test_draw_count_single_per_draw() -> None:
    """같은 구간 번호 여러 개여도 draw_count는 회차당 1만 증가한다."""
    # '1-9'에 3개 번호가 있어도 draw_count는 1
    result = wd.get_range_dist_stats([_mk(1, [1, 2, 3, 11, 21, 31])])
    assert result["range_stats"]["1-9"]["total_count"] == 3
    assert result["range_stats"]["1-9"]["draw_count"] == 1


# --------------------------------------------------------------------------- #
# most_covered_range
# --------------------------------------------------------------------------- #


def test_most_covered_range() -> None:
    """AC-068-011: '10-19' 가 단독 최다 draw_count 면 most_covered_range='10-19'."""
    # 3 회차 모두 '10-19' 포함(draw_count=3). 다른 구간은 일부 회차만 포함하도록
    # 구성하여 '10-19' 가 단독 최댓값이 되게 한다.
    draws = [
        _mk(1, [11, 12, 13, 14, 15, 16]),  # '10-19' 만 (draw_count: 10-19)
        _mk(2, [11, 12, 13, 14, 15, 1]),   # '10-19' + '1-9'
        _mk(3, [11, 12, 13, 14, 15, 21]),  # '10-19' + '20-29'
    ]
    result = wd.get_range_dist_stats(draws)
    # 10-19: 3, 1-9: 1, 20-29: 1, 나머지 0 → 단독 최댓값 '10-19'
    assert result["range_stats"]["10-19"]["draw_count"] == 3
    assert result["most_covered_range"] == "10-19"


def test_most_covered_range_tiebreak() -> None:
    """AC-068-012: 동점 시 _RANGES 에서 앞서는 구간이 이긴다."""
    # 모든 회차가 5개 구간 전부 포함 → draw_count 모두 동일 → '1-9' 이김
    draws = [
        _mk(1, [1, 11, 21, 31, 41, 42]),
        _mk(2, [2, 12, 22, 32, 43, 44]),
    ]
    result = wd.get_range_dist_stats(draws)
    assert result["most_covered_range"] == "1-9"


# --------------------------------------------------------------------------- #
# 불변식
# --------------------------------------------------------------------------- #


def test_draw_count_le_total_draws() -> None:
    """AC-068-013: 모든 구간에 대해 draw_count <= total_draws."""
    draws = [
        _mk(1, [5, 15, 25, 35, 42, 43]),
        _mk(2, [1, 2, 3, 11, 21, 31]),
        _mk(3, [40, 41, 42, 43, 44, 45]),
    ]
    result = wd.get_range_dist_stats(draws)
    n = result["total_draws"]
    for r in _RANGE_KEYS:
        assert result["range_stats"][r]["draw_count"] <= n


def test_pct_of_numbers_sums_to_100() -> None:
    """AC-068-014: 5개 구간 pct_of_numbers 합 ≈ 100.0."""
    draws = [
        _mk(1, [5, 15, 25, 35, 42, 43]),
        _mk(2, [1, 12, 23, 34, 40, 45]),
        _mk(3, [9, 10, 29, 30, 39, 44]),
    ]
    result = wd.get_range_dist_stats(draws)
    total_pct = sum(
        result["range_stats"][r]["pct_of_numbers"] for r in _RANGE_KEYS
    )
    assert abs(total_pct - 100.0) <= 0.1


# --------------------------------------------------------------------------- #
# 구간 경계값
# --------------------------------------------------------------------------- #


def test_boundary_9_vs_10() -> None:
    """AC-068-022: 번호 9 → '1-9', 번호 10 → '10-19'."""
    result = wd.get_range_dist_stats([_mk(1, [9, 10, 21, 31, 41, 45])])
    rs = result["range_stats"]
    assert rs["1-9"]["total_count"] == 1   # 9
    assert rs["10-19"]["total_count"] == 1  # 10


def test_boundary_19_vs_20_and_39_vs_40() -> None:
    """경계 19→'10-19', 20→'20-29', 39→'30-39', 40→'40-45'."""
    result = wd.get_range_dist_stats([_mk(1, [19, 20, 29, 30, 39, 40])])
    rs = result["range_stats"]
    assert rs["10-19"]["total_count"] == 1  # 19
    assert rs["20-29"]["total_count"] == 2  # 20, 29
    assert rs["30-39"]["total_count"] == 2  # 30, 39
    assert rs["40-45"]["total_count"] == 1  # 40


# --------------------------------------------------------------------------- #
# 입력 비변형
# --------------------------------------------------------------------------- #


def test_does_not_mutate_input() -> None:
    """집계가 입력 draws 리스트를 변형하지 않는다."""
    draws = [_mk(1, [5, 15, 25, 35, 42, 43])]
    before = list(draws)
    wd.get_range_dist_stats(draws)
    assert draws == before


# --------------------------------------------------------------------------- #
# 캐시
# --------------------------------------------------------------------------- #


def test_cache_hit_same_length() -> None:
    """AC-068-015: 동일 길이 입력의 재호출은 캐시된 동일 객체를 반환한다."""
    wd._range_dist_cache.clear()
    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    first = wd.get_range_dist_stats(draws)
    second = wd.get_range_dist_stats(draws)
    assert first is second
    assert "1" in wd._range_dist_cache


def test_cache_miss_different_length() -> None:
    """AC-068-016: 길이가 다른 입력은 캐시 미스로 새로 계산된다."""
    wd._range_dist_cache.clear()
    one = wd.get_range_dist_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    two = wd.get_range_dist_stats(
        [_mk(1, [1, 2, 3, 4, 5, 6]), _mk(2, [40, 41, 42, 43, 44, 45])]
    )
    assert one is not two
    assert "1" in wd._range_dist_cache
    assert "2" in wd._range_dist_cache


def test_invalidate_cache() -> None:
    """AC-068-017: invalidate_cache() 호출 시 구간 분포 캐시가 비워진다."""
    wd.get_range_dist_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert wd._range_dist_cache
    wd.invalidate_cache()
    assert not wd._range_dist_cache


# --------------------------------------------------------------------------- #
# 라우트: API / 페이지
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """AC-068-018: GET /api/stats/range_dist 는 구간 분포 JSON 을 200 으로 반환한다."""
    draws = [
        _mk(1, [5, 15, 25, 35, 42, 43]),
        _mk(2, [1, 12, 23, 34, 40, 45]),
        _mk(3, [9, 10, 29, 30, 39, 44]),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = _client().get("/api/stats/range_dist")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 3
    assert "most_covered_range" in body
    assert set(body["range_stats"].keys()) == set(_RANGE_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/range_dist 는 데이터가 없어도 200 을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/range_dist")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """AC-068-019: GET /stats/range_dist 는 200(구간 안내 포함)을 반환한다."""
    draws = [_mk(1, [5, 15, 25, 35, 42, 43])]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = _client().get("/stats/range_dist")
    assert resp.status_code == 200
    assert "구간" in resp.text


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/range_dist 는 데이터가 없어도 200(빈 상태)을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/range_dist")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 실데이터 스모크
# --------------------------------------------------------------------------- #


def test_real_data_smoke() -> None:
    """AC-068-020: 실제 데이터가 있으면 total_draws>0, '10-19' avg_per_draw>0.5."""
    draws = wd.get_draws()
    if not draws:
        return  # 데이터 미수집 환경에서는 스킵
    result = wd.get_range_dist_stats(draws)
    assert result["total_draws"] > 0
    assert result["range_stats"]["10-19"]["avg_per_draw"] > 0.5


def test_real_data_wide_ranges_dominate() -> None:
    """AC-068-021: 10폭 구간('10-19'+'20-29') total_count > 9폭 구간('1-9')."""
    draws = wd.get_draws()
    if not draws:
        return
    result = wd.get_range_dist_stats(draws)
    rs = result["range_stats"]
    assert (
        rs["10-19"]["total_count"] + rs["20-29"]["total_count"]
        > rs["1-9"]["total_count"]
    )
