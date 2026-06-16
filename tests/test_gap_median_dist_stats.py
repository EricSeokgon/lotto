"""SPEC-LOTTO-097: 번호 간격 중앙값 구간 분포 분석 테스트.

데이터 계층(get_gap_median_dist_stats), 헬퍼(_gap_median_bucket),
캐시(_gap_median_dist_cache), 페이지/API 라우트를 RED-GREEN-REFACTOR로 검증한다.

gap_median(번호 간격 중앙값):
- 한 회차의 정렬된 본번호 6개(보너스 제외)에서 인접 차이 5개를 정렬하여 3번째(인덱스 2) 값.
- 6개 고정 구간 버킷("1-2","3-4","5-6","7-8","9-10","11+")으로 분류(zero-fill).
- avg_gap_median(회차별 gap_median 평균) / most_common_range(동률 시 앞선 구간)
  / low_median_pct(gap_median<=4인 회차 비율) / high_median_pct(gap_median>=9 비율).
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd


_GAP_MEDIAN_KEYS = ["1-2", "3-4", "5-6", "7-8", "9-10", "11+"]


def _mk(no: int, nums: list[int], bonus: int = 45) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼."""
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# --------------------------------------------------------------------------- #
# 헬퍼 함수 (_gap_median_bucket)
# --------------------------------------------------------------------------- #

def test_bucket_1() -> None:
    """gap_median == 1은 '1-2' 버킷."""
    assert wd._gap_median_bucket(1) == "1-2"


def test_bucket_2() -> None:
    """gap_median == 2는 '1-2' 버킷."""
    assert wd._gap_median_bucket(2) == "1-2"


def test_bucket_3() -> None:
    """gap_median == 3은 '3-4' 버킷."""
    assert wd._gap_median_bucket(3) == "3-4"


def test_bucket_4() -> None:
    """gap_median == 4는 '3-4' 버킷."""
    assert wd._gap_median_bucket(4) == "3-4"


def test_bucket_5() -> None:
    """gap_median == 5는 '5-6' 버킷."""
    assert wd._gap_median_bucket(5) == "5-6"


def test_bucket_6() -> None:
    """gap_median == 6은 '5-6' 버킷."""
    assert wd._gap_median_bucket(6) == "5-6"


def test_bucket_7() -> None:
    """gap_median == 7은 '7-8' 버킷."""
    assert wd._gap_median_bucket(7) == "7-8"


def test_bucket_8() -> None:
    """gap_median == 8은 '7-8' 버킷."""
    assert wd._gap_median_bucket(8) == "7-8"


def test_bucket_9() -> None:
    """gap_median == 9는 '9-10' 버킷."""
    assert wd._gap_median_bucket(9) == "9-10"


def test_bucket_10() -> None:
    """gap_median == 10은 '9-10' 버킷."""
    assert wd._gap_median_bucket(10) == "9-10"


def test_bucket_11() -> None:
    """gap_median == 11은 '11+' 버킷."""
    assert wd._gap_median_bucket(11) == "11+"


def test_bucket_20() -> None:
    """gap_median == 20은 '11+' 버킷."""
    assert wd._gap_median_bucket(20) == "11+"


# --------------------------------------------------------------------------- #
# AC-01 / AC-02: 빈 데이터 처리
# --------------------------------------------------------------------------- #

def test_none_draws_returns_empty() -> None:
    """AC-01: draws=None 입력 시 기본 구조 반환."""
    wd.invalidate_cache()
    result = wd.get_gap_median_dist_stats(None)
    assert result["total_draws"] == 0
    assert result["avg_gap_median"] == 0.0
    assert result["most_common_range"] == "1-2"
    assert result["low_median_pct"] == 0.0
    assert result["high_median_pct"] == 0.0
    for k in _GAP_MEDIAN_KEYS:
        assert result["gap_median_distribution"][k]["count"] == 0
        assert result["gap_median_distribution"][k]["pct"] == 0.0


