"""SPEC-LOTTO-067: 번호 총합 분포 분석 테스트.

데이터 계층(get_total_sum_stats), 캐시, 페이지/API 라우트를
RED-GREEN-REFACTOR로 검증한다.

분석(회차별 본번호 6개, 보너스 제외):
- total_sum = sum(draw.numbers())
  이론적 범위: 21 ([1,2,3,4,5,6]) ~ 255 ([40,41,42,43,44,45])
  평균 ≈ 138, 표준편차 ≈ 30
- 3단계 분류: low(total_sum < 110), mid(110 <= total_sum <= 170), high(total_sum > 170)
- total_sum_distribution: 6개 고정 bucket 키를 항상 포함(미관측 구간 0 유지)
    "21-80"(<=80), "81-110"(<=110), "111-130"(<=130),
    "131-150"(<=150), "151-170"(<=170), "171-255"(>=171)
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


_BUCKET_KEYS = ["21-80", "81-110", "111-130", "131-150", "151-170", "171-255"]


def _mk(no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    bonus는 본번호 외 값을 사용해 총합 집계에 영향을 주지 않음을 검증할 수 있게 한다.
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
    """빈 리스트는 total_draws=0 과 모든 수치 0을 반환한다."""
    result = wd.get_total_sum_stats([])
    assert result["total_draws"] == 0
    assert result["avg_total_sum"] == 0.0
    assert result["min_total_sum"] == 0
    assert result["max_total_sum"] == 0
    assert result["low_count"] == 0
    assert result["mid_count"] == 0
    assert result["high_count"] == 0
    assert result["low_pct"] == 0.0
    assert result["mid_pct"] == 0.0
    assert result["high_pct"] == 0.0
    assert result["most_common_bucket"] == ""


def test_empty_has_all_six_buckets() -> None:
    """빈 데이터에서도 6개 bucket 키가 모두 0으로 존재한다."""
    result = wd.get_total_sum_stats([])
    assert list(result["total_sum_distribution"].keys()) == _BUCKET_KEYS
    assert all(v == 0 for v in result["total_sum_distribution"].values())


def test_none_returns_zero_stats() -> None:
    """None 입력도 빈 데이터와 동일한 구조를 반환한다."""
    result = wd.get_total_sum_stats(None)
    assert result["total_draws"] == 0
    assert list(result["total_sum_distribution"].keys()) == _BUCKET_KEYS


# --------------------------------------------------------------------------- #
# 회차별 총합 산출
# --------------------------------------------------------------------------- #


def test_minimum_total_sum() -> None:
    """이론적 최솟값 21 ([1,2,3,4,5,6])은 '21-80' bucket, low tier이다."""
    result = wd.get_total_sum_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert result["total_draws"] == 1
    assert result["avg_total_sum"] == 21.0
    assert result["min_total_sum"] == 21
    assert result["max_total_sum"] == 21
    assert result["total_sum_distribution"]["21-80"] == 1
    assert result["low_count"] == 1


def test_maximum_total_sum() -> None:
    """이론적 최댓값 255 ([40,41,42,43,44,45])는 '171-255' bucket, high tier이다."""
    result = wd.get_total_sum_stats([_mk(1, [40, 41, 42, 43, 44, 45])])
    assert result["max_total_sum"] == 255
    assert result["total_sum_distribution"]["171-255"] == 1
    assert result["high_count"] == 1


def test_bonus_excluded_from_total_sum() -> None:
    """보너스 번호는 총합 산출에서 제외된다 (본번호 6개만)."""
    # bonus 를 큰 값 45 로 줘도 총합은 본번호 [1,2,3,4,5,6] 기준 21 이어야 한다.
    result = wd.get_total_sum_stats([_mk(1, [1, 2, 3, 4, 5, 6], bonus=45)])
    assert result["avg_total_sum"] == 21.0
    assert result["max_total_sum"] == 21


# --------------------------------------------------------------------------- #
# 다회차 집계: avg/min/max
# --------------------------------------------------------------------------- #


def test_avg_min_max_accuracy() -> None:
    """3회차: 총합 100, 138, 175 → avg=137.67, min=100, max=175."""
    draws = [
        _mk(1, [10, 15, 18, 19, 18, 20]),   # sum=100
        _mk(2, [20, 23, 24, 23, 24, 24]),   # sum=138
        _mk(3, [28, 29, 30, 29, 29, 30]),   # sum=175
    ]
    result = wd.get_total_sum_stats(draws)
    assert result["total_draws"] == 3
    assert result["avg_total_sum"] == 137.67
    assert result["min_total_sum"] == 100
    assert result["max_total_sum"] == 175


# --------------------------------------------------------------------------- #
# 분포 키 불변성
# --------------------------------------------------------------------------- #


def test_all_six_buckets_always_present() -> None:
    """단일 회차에서도 미관측 bucket 까지 6개 키가 모두 존재한다."""
    result = wd.get_total_sum_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert list(result["total_sum_distribution"].keys()) == _BUCKET_KEYS
    assert result["total_sum_distribution"]["21-80"] == 1
    assert result["total_sum_distribution"]["171-255"] == 0


# --------------------------------------------------------------------------- #
# bucket 경계 (모든 6개 bucket 경계값)
# --------------------------------------------------------------------------- #


def _mk_sum(no: int, target: int) -> DrawResult:
    """본번호 6개의 합이 정확히 target 이 되는 회차를 생성한다.

    target(21..255)을 6개 번호에 고르게 분배하고, 1..45 범위를 넘지 않도록
    앞쪽 번호부터 잔여분을 채운다. 본 테스트는 총합만 검증하므로 번호 중복은 무방하다.
    """
    base = target // 6
    rem = target - base * 6
    nums = [base] * 6
    i = 0
    while rem > 0:
        add = min(45 - nums[i], rem)
        nums[i] += add
        rem -= add
        i += 1
    return _mk(no, nums)


def test_bucket_boundary_80_vs_81() -> None:
    """총합 80은 '21-80', 81은 '81-110' bucket에 속한다(상한 포함)."""
    result = wd.get_total_sum_stats([_mk_sum(1, 80), _mk_sum(2, 81)])
    assert result["total_sum_distribution"]["21-80"] == 1
    assert result["total_sum_distribution"]["81-110"] == 1


def test_bucket_boundary_110_vs_111() -> None:
    """총합 110은 '81-110', 111은 '111-130' bucket에 속한다(상한 포함)."""
    result = wd.get_total_sum_stats([_mk_sum(1, 110), _mk_sum(2, 111)])
    assert result["total_sum_distribution"]["81-110"] == 1
    assert result["total_sum_distribution"]["111-130"] == 1


def test_bucket_boundary_130_vs_131() -> None:
    """총합 130은 '111-130', 131은 '131-150' bucket에 속한다(상한 포함)."""
    result = wd.get_total_sum_stats([_mk_sum(1, 130), _mk_sum(2, 131)])
    assert result["total_sum_distribution"]["111-130"] == 1
    assert result["total_sum_distribution"]["131-150"] == 1


def test_bucket_boundary_150_vs_151() -> None:
    """총합 150은 '131-150', 151은 '151-170' bucket에 속한다(상한 포함)."""
    result = wd.get_total_sum_stats([_mk_sum(1, 150), _mk_sum(2, 151)])
    assert result["total_sum_distribution"]["131-150"] == 1
    assert result["total_sum_distribution"]["151-170"] == 1


def test_bucket_boundary_170_vs_171() -> None:
    """총합 170은 '151-170', 171은 '171-255' bucket에 속한다(상한 포함)."""
    result = wd.get_total_sum_stats([_mk_sum(1, 170), _mk_sum(2, 171)])
    assert result["total_sum_distribution"]["151-170"] == 1
    assert result["total_sum_distribution"]["171-255"] == 1


# --------------------------------------------------------------------------- #
# tier 경계
# --------------------------------------------------------------------------- #


def test_tier_low_boundary() -> None:
    """총합 109는 low, 110은 mid tier이다 (low: <110, mid: [110,170])."""
    result = wd.get_total_sum_stats([_mk_sum(1, 109), _mk_sum(2, 110)])
    assert result["low_count"] == 1
    assert result["mid_count"] == 1
    assert result["high_count"] == 0


def test_tier_high_boundary() -> None:
    """총합 170은 mid, 171은 high tier이다 (mid: [110,170], high: >170)."""
    result = wd.get_total_sum_stats([_mk_sum(1, 170), _mk_sum(2, 171)])
    assert result["mid_count"] == 1
    assert result["high_count"] == 1
    assert result["low_count"] == 0


def test_tier_partition_sums_to_total() -> None:
    """세 tier 합은 total_draws 와 같다(분할)."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),         # sum=21 low
        _mk(2, [20, 23, 24, 23, 24, 24]),   # sum=138 mid
        _mk(3, [40, 41, 42, 43, 44, 45]),   # sum=255 high
    ]
    result = wd.get_total_sum_stats(draws)
    total = result["low_count"] + result["mid_count"] + result["high_count"]
    assert total == result["total_draws"] == 3


