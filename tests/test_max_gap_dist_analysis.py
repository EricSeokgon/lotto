"""SPEC-LOTTO-080: 번호 간격 최대값 분포 분석 테스트.

데이터 계층(get_max_gap_dist_stats), 헬퍼(_max_gap_bucket),
캐시(_max_gap_dist_cache), 페이지/API 라우트를 RED-GREEN-REFACTOR로 검증한다.

max_gap(번호 간격 최대값):
- 한 회차의 정렬된 본번호 6개(보너스 제외)에서 인접 차이 5개 중 최댓값.
- 6개 고정 구간 버킷("1-5","6-10","11-15","16-20","21-30","31+")으로 분류(zero-fill).
- avg_max_gap(회차별 max_gap 평균) / most_common_range(동률 시 앞선 구간)
  / high_gap_pct(max_gap>=21 비율).

기존 get_gap_stats(SPEC-056, small/medium/large 분류 + avg_max_gap 단일 수치)와는
출력 구조가 완전히 다른 별개 기능이다.
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


_MAX_GAP_KEYS = ["1-5", "6-10", "11-15", "16-20", "21-30", "31+"]


def _mk(no: int, nums: list[int], bonus: int = 45) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# 손계산 검증용 4개 회차 픽스처.
# D1 [1,2,3,4,5,6]        간격 [1,1,1,1,1]    max 1  → "1-5"
# D2 [1,10,20,30,40,44]   간격 [9,10,10,10,4] max 10 → "6-10"
# D3 [1,2,3,40,41,42]     간격 [1,1,37,1,1]   max 37 → "31+"
# D4 [5,10,15,20,25,30]   간격 [5,5,5,5,5]    max 5  → "1-5"
def _fixture_draws() -> list[DrawResult]:
    return [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [1, 10, 20, 30, 40, 44]),
        _mk(3, [1, 2, 3, 40, 41, 42]),
        _mk(4, [5, 10, 15, 20, 25, 30]),
    ]


# --------------------------------------------------------------------------- #
# 헬퍼 함수 (_max_gap_bucket)
# --------------------------------------------------------------------------- #


def test_bucket_1_5() -> None:
    """max_gap 1~5는 '1-5' 버킷 (AC-06)."""
    assert wd._max_gap_bucket(1) == "1-5"
    assert wd._max_gap_bucket(5) == "1-5"


def test_bucket_6_10() -> None:
    """max_gap 6~10은 '6-10' 버킷 (AC-07)."""
    assert wd._max_gap_bucket(6) == "6-10"
    assert wd._max_gap_bucket(10) == "6-10"


def test_bucket_11_15() -> None:
    """max_gap 11~15는 '11-15' 버킷 (AC-08)."""
    assert wd._max_gap_bucket(11) == "11-15"
    assert wd._max_gap_bucket(15) == "11-15"


def test_bucket_16_20() -> None:
    """max_gap 16~20은 '16-20' 버킷 (AC-09)."""
    assert wd._max_gap_bucket(16) == "16-20"
    assert wd._max_gap_bucket(20) == "16-20"


def test_bucket_21_30() -> None:
    """max_gap 21~30은 '21-30' 버킷 (AC-10)."""
    assert wd._max_gap_bucket(21) == "21-30"
    assert wd._max_gap_bucket(30) == "21-30"


def test_bucket_high() -> None:
    """max_gap 31 이상은 '31+' 버킷 (AC-11)."""
    assert wd._max_gap_bucket(31) == "31+"
    assert wd._max_gap_bucket(44) == "31+"


# --------------------------------------------------------------------------- #
# max_gap 계산 (단일 회차)
# --------------------------------------------------------------------------- #


def test_max_gap_1_bucket_1_5() -> None:
    """[1,2,3,4,5,6] → max_gap 1 → '1-5' (AC-12)."""
    stats = wd.get_max_gap_dist_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert stats["max_gap_distribution"]["1-5"]["count"] == 1


def test_max_gap_37_bucket_31plus() -> None:
    """[1,2,3,40,41,42] → max_gap 37 → '31+' (AC-13)."""
    stats = wd.get_max_gap_dist_stats([_mk(1, [1, 2, 3, 40, 41, 42])])
    assert stats["max_gap_distribution"]["31+"]["count"] == 1


def test_max_gap_5_bucket_1_5() -> None:
    """[5,10,15,20,25,30] → max_gap 5 → '1-5' (AC-14)."""
    stats = wd.get_max_gap_dist_stats([_mk(1, [5, 10, 15, 20, 25, 30])])
    assert stats["max_gap_distribution"]["1-5"]["count"] == 1


def test_max_gap_10_bucket_6_10() -> None:
    """[1,10,20,30,40,44] → max_gap 10 → '6-10' (AC-15)."""
    stats = wd.get_max_gap_dist_stats([_mk(1, [1, 10, 20, 30, 40, 44])])
    assert stats["max_gap_distribution"]["6-10"]["count"] == 1


def test_bonus_excluded() -> None:
    """보너스 번호는 max_gap 계산에 포함되지 않는다 (AC-16).

    본번호 [1,2,3,4,5,6] → max_gap 1. bonus 값과 무관하게 '1-5'.
    """
    s = wd.get_max_gap_dist_stats([_mk(1, [1, 2, 3, 4, 5, 6], bonus=44)])
    assert s["max_gap_distribution"]["1-5"]["count"] == 1


# --------------------------------------------------------------------------- #
# 응답 구조 및 분포
# --------------------------------------------------------------------------- #


def test_response_has_all_top_level_keys() -> None:
    """반환 dict는 5개 최상위 키를 모두 포함한다 (AC-17)."""
    stats = wd.get_max_gap_dist_stats(_fixture_draws())
    for key in (
        "total_draws",
        "avg_max_gap",
        "most_common_range",
        "high_gap_pct",
        "max_gap_distribution",
    ):
        assert key in stats


def test_distribution_always_has_six_keys() -> None:
    """max_gap_distribution은 항상 6개 고정 키만 포함한다 (AC-18)."""
    stats = wd.get_max_gap_dist_stats(_fixture_draws())
    assert set(stats["max_gap_distribution"].keys()) == set(_MAX_GAP_KEYS)


def test_distribution_cells_have_count_and_pct() -> None:
    """각 분포 항목은 count·pct 두 키를 가진다 (AC-19)."""
    stats = wd.get_max_gap_dist_stats(_fixture_draws())
    for key in _MAX_GAP_KEYS:
        cell = stats["max_gap_distribution"][key]
        assert "count" in cell
        assert "pct" in cell


def test_bucket_counts_sum_to_total() -> None:
    """모든 버킷 count 합은 total_draws와 같다 (AC-20)."""
    stats = wd.get_max_gap_dist_stats(_fixture_draws())
    total = sum(c["count"] for c in stats["max_gap_distribution"].values())
    assert total == stats["total_draws"] == 4


def test_distribution_counts_match_fixture() -> None:
    """D1~D4 분포 count — '1-5'=2, '6-10'=1, '31+'=1, 나머지 0 (AC-20)."""
    dist = wd.get_max_gap_dist_stats(_fixture_draws())["max_gap_distribution"]
    assert dist["1-5"]["count"] == 2
    assert dist["6-10"]["count"] == 1
    assert dist["11-15"]["count"] == 0
    assert dist["16-20"]["count"] == 0
    assert dist["21-30"]["count"] == 0
    assert dist["31+"]["count"] == 1


def test_distribution_pct_values() -> None:
    """D1~D4 pct — '1-5'=50.0, '6-10'=25.0, '31+'=25.0 (AC-21)."""
    dist = wd.get_max_gap_dist_stats(_fixture_draws())["max_gap_distribution"]
    assert dist["1-5"]["pct"] == 50.0
    assert dist["6-10"]["pct"] == 25.0
    assert dist["31+"]["pct"] == 25.0


def test_pct_rounded_two_decimals() -> None:
    """3개 회차 → pct는 33.33 형태로 소수 2자리 반올림된다 (AC-21)."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),         # max 1  → 1-5
        _mk(2, [1, 10, 20, 30, 40, 44]),    # max 10 → 6-10
        _mk(3, [1, 2, 3, 40, 41, 42]),      # max 37 → 31+
    ]
    dist = wd.get_max_gap_dist_stats(draws)["max_gap_distribution"]
    assert dist["1-5"]["pct"] == 33.33
    assert dist["6-10"]["pct"] == 33.33
    assert dist["31+"]["pct"] == 33.33