def test_empty_list_returns_empty() -> None:
    """AC-02: draws=[] 입력 시 기본 구조 반환."""
    wd.invalidate_cache()
    result = wd.get_gap_median_dist_stats([])
    assert result["total_draws"] == 0
    assert result["avg_gap_median"] == 0.0
    assert result["most_common_range"] == "1-2"
    assert result["low_median_pct"] == 0.0
    assert result["high_median_pct"] == 0.0


def test_empty_list_has_all_six_bucket_keys() -> None:
    """AC-03: 빈 리스트 반환값에 6개 버킷 키가 모두 포함."""
    wd.invalidate_cache()
    result = wd.get_gap_median_dist_stats([])
    assert set(result["gap_median_distribution"].keys()) == set(_GAP_MEDIAN_KEYS)


# --------------------------------------------------------------------------- #
# AC-04 ~ AC-16: 단일 회차 버킷 분류 검증
# --------------------------------------------------------------------------- #

def test_single_draw_median_1() -> None:
    """AC-04: [1,2,3,4,5,6]: gaps=[1,1,1,1,1], sorted=[1,1,1,1,1], median=1 → '1-2'."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["1-2"]["count"] == 1
    assert result["avg_gap_median"] == 1.0


def test_single_draw_median_2() -> None:
    """AC-05: [1,3,5,7,9,11]: gaps=[2,2,2,2,2], median=2 → '1-2'."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 3, 5, 7, 9, 11])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["1-2"]["count"] == 1
    assert result["avg_gap_median"] == 2.0


def test_single_draw_median_3() -> None:
    """AC-06: [1,4,7,10,13,16]: gaps=[3,3,3,3,3], median=3 → '3-4'."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 4, 7, 10, 13, 16])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["3-4"]["count"] == 1
    assert result["avg_gap_median"] == 3.0


def test_single_draw_median_4() -> None:
    """AC-07: [1,5,9,13,17,21]: gaps=[4,4,4,4,4], median=4 → '3-4'."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 5, 9, 13, 17, 21])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["3-4"]["count"] == 1
    assert result["avg_gap_median"] == 4.0


def test_single_draw_median_5() -> None:
    """AC-08: [1,6,11,16,21,26]: gaps=[5,5,5,5,5], median=5 → '5-6'."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 6, 11, 16, 21, 26])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["5-6"]["count"] == 1
    assert result["avg_gap_median"] == 5.0


def test_single_draw_median_6() -> None:
    """AC-09: [1,7,13,19,25,31]: gaps=[6,6,6,6,6], median=6 → '5-6'."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 7, 13, 19, 25, 31])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["5-6"]["count"] == 1
    assert result["avg_gap_median"] == 6.0


def test_single_draw_median_7() -> None:
    """AC-10: [1,8,15,22,29,36]: gaps=[7,7,7,7,7], median=7 → '7-8'."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 8, 15, 22, 29, 36])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["7-8"]["count"] == 1
    assert result["avg_gap_median"] == 7.0


def test_single_draw_median_8() -> None:
    """AC-11: [1,9,17,25,33,41]: gaps=[8,8,8,8,8], median=8 → '7-8'."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 9, 17, 25, 33, 41])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["7-8"]["count"] == 1
    assert result["avg_gap_median"] == 8.0


def test_single_draw_median_9() -> None:
    """AC-12: [1,10,19,28,37,44]: gaps=[9,9,9,9,7], sorted=[7,9,9,9,9], median=9 → '9-10'."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 10, 19, 28, 37, 44])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["9-10"]["count"] == 1
    assert result["avg_gap_median"] == 9.0


def test_single_draw_median_10() -> None:
    """AC-13: [1,11,21,31,41,43]: gaps=[10,10,10,10,2], sorted=[2,10,10,10,10], median=10 → '9-10'."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 11, 21, 31, 41, 43])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["9-10"]["count"] == 1
    assert result["avg_gap_median"] == 10.0


