"""SPEC-LOTTO-088: 번호 간격 분산 분포 분석 테스트.

각 회차 본번호 6개를 정렬한 뒤 인접 번호 간 5개 간격(gap)의 모분산을 산출하고
그 분산값이 속하는 5개 구간의 분포를 검증한다.
구간: "0-10"(<10), "10-30"(<30), "30-60"(<60), "60-100"(<100), "100+"(>=100).
SPEC-056(간격 패턴)·SPEC-079(최대 간격 분포)와는 산출 대상이 다른 별개 지표다.
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

_GAP_VAR_KEYS = ["0-10", "10-30", "30-60", "60-100", "100+"]


# --------------------------------------------------------------------------- #
# 헬퍼
# --------------------------------------------------------------------------- #


def _make_draw(drw_no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """6개 본번호로 DrawResult를 만든다 (bonus는 간격 분산과 무관)."""
    n1, n2, n3, n4, n5, n6 = nums
    return DrawResult(
        drwNo=drw_no,
        date=date(2002, 12, 7) + timedelta(days=7 * drw_no),
        n1=n1, n2=n2, n3=n3, n4=n4, n5=n5, n6=n6, bonus=bonus,
    )


def _fixture_draws() -> list[DrawResult]:
    """4-draw 손계산 픽스처.

    D1 [1,2,3,4,5,6]        gaps=[1,1,1,1,1]  var=0      → "0-10"
    D2 [1,6,11,16,21,45]    gaps=[5,5,5,5,24] var=57.76  → "30-60"
    D3 [1,2,30,31,40,45]    gaps=[1,28,1,9,5] var=100.96 → "100+"
    D4 [5,10,15,20,25,30]   gaps=[5,5,5,5,5]  var=0      → "0-10"

    avg_variance      = (0+57.76+100.96+0)/4 = 39.68
    most_common_range = "0-10" (count=2)
    uniform_gap_pct   = 2/4*100 = 50.0
    """
    return [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),
        _make_draw(2, [1, 6, 11, 16, 21, 45]),
        _make_draw(3, [1, 2, 30, 31, 40, 45]),
        _make_draw(4, [5, 10, 15, 20, 25, 30]),
    ]


# --------------------------------------------------------------------------- #
# 빈 데이터
# --------------------------------------------------------------------------- #


def test_empty_draws_zeros() -> None:
    """빈 draws → 0/기본값 (AC-01)."""
    r = wd.get_gap_variance_stats([])
    assert r["total_draws"] == 0
    assert r["avg_variance"] == 0.0
    assert r["most_common_range"] == "0-10"
    assert r["uniform_gap_pct"] == 0.0


def test_empty_draws_none_zeros() -> None:
    """None draws → 빈 구조 (AC-02)."""
    r = wd.get_gap_variance_stats(None)
    assert r["total_draws"] == 0
    assert r["most_common_range"] == "0-10"
    assert len(r["gap_variance_distribution"]) == 5


def test_empty_draws_all_keys_zero() -> None:
    """빈 draws → 5개 키 모두 count=0, pct=0.0 (AC-03)."""
    r = wd.get_gap_variance_stats([])
    dist = r["gap_variance_distribution"]
    assert list(dist.keys()) == _GAP_VAR_KEYS
    for k in _GAP_VAR_KEYS:
        assert dist[k]["count"] == 0
        assert dist[k]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 단일 회차 구간 분류
# --------------------------------------------------------------------------- #


def test_variance_zero_uniform() -> None:
    """[1,2,3,4,5,6] var=0 → "0-10" (AC-04)."""
    r = wd.get_gap_variance_stats([_make_draw(1, [1, 2, 3, 4, 5, 6])])
    assert r["gap_variance_distribution"]["0-10"]["count"] == 1


def test_variance_57_76() -> None:
    """[1,6,11,16,21,45] var=57.76 → "30-60" (AC-05)."""
    r = wd.get_gap_variance_stats([_make_draw(1, [1, 6, 11, 16, 21, 45])])
    assert r["gap_variance_distribution"]["30-60"]["count"] == 1


def test_variance_100_96() -> None:
    """[1,2,30,31,40,45] var=100.96 → "100+" (AC-06)."""
    r = wd.get_gap_variance_stats([_make_draw(1, [1, 2, 30, 31, 40, 45])])
    assert r["gap_variance_distribution"]["100+"]["count"] == 1


def test_variance_zero_spaced() -> None:
    """[5,10,15,20,25,30] var=0 → "0-10" (AC-07)."""
    r = wd.get_gap_variance_stats([_make_draw(1, [5, 10, 15, 20, 25, 30])])
    assert r["gap_variance_distribution"]["0-10"]["count"] == 1


def test_variance_0_64() -> None:
    """[1,10,19,28,37,44] gaps=[9,9,9,9,7] var=0.64 → "0-10" (AC-08)."""
    r = wd.get_gap_variance_stats([_make_draw(1, [1, 10, 19, 28, 37, 44])])
    assert r["gap_variance_distribution"]["0-10"]["count"] == 1


# --------------------------------------------------------------------------- #
# 헬퍼 / 분산 계산
# --------------------------------------------------------------------------- #


def test_compute_gap_variance_57_76() -> None:
    """_compute_gap_variance([1,6,11,16,21,45]) ≈ 57.76 (AC-09).

    부동소수 오차가 있을 수 있으므로 2자리로 반올림하여 비교한다.
    """
    assert round(wd._compute_gap_variance([1, 6, 11, 16, 21, 45]), 2) == 57.76


def test_compute_gap_variance_100_96() -> None:
    """_compute_gap_variance([1,2,30,31,40,45]) ≈ 100.96 (AC-10).

    부동소수 오차가 있을 수 있으므로 2자리로 반올림하여 비교한다.
    """
    assert round(wd._compute_gap_variance([1, 2, 30, 31, 40, 45]), 2) == 100.96


# --------------------------------------------------------------------------- #
# 버킷 경계 (헬퍼는 numbers 입력 → variance 산출)
# --------------------------------------------------------------------------- #


def test_boundary_below_10() -> None:
    """var=9.9 → "0-10" (AC-11)."""
    assert wd._gap_variance_bucket_from_variance(9.9) == "0-10"


def test_boundary_10_0() -> None:
    """var=10.0 → "10-30" (AC-12)."""
    assert wd._gap_variance_bucket_from_variance(10.0) == "10-30"


def test_boundary_29_9() -> None:
    """var=29.9 → "10-30" (AC-13)."""
    assert wd._gap_variance_bucket_from_variance(29.9) == "10-30"


def test_boundary_30_0() -> None:
    """var=30.0 → "30-60" (AC-14)."""
    assert wd._gap_variance_bucket_from_variance(30.0) == "30-60"


def test_boundary_59_9() -> None:
    """var=59.9 → "30-60" (AC-15)."""
    assert wd._gap_variance_bucket_from_variance(59.9) == "30-60"


def test_boundary_60_0() -> None:
    """var=60.0 → "60-100" (AC-16)."""
    assert wd._gap_variance_bucket_from_variance(60.0) == "60-100"


def test_boundary_99_9() -> None:
    """var=99.9 → "60-100" (AC-17)."""
    assert wd._gap_variance_bucket_from_variance(99.9) == "60-100"


def test_boundary_100_0() -> None:
    """var=100.0 → "100+" (AC-18)."""
    assert wd._gap_variance_bucket_from_variance(100.0) == "100+"


# --------------------------------------------------------------------------- #
# 구조 / 집계
# --------------------------------------------------------------------------- #


def test_distribution_has_five_keys() -> None:
    """분포는 정확히 5개 키 (AC-19)."""
    r = wd.get_gap_variance_stats(_fixture_draws())
    assert set(r["gap_variance_distribution"].keys()) == set(_GAP_VAR_KEYS)
    assert len(r["gap_variance_distribution"]) == 5


def test_counts_sum_to_total() -> None:
    """모든 count 합 == total_draws (AC-20)."""
    r = wd.get_gap_variance_stats(_fixture_draws())
    total = sum(c["count"] for c in r["gap_variance_distribution"].values())
    assert total == r["total_draws"] == 4


def test_pct_rounded_2dp() -> None:
    """pct는 소수 2자리 (AC-21)."""
    # 3회차 중 1회만 "30-60" → 1/3*100 = 33.33
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),        # var=0      → 0-10
        _make_draw(2, [1, 6, 11, 16, 21, 45]),    # var=57.76  → 30-60
        _make_draw(3, [5, 10, 15, 20, 25, 30]),   # var=0      → 0-10
    ]
    r = wd.get_gap_variance_stats(draws)
    assert r["gap_variance_distribution"]["30-60"]["pct"] == 33.33


def test_most_common_tie_break_smallest_key() -> None:
    """most_common_range 동률 시 정의 순서상 앞선 구간 (AC-22)."""
    # "30-60" 1개, "100+" 1개 동률 → "30-60"
    draws = [
        _make_draw(1, [1, 6, 11, 16, 21, 45]),    # 57.76  → 30-60
        _make_draw(2, [1, 2, 30, 31, 40, 45]),    # 100.96 → 100+
    ]
    r = wd.get_gap_variance_stats(draws)
    assert r["most_common_range"] == "30-60"


def test_uniform_gap_pct_is_0_10_only() -> None:
    """uniform_gap_pct = "0-10"(분산<10) 구간 비율만 (AC-23)."""
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),        # var=0      → 0-10
        _make_draw(2, [5, 10, 15, 20, 25, 30]),   # var=0      → 0-10
        _make_draw(3, [1, 6, 11, 16, 21, 45]),    # var=57.76  → 30-60
        _make_draw(4, [1, 2, 30, 31, 40, 45]),    # var=100.96 → 100+
    ]
    r = wd.get_gap_variance_stats(draws)
    # 2/4 = 50.0
    assert r["uniform_gap_pct"] == 50.0


def test_avg_variance_rounded_2dp() -> None:
    """avg_variance은 소수 2자리 (AC-24)."""
    r = wd.get_gap_variance_stats(_fixture_draws())
    assert r["avg_variance"] == 39.68


# --------------------------------------------------------------------------- #
# 4-draw 픽스처
# --------------------------------------------------------------------------- #


def test_fixture_summary() -> None:
    """4-draw 픽스처 요약값 (AC-25)."""
    r = wd.get_gap_variance_stats(_fixture_draws())
    assert r["total_draws"] == 4
    assert r["avg_variance"] == 39.68
    assert r["most_common_range"] == "0-10"
    assert r["uniform_gap_pct"] == 50.0


def test_fixture_distribution() -> None:
    """4-draw 픽스처 분포 (AC-26)."""
    r = wd.get_gap_variance_stats(_fixture_draws())
    dist = r["gap_variance_distribution"]
    assert dist["0-10"]["count"] == 2
    assert dist["10-30"]["count"] == 0
    assert dist["30-60"]["count"] == 1
    assert dist["60-100"]["count"] == 0
    assert dist["100+"]["count"] == 1


# --------------------------------------------------------------------------- #
# 캐시
# --------------------------------------------------------------------------- #


def test_cache_returns_same_object() -> None:
    """동일 회차 수 재호출 시 캐시 결과 반환 (AC-27)."""
    draws = _fixture_draws()
    r1 = wd.get_gap_variance_stats(draws)
    r2 = wd.get_gap_variance_stats(draws)
    assert r1 is r2


def test_invalidate_cache_clears() -> None:
    """invalidate_cache()가 _gap_var_cache를 비운다 (AC-28)."""
    wd.get_gap_variance_stats(_fixture_draws())
    assert len(wd._gap_var_cache) > 0
    wd.invalidate_cache()
    assert len(wd._gap_var_cache) == 0


# --------------------------------------------------------------------------- #
# 라우트
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/gap_variance → 200 + 키 구조 (AC-29)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/gap_variance")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "avg_variance",
        "most_common_range",
        "uniform_gap_pct",
        "gap_variance_distribution",
    ):
        assert key in body
    assert set(body["gap_variance_distribution"].keys()) == set(_GAP_VAR_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/gap_variance 은 데이터가 없어도 200 (AC-30)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/gap_variance")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/gap-variance → 200(HTML) (AC-31)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/gap-variance")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/gap-variance 은 데이터가 없어도 200 (AC-32)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/gap-variance")
    assert resp.status_code == 200
