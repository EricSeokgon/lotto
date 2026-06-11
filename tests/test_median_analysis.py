"""SPEC-LOTTO-071: 번호 중앙값(median) 분포 분석 테스트.

데이터 계층(get_median_stats), 헬퍼(_compute_median·_median_bucket),
캐시(_median_cache), 페이지/API 라우트를 RED-GREEN-REFACTOR로 검증한다.

중앙값(median):
- 한 회차 본번호 6개(보너스 제외)를 오름차순 정렬한 [a,b,c,d,e,f]의 (c+d)/2.0.
- 분포 키는 "1-5".."41-45" 9개 고정 버킷.
- 경계값은 상위 버킷에 귀속(예: 5.5 → "6-10").
- avg_median / most_common_range / low_median_pct(< 23.0 strict)를 제공한다.
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


_MEDIAN_KEYS = [
    "1-5", "6-10", "11-15", "16-20", "21-25",
    "26-30", "31-35", "36-40", "41-45",
]


def _mk(no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    bonus 기본값 7은 본번호와 인접해도 중앙값 집계에서 제외됨을 검증하기 위함이다.
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# --------------------------------------------------------------------------- #
# _compute_median 헬퍼
# --------------------------------------------------------------------------- #


def test_compute_median_basic() -> None:
    """[1,2,3,10,11,12] → (3+10)/2 = 6.5."""
    assert wd._compute_median([1, 2, 3, 10, 11, 12]) == 6.5


def test_compute_median_minimum() -> None:
    """[1,2,3,4,5,6] → (3+4)/2 = 3.5 (최소 구성)."""
    assert wd._compute_median([1, 2, 3, 4, 5, 6]) == 3.5


def test_compute_median_maximum() -> None:
    """[40,41,42,43,44,45] → (42+43)/2 = 42.5 (최대 구성)."""
    assert wd._compute_median([40, 41, 42, 43, 44, 45]) == 42.5


def test_compute_median_order_independent() -> None:
    """입력 순서가 달라도 중앙값은 동일하다(내부 정렬)."""
    assert wd._compute_median([12, 1, 11, 3, 2, 10]) == 6.5


def test_compute_median_even_pair() -> None:
    """[4,8,12,16,20,24] → (12+16)/2 = 14.0."""
    assert wd._compute_median([4, 8, 12, 16, 20, 24]) == 14.0


# --------------------------------------------------------------------------- #
# _median_bucket 경계
# --------------------------------------------------------------------------- #


def test_bucket_low_edge() -> None:
    """중앙값 3.5 → "1-5" (< 5.5)."""
    assert wd._median_bucket(3.5) == "1-5"


def test_bucket_boundary_5_5_goes_upper() -> None:
    """경계값 5.5 → "6-10" (상위 버킷에 귀속)."""
    assert wd._median_bucket(5.5) == "6-10"


def test_bucket_boundary_10_5_goes_upper() -> None:
    """경계값 10.5 → "11-15" (상위 버킷)."""
    assert wd._median_bucket(10.5) == "11-15"


def test_bucket_boundary_20_5_goes_upper() -> None:
    """경계값 20.5 → "21-25" (상위 버킷)."""
    assert wd._median_bucket(20.5) == "21-25"


def test_bucket_boundary_25_5_goes_upper() -> None:
    """경계값 25.5 → "26-30" (상위 버킷)."""
    assert wd._median_bucket(25.5) == "26-30"


def test_bucket_boundary_40_5_goes_top() -> None:
    """경계값 40.5 → "41-45" (>= 40.5)."""
    assert wd._median_bucket(40.5) == "41-45"


def test_bucket_top_max() -> None:
    """중앙값 42.5 → "41-45"."""
    assert wd._median_bucket(42.5) == "41-45"


def test_bucket_mid_23() -> None:
    """중앙값 23.0 → "21-25" (20.5 <= 23.0 < 25.5)."""
    assert wd._median_bucket(23.0) == "21-25"


# --------------------------------------------------------------------------- #
# get_median_stats: 빈 데이터 / 기본 분포
# --------------------------------------------------------------------------- #


def test_empty_draws() -> None:
    """MED-071-001: 빈 draws → 0-값, 9 키 존재, most_common_range="1-5"."""
    result = wd.get_median_stats([])
    assert result["total_draws"] == 0
    assert result["avg_median"] == 0.0
    assert result["most_common_range"] == "1-5"
    assert result["low_median_pct"] == 0.0
    assert set(result["median_distribution"].keys()) == set(_MEDIAN_KEYS)
    for cell in result["median_distribution"].values():
        assert cell["count"] == 0
        assert cell["pct"] == 0.0


def test_single_draw_distribution() -> None:
    """MED-071-002: [1,2,3,10,11,12] → median 6.5 → "6-10" count=1, 나머지 0."""
    result = wd.get_median_stats([_mk(1, [1, 2, 3, 10, 11, 12])])
    assert result["median_distribution"]["6-10"]["count"] == 1
    for key in _MEDIAN_KEYS:
        if key != "6-10":
            assert result["median_distribution"][key]["count"] == 0


def test_single_draw_min_bucket() -> None:
    """MED-071-003: [1,2,3,4,5,6] → median 3.5 → "1-5"."""
    result = wd.get_median_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert result["median_distribution"]["1-5"]["count"] == 1


def test_single_draw_max_bucket() -> None:
    """MED-071-004: [40,41,42,43,44,45] → median 42.5 → "41-45"."""
    result = wd.get_median_stats([_mk(1, [40, 41, 42, 43, 44, 45])])
    assert result["median_distribution"]["41-45"]["count"] == 1


def test_bonus_excluded() -> None:
    """MED-071-005: 본번호 [1,2,3,4,5,6] + bonus=45 → median 3.5 (보너스 제외)."""
    result = wd.get_median_stats([_mk(1, [1, 2, 3, 4, 5, 6], bonus=45)])
    assert result["median_distribution"]["1-5"]["count"] == 1


# --------------------------------------------------------------------------- #
# 분포 정확도 (count + pct)
# --------------------------------------------------------------------------- #


def test_multiple_draws_counts() -> None:
    """MED-071-006: 서로 다른 버킷 3회차의 count 분포."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),       # 3.5 → "1-5"
        _mk(2, [1, 2, 3, 10, 11, 12]),    # 6.5 → "6-10"
        _mk(3, [40, 41, 42, 43, 44, 45]),  # 42.5 → "41-45"
    ]
    result = wd.get_median_stats(draws)
    assert result["median_distribution"]["1-5"]["count"] == 1
    assert result["median_distribution"]["6-10"]["count"] == 1
    assert result["median_distribution"]["41-45"]["count"] == 1