def test_pct_sums_to_100() -> None:
    """tier 비율의 합은 100.0% 이다(4회차)."""
    draws = [
        _mk_sum(1, 109),   # low
        _mk_sum(2, 110),   # mid
        _mk_sum(3, 170),   # mid
        _mk_sum(4, 171),   # high
    ]
    result = wd.get_total_sum_stats(draws)
    assert result["low_pct"] == 25.0
    assert result["mid_pct"] == 50.0
    assert result["high_pct"] == 25.0
    assert round(
        result["low_pct"] + result["mid_pct"] + result["high_pct"], 2
    ) == 100.0


# --------------------------------------------------------------------------- #
# most_common_bucket
# --------------------------------------------------------------------------- #


def test_most_common_bucket_correct() -> None:
    """최다 출현 bucket 이 most_common_bucket 으로 선택된다.

    '131-150' 2회 + '21-80' 1회 → '131-150' 이 최빈.
    """
    draws = [
        _mk_sum(1, 138),   # "131-150"
        _mk_sum(2, 140),   # "131-150"
        _mk(3, [1, 2, 3, 4, 5, 6]),  # sum=21 → "21-80"
    ]
    result = wd.get_total_sum_stats(draws)
    assert result["most_common_bucket"] == "131-150"


def test_most_common_bucket_tiebreak() -> None:
    """동률 시 정의 순서상 앞선 bucket 이 선택된다.

    '21-80'(sum=21) 1회 + '131-150'(sum=138) 1회 → 둘 다 1회 동률 →
    정의 순서상 '21-80' 이 '131-150' 보다 앞서므로 '21-80' 선택.
    """
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),   # sum=21 → "21-80"
        _mk_sum(2, 138),              # "131-150"
    ]
    result = wd.get_total_sum_stats(draws)
    assert result["total_sum_distribution"]["21-80"] == 1
    assert result["total_sum_distribution"]["131-150"] == 1
    assert result["most_common_bucket"] == "21-80"


