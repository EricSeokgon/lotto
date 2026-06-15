"""SPEC-LOTTO-082: 10단위 다양성 분포 분석 테스트.

데이터 계층(get_decade_diversity_stats), 헬퍼(_decade_of),
캐시(_decade_div_cache), 페이지/API 라우트를 RED-GREEN-REFACTOR로 검증한다.

10단위 다양성(decade diversity):
- 한 회차 본번호 6개(보너스 제외)가 커버하는 서로 다른 10단위 그룹의 수.
- 10단위 그룹은 5개: 1(1~9), 2(10~19), 3(20~29), 4(30~39), 5(40~45).
- decade_count 범위 1~5 (본번호 6개이므로 최소 1, 최대 5).
- 분포는 5개 고정 키("1".."5")로 분류(zero-fill).
- avg_decade_count / most_common_count(동률 시 작은 키)
  / full_coverage_pct(count==5 비율).

SPEC-059(get_decade_stats, 구간당 출현 개수 0~6)와는 출력 구조와 정의가
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


_DECADE_DIV_KEYS = ["1", "2", "3", "4", "5"]


def _mk(no: int, nums: list[int], bonus: int = 45) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼."""
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# 손계산 검증용 4개 회차 픽스처.
# D1 [1,11,21,31,41,42]  {1,2,3,4,5} → 5
# D2 [1,2,3,4,5,6]       {1}         → 1
# D3 [1,2,10,11,20,21]   {1,2,3}     → 3
# D4 [10,11,20,21,30,31] {2,3,4}     → 3
def _fixture_draws() -> list[DrawResult]:
    return [
        _mk(1, [1, 11, 21, 31, 41, 42]),
        _mk(2, [1, 2, 3, 4, 5, 6]),
        _mk(3, [1, 2, 10, 11, 20, 21]),
        _mk(4, [10, 11, 20, 21, 30, 31]),
    ]


# --------------------------------------------------------------------------- #
# 헬퍼 함수 (_decade_of)
# --------------------------------------------------------------------------- #


def test_decade_of_first_group() -> None:
    """1~9 는 decade 1 (AC-01)."""
    assert wd._decade_of(1) == 1
    assert wd._decade_of(9) == 1


def test_decade_of_second_group() -> None:
    """10~19 는 decade 2 (AC-02)."""
    assert wd._decade_of(10) == 2
    assert wd._decade_of(19) == 2


def test_decade_of_third_group() -> None:
    """20~29 는 decade 3 (AC-03)."""
    assert wd._decade_of(20) == 3
    assert wd._decade_of(29) == 3


def test_decade_of_fourth_group() -> None:
    """30~39 는 decade 4 (AC-04)."""
    assert wd._decade_of(30) == 4
    assert wd._decade_of(39) == 4


def test_decade_of_fifth_group() -> None:
    """40~45 는 decade 5 (AC-05)."""
    assert wd._decade_of(40) == 5
    assert wd._decade_of(45) == 5


# --------------------------------------------------------------------------- #
# 커버 구간 수 계산
# --------------------------------------------------------------------------- #


def test_count_full_coverage() -> None:
    """[1,11,21,31,41,42] → 5개 구간 (AC-06)."""
    result = wd.get_decade_diversity_stats([_mk(1, [1, 11, 21, 31, 41, 42])])
    assert result["decade_diversity_distribution"]["5"]["count"] == 1


def test_count_single_decade() -> None:
    """[1,2,3,4,5,6] → 1개 구간 (AC-07)."""
    result = wd.get_decade_diversity_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert result["decade_diversity_distribution"]["1"]["count"] == 1


def test_count_three_decades() -> None:
    """[1,2,10,11,20,21] → 3개 구간 (AC-08)."""
    result = wd.get_decade_diversity_stats([_mk(1, [1, 2, 10, 11, 20, 21])])
    assert result["decade_diversity_distribution"]["3"]["count"] == 1


def test_count_three_decades_middle() -> None:
    """[10,11,20,21,30,31] → 3개 구간 {2,3,4} (AC-09)."""
    result = wd.get_decade_diversity_stats([_mk(1, [10, 11, 20, 21, 30, 31])])
    assert result["decade_diversity_distribution"]["3"]["count"] == 1


