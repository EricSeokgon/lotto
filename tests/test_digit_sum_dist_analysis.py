"""SPEC-LOTTO-079: 끝자리 합계 분포 분석 테스트.

데이터 계층(get_digit_sum_dist_stats), 헬퍼(_digit_sum_bucket),
캐시(_digit_sum_dist_cache), 페이지/API 라우트를 RED-GREEN-REFACTOR로 검증한다.

끝자리 합(digit sum):
- 한 회차 본번호 6개(보너스 제외)에서 끝자리(n % 10)의 합.
- 이론상 범위 0~54(6 x 9).
- 6개 고정 구간 버킷("0-9","10-14","15-19","20-24","25-29","30+")으로 분류(zero-fill).
- avg_digit_sum(평균) / most_common_range(동률 시 앞선 구간)
  / high_digit_sum_pct(합>=25 비율).

기존 get_last_digit_sum_stats(SPEC-063, low/mid/high 3카테고리)와는 출력 구조가
완전히 다른 별개 기능이다.
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


_DIGIT_SUM_KEYS = ["0-9", "10-14", "15-19", "20-24", "25-29", "30+"]


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
# D1 [1,2,3,4,5,6]        끝자리 [1,2,3,4,5,6] 합 21 → "20-24"
# D2 [10,20,30,40,41,42]  끝자리 [0,0,0,0,1,2] 합 3  → "0-9"
# D3 [5,15,25,35,6,7]     끝자리 [5,5,5,5,6,7] 합 33 → "30+"
# D4 [3,13,23,33,4,14]    끝자리 [3,3,3,3,4,4] 합 20 → "20-24"
def _fixture_draws() -> list[DrawResult]:
    return [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [10, 20, 30, 40, 41, 42]),
        _mk(3, [5, 15, 25, 35, 6, 7]),
        _mk(4, [3, 13, 23, 33, 4, 14]),
    ]


# --------------------------------------------------------------------------- #
# 헬퍼 함수 (_digit_sum_bucket)
# --------------------------------------------------------------------------- #


def test_bucket_low_boundary() -> None:
    """합 0~9는 '0-9' 버킷 (AC-12)."""
    assert wd._digit_sum_bucket(0) == "0-9"
    assert wd._digit_sum_bucket(9) == "0-9"


def test_bucket_10_14() -> None:
    """합 10~14는 '10-14' 버킷 (AC-12)."""
    assert wd._digit_sum_bucket(10) == "10-14"
    assert wd._digit_sum_bucket(14) == "10-14"


def test_bucket_15_19() -> None:
    """합 15~19는 '15-19' 버킷 (AC-12)."""
    assert wd._digit_sum_bucket(15) == "15-19"
    assert wd._digit_sum_bucket(19) == "15-19"


def test_bucket_20_24() -> None:
    """합 20~24는 '20-24' 버킷 (AC-12)."""
    assert wd._digit_sum_bucket(20) == "20-24"
    assert wd._digit_sum_bucket(24) == "20-24"


def test_bucket_25_29() -> None:
    """합 25~29는 '25-29' 버킷 (AC-12)."""
    assert wd._digit_sum_bucket(25) == "25-29"
    assert wd._digit_sum_bucket(29) == "25-29"


def test_bucket_high() -> None:
    """합 30 이상은 '30+' 버킷 (AC-12)."""
    assert wd._digit_sum_bucket(30) == "30+"
    assert wd._digit_sum_bucket(54) == "30+"


# --------------------------------------------------------------------------- #
# 끝자리 합 / 버킷 계산 (단일 회차)
# --------------------------------------------------------------------------- #


def test_digit_sum_21_bucket_20_24() -> None:
    """[1,2,3,4,5,6] → 끝자리 합 21 → '20-24' (AC-06)."""
    stats = wd.get_digit_sum_dist_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert stats["digit_sum_distribution"]["20-24"]["count"] == 1


def test_digit_sum_3_bucket_0_9() -> None:
    """[10,20,30,40,41,42] → 끝자리 합 3 → '0-9' (AC-07)."""
    stats = wd.get_digit_sum_dist_stats([_mk(1, [10, 20, 30, 40, 41, 42])])
    assert stats["digit_sum_distribution"]["0-9"]["count"] == 1


def test_digit_sum_33_bucket_30plus() -> None:
    """[5,15,25,35,6,7] → 끝자리 합 33 → '30+' (AC-08)."""
    stats = wd.get_digit_sum_dist_stats([_mk(1, [5, 15, 25, 35, 6, 7])])
    assert stats["digit_sum_distribution"]["30+"]["count"] == 1


def test_digit_sum_20_bucket_20_24() -> None:
    """[3,13,23,33,4,14] → 끝자리 합 20 → '20-24' (AC-09)."""
    stats = wd.get_digit_sum_dist_stats([_mk(1, [3, 13, 23, 33, 4, 14])])
    assert stats["digit_sum_distribution"]["20-24"]["count"] == 1


def test_last_digit_of_45_is_5() -> None:
    """번호 45의 끝자리는 5 (AC-10).

    [45,44,43,42,41,40] → 끝자리 [5,4,3,2,1,0] 합 15 → '15-19'.
    """
    stats = wd.get_digit_sum_dist_stats([_mk(1, [40, 41, 42, 43, 44, 45])])
    assert stats["digit_sum_distribution"]["15-19"]["count"] == 1


def test_bonus_excluded() -> None:
    """보너스 번호는 끝자리 합 계산에 포함되지 않는다 (AC-11)."""
    # 본번호 [1,2,3,4,5,6] → 합 21. bonus 값과 무관하게 '20-24'.
    s3 = wd.get_digit_sum_dist_stats([_mk(1, [1, 2, 3, 4, 5, 6], bonus=3)])
    assert s3["digit_sum_distribution"]["20-24"]["count"] == 1


# --------------------------------------------------------------------------- #
# 응답 구조 및 분포
# --------------------------------------------------------------------------- #


def test_response_has_all_top_level_keys() -> None:
    """반환 dict는 5개 최상위 키를 모두 포함한다 (AC-13)."""
    stats = wd.get_digit_sum_dist_stats(_fixture_draws())
    for key in (
        "total_draws",
        "avg_digit_sum",
        "most_common_range",
        "high_digit_sum_pct",
        "digit_sum_distribution",
    ):
        assert key in stats


def test_distribution_always_has_six_keys() -> None:
    """digit_sum_distribution은 항상 6개 고정 키만 포함한다 (AC-14)."""
    stats = wd.get_digit_sum_dist_stats(_fixture_draws())
    assert set(stats["digit_sum_distribution"].keys()) == set(_DIGIT_SUM_KEYS)


def test_distribution_cells_have_count_and_pct() -> None:
    """각 분포 항목은 count·pct 두 키를 가진다 (AC-15)."""
    stats = wd.get_digit_sum_dist_stats(_fixture_draws())
    for key in _DIGIT_SUM_KEYS:
        cell = stats["digit_sum_distribution"][key]
        assert "count" in cell
        assert "pct" in cell


def test_bucket_counts_sum_to_total() -> None:
    """모든 버킷 count 합은 total_draws와 같다 (AC-16)."""
    stats = wd.get_digit_sum_dist_stats(_fixture_draws())
    total = sum(c["count"] for c in stats["digit_sum_distribution"].values())
    assert total == stats["total_draws"] == 4


def test_distribution_counts_match_fixture() -> None:
    """D1~D4 분포 count — '0-9'=1, '20-24'=2, '30+'=1, 나머지 0 (AC-18)."""
    dist = wd.get_digit_sum_dist_stats(_fixture_draws())["digit_sum_distribution"]
    assert dist["0-9"]["count"] == 1
    assert dist["10-14"]["count"] == 0
    assert dist["15-19"]["count"] == 0
    assert dist["20-24"]["count"] == 2
    assert dist["25-29"]["count"] == 0
    assert dist["30+"]["count"] == 1


def test_distribution_pct_values() -> None:
    """D1~D4 pct — '0-9'=25.0, '20-24'=50.0, '30+'=25.0 (AC-19)."""
    dist = wd.get_digit_sum_dist_stats(_fixture_draws())["digit_sum_distribution"]
    assert dist["0-9"]["pct"] == 25.0
    assert dist["20-24"]["pct"] == 50.0
    assert dist["30+"]["pct"] == 25.0


def test_pct_rounded_two_decimals() -> None:
    """3개 회차 → pct는 33.33 형태로 소수 2자리 반올림된다 (AC-17)."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),         # 합 21 → 20-24
        _mk(2, [10, 20, 30, 40, 41, 42]),   # 합 3  → 0-9
        _mk(3, [5, 15, 25, 35, 6, 7]),      # 합 33 → 30+
    ]
    dist = wd.get_digit_sum_dist_stats(draws)["digit_sum_distribution"]
    assert dist["0-9"]["pct"] == 33.33
    assert dist["20-24"]["pct"] == 33.33
    assert dist["30+"]["pct"] == 33.33