# --------------------------------------------------------------------------- #
# 파생 지표
# --------------------------------------------------------------------------- #


def test_avg_max_gap_fixture() -> None:
    """D1~D4 → (1+10+37+5)/4 = 13.25 (AC-22)."""
    stats = wd.get_max_gap_dist_stats(_fixture_draws())
    assert stats["avg_max_gap"] == 13.25


def test_most_common_range_fixture() -> None:
    """D1~D4 → '1-5'가 2회로 최빈 (AC-23)."""
    stats = wd.get_max_gap_dist_stats(_fixture_draws())
    assert stats["most_common_range"] == "1-5"


def test_high_gap_pct_fixture() -> None:
    """D1~D4 → max_gap>=21 인 D3 1건/4건 → 25.0 (AC-24)."""
    stats = wd.get_max_gap_dist_stats(_fixture_draws())
    assert stats["high_gap_pct"] == 25.0


def test_most_common_range_tie_smaller_wins() -> None:
    """most_common_range 동률 시 더 작은(앞선) 구간이 선택된다 (AC-25).

    max 10('6-10')·max 37('31+') 각 1회 동률 → 앞선 '6-10'이 이긴다.
    """
    draws = [
        _mk(1, [1, 10, 20, 30, 40, 44]),    # max 10 → 6-10
        _mk(2, [1, 2, 3, 40, 41, 42]),      # max 37 → 31+
    ]
    stats = wd.get_max_gap_dist_stats(draws)
    assert stats["most_common_range"] == "6-10"