def test_count_single_decade_teens() -> None:
    """[10,11,12,13,14,15] → 1개 구간 (AC-10)."""
    result = wd.get_decade_diversity_stats([_mk(1, [10, 11, 12, 13, 14, 15])])
    assert result["decade_diversity_distribution"]["1"]["count"] == 1


def test_count_spread_full() -> None:
    """[1,10,20,30,40,45] → 5개 구간 (AC-11)."""
    result = wd.get_decade_diversity_stats([_mk(1, [1, 10, 20, 30, 40, 45])])
    assert result["decade_diversity_distribution"]["5"]["count"] == 1


# --------------------------------------------------------------------------- #
# 빈 입력
# --------------------------------------------------------------------------- #


def test_empty_total_and_avg() -> None:
    """빈 입력 → total_draws 0, avg_decade_count 0.0 (AC-12)."""
    result = wd.get_decade_diversity_stats([])
    assert result["total_draws"] == 0
    assert result["avg_decade_count"] == 0.0


def test_empty_most_common_is_one() -> None:
    """빈 입력 → most_common_count 1 (AC-13)."""
    result = wd.get_decade_diversity_stats([])
    assert result["most_common_count"] == 1


def test_empty_full_coverage_zero() -> None:
    """빈 입력 → full_coverage_pct 0.0 (AC-14)."""
    result = wd.get_decade_diversity_stats([])
    assert result["full_coverage_pct"] == 0.0


def test_empty_distribution_zero_filled() -> None:
    """빈 입력 → 5개 키 모두 count 0, pct 0.0 (AC-15)."""
    result = wd.get_decade_diversity_stats([])
    dist = result["decade_diversity_distribution"]
    assert set(dist.keys()) == set(_DECADE_DIV_KEYS)
    for k in _DECADE_DIV_KEYS:
        assert dist[k]["count"] == 0
        assert dist[k]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 분포 구조 / 집계
# --------------------------------------------------------------------------- #


def test_distribution_exactly_five_keys() -> None:
    """distribution 키는 정확히 1~5 (AC-16)."""
    result = wd.get_decade_diversity_stats(_fixture_draws())
    assert set(result["decade_diversity_distribution"].keys()) == set(
        _DECADE_DIV_KEYS
    )


def test_counts_sum_to_total() -> None:
    """distribution count 합 == total_draws (AC-17)."""
    result = wd.get_decade_diversity_stats(_fixture_draws())
    dist = result["decade_diversity_distribution"]
    assert sum(dist[k]["count"] for k in _DECADE_DIV_KEYS) == result["total_draws"]


def test_pct_rounded_two_dp() -> None:
    """모든 pct 소수 2자리 (AC-18)."""
    result = wd.get_decade_diversity_stats(_fixture_draws())
    dist = result["decade_diversity_distribution"]
    for k in _DECADE_DIV_KEYS:
        assert round(dist[k]["pct"], 2) == dist[k]["pct"]


def test_avg_rounded_two_dp() -> None:
    """avg_decade_count 소수 2자리 (AC-19)."""
    # D1=5, D2=1, D3=3 → 합 9 / 3 = 3.0 (반올림 안정성 확인용으로 3-회차 사용)
    draws = [
        _mk(1, [1, 11, 21, 31, 41, 42]),
        _mk(2, [1, 2, 3, 4, 5, 6]),
        _mk(3, [1, 2, 10, 11, 20, 21]),
    ]
    result = wd.get_decade_diversity_stats(draws)
    assert round(result["avg_decade_count"], 2) == result["avg_decade_count"]


def test_most_common_tie_break_smaller_key() -> None:
    """most_common_count 동률 시 작은 키 우선 (AC-20)."""
    # count1=1개(D2), count5=1개(D1) → 동률 → 작은 키 "1" 우선
    draws = [
        _mk(1, [1, 11, 21, 31, 41, 42]),  # 5
        _mk(2, [1, 2, 3, 4, 5, 6]),  # 1
    ]
    result = wd.get_decade_diversity_stats(draws)
    assert result["most_common_count"] == 1