# --------------------------------------------------------------------------- #
# 파생 지표
# --------------------------------------------------------------------------- #


def test_avg_digit_sum_fixture() -> None:
    """D1~D4 → (21+3+33+20)/4 = 19.25 (AC-20)."""
    stats = wd.get_digit_sum_dist_stats(_fixture_draws())
    assert stats["avg_digit_sum"] == 19.25


def test_most_common_range_fixture() -> None:
    """D1~D4 → '20-24'가 2회로 최빈 (AC-21)."""
    stats = wd.get_digit_sum_dist_stats(_fixture_draws())
    assert stats["most_common_range"] == "20-24"


def test_high_digit_sum_pct_fixture() -> None:
    """D1~D4 → 합>=25 인 D3 1건/4건 → 25.0 (AC-22)."""
    stats = wd.get_digit_sum_dist_stats(_fixture_draws())
    assert stats["high_digit_sum_pct"] == 25.0


def test_most_common_range_tie_smaller_wins() -> None:
    """most_common_range 동률 시 더 작은(앞선) 구간이 선택된다 (AC-23).

    합 3('0-9')·합 33('30+') 각 1회 동률 → 앞선 '0-9'가 이긴다.
    """
    draws = [
        _mk(1, [10, 20, 30, 40, 41, 42]),   # 합 3  → 0-9
        _mk(2, [5, 15, 25, 35, 6, 7]),      # 합 33 → 30+
    ]
    stats = wd.get_digit_sum_dist_stats(draws)
    assert stats["most_common_range"] == "0-9"