def test_single_draw_median_11() -> None:
    """AC-14: [1,12,23,34,40,42]: gaps=[11,11,11,6,2], sorted=[2,6,11,11,11], median=11 → '11+'."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 12, 23, 34, 40, 42])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["11+"]["count"] == 1
    assert result["avg_gap_median"] == 11.0


def test_single_draw_mixed_gaps_ac15() -> None:
    """AC-15: [1,3,5,21,36,45]: gaps=[2,2,16,15,9], sorted=[2,2,9,15,16], median=9 → '9-10'."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 3, 5, 21, 36, 45])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["9-10"]["count"] == 1


def test_single_draw_unequal_gaps_median_ac16() -> None:
    """AC-16: [1,2,10,20,30,40]: gaps=[1,8,10,10,10], sorted=[1,8,10,10,10], median=10 → '9-10'."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 2, 10, 20, 30, 40])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["9-10"]["count"] == 1
    assert result["avg_gap_median"] == 10.0


def test_single_draw_equal_gaps_5_ac17() -> None:
    """AC-17: [5,10,15,20,25,30]: gaps=[5,5,5,5,5], median=5 → '5-6'."""
    wd.invalidate_cache()
    draws = [_mk(1, [5, 10, 15, 20, 25, 30])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["avg_gap_median"] == 5.0
    assert result["gap_median_distribution"]["5-6"]["count"] == 1


def test_bonus_number_excluded_ac18() -> None:
    """AC-18: bonus=45는 계산에 포함되지 않으므로 gaps=[6,6,6,6,6], median=6."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 7, 13, 19, 25, 31], bonus=45)]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["avg_gap_median"] == 6.0


