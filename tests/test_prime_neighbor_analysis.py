"""SPEC-LOTTO-091: 소수 이웃 번호 포함 분포 분석 테스트.

각 회차 본번호 6개(보너스 제외) 중 "소수 이웃(prime neighbor)"에 해당하는 번호가
몇 개 포함되는지(0~6)를 집계해 7개 고정 키 분포를 검증한다. 소수 이웃이란 1~45에서
자기 자신이 소수이거나 소수와 인접(소수±1)한 번호이다. SPEC-058(소수 개수만 세는
get_prime_stats)와는 정의·출력 구조가 다른 별개 지표다.
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

_PRIME_NEIGHBOR_KEYS = [str(i) for i in range(7)]


# --------------------------------------------------------------------------- #
# 헬퍼
# --------------------------------------------------------------------------- #


def _make_draw(drw_no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """6개 본번호로 DrawResult를 만든다 (bonus는 집계와 무관)."""
    n1, n2, n3, n4, n5, n6 = nums
    return DrawResult(
        drwNo=drw_no,
        date=date(2002, 12, 7) + timedelta(days=7 * drw_no),
        n1=n1, n2=n2, n3=n3, n4=n4, n5=n5, n6=n6, bonus=bonus,
    )


def _fixture_draws() -> list[DrawResult]:
    """4-draw 손계산 픽스처.

    D1 [9,15,21,25,33,35]  → 전부 비이웃 → count=0 → "0"
    D2 [2,3,5,7,11,13]     → 전부 소수(이웃) → count=6 → "6"
    D3 [2,3,5,9,15,21]     → 2,3,5 이웃 / 9,15,21 비이웃 → count=3 → "3"
    D4 [1,4,6,8,10,12]     → 전부 이웃 → count=6 → "6"

    avg_neighbor_count = (0+6+3+6)/4 = 15/4 = 3.75
    most_common_count  = "6" (count=2)
    high_neighbor_pct  = 2/4*100 = 50.0  (count>=5: D2, D4)
    """
    return [
        _make_draw(1, [9, 15, 21, 25, 33, 35]),
        _make_draw(2, [2, 3, 5, 7, 11, 13]),
        _make_draw(3, [2, 3, 5, 9, 15, 21]),
        _make_draw(4, [1, 4, 6, 8, 10, 12]),
    ]


# --------------------------------------------------------------------------- #
# 빈 데이터
# --------------------------------------------------------------------------- #


def test_empty_draws_zeros() -> None:
    """빈 draws → 0/기본값 (AC-01)."""
    r = wd.get_prime_neighbor_stats([])
    assert r["total_draws"] == 0
    assert r["avg_neighbor_count"] == 0.0
    assert r["most_common_count"] == "0"
    assert r["high_neighbor_pct"] == 0.0


def test_empty_draws_none_zeros() -> None:
    """None draws → 빈 구조, 7개 키 (AC-02)."""
    r = wd.get_prime_neighbor_stats(None)
    assert r["total_draws"] == 0
    assert r["most_common_count"] == "0"
    assert len(r["prime_neighbor_distribution"]) == 7


def test_empty_draws_all_keys_zero() -> None:
    """빈 draws → 7개 키 모두 count=0, pct=0.0, 키 순서 일치 (AC-03)."""
    r = wd.get_prime_neighbor_stats([])
    dist = r["prime_neighbor_distribution"]
    assert list(dist.keys()) == _PRIME_NEIGHBOR_KEYS
    for k in _PRIME_NEIGHBOR_KEYS:
        assert dist[k]["count"] == 0
        assert dist[k]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 개수 계산 (집계 경로)
# --------------------------------------------------------------------------- #


def test_all_non_neighbors_count_0() -> None:
    """[9,15,21,25,33,35] → 전부 비이웃 → "0" (AC-04)."""
    r = wd.get_prime_neighbor_stats([_make_draw(1, [9, 15, 21, 25, 33, 35])])
    assert r["prime_neighbor_distribution"]["0"]["count"] == 1


def test_all_primes_count_6() -> None:
    """[2,3,5,7,11,13] → 전부 소수(이웃) → "6" (AC-05)."""
    r = wd.get_prime_neighbor_stats([_make_draw(1, [2, 3, 5, 7, 11, 13])])
    assert r["prime_neighbor_distribution"]["6"]["count"] == 1


def test_mixed_count_3() -> None:
    """[2,3,5,9,15,21] → 2,3,5 이웃 / 나머지 비이웃 → "3" (AC-06)."""
    r = wd.get_prime_neighbor_stats([_make_draw(1, [2, 3, 5, 9, 15, 21])])
    assert r["prime_neighbor_distribution"]["3"]["count"] == 1


def test_all_neighbors_count_6() -> None:
    """[1,4,6,8,10,12] → 전부 이웃 → "6" (AC-07)."""
    r = wd.get_prime_neighbor_stats([_make_draw(1, [1, 4, 6, 8, 10, 12])])
    assert r["prime_neighbor_distribution"]["6"]["count"] == 1


def test_single_neighbor_count_1() -> None:
    """[1,9,15,21,25,26] → 1만 이웃 → "1" (AC-08)."""
    r = wd.get_prime_neighbor_stats([_make_draw(1, [1, 9, 15, 21, 25, 26])])
    assert r["prime_neighbor_distribution"]["1"]["count"] == 1


# --------------------------------------------------------------------------- #
# 집합 검증 (헬퍼 직접 호출)
# --------------------------------------------------------------------------- #


def test_non_neighbors_not_in_set() -> None:
    """비이웃 번호는 집합에 없다 (AC-09)."""
    for n in (9, 15, 21, 25, 26, 27, 33, 34, 35, 39, 45):
        assert n not in wd._PRIME_NEIGHBOR_SET


def test_low_neighbors_in_set() -> None:
    """1~8 은 모두 소수 이웃 집합에 있다 (AC-10)."""
    for n in (1, 2, 3, 4, 5, 6, 7, 8):
        assert n in wd._PRIME_NEIGHBOR_SET


def test_boundary_44_in_45_out() -> None:
    """44 는 이웃(43+1), 45 는 비이웃 (AC-11)."""
    assert 44 in wd._PRIME_NEIGHBOR_SET
    assert 45 not in wd._PRIME_NEIGHBOR_SET


def test_helper_count_prime_neighbors() -> None:
    """_count_prime_neighbors 직접 검증."""
    assert wd._count_prime_neighbors([9, 15, 21, 25, 33, 35]) == 0
    assert wd._count_prime_neighbors([2, 3, 5, 7, 11, 13]) == 6
    assert wd._count_prime_neighbors([2, 3, 5, 9, 15, 21]) == 3


def test_prime_neighbor_set_size() -> None:
    """소수 이웃 집합은 34개 원소."""
    assert len(wd._PRIME_NEIGHBOR_SET) == 34


# --------------------------------------------------------------------------- #
# 구조 / 집계
# --------------------------------------------------------------------------- #


def test_distribution_has_seven_keys() -> None:
    """분포는 정확히 7개 키 (AC-12)."""
    r = wd.get_prime_neighbor_stats(_fixture_draws())
    assert set(r["prime_neighbor_distribution"].keys()) == set(_PRIME_NEIGHBOR_KEYS)
    assert len(r["prime_neighbor_distribution"]) == 7


def test_counts_sum_to_total() -> None:
    """모든 count 합 == total_draws (AC-13)."""
    r = wd.get_prime_neighbor_stats(_fixture_draws())
    total = sum(c["count"] for c in r["prime_neighbor_distribution"].values())
    assert total == r["total_draws"] == 4


def test_pct_rounded_2dp() -> None:
    """pct는 소수 2자리 (1/3 → 33.33) (AC-14)."""
    draws = [
        _make_draw(1, [9, 15, 21, 25, 33, 35]),  # count=0
        _make_draw(2, [2, 3, 5, 7, 11, 13]),     # count=6
        _make_draw(3, [2, 3, 5, 9, 15, 21]),     # count=3
    ]
    r = wd.get_prime_neighbor_stats(draws)
    assert r["prime_neighbor_distribution"]["0"]["pct"] == 33.33


def test_most_common_tie_break_smallest_key() -> None:
    """most_common_count 동률 시 가장 작은 키 (AC-15)."""
    # "0" 1개, "6" 1개 동률 → "0"
    draws = [
        _make_draw(1, [9, 15, 21, 25, 33, 35]),  # count=0
        _make_draw(2, [2, 3, 5, 7, 11, 13]),     # count=6
    ]
    r = wd.get_prime_neighbor_stats(draws)
    assert r["most_common_count"] == "0"


def test_avg_neighbor_count_rounded_2dp() -> None:
    """avg_neighbor_count는 소수 2자리 (AC-16)."""
    r = wd.get_prime_neighbor_stats(_fixture_draws())
    assert r["avg_neighbor_count"] == 3.75


def test_high_neighbor_pct_definition() -> None:
    """high_neighbor_pct = count>=5(5,6) 회차 비율 (AC-17)."""
    draws = [
        _make_draw(1, [2, 3, 5, 7, 11, 13]),     # count=6 (>=5)
        _make_draw(2, [1, 4, 6, 8, 10, 12]),     # count=6 (>=5)
        _make_draw(3, [2, 3, 5, 9, 15, 21]),     # count=3 (<5)
        _make_draw(4, [9, 15, 21, 25, 33, 35]),  # count=0 (<5)
    ]
    r = wd.get_prime_neighbor_stats(draws)
    # 2/4 = 50.0
    assert r["high_neighbor_pct"] == 50.0


# --------------------------------------------------------------------------- #
# 4-draw 픽스처
# --------------------------------------------------------------------------- #


def test_fixture_summary() -> None:
    """4-draw 픽스처 요약값 (AC-18, AC-19)."""
    r = wd.get_prime_neighbor_stats(_fixture_draws())
    assert r["total_draws"] == 4
    assert r["avg_neighbor_count"] == 3.75
    assert r["most_common_count"] == "6"
    assert r["high_neighbor_pct"] == 50.0


def test_fixture_distribution() -> None:
    """4-draw 픽스처 분포 (AC-20)."""
    r = wd.get_prime_neighbor_stats(_fixture_draws())
    dist = r["prime_neighbor_distribution"]
    assert dist["0"]["count"] == 1
    assert dist["3"]["count"] == 1
    assert dist["6"]["count"] == 2
    for k in ("1", "2", "4", "5"):
        assert dist[k]["count"] == 0


def test_fixture_distribution_pct() -> None:
    """4-draw 픽스처 분포 pct (AC-21)."""
    r = wd.get_prime_neighbor_stats(_fixture_draws())
    dist = r["prime_neighbor_distribution"]
    assert dist["0"]["pct"] == 25.0
    assert dist["3"]["pct"] == 25.0
    assert dist["6"]["pct"] == 50.0
    assert dist["1"]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 캐시
# --------------------------------------------------------------------------- #


def test_cache_returns_same_object() -> None:
    """동일 회차 수 재호출 시 캐시 결과 반환 (AC-22)."""
    draws = _fixture_draws()
    r1 = wd.get_prime_neighbor_stats(draws)
    r2 = wd.get_prime_neighbor_stats(draws)
    assert r1 is r2


def test_invalidate_cache_clears() -> None:
    """invalidate_cache()가 _prime_neighbor_cache를 비운다 (AC-23)."""
    wd.get_prime_neighbor_stats(_fixture_draws())
    assert len(wd._prime_neighbor_cache) > 0
    wd.invalidate_cache()
    assert len(wd._prime_neighbor_cache) == 0


# --------------------------------------------------------------------------- #
# 라우트
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/prime_neighbor → 200 + 키 구조 (AC-24)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/prime_neighbor")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "avg_neighbor_count",
        "most_common_count",
        "high_neighbor_pct",
        "prime_neighbor_distribution",
    ):
        assert key in body
    assert set(body["prime_neighbor_distribution"].keys()) == set(_PRIME_NEIGHBOR_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/prime_neighbor 은 데이터가 없어도 200 (AC-25)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/prime_neighbor")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/prime-neighbor → 200(HTML) (AC-26)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/prime-neighbor")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/prime-neighbor 은 데이터가 없어도 200 (AC-27)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/prime-neighbor")
    assert resp.status_code == 200