# --------------------------------------------------------------------------- #
# 경계 및 예외
# --------------------------------------------------------------------------- #


def test_empty_draws_returns_consistent_zero_structure() -> None:
    """빈 draws → 예외 없이 일관된 zero 구조 (AC-01~05)."""
    stats = wd.get_digit_sum_dist_stats([])
    assert stats["total_draws"] == 0
    assert stats["avg_digit_sum"] == 0.0
    assert stats["high_digit_sum_pct"] == 0.0
    assert stats["most_common_range"] == "0-9"
    assert set(stats["digit_sum_distribution"].keys()) == set(_DIGIT_SUM_KEYS)
    for key in _DIGIT_SUM_KEYS:
        assert stats["digit_sum_distribution"][key]["count"] == 0
        assert stats["digit_sum_distribution"][key]["pct"] == 0.0


def test_none_draws_returns_zero_structure() -> None:
    """None 입력도 예외 없이 빈 구조를 반환한다 (AC-04)."""
    stats = wd.get_digit_sum_dist_stats(None)
    assert stats["total_draws"] == 0
    assert set(stats["digit_sum_distribution"].keys()) == set(_DIGIT_SUM_KEYS)


def test_single_draw() -> None:
    """단일 회차도 정상 집계된다."""
    stats = wd.get_digit_sum_dist_stats([_mk(1, [5, 15, 25, 35, 6, 7])])
    assert stats["total_draws"] == 1
    assert stats["most_common_range"] == "30+"
    assert stats["digit_sum_distribution"]["30+"]["count"] == 1


# --------------------------------------------------------------------------- #
# 캐시 동작
# --------------------------------------------------------------------------- #


def test_cache_populated_and_hit() -> None:
    """동일 입력 재호출 시 캐시된 동일 객체를 반환한다 (AC-24)."""
    draws = _fixture_draws()
    first = wd.get_digit_sum_dist_stats(draws)
    second = wd.get_digit_sum_dist_stats(draws)
    assert first is second


def test_cache_invalidated() -> None:
    """invalidate_cache 후에는 새 결과 객체를 생성한다 (AC-25)."""
    draws = _fixture_draws()
    first = wd.get_digit_sum_dist_stats(draws)
    wd.invalidate_cache()
    second = wd.get_digit_sum_dist_stats(draws)
    assert first is not second
    assert first == second


def test_invalidate_cache_clears_digit_sum_dist_cache() -> None:
    """invalidate_cache가 _digit_sum_dist_cache를 비운다 (AC-26)."""
    wd.get_digit_sum_dist_stats(_fixture_draws())
    assert len(wd._digit_sum_dist_cache) > 0
    wd.invalidate_cache()
    assert len(wd._digit_sum_dist_cache) == 0


# --------------------------------------------------------------------------- #
# 라우트
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/digit_sum_dist → 200 + 키 구조 (AC-27)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/digit_sum_dist")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "avg_digit_sum",
        "most_common_range",
        "high_digit_sum_pct",
        "digit_sum_distribution",
    ):
        assert key in body
    assert set(body["digit_sum_distribution"].keys()) == set(_DIGIT_SUM_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/digit_sum_dist 은 데이터가 없어도 200을 반환한다 (AC-28)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/digit_sum_dist")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/digit-sum-dist → 200(HTML) (AC-29)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/digit-sum-dist")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/digit-sum-dist 은 데이터가 없어도 200(빈 상태)을 반환한다 (AC-30)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/digit-sum-dist")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 실데이터 스모크
# --------------------------------------------------------------------------- #


def test_real_data_smoke() -> None:
    """실제 데이터가 있으면 total_draws>0, avg_digit_sum은 0~54 범위."""
    draws = wd.get_draws()
    if not draws:
        return  # 데이터 미수집 환경에서는 스킵
    result = wd.get_digit_sum_dist_stats(draws)
    assert result["total_draws"] > 0
    assert 0.0 <= result["avg_digit_sum"] <= 54.0
    assert result["most_common_range"] in _DIGIT_SUM_KEYS
