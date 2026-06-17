"""SPEC-LOTTO-066: 소수합 분포 분석 테스트.

데이터 계층(get_prime_sum_stats), 캐시, 페이지/API 라우트를
RED-GREEN-REFACTOR로 검증한다.

분석(회차별 본번호 6개, 보너스 제외):
- prime_sum = sum(n for n in nums if n in _PRIMES_1_45)
  소수: {2,3,5,7,11,13,17,19,23,29,31,37,41,43}
  이론적 범위: 0 (소수 없음) ~ 204 (43+41+37+31+29+23)
- 3단계 분류: low(prime_sum < 40), mid(40 <= prime_sum <= 80), high(prime_sum > 80)
- prime_sum_distribution: 6개 고정 bucket 키를 항상 포함(미관측 구간 0 유지)
    "0-30"[0,30), "30-60"[30,60), "60-90"[60,90),
    "90-120"[90,120), "120-150"[120,150), "150+"[150,∞)
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


_BUCKET_KEYS = ["0-30", "30-60", "60-90", "90-120", "120-150", "150+"]


def _mk(no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    bonus는 본번호 외 값을 사용해 소수합 집계에 영향을 주지 않음을 검증할 수 있게 한다.
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# --------------------------------------------------------------------------- #
# 빈 데이터 / 일관된 빈 구조 (REQ-066-NF-001)
# --------------------------------------------------------------------------- #


def test_empty_returns_zero_stats() -> None:
    """빈 리스트는 total_draws=0 과 모든 수치 0을 반환한다."""
    result = wd.get_prime_sum_stats([])
    assert result["total_draws"] == 0
    assert result["avg_prime_sum"] == 0.0
    assert result["min_prime_sum"] == 0
    assert result["max_prime_sum"] == 0
    assert result["low_count"] == 0
    assert result["mid_count"] == 0
    assert result["high_count"] == 0
    assert result["low_pct"] == 0.0
    assert result["mid_pct"] == 0.0
    assert result["high_pct"] == 0.0


def test_empty_has_all_six_buckets() -> None:
    """빈 데이터에서도 6개 bucket 키가 모두 0으로 존재한다."""
    result = wd.get_prime_sum_stats([])
    assert list(result["prime_sum_distribution"].keys()) == _BUCKET_KEYS
    assert all(v == 0 for v in result["prime_sum_distribution"].values())


def test_none_returns_zero_stats() -> None:
    """None 입력도 빈 데이터와 동일한 구조를 반환한다."""
    result = wd.get_prime_sum_stats(None)
    assert result["total_draws"] == 0
    assert list(result["prime_sum_distribution"].keys()) == _BUCKET_KEYS


# --------------------------------------------------------------------------- #
# 회차별 소수합 산출 (REQ-066-F-001)
# --------------------------------------------------------------------------- #


def test_no_primes_in_draw() -> None:
    """소수가 하나도 없는 회차의 소수합은 0이다."""
    result = wd.get_prime_sum_stats([_mk(1, [1, 4, 6, 8, 9, 10])])
    assert result["total_draws"] == 1
    assert result["avg_prime_sum"] == 0.0
    assert result["min_prime_sum"] == 0
    assert result["max_prime_sum"] == 0


def test_single_prime_in_draw() -> None:
    """소수 1개([2])만 있는 회차의 소수합은 그 소수값이다."""
    result = wd.get_prime_sum_stats([_mk(1, [2, 4, 6, 8, 9, 10])])
    assert result["avg_prime_sum"] == 2.0
    assert result["min_prime_sum"] == 2
    assert result["max_prime_sum"] == 2


def test_all_primes_in_draw() -> None:
    """본번호 6개가 모두 소수면 소수합은 그 6개의 합이다 (2+3+5+7+11+13=41)."""
    result = wd.get_prime_sum_stats([_mk(1, [2, 3, 5, 7, 11, 13])])
    assert result["avg_prime_sum"] == 41.0
    assert result["max_prime_sum"] == 41
    assert result["prime_sum_distribution"]["30-60"] == 1


def test_max_prime_sum() -> None:
    """이론적 최댓값 204 ([43,41,37,31,29,23])는 '150+' bucket, high tier이다."""
    result = wd.get_prime_sum_stats([_mk(1, [43, 41, 37, 31, 29, 23])])
    assert result["max_prime_sum"] == 204
    assert result["prime_sum_distribution"]["150+"] == 1
    assert result["high_count"] == 1


def test_bonus_excluded_from_prime_sum() -> None:
    """보너스 번호는 소수합 산출에서 제외된다 (본번호 6개만)."""
    # bonus 를 소수 43 으로 줘도 소수합은 본번호 [1,2,3,4,5,6] 기준 (2+3+5)=10 이어야 한다.
    result = wd.get_prime_sum_stats([_mk(1, [1, 2, 3, 4, 5, 6], bonus=43)])
    assert result["avg_prime_sum"] == 10.0
    assert result["max_prime_sum"] == 10


# --------------------------------------------------------------------------- #
# 다회차 집계: avg/min/max (REQ-066-F-002)
# --------------------------------------------------------------------------- #


def test_avg_min_max_accuracy() -> None:
    """3회차: 소수합 0, 10, 41 → avg=17.0, min=0, max=41."""
    draws = [
        _mk(1, [1, 4, 6, 8, 9, 10]),    # ps=0
        _mk(2, [1, 2, 3, 4, 5, 6]),     # ps=2+3+5=10
        _mk(3, [2, 3, 5, 7, 11, 13]),   # ps=41
    ]
    result = wd.get_prime_sum_stats(draws)
    assert result["total_draws"] == 3
    assert result["avg_prime_sum"] == 17.0
    assert result["min_prime_sum"] == 0
    assert result["max_prime_sum"] == 41


# --------------------------------------------------------------------------- #
# 분포 키 불변성 (REQ-066-F-004)
# --------------------------------------------------------------------------- #


def test_all_six_buckets_always_present() -> None:
    """단일 회차에서도 미관측 bucket 까지 6개 키가 모두 존재한다."""
    result = wd.get_prime_sum_stats([_mk(1, [2, 3, 5, 7, 11, 13])])
    assert list(result["prime_sum_distribution"].keys()) == _BUCKET_KEYS
    assert result["prime_sum_distribution"]["30-60"] == 1
    assert result["prime_sum_distribution"]["150+"] == 0


# --------------------------------------------------------------------------- #
# bucket 경계 (REQ-066-F-004)
# --------------------------------------------------------------------------- #


def test_bucket_boundary_0_30_vs_30_60() -> None:
    """소수합 29는 '0-30', 30은 '30-60' bucket에 속한다(상한 배타).

    29 = 2+3+5+19 / 30 = 7+23.
    """
    draws = [
        _mk(1, [2, 3, 5, 19, 4, 6]),   # ps=29 → "0-30"
        _mk(2, [7, 23, 4, 6, 8, 9]),   # ps=30 → "30-60"
    ]
    result = wd.get_prime_sum_stats(draws)
    assert result["prime_sum_distribution"]["0-30"] == 1
    assert result["prime_sum_distribution"]["30-60"] == 1


def test_bucket_boundary_150_plus() -> None:
    """소수합 149는 '120-150', 150은 '150+' bucket에 속한다(상한 배타).

    149 = 43+41+37+19+9? -> use prime combos; 150 = 43+41+37+29.
    """
    # 149 = 43+41+37+23+5 = 149 ; 150 = 43+41+37+29 = 150
    draws = [
        _mk(1, [43, 41, 37, 23, 5, 1]),   # ps=149 → "120-150"
        _mk(2, [43, 41, 37, 29, 1, 4]),   # ps=150 → "150+"
    ]
    result = wd.get_prime_sum_stats(draws)
    assert result["prime_sum_distribution"]["120-150"] == 1
    assert result["prime_sum_distribution"]["150+"] == 1


# --------------------------------------------------------------------------- #
# tier 경계 (REQ-066-F-005)
# --------------------------------------------------------------------------- #


def test_tier_low_boundary() -> None:
    """소수합 39는 low, 40은 mid tier이다 (low: <40, mid: [40,80]).

    39 = 2+37 / 40 = 3+37.
    """
    draws = [
        _mk(1, [2, 37, 4, 6, 8, 9]),   # ps=39 → low
        _mk(2, [3, 37, 4, 6, 8, 9]),   # ps=40 → mid
    ]
    result = wd.get_prime_sum_stats(draws)
    assert result["low_count"] == 1
    assert result["mid_count"] == 1
    assert result["high_count"] == 0


def test_tier_high_boundary() -> None:
    """소수합 80은 mid, 81은 high tier이다 (mid: [40,80], high: >80).

    80 = 37+43 / 81 = 7+31+43.
    """
    draws = [
        _mk(1, [37, 43, 4, 6, 8, 9]),   # ps=80 → mid
        _mk(2, [7, 31, 43, 4, 6, 8]),   # ps=81 → high
    ]
    result = wd.get_prime_sum_stats(draws)
    assert result["mid_count"] == 1
    assert result["high_count"] == 1
    assert result["low_count"] == 0


def test_tier_partition_sums_to_total() -> None:
    """세 tier 합은 total_draws 와 같다(분할)."""
    draws = [
        _mk(1, [1, 4, 6, 8, 9, 10]),    # ps=0 low
        _mk(2, [37, 43, 4, 6, 8, 9]),   # ps=80 mid
        _mk(3, [43, 41, 37, 31, 29, 23]),  # ps=204 high
    ]
    result = wd.get_prime_sum_stats(draws)
    total = result["low_count"] + result["mid_count"] + result["high_count"]
    assert total == result["total_draws"] == 3


def test_pct_sums_to_100() -> None:
    """tier 비율의 합은 100.0% 이다(동일 분포 4회차)."""
    draws = [
        _mk(1, [2, 37, 4, 6, 8, 9]),    # ps=39 low
        _mk(2, [3, 37, 4, 6, 8, 9]),    # ps=40 mid
        _mk(3, [37, 43, 4, 6, 8, 9]),   # ps=80 mid
        _mk(4, [7, 31, 43, 4, 6, 8]),   # ps=81 high
    ]
    result = wd.get_prime_sum_stats(draws)
    assert result["low_pct"] == 25.0
    assert result["mid_pct"] == 50.0
    assert result["high_pct"] == 25.0
    assert round(result["low_pct"] + result["mid_pct"] + result["high_pct"], 2) == 100.0


# --------------------------------------------------------------------------- #
# most_common_bucket (REQ-066-F-002)
# --------------------------------------------------------------------------- #


def test_most_common_bucket_correct() -> None:
    """최다 출현 bucket 이 most_common_bucket 으로 선택된다.

    '30-60' 2회 + '0-30' 1회 → '30-60' 이 최빈.
    """
    draws = [
        _mk(1, [2, 3, 5, 7, 11, 13]),   # ps=41 → "30-60"
        _mk(2, [3, 37, 4, 6, 8, 9]),    # ps=40 → "30-60"
        _mk(3, [1, 2, 3, 4, 5, 6]),     # ps=10 → "0-30"
    ]
    result = wd.get_prime_sum_stats(draws)
    assert result["most_common_bucket"] == "30-60"


def test_most_common_bucket_tiebreak() -> None:
    """동률 시 정의 순서상 앞선 bucket 이 선택된다.

    '0-30'(ps=10) 1회 + '30-60'(ps=41) 1회 → 둘 다 1회 동률 →
    정의 순서상 '0-30' 이 '30-60' 보다 앞서므로 '0-30' 선택.
    """
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),     # ps=10 → "0-30"
        _mk(2, [2, 3, 5, 7, 11, 13]),   # ps=41 → "30-60"
    ]
    result = wd.get_prime_sum_stats(draws)
    assert result["prime_sum_distribution"]["0-30"] == 1
    assert result["prime_sum_distribution"]["30-60"] == 1
    assert result["most_common_bucket"] == "0-30"


# --------------------------------------------------------------------------- #
# 입력 불변성
# --------------------------------------------------------------------------- #


def test_does_not_mutate_input() -> None:
    """입력 draws 리스트를 변경하지 않는다."""
    draws = [_mk(1, [2, 3, 5, 7, 11, 13]), _mk(2, [1, 2, 3, 4, 5, 6])]
    snapshot = list(draws)
    wd.get_prime_sum_stats(draws)
    assert draws == snapshot
    assert len(draws) == 2


# --------------------------------------------------------------------------- #
# 캐시 (REQ-066-F-006)
# --------------------------------------------------------------------------- #


def test_cache_hit_same_length() -> None:
    """동일 길이 입력의 재호출은 캐시된 동일 객체를 반환한다."""
    wd._prime_sum_cache.clear()
    draws = [_mk(1, [2, 3, 5, 7, 11, 13])]
    first = wd.get_prime_sum_stats(draws)
    second = wd.get_prime_sum_stats(draws)
    assert first is second
    assert "1" in wd._prime_sum_cache


def test_cache_miss_different_length() -> None:
    """길이가 다른 입력은 캐시 미스로 새로 계산된다."""
    wd._prime_sum_cache.clear()
    one = wd.get_prime_sum_stats([_mk(1, [2, 3, 5, 7, 11, 13])])
    two = wd.get_prime_sum_stats(
        [_mk(1, [2, 3, 5, 7, 11, 13]), _mk(2, [1, 2, 3, 4, 5, 6])]
    )
    assert one is not two
    assert "1" in wd._prime_sum_cache
    assert "2" in wd._prime_sum_cache


def test_invalidate_cache() -> None:
    """invalidate_cache() 호출 시 소수합 캐시가 비워진다."""
    wd.get_prime_sum_stats([_mk(1, [2, 3, 5, 7, 11, 13])])
    assert wd._prime_sum_cache
    wd.invalidate_cache()
    assert not wd._prime_sum_cache


# --------------------------------------------------------------------------- #
# 라우트: API / 페이지 (REQ-066-F-002, REQ-066-F-003)
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/prime_sum 는 소수합 분석 JSON 을 200 으로 반환한다."""
    draws = [
        _mk(1, [1, 4, 6, 8, 9, 10]),    # ps=0
        _mk(2, [1, 2, 3, 4, 5, 6]),     # ps=10
        _mk(3, [2, 3, 5, 7, 11, 13]),   # ps=41
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = _client().get("/api/stats/prime_sum")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 3
    assert body["avg_prime_sum"] == 17.0
    assert body["min_prime_sum"] == 0
    assert body["max_prime_sum"] == 41
    assert set(body["prime_sum_distribution"].keys()) == set(_BUCKET_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/prime_sum 는 데이터가 없어도 200 을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/prime_sum")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/prime_sum 는 데이터가 있을 때 200(소수합 안내 포함)을 반환한다."""
    draws = [_mk(1, [2, 3, 5, 7, 11, 13])]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = _client().get("/stats/prime_sum")
    assert resp.status_code == 200
    assert "소수합" in resp.text


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/prime_sum 는 데이터가 없어도 200(빈 상태)을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/prime_sum")
    assert resp.status_code == 200