def test_single_draw_extreme_variance_ac48() -> None:
    """AC-48: [1,2,3,4,5,45]: gaps=[1,1,1,1,40], sorted=[1,1,1,1,40], median=1 → '1-2'."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 2, 3, 4, 5, 45])]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["1-2"]["count"] == 1
    assert result["avg_gap_median"] == 1.0


# --------------------------------------------------------------------------- #
# AC-19 ~ AC-27: 다중 회차 집계 검증
# --------------------------------------------------------------------------- #

def test_multi_draw_total_draws_ac19() -> None:
    """AC-19: 3개 회차 데이터 → total_draws==3."""
    wd.invalidate_cache()
    draws = [
        _mk(1, [1, 4, 7, 10, 13, 16]),   # median=3 → '3-4'
        _mk(2, [1, 7, 13, 19, 25, 31]),   # median=6 → '5-6'
        _mk(3, [1, 9, 17, 25, 33, 41]),   # median=8 → '7-8'
    ]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["total_draws"] == 3


def test_multi_draw_avg_gap_median_ac20() -> None:
    """AC-20: gap_median=[4,6,8] → avg_gap_median == 6.0."""
    wd.invalidate_cache()
    draws = [
        _mk(1, [1, 5, 9, 13, 17, 21]),   # median=4
        _mk(2, [1, 7, 13, 19, 25, 31]),   # median=6
        _mk(3, [1, 9, 17, 25, 33, 41]),   # median=8
    ]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["avg_gap_median"] == round((4 + 6 + 8) / 3, 2)


def test_count_sum_equals_total_draws_ac21() -> None:
    """AC-21: count 합산이 total_draws와 일치."""
    wd.invalidate_cache()
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),    # median=1 → '1-2'
        _mk(2, [1, 4, 7, 10, 13, 16]),  # median=3 → '3-4'
        _mk(3, [1, 6, 11, 16, 21, 26]), # median=5 → '5-6'
        _mk(4, [1, 8, 15, 22, 29, 36]), # median=7 → '7-8'
        _mk(5, [1, 10, 19, 28, 37, 44]),# median=9 → '9-10'
    ]
    result = wd.get_gap_median_dist_stats(draws)
    total_count = sum(v["count"] for v in result["gap_median_distribution"].values())
    assert total_count == result["total_draws"]


def test_pct_sum_approx_100_ac22() -> None:
    """AC-22: pct 합산이 100.0에 근사(0.1 허용)."""
    wd.invalidate_cache()
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [1, 4, 7, 10, 13, 16]),
        _mk(3, [1, 6, 11, 16, 21, 26]),
        _mk(4, [1, 8, 15, 22, 29, 36]),
        _mk(5, [1, 10, 19, 28, 37, 44]),
    ]
    result = wd.get_gap_median_dist_stats(draws)
    pct_sum = sum(v["pct"] for v in result["gap_median_distribution"].values())
    assert abs(pct_sum - 100.0) <= 0.1


def test_most_common_range_single_winner_ac23() -> None:
    """AC-23: '5-6' 구간이 다른 구간보다 많을 때 most_common_range == '5-6'."""
    wd.invalidate_cache()
    draws = [
        _mk(1, [1, 6, 11, 16, 21, 26]),  # median=5 → '5-6'
        _mk(2, [1, 7, 13, 19, 25, 31]),  # median=6 → '5-6'
        _mk(3, [1, 4, 7, 10, 13, 16]),   # median=3 → '3-4'
    ]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["most_common_range"] == "5-6"


def test_most_common_range_tie_lower_wins_ac24() -> None:
    """AC-24: '3-4'와 '5-6'이 동률이면 most_common_range == '3-4'(정의 순서상 앞선 것)."""
    wd.invalidate_cache()
    draws = [
        _mk(1, [1, 4, 7, 10, 13, 16]),   # median=3 → '3-4'
        _mk(2, [1, 5, 9, 13, 17, 21]),   # median=4 → '3-4'
        _mk(3, [1, 6, 11, 16, 21, 26]),  # median=5 → '5-6'
        _mk(4, [1, 7, 13, 19, 25, 31]),  # median=6 → '5-6'
    ]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["most_common_range"] == "3-4"


def test_low_median_pct_ac25() -> None:
    """AC-25: 5개 회차 중 2개가 gap_median <= 4 → low_median_pct == 40.0."""
    wd.invalidate_cache()
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),      # median=1 → <=4 ✓
        _mk(2, [1, 4, 7, 10, 13, 16]),   # median=3 → <=4 ✓
        _mk(3, [1, 6, 11, 16, 21, 26]),  # median=5 → <=4 ✗
        _mk(4, [1, 8, 15, 22, 29, 36]),  # median=7 → <=4 ✗
        _mk(5, [1, 10, 19, 28, 37, 44]), # median=9 → <=4 ✗
    ]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["low_median_pct"] == 40.0


def test_high_median_pct_ac26() -> None:
    """AC-26: 4개 회차 중 1개가 gap_median >= 9 → high_median_pct == 25.0."""
    wd.invalidate_cache()
    draws = [
        _mk(1, [1, 6, 11, 16, 21, 26]),  # median=5 → >=9 ✗
        _mk(2, [1, 7, 13, 19, 25, 31]),  # median=6 → >=9 ✗
        _mk(3, [1, 8, 15, 22, 29, 36]),  # median=7 → >=9 ✗
        _mk(4, [1, 10, 19, 28, 37, 44]), # median=9 → >=9 ✓
    ]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["high_median_pct"] == 25.0


def test_both_low_and_high_pct_zero_ac27() -> None:
    """AC-27: 모든 회차의 gap_median이 5~8 범위이면 low/high 모두 0."""
    wd.invalidate_cache()
    draws = [
        _mk(1, [1, 6, 11, 16, 21, 26]),  # median=5
        _mk(2, [1, 7, 13, 19, 25, 31]),  # median=6
        _mk(3, [1, 8, 15, 22, 29, 36]),  # median=7
    ]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["low_median_pct"] == 0.0
    assert result["high_median_pct"] == 0.0


# --------------------------------------------------------------------------- #
# AC-28 / AC-29: 캐시 동작
# --------------------------------------------------------------------------- #

def test_cache_hit_returns_same_object_ac28() -> None:
    """AC-28: 동일 draws로 두 번 호출 시 동일 dict 반환(is 비교)."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 6, 11, 16, 21, 26])]
    result1 = wd.get_gap_median_dist_stats(draws)
    result2 = wd.get_gap_median_dist_stats(draws)
    assert result1 is result2


