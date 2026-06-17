"""SPEC-LOTTO-087: 번호 중앙값 구간 분포 분석 테스트.

각 회차 본번호 6개를 정렬한 뒤 3·4번째 수의 평균(중앙값)이 속하는 10단위
구간(5개)의 분포를 검증한다.
구간: "1-9"(<10), "10-19"(<20), "20-29"(<30), "30-39"(<40), "40-45"(>=40).
SPEC-071(중앙값 9구간 "1-5".."41-45")과는 버킷 정의가 다른 별개 지표다.
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

_MEDIAN_RANGE_KEYS = ["1-9", "10-19", "20-29", "30-39", "40-45"]


# --------------------------------------------------------------------------- #
# 헬퍼
# --------------------------------------------------------------------------- #


def _make_draw(drw_no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """6개 본번호로 DrawResult를 만든다 (bonus는 중앙값과 무관)."""
    n1, n2, n3, n4, n5, n6 = nums
    return DrawResult(
        drwNo=drw_no,
        date=date(2002, 12, 7) + timedelta(days=7 * drw_no),
        n1=n1, n2=n2, n3=n3, n4=n4, n5=n5, n6=n6, bonus=bonus,
    )


def _fixture_draws() -> list[DrawResult]:
    """4-draw 손계산 픽스처.

    D1 [1,2,3,4,5,6]        → median=(3+4)/2=3.5   → "1-9"
    D2 [20,21,22,23,24,25]  → median=(22+23)/2=22.5 → "20-29"
    D3 [30,31,32,33,34,35]  → median=(32+33)/2=32.5 → "30-39"
    D4 [1,2,3,40,41,42]     → median=(3+40)/2=21.5  → "20-29"

    avg_median = (3.5+22.5+32.5+21.5)/4 = 20.0
    most_common_range = "20-29" (count=2)
    central_median_pct = 2/4*100 = 50.0
    """
    return [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),
        _make_draw(2, [20, 21, 22, 23, 24, 25]),
        _make_draw(3, [30, 31, 32, 33, 34, 35]),
        _make_draw(4, [1, 2, 3, 40, 41, 42]),
    ]


# --------------------------------------------------------------------------- #
# 빈 데이터
# --------------------------------------------------------------------------- #


def test_empty_draws_zeros() -> None:
    """빈 draws → 0/기본값 (AC-01)."""
    r = wd.get_median_range_stats([])
    assert r["total_draws"] == 0
    assert r["avg_median"] == 0.0
    assert r["most_common_range"] == "1-9"
    assert r["central_median_pct"] == 0.0


def test_empty_draws_none_zeros() -> None:
    """None draws → 빈 구조 (AC-02)."""
    r = wd.get_median_range_stats(None)
    assert r["total_draws"] == 0
    assert r["most_common_range"] == "1-9"
    assert len(r["median_range_distribution"]) == 5


def test_empty_draws_all_keys_zero() -> None:
    """빈 draws → 5개 키 모두 count=0, pct=0.0 (AC-03)."""
    r = wd.get_median_range_stats([])
    dist = r["median_range_distribution"]
    assert list(dist.keys()) == _MEDIAN_RANGE_KEYS
    for k in _MEDIAN_RANGE_KEYS:
        assert dist[k]["count"] == 0
        assert dist[k]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 단일 회차 구간 분류
# --------------------------------------------------------------------------- #


def test_median_3_5() -> None:
    """[1,2,3,4,5,6] median=3.5 → "1-9" (AC-04)."""
    r = wd.get_median_range_stats([_make_draw(1, [1, 2, 3, 4, 5, 6])])
    assert r["median_range_distribution"]["1-9"]["count"] == 1


def test_median_22_5() -> None:
    """[20,21,22,23,24,25] median=22.5 → "20-29" (AC-05)."""
    r = wd.get_median_range_stats([_make_draw(1, [20, 21, 22, 23, 24, 25])])
    assert r["median_range_distribution"]["20-29"]["count"] == 1


def test_median_32_5() -> None:
    """[30,31,32,33,34,35] median=32.5 → "30-39" (AC-06)."""
    r = wd.get_median_range_stats([_make_draw(1, [30, 31, 32, 33, 34, 35])])
    assert r["median_range_distribution"]["30-39"]["count"] == 1


def test_median_21_5() -> None:
    """[1,2,3,40,41,42] median=21.5 → "20-29" (AC-07)."""
    r = wd.get_median_range_stats([_make_draw(1, [1, 2, 3, 40, 41, 42])])
    assert r["median_range_distribution"]["20-29"]["count"] == 1


def test_median_11_5() -> None:
    """[1,10,11,12,13,40] median=(11+12)/2=11.5 → "10-19" (AC-08)."""
    r = wd.get_median_range_stats([_make_draw(1, [1, 10, 11, 12, 13, 40])])
    assert r["median_range_distribution"]["10-19"]["count"] == 1


def test_median_37_5() -> None:
    """[35,36,37,38,39,40] median=(37+38)/2=37.5 → "30-39" (AC-09)."""
    r = wd.get_median_range_stats([_make_draw(1, [35, 36, 37, 38, 39, 40])])
    assert r["median_range_distribution"]["30-39"]["count"] == 1


def test_median_42_5() -> None:
    """[40,41,42,43,44,45] median=(42+43)/2=42.5 → "40-45" (AC-10)."""
    r = wd.get_median_range_stats([_make_draw(1, [40, 41, 42, 43, 44, 45])])
    assert r["median_range_distribution"]["40-45"]["count"] == 1


# --------------------------------------------------------------------------- #
# 버킷 경계 (헬퍼는 numbers 입력 → median 산출)
# --------------------------------------------------------------------------- #


def test_boundary_9_5() -> None:
    """median=9.5 → "1-9" (AC-11). [1,2,9,10,11,12] → (9+10)/2=9.5."""
    assert wd._median_range_bucket([1, 2, 9, 10, 11, 12]) == "1-9"


def test_boundary_10_0() -> None:
    """median=10.0 → "10-19" (AC-12). [1,2,9,11,12,13] → (9+11)/2=10.0."""
    assert wd._median_range_bucket([1, 2, 9, 11, 12, 13]) == "10-19"


def test_boundary_19_5() -> None:
    """median=19.5 → "10-19" (AC-13). [1,2,19,20,21,22] → (19+20)/2=19.5."""
    assert wd._median_range_bucket([1, 2, 19, 20, 21, 22]) == "10-19"


def test_boundary_20_0() -> None:
    """median=20.0 → "20-29" (AC-14). [1,2,19,21,22,23] → (19+21)/2=20.0."""
    assert wd._median_range_bucket([1, 2, 19, 21, 22, 23]) == "20-29"


def test_boundary_39_5() -> None:
    """median=39.5 → "30-39" (AC-15). [1,2,39,40,41,42] → (39+40)/2=39.5."""
    assert wd._median_range_bucket([1, 2, 39, 40, 41, 42]) == "30-39"


def test_boundary_40_0() -> None:
    """median=40.0 → "40-45" (AC-16). [1,2,39,41,42,43] → (39+41)/2=40.0."""
    assert wd._median_range_bucket([1, 2, 39, 41, 42, 43]) == "40-45"


# --------------------------------------------------------------------------- #
# 구조/집계
# --------------------------------------------------------------------------- #


def test_distribution_has_five_keys() -> None:
    """분포는 정확히 5개 키 (AC-17)."""
    r = wd.get_median_range_stats(_fixture_draws())
    assert set(r["median_range_distribution"].keys()) == set(_MEDIAN_RANGE_KEYS)
    assert len(r["median_range_distribution"]) == 5


def test_counts_sum_to_total() -> None:
    """모든 count 합 == total_draws (AC-18)."""
    r = wd.get_median_range_stats(_fixture_draws())
    total = sum(c["count"] for c in r["median_range_distribution"].values())
    assert total == r["total_draws"] == 4


def test_pct_rounded_2dp() -> None:
    """pct는 소수 2자리 (AC-19)."""
    # 3회차 중 1회만 "1-9" → 1/3*100 = 33.33
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),        # 3.5  → 1-9
        _make_draw(2, [20, 21, 22, 23, 24, 25]),  # 22.5 → 20-29
        _make_draw(3, [30, 31, 32, 33, 34, 35]),  # 32.5 → 30-39
    ]
    r = wd.get_median_range_stats(draws)
    assert r["median_range_distribution"]["1-9"]["pct"] == 33.33


def test_most_common_tie_break_smallest_key() -> None:
    """most_common_range 동률 시 정의 순서상 앞선 구간 (AC-20)."""
    # "1-9" 1개, "40-45" 1개 동률 → "1-9"
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),          # 3.5  → 1-9
        _make_draw(2, [40, 41, 42, 43, 44, 45]),    # 42.5 → 40-45
    ]
    r = wd.get_median_range_stats(draws)
    assert r["most_common_range"] == "1-9"


def test_central_median_pct_is_20_29_only() -> None:
    """central_median_pct = "20-29" 구간 비율만 (AC-21)."""
    draws = [
        _make_draw(1, [20, 21, 22, 23, 24, 25]),  # 22.5 → 20-29
        _make_draw(2, [1, 2, 3, 40, 41, 42]),     # 21.5 → 20-29
        _make_draw(3, [1, 2, 3, 4, 5, 6]),        # 3.5  → 1-9
        _make_draw(4, [40, 41, 42, 43, 44, 45]),  # 42.5 → 40-45
    ]
    r = wd.get_median_range_stats(draws)
    # 2/4 = 50.0
    assert r["central_median_pct"] == 50.0


def test_avg_median_rounded_2dp() -> None:
    """avg_median은 소수 2자리 (AC-22)."""
    r = wd.get_median_range_stats(_fixture_draws())
    assert r["avg_median"] == 20.0


# --------------------------------------------------------------------------- #
# 4-draw 픽스처
# --------------------------------------------------------------------------- #


def test_fixture_summary() -> None:
    """4-draw 픽스처 요약값 (AC-23)."""
    r = wd.get_median_range_stats(_fixture_draws())
    assert r["total_draws"] == 4
    assert r["avg_median"] == 20.0
    assert r["most_common_range"] == "20-29"
    assert r["central_median_pct"] == 50.0


def test_fixture_distribution() -> None:
    """4-draw 픽스처 분포 (AC-24)."""
    r = wd.get_median_range_stats(_fixture_draws())
    dist = r["median_range_distribution"]
    assert dist["1-9"]["count"] == 1
    assert dist["10-19"]["count"] == 0
    assert dist["20-29"]["count"] == 2
    assert dist["30-39"]["count"] == 1
    assert dist["40-45"]["count"] == 0


# --------------------------------------------------------------------------- #
# 캐시
# --------------------------------------------------------------------------- #


def test_cache_returns_same_object() -> None:
    """동일 회차 수 재호출 시 캐시 결과 반환 (AC-25)."""
    draws = _fixture_draws()
    r1 = wd.get_median_range_stats(draws)
    r2 = wd.get_median_range_stats(draws)
    assert r1 is r2


def test_invalidate_cache_clears() -> None:
    """invalidate_cache()가 _median_range_cache를 비운다 (AC-26)."""
    wd.get_median_range_stats(_fixture_draws())
    assert len(wd._median_range_cache) > 0
    wd.invalidate_cache()
    assert len(wd._median_range_cache) == 0


# --------------------------------------------------------------------------- #
# 라우트
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/median_range → 200 + 키 구조 (AC-27)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/median_range")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "avg_median",
        "most_common_range",
        "central_median_pct",
        "median_range_distribution",
    ):
        assert key in body
    assert set(body["median_range_distribution"].keys()) == set(_MEDIAN_RANGE_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/median_range 은 데이터가 없어도 200 (AC-28)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/median_range")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/median-range → 200(HTML) (AC-29)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/median-range")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/median-range 은 데이터가 없어도 200 (AC-30)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/median-range")
    assert resp.status_code == 200