def test_pct_accuracy() -> None:
    """MED-071-007: 동일 버킷 2회차 → 해당 버킷 pct=100.0."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),  # 3.5 → "1-5"
        _mk(2, [1, 2, 4, 4, 5, 6]),  # (4+4)/2=4.0 → "1-5"
    ]
    result = wd.get_median_stats(draws)
    assert result["median_distribution"]["1-5"]["count"] == 2
    assert result["median_distribution"]["1-5"]["pct"] == 100.0


def test_pct_sums_to_100() -> None:
    """MED-071-008: 9개 키 pct 합 ≈ 100.0."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [1, 2, 3, 10, 11, 12]),
        _mk(3, [40, 41, 42, 43, 44, 45]),
    ]
    result = wd.get_median_stats(draws)
    total_pct = sum(cell["pct"] for cell in result["median_distribution"].values())
    assert abs(total_pct - 100.0) < 0.1


def test_count_sum_equals_total() -> None:
    """MED-071-009: 9개 키 count 합 = total_draws."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [1, 2, 3, 10, 11, 12]),
        _mk(3, [40, 41, 42, 43, 44, 45]),
    ]
    result = wd.get_median_stats(draws)
    total_count = sum(
        cell["count"] for cell in result["median_distribution"].values()
    )
    assert total_count == result["total_draws"] == 3


# --------------------------------------------------------------------------- #
# avg_median
# --------------------------------------------------------------------------- #


def test_avg_median() -> None:
    """MED-071-010: median 3.5, 6.5 → avg=5.0."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),     # 3.5
        _mk(2, [1, 2, 3, 10, 11, 12]),  # 6.5
    ]
    result = wd.get_median_stats(draws)
    assert result["avg_median"] == 5.0


def test_avg_median_rounding() -> None:
    """MED-071-011: median 3.5, 3.5, 4.0 → avg=3.67 (소수 2자리 반올림)."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),  # 3.5
        _mk(2, [1, 2, 3, 4, 6, 7]),  # 3.5
        _mk(3, [1, 2, 4, 4, 5, 6]),  # 4.0
    ]
    result = wd.get_median_stats(draws)
    assert result["avg_median"] == 3.67


# --------------------------------------------------------------------------- #
# low_median_pct (strict < 23.0)
# --------------------------------------------------------------------------- #


def test_low_median_pct() -> None:
    """MED-071-012: median 3.5(low), 42.5(high) → low_median_pct=50.0."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),       # 3.5 < 23.0
        _mk(2, [40, 41, 42, 43, 44, 45]),  # 42.5 >= 23.0
    ]
    result = wd.get_median_stats(draws)
    assert result["low_median_pct"] == 50.0


