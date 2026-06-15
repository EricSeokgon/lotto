"""SPEC-LOTTO-086: 번호 합계 구간 세분화 분포 분석 테스트.

본번호 6개 합계를 비균등 10단위 세분화 6구간으로 분류한 분포를 검증한다.
구간: "21-60", "61-100", "101-130", "131-160", "161-200", "201-255".
SPEC-049(sum_range_analysis, 폭 20 버킷)와는 별개 지표다.
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

_SUM_RANGE_KEYS = ["21-60", "61-100", "101-130", "131-160", "161-200", "201-255"]


# --------------------------------------------------------------------------- #
# 헬퍼
# --------------------------------------------------------------------------- #


def _make_draw(drw_no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """6개 본번호로 DrawResult를 만든다 (bonus는 합계와 무관)."""
    n1, n2, n3, n4, n5, n6 = nums
    return DrawResult(
        drwNo=drw_no,
        date=date(2002, 12, 7) + timedelta(days=7 * drw_no),
        n1=n1, n2=n2, n3=n3, n4=n4, n5=n5, n6=n6, bonus=bonus,
    )


def _fixture_draws() -> list[DrawResult]:
    """4-draw 손계산 픽스처.

    D1 [1,2,3,4,5,6]      → 21  → "21-60"
    D2 [40,41,42,43,44,45]→ 255 → "201-255"
    D3 [10,20,30,22,23,24]→ 129 → "101-130"
    D4 [15,20,25,30,35,37]→ 162 → "161-200"
    """
    return [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),
        _make_draw(2, [40, 41, 42, 43, 44, 45]),
        _make_draw(3, [10, 20, 30, 22, 23, 24]),
        _make_draw(4, [15, 20, 25, 30, 35, 37]),
    ]


# --------------------------------------------------------------------------- #
# 빈 데이터
# --------------------------------------------------------------------------- #


def test_empty_draws_zeros() -> None:
    """빈 draws → 0/기본값 (AC-01)."""
    r = wd.get_sum_range_stats([])
    assert r["total_draws"] == 0
    assert r["avg_sum"] == 0.0
    assert r["most_common_range"] == "21-60"
    assert r["middle_range_pct"] == 0.0


def test_empty_draws_none_zeros() -> None:
    """None draws → 빈 구조 (AC-01)."""
    r = wd.get_sum_range_stats(None)
    assert r["total_draws"] == 0
    assert r["most_common_range"] == "21-60"


def test_empty_draws_all_keys_zero() -> None:
    """빈 draws → 6개 키 모두 count=0, pct=0.0 (AC-02)."""
    r = wd.get_sum_range_stats([])
    dist = r["sum_range_distribution"]
    assert list(dist.keys()) == _SUM_RANGE_KEYS
    for k in _SUM_RANGE_KEYS:
        assert dist[k]["count"] == 0
        assert dist[k]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 단일 회차 구간 분류
# --------------------------------------------------------------------------- #


def test_min_sum_21() -> None:
    """[1,2,3,4,5,6] sum=21 → "21-60" (AC-03)."""
    r = wd.get_sum_range_stats([_make_draw(1, [1, 2, 3, 4, 5, 6])])
    assert r["sum_range_distribution"]["21-60"]["count"] == 1


def test_max_sum_255() -> None:
    """[40,41,42,43,44,45] sum=255 → "201-255" (AC-04)."""
    r = wd.get_sum_range_stats([_make_draw(1, [40, 41, 42, 43, 44, 45])])
    assert r["sum_range_distribution"]["201-255"]["count"] == 1


def test_sum_129() -> None:
    """sum=129 → "101-130" (AC-05)."""
    r = wd.get_sum_range_stats([_make_draw(1, [10, 20, 30, 22, 23, 24])])
    assert r["sum_range_distribution"]["101-130"]["count"] == 1


def test_sum_162() -> None:
    """sum=162 → "161-200" (AC-06)."""
    r = wd.get_sum_range_stats([_make_draw(1, [15, 20, 25, 30, 35, 37])])
    assert r["sum_range_distribution"]["161-200"]["count"] == 1


def test_sum_135() -> None:
    """sum=135 → "131-160" (AC-07)."""
    r = wd.get_sum_range_stats([_make_draw(1, [20, 21, 22, 23, 24, 25])])
    assert r["sum_range_distribution"]["131-160"]["count"] == 1


def test_sum_75() -> None:
    """sum=75 → "61-100" (AC-08)."""
    r = wd.get_sum_range_stats([_make_draw(1, [10, 11, 12, 13, 14, 15])])
    assert r["sum_range_distribution"]["61-100"]["count"] == 1


# --------------------------------------------------------------------------- #
# 버킷 경계
# --------------------------------------------------------------------------- #


def test_boundary_60() -> None:
    """sum=60 → "21-60" (AC-09)."""
    assert wd._sum_range_bucket(60) == "21-60"


def test_boundary_61() -> None:
    """sum=61 → "61-100" (AC-10)."""
    assert wd._sum_range_bucket(61) == "61-100"


def test_boundary_100() -> None:
    """sum=100 → "61-100" (AC-11)."""
    assert wd._sum_range_bucket(100) == "61-100"


def test_boundary_101() -> None:
    """sum=101 → "101-130" (AC-12)."""
    assert wd._sum_range_bucket(101) == "101-130"


def test_boundary_130() -> None:
    """sum=130 → "101-130" (AC-13)."""
    assert wd._sum_range_bucket(130) == "101-130"


def test_boundary_131() -> None:
    """sum=131 → "131-160" (AC-14)."""
    assert wd._sum_range_bucket(131) == "131-160"


def test_boundary_160() -> None:
    """sum=160 → "131-160" (AC-15)."""
    assert wd._sum_range_bucket(160) == "131-160"


def test_boundary_161() -> None:
    """sum=161 → "161-200" (AC-16)."""
    assert wd._sum_range_bucket(161) == "161-200"


def test_boundary_200() -> None:
    """sum=200 → "161-200" (AC-17)."""
    assert wd._sum_range_bucket(200) == "161-200"


def test_boundary_201() -> None:
    """sum=201 → "201-255" (AC-18)."""
    assert wd._sum_range_bucket(201) == "201-255"


# --------------------------------------------------------------------------- #
# 구조/집계
# --------------------------------------------------------------------------- #


def test_distribution_has_six_keys() -> None:
    """분포는 정확히 6개 키 (AC-19)."""
    r = wd.get_sum_range_stats(_fixture_draws())
    assert set(r["sum_range_distribution"].keys()) == set(_SUM_RANGE_KEYS)
    assert len(r["sum_range_distribution"]) == 6


def test_counts_sum_to_total() -> None:
    """모든 count 합 == total_draws (AC-20)."""
    r = wd.get_sum_range_stats(_fixture_draws())
    total = sum(c["count"] for c in r["sum_range_distribution"].values())
    assert total == r["total_draws"] == 4


def test_pct_rounded_2dp() -> None:
    """pct는 소수 2자리 (AC-21)."""
    # 3회차 중 1회만 "21-60" → 1/3*100 = 33.33
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),        # 21  → 21-60
        _make_draw(2, [40, 41, 42, 43, 44, 45]),  # 255 → 201-255
        _make_draw(3, [10, 11, 12, 13, 14, 15]),  # 75  → 61-100
    ]
    r = wd.get_sum_range_stats(draws)
    assert r["sum_range_distribution"]["21-60"]["pct"] == 33.33


def test_most_common_tie_break_smallest_key() -> None:
    """most_common_range 동률 시 정의 순서상 앞선 구간 (AC-22)."""
    # "21-60" 1개, "201-255" 1개 동률 → "21-60"
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),
        _make_draw(2, [40, 41, 42, 43, 44, 45]),
    ]
    r = wd.get_sum_range_stats(draws)
    assert r["most_common_range"] == "21-60"


def test_middle_range_pct_combined() -> None:
    """middle_range_pct = ("101-130"+"131-160") / total * 100 (AC-23)."""
    draws = [
        _make_draw(1, [10, 20, 30, 22, 23, 24]),  # 129 → 101-130
        _make_draw(2, [20, 21, 22, 23, 24, 25]),  # 135 → 131-160
        _make_draw(3, [1, 2, 3, 4, 5, 6]),        # 21  → 21-60
        _make_draw(4, [40, 41, 42, 43, 44, 45]),  # 255 → 201-255
    ]
    r = wd.get_sum_range_stats(draws)
    # 2/4 = 50.0
    assert r["middle_range_pct"] == 50.0


def test_avg_sum_rounded_2dp() -> None:
    """avg_sum은 소수 2자리 (AC-24)."""
    r = wd.get_sum_range_stats(_fixture_draws())
    assert r["avg_sum"] == 141.75


# --------------------------------------------------------------------------- #
# 4-draw 픽스처
# --------------------------------------------------------------------------- #


def test_fixture_summary() -> None:
    """4-draw 픽스처 요약값 (AC-25)."""
    r = wd.get_sum_range_stats(_fixture_draws())
    assert r["total_draws"] == 4
    assert r["avg_sum"] == 141.75
    assert r["most_common_range"] == "21-60"
    assert r["middle_range_pct"] == 25.0


def test_fixture_distribution() -> None:
    """4-draw 픽스처 분포 (AC-26)."""
    r = wd.get_sum_range_stats(_fixture_draws())
    dist = r["sum_range_distribution"]
    assert dist["21-60"]["count"] == 1
    assert dist["61-100"]["count"] == 0
    assert dist["101-130"]["count"] == 1
    assert dist["131-160"]["count"] == 0
    assert dist["161-200"]["count"] == 1
    assert dist["201-255"]["count"] == 1


# --------------------------------------------------------------------------- #
# 캐시
# --------------------------------------------------------------------------- #


def test_cache_returns_same_object() -> None:
    """동일 회차 수 재호출 시 캐시 결과 반환 (AC-27)."""
    draws = _fixture_draws()
    r1 = wd.get_sum_range_stats(draws)
    r2 = wd.get_sum_range_stats(draws)
    assert r1 is r2


def test_invalidate_cache_clears() -> None:
    """invalidate_cache()가 _sum_range_cache를 비운다 (AC-28)."""
    wd.get_sum_range_stats(_fixture_draws())
    assert len(wd._sum_range_cache) > 0
    wd.invalidate_cache()
    assert len(wd._sum_range_cache) == 0


# --------------------------------------------------------------------------- #
# 라우트
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/sum_range → 200 + 키 구조 (AC-29)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/sum_range")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "avg_sum",
        "most_common_range",
        "middle_range_pct",
        "sum_range_distribution",
    ):
        assert key in body
    assert set(body["sum_range_distribution"].keys()) == set(_SUM_RANGE_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/sum_range 은 데이터가 없어도 200 (AC-30)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/sum_range")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/sum-range-detailed → 200(HTML) (AC-31)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/sum-range-detailed")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/sum-range-detailed 은 데이터가 없어도 200 (AC-32)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/sum-range-detailed")
    assert resp.status_code == 200