# --------------------------------------------------------------------------- #
# 경계 및 예외
# --------------------------------------------------------------------------- #


def test_empty_draws_returns_consistent_zero_structure() -> None:
    """빈 draws → 예외 없이 일관된 zero 구조 (AC-01~05)."""
    stats = wd.get_max_gap_dist_stats([])
    assert stats["total_draws"] == 0
    assert stats["avg_max_gap"] == 0.0
    assert stats["high_gap_pct"] == 0.0
    assert stats["most_common_range"] == "1-5"
    assert set(stats["max_gap_distribution"].keys()) == set(_MAX_GAP_KEYS)
    for key in _MAX_GAP_KEYS:
        assert stats["max_gap_distribution"][key]["count"] == 0
        assert stats["max_gap_distribution"][key]["pct"] == 0.0


def test_none_draws_returns_zero_structure() -> None:
    """None 입력도 예외 없이 빈 구조를 반환한다 (AC-04)."""
    stats = wd.get_max_gap_dist_stats(None)
    assert stats["total_draws"] == 0
    assert set(stats["max_gap_distribution"].keys()) == set(_MAX_GAP_KEYS)


def test_single_draw() -> None:
    """단일 회차도 정상 집계된다."""
    stats = wd.get_max_gap_dist_stats([_mk(1, [1, 2, 3, 40, 41, 42])])
    assert stats["total_draws"] == 1
    assert stats["most_common_range"] == "31+"
    assert stats["max_gap_distribution"]["31+"]["count"] == 1


# --------------------------------------------------------------------------- #
# 캐시 동작
# --------------------------------------------------------------------------- #


def test_cache_populated_and_hit() -> None:
    """동일 입력 재호출 시 캐시된 동일 객체를 반환한다 (AC-26)."""
    draws = _fixture_draws()
    first = wd.get_max_gap_dist_stats(draws)
    second = wd.get_max_gap_dist_stats(draws)
    assert first is second


def test_cache_invalidated() -> None:
    """invalidate_cache 후에는 새 결과 객체를 생성한다 (AC-27)."""
    draws = _fixture_draws()
    first = wd.get_max_gap_dist_stats(draws)
    wd.invalidate_cache()
    second = wd.get_max_gap_dist_stats(draws)
    assert first is not second
    assert first == second


def test_invalidate_cache_clears_max_gap_dist_cache() -> None:
    """invalidate_cache가 _max_gap_dist_cache를 비운다 (AC-28)."""
    wd.get_max_gap_dist_stats(_fixture_draws())
    assert len(wd._max_gap_dist_cache) > 0
    wd.invalidate_cache()
    assert len(wd._max_gap_dist_cache) == 0


# --------------------------------------------------------------------------- #
# 라우트
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/max_gap_dist → 200 + 키 구조 (AC-29)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/max_gap_dist")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "avg_max_gap",
        "most_common_range",
        "high_gap_pct",
        "max_gap_distribution",
    ):
        assert key in body
    assert set(body["max_gap_distribution"].keys()) == set(_MAX_GAP_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/max_gap_dist 은 데이터가 없어도 200을 반환한다 (AC-30)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/max_gap_dist")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/max-gap-dist → 200(HTML) (AC-31)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/max-gap-dist")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/max-gap-dist 은 데이터가 없어도 200(빈 상태)을 반환한다 (AC-32)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/max-gap-dist")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 실데이터 스모크
# --------------------------------------------------------------------------- #


def test_real_data_smoke() -> None:
    """실제 데이터가 있으면 total_draws>0, avg_max_gap은 1~44 범위."""
    draws = wd.get_draws()
    if not draws:
        return  # 데이터 미수집 환경에서는 스킵
    result = wd.get_max_gap_dist_stats(draws)
    assert result["total_draws"] > 0
    assert 1.0 <= result["avg_max_gap"] <= 44.0
    assert result["most_common_range"] in _MAX_GAP_KEYS