# --------------------------------------------------------------------------- #
# 입력 불변성
# --------------------------------------------------------------------------- #


def test_does_not_mutate_input() -> None:
    """입력 draws 리스트를 변경하지 않는다."""
    draws = [_mk(1, [1, 2, 3, 4, 5, 6]), _mk(2, [40, 41, 42, 43, 44, 45])]
    snapshot = list(draws)
    wd.get_total_sum_stats(draws)
    assert draws == snapshot
    assert len(draws) == 2


# --------------------------------------------------------------------------- #
# 캐시
# --------------------------------------------------------------------------- #


def test_cache_hit_same_length() -> None:
    """동일 길이 입력의 재호출은 캐시된 동일 객체를 반환한다."""
    wd._total_sum_cache.clear()
    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    first = wd.get_total_sum_stats(draws)
    second = wd.get_total_sum_stats(draws)
    assert first is second
    assert "1" in wd._total_sum_cache


def test_cache_miss_different_length() -> None:
    """길이가 다른 입력은 캐시 미스로 새로 계산된다."""
    wd._total_sum_cache.clear()
    one = wd.get_total_sum_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    two = wd.get_total_sum_stats(
        [_mk(1, [1, 2, 3, 4, 5, 6]), _mk(2, [40, 41, 42, 43, 44, 45])]
    )
    assert one is not two
    assert "1" in wd._total_sum_cache
    assert "2" in wd._total_sum_cache


def test_invalidate_cache() -> None:
    """invalidate_cache() 호출 시 총합 캐시가 비워진다."""
    wd.get_total_sum_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert wd._total_sum_cache
    wd.invalidate_cache()
    assert not wd._total_sum_cache


# --------------------------------------------------------------------------- #
# 라우트: API / 페이지
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/total_sum 는 총합 분석 JSON 을 200 으로 반환한다."""
    draws = [
        _mk(1, [10, 15, 18, 19, 18, 20]),   # sum=100
        _mk(2, [20, 23, 24, 23, 24, 24]),   # sum=138
        _mk(3, [28, 29, 30, 29, 29, 30]),   # sum=175
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = _client().get("/api/stats/total_sum")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 3
    assert body["avg_total_sum"] == 137.67
    assert body["min_total_sum"] == 100
    assert body["max_total_sum"] == 175
    assert set(body["total_sum_distribution"].keys()) == set(_BUCKET_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/total_sum 는 데이터가 없어도 200 을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/total_sum")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/total_sum 는 데이터가 있을 때 200(총합 안내 포함)을 반환한다."""
    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = _client().get("/stats/total_sum")
    assert resp.status_code == 200
    assert "총합" in resp.text


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/total_sum 는 데이터가 없어도 200(빈 상태)을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/total_sum")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 실데이터 스모크
# --------------------------------------------------------------------------- #


def test_real_data_smoke() -> None:
    """실제 수집 데이터가 있으면 total_draws>0, avg_total_sum>100.0 이다."""
    draws = wd.get_draws()
    if not draws:
        return  # 데이터 미수집 환경에서는 스킵 (빈 결과 일관성은 별도 테스트가 보장)
    result = wd.get_total_sum_stats(draws)
    assert result["total_draws"] > 0
    assert result["avg_total_sum"] > 100.0
    assert 21 <= result["min_total_sum"] <= result["max_total_sum"] <= 255