def test_low_median_pct_boundary_23_not_counted() -> None:
    """MED-071-013: median 23.0 은 low 아님 (strict < 23.0)."""
    draws = [
        _mk(1, [10, 20, 22, 24, 30, 40]),  # (22+24)/2 = 23.0 → not low
    ]
    result = wd.get_median_stats(draws)
    assert result["low_median_pct"] == 0.0


def test_low_median_pct_just_below_23() -> None:
    """MED-071-014: median 22.5 < 23.0 → low 포함."""
    draws = [
        _mk(1, [10, 20, 22, 23, 30, 40]),  # (22+23)/2 = 22.5 → low
    ]
    result = wd.get_median_stats(draws)
    assert result["low_median_pct"] == 100.0


# --------------------------------------------------------------------------- #
# most_common_range
# --------------------------------------------------------------------------- #


def test_most_common_range() -> None:
    """MED-071-015: "1-5" 2개, "6-10" 1개 → most_common_range="1-5"."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),     # 3.5 → "1-5"
        _mk(2, [1, 2, 4, 4, 5, 6]),     # 4.0 → "1-5"
        _mk(3, [1, 2, 3, 10, 11, 12]),  # 6.5 → "6-10"
    ]
    result = wd.get_median_stats(draws)
    assert result["most_common_range"] == "1-5"


def test_most_common_range_tie_smaller_lower_bound_wins() -> None:
    """MED-071-016: "1-5" 1개, "6-10" 1개 (동점) → 더 작은 하한 "1-5"."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),     # 3.5 → "1-5"
        _mk(2, [1, 2, 3, 10, 11, 12]),  # 6.5 → "6-10"
    ]
    result = wd.get_median_stats(draws)
    assert result["most_common_range"] == "1-5"


# --------------------------------------------------------------------------- #
# 키 존재 보장
# --------------------------------------------------------------------------- #


def test_9_keys_always_present() -> None:
    """MED-071-017: 비어 있지 않은 draws → 9 키 항상 존재."""
    result = wd.get_median_stats([_mk(1, [1, 2, 3, 10, 11, 12])])
    assert set(result["median_distribution"].keys()) == set(_MEDIAN_KEYS)


# --------------------------------------------------------------------------- #
# 캐시
# --------------------------------------------------------------------------- #


def test_cache_hit_same_object() -> None:
    """MED-071-018: 동일 len(draws) 두 번째 호출 → 동일 객체(id)."""
    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    first = wd.get_median_stats(draws)
    second = wd.get_median_stats(draws)
    assert first is second


def test_cache_miss_different_length() -> None:
    """MED-071-019: 다른 len(draws) → 새로 계산한 결과."""
    draws1 = [_mk(1, [1, 2, 3, 4, 5, 6])]
    draws2 = [_mk(1, [1, 2, 3, 4, 5, 6]), _mk(2, [1, 2, 3, 10, 11, 12])]
    first = wd.get_median_stats(draws1)
    second = wd.get_median_stats(draws2)
    assert first is not second
    assert second["total_draws"] == 2


def test_invalidate_cache_clears() -> None:
    """MED-071-020: invalidate_cache() → _median_cache 비워짐."""
    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    wd.get_median_stats(draws)
    assert wd._median_cache  # 채워진 상태
    wd.invalidate_cache()
    assert wd._median_cache == {}


# --------------------------------------------------------------------------- #
# 라우트: API / 페이지
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """MED-071-021: GET /api/stats/median 은 200 + 키 구조(9 분포 키)를 반환한다."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [1, 2, 3, 10, 11, 12]),
        _mk(3, [40, 41, 42, 43, 44, 45]),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = _client().get("/api/stats/median")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 3
    for key in (
        "total_draws",
        "avg_median",
        "most_common_range",
        "low_median_pct",
        "median_distribution",
    ):
        assert key in body
    assert set(body["median_distribution"].keys()) == set(_MEDIAN_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/median 은 데이터가 없어도 200 을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/median")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """MED-071-022: GET /stats/median 은 200(HTML, "중앙값" 텍스트 포함)을 반환한다."""
    draws = [_mk(1, [1, 2, 3, 10, 11, 12])]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = _client().get("/stats/median")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "중앙값" in resp.text


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/median 은 데이터가 없어도 200(빈 상태)을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/median")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 실데이터 스모크
# --------------------------------------------------------------------------- #


def test_real_data_smoke() -> None:
    """MED-071-023(smoke): 실제 데이터가 있으면 total_draws>0, avg_median>0."""
    draws = wd.get_draws()
    if not draws:
        return  # 데이터 미수집 환경에서는 스킵
    result = wd.get_median_stats(draws)
    assert result["total_draws"] > 0
    assert result["avg_median"] > 0