def test_cache_invalidation_forces_recompute_ac29() -> None:
    """AC-29: invalidate_cache() 호출 후 재계산 시 새 dict 반환."""
    wd.invalidate_cache()
    draws = [_mk(1, [1, 6, 11, 16, 21, 26])]
    result1 = wd.get_gap_median_dist_stats(draws)
    wd.invalidate_cache()
    result2 = wd.get_gap_median_dist_stats(draws)
    assert result1 is not result2


# --------------------------------------------------------------------------- #
# AC-30 / AC-31: 반올림 정밀도
# --------------------------------------------------------------------------- #

def test_pct_rounded_to_2dp_ac30() -> None:
    """AC-30: 3개 회차 중 1개 '1-2' 버킷 → pct == 33.33."""
    wd.invalidate_cache()
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),      # median=1 → '1-2'
        _mk(2, [1, 6, 11, 16, 21, 26]),  # median=5 → '5-6'
        _mk(3, [1, 8, 15, 22, 29, 36]),  # median=7 → '7-8'
    ]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["gap_median_distribution"]["1-2"]["pct"] == 33.33


def test_avg_gap_median_rounded_to_2dp_ac31() -> None:
    """AC-31: gap_median=[1,2,3] → avg == 2.0."""
    wd.invalidate_cache()
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),      # median=1
        _mk(2, [1, 3, 5, 7, 9, 11]),     # median=2
        _mk(3, [1, 4, 7, 10, 13, 16]),   # median=3
    ]
    result = wd.get_gap_median_dist_stats(draws)
    assert result["avg_gap_median"] == 2.0


# --------------------------------------------------------------------------- #
# AC-32 ~ AC-34: API / 페이지 엔드포인트
# --------------------------------------------------------------------------- #

def test_api_endpoint_returns_200_ac32() -> None:
    """AC-32: GET /api/stats/gap_median_dist → HTTP 200, 필수 키 포함."""
    from lotto.web.app import app
    client = TestClient(app)
    resp = client.get("/api/stats/gap_median_dist")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_draws" in data
    assert "avg_gap_median" in data
    assert "most_common_range" in data
    assert "low_median_pct" in data
    assert "high_median_pct" in data
    assert "gap_median_distribution" in data


def test_api_endpoint_limit_param_ac33() -> None:
    """AC-33: GET /api/stats/gap_median_dist?limit=2 → total_draws==2."""
    from lotto.web.app import app
    client = TestClient(app)

    draws = [
        _mk(1, [1, 6, 11, 16, 21, 26]),
        _mk(2, [1, 7, 13, 19, 25, 31]),
        _mk(3, [1, 8, 15, 22, 29, 36]),
    ]
    with patch("lotto.web.data.get_draws", return_value=draws):
        resp = client.get("/api/stats/gap_median_dist?limit=2")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 2


def test_page_endpoint_returns_200_ac34() -> None:
    """AC-34: GET /stats/gap-median-dist → HTTP 200, text/html."""
    from lotto.web.app import app
    client = TestClient(app)
    resp = client.get("/stats/gap-median-dist")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


# --------------------------------------------------------------------------- #
# AC-35 / AC-47: 템플릿 내용
# --------------------------------------------------------------------------- #

def test_page_contains_bucket_labels_ac35() -> None:
    """AC-35: 페이지가 6개 구간 레이블 및 한국어 제목 포함."""
    from lotto.web.app import app
    client = TestClient(app)
    resp = client.get("/stats/gap-median-dist")
    assert resp.status_code == 200
    body = resp.text
    for label in _GAP_MEDIAN_KEYS:
        assert label in body
    assert "번호 간격 중앙값 구간 분포" in body