def test_full_coverage_pct_matches_count5() -> None:
    """full_coverage_pct == count==5 비율 (AC-21)."""
    # 2회차 중 1회차만 count==5 → 50.0
    draws = [
        _mk(1, [1, 11, 21, 31, 41, 42]),  # 5
        _mk(2, [1, 2, 3, 4, 5, 6]),  # 1
    ]
    result = wd.get_decade_diversity_stats(draws)
    assert result["full_coverage_pct"] == 50.0


# --------------------------------------------------------------------------- #
# 손계산 4-회차 픽스처
# --------------------------------------------------------------------------- #


def test_fixture_avg() -> None:
    """4-회차 픽스처 avg_decade_count == 3.0 (AC-22)."""
    result = wd.get_decade_diversity_stats(_fixture_draws())
    assert result["avg_decade_count"] == 3.0


def test_fixture_most_common() -> None:
    """4-회차 픽스처 most_common_count == 3 (AC-23)."""
    result = wd.get_decade_diversity_stats(_fixture_draws())
    assert result["most_common_count"] == 3


def test_fixture_full_coverage() -> None:
    """4-회차 픽스처 full_coverage_pct == 25.0 (AC-24)."""
    result = wd.get_decade_diversity_stats(_fixture_draws())
    assert result["full_coverage_pct"] == 25.0


def test_fixture_distribution_values() -> None:
    """4-회차 픽스처 distribution["3"] count 2, pct 50.0 (AC-25)."""
    result = wd.get_decade_diversity_stats(_fixture_draws())
    dist = result["decade_diversity_distribution"]
    assert dist["3"]["count"] == 2
    assert dist["3"]["pct"] == 50.0
    assert dist["1"]["count"] == 1
    assert dist["1"]["pct"] == 25.0
    assert dist["5"]["count"] == 1
    assert dist["5"]["pct"] == 25.0
    assert dist["2"]["count"] == 0
    assert dist["4"]["count"] == 0


def test_fixture_total_draws() -> None:
    """4-회차 픽스처 total_draws == 4."""
    result = wd.get_decade_diversity_stats(_fixture_draws())
    assert result["total_draws"] == 4


# --------------------------------------------------------------------------- #
# 캐시
# --------------------------------------------------------------------------- #


def test_cache_returns_same_object() -> None:
    """동일 길이 반복 호출 시 캐시된 동일 객체 재사용 (AC-26)."""
    draws = _fixture_draws()
    first = wd.get_decade_diversity_stats(draws)
    second = wd.get_decade_diversity_stats(draws)
    assert first is second


def test_invalidate_cache_clears() -> None:
    """invalidate_cache()가 _decade_div_cache를 비운다 (AC-27)."""
    wd.get_decade_diversity_stats(_fixture_draws())
    assert wd._decade_div_cache
    wd.invalidate_cache()
    assert not wd._decade_div_cache


# --------------------------------------------------------------------------- #
# 라우트
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/decade_diversity → 200 + 키 구조 (AC-28)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/decade_diversity")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "avg_decade_count",
        "most_common_count",
        "full_coverage_pct",
        "decade_diversity_distribution",
    ):
        assert key in body
    assert set(body["decade_diversity_distribution"].keys()) == set(
        _DECADE_DIV_KEYS
    )


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/decade_diversity 은 데이터가 없어도 200 (AC-29)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/decade_diversity")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/decade-diversity → 200(HTML) (AC-30)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/decade-diversity")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/decade-diversity 은 데이터가 없어도 200 (AC-31)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/decade-diversity")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 실데이터 스모크
# --------------------------------------------------------------------------- #


def test_real_data_smoke() -> None:
    """실제 데이터가 있으면 total_draws>0, avg_decade_count는 1~5 범위."""
    draws = wd.get_draws()
    if not draws:
        return  # 데이터 미수집 환경에서는 스킵
    result = wd.get_decade_diversity_stats(draws)
    assert result["total_draws"] > 0
    assert 1.0 <= result["avg_decade_count"] <= 5.0
    assert result["most_common_count"] in (1, 2, 3, 4, 5)