def test_nav_contains_gap_median_dist_link_ac47() -> None:
    """AC-47: base.html 사이드바에 /stats/gap-median-dist 링크와 텍스트 포함."""
    from lotto.web.app import app
    client = TestClient(app)
    # 아무 페이지나 불러 nav를 확인
    resp = client.get("/stats/gap-median-dist")
    body = resp.text
    assert "/stats/gap-median-dist" in body
    assert "간격 중앙값 구간 분포" in body


# --------------------------------------------------------------------------- #
# AC-36 ~ AC-46: 버킷 경계 세부 검증
# --------------------------------------------------------------------------- #

def test_bucket_boundary_2_is_1_2_ac36() -> None:
    """AC-36: gap_median=2 → '1-2'."""
    assert wd._gap_median_bucket(2) == "1-2"


def test_bucket_boundary_3_is_3_4_ac37() -> None:
    """AC-37: gap_median=3 → '3-4'."""
    assert wd._gap_median_bucket(3) == "3-4"


def test_bucket_boundary_4_is_3_4_ac38() -> None:
    """AC-38: gap_median=4 → '3-4'."""
    assert wd._gap_median_bucket(4) == "3-4"


def test_bucket_boundary_5_is_5_6_ac39() -> None:
    """AC-39: gap_median=5 → '5-6'."""
    assert wd._gap_median_bucket(5) == "5-6"


def test_bucket_boundary_6_is_5_6_ac40() -> None:
    """AC-40: gap_median=6 → '5-6'."""
    assert wd._gap_median_bucket(6) == "5-6"


def test_bucket_boundary_7_is_7_8_ac41() -> None:
    """AC-41: gap_median=7 → '7-8'."""
    assert wd._gap_median_bucket(7) == "7-8"


def test_bucket_boundary_8_is_7_8_ac42() -> None:
    """AC-42: gap_median=8 → '7-8'."""
    assert wd._gap_median_bucket(8) == "7-8"


def test_bucket_boundary_9_is_9_10_ac43() -> None:
    """AC-43: gap_median=9 → '9-10'."""
    assert wd._gap_median_bucket(9) == "9-10"


def test_bucket_boundary_10_is_9_10_ac44() -> None:
    """AC-44: gap_median=10 → '9-10'."""
    assert wd._gap_median_bucket(10) == "9-10"


def test_bucket_boundary_11_is_11plus_ac45() -> None:
    """AC-45: gap_median=11 → '11+'."""
    assert wd._gap_median_bucket(11) == "11+"


def test_bucket_boundary_20_is_11plus_ac46() -> None:
    """AC-46: gap_median=20 → '11+'."""
    assert wd._gap_median_bucket(20) == "11+"


# --------------------------------------------------------------------------- #
# AC-49: 모든 구간에 적어도 1개씩 분포
# --------------------------------------------------------------------------- #

def test_all_buckets_have_one_each_ac49() -> None:
    """AC-49: 6개 회차로 각 구간에 정확히 1개씩 분포."""
    wd.invalidate_cache()
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),        # median=1 → '1-2'
        _mk(2, [1, 4, 7, 10, 13, 16]),     # median=3 → '3-4'
        _mk(3, [1, 6, 11, 16, 21, 26]),    # median=5 → '5-6'
        _mk(4, [1, 8, 15, 22, 29, 36]),    # median=7 → '7-8'
        _mk(5, [1, 10, 19, 28, 37, 44]),   # median=9 → '9-10'
        _mk(6, [1, 12, 23, 34, 40, 42]),   # median=11 → '11+'
    ]
    result = wd.get_gap_median_dist_stats(draws)
    for k in _GAP_MEDIAN_KEYS:
        assert result["gap_median_distribution"][k]["count"] == 1
    assert result["total_draws"] == 6
