"""SPEC-LOTTO-093: 첫·마지막 번호 구간 조합 분포 분석 테스트.

각 회차 본번호 6개(보너스 제외)의 최솟값(첫 번호)과 최댓값(마지막 번호)이 각각
어느 3구간 밴드(A:1-15 / B:16-30 / C:31-45)에 속하는지 판정해 조합 키(AA~CC,
6개)로 분류한다. min ≤ max 이므로 BA/CA/CB 조합은 불가능하다. SPEC-064
(get_min_max_stats: 값/범위)와는 정의·출력 구조가 다른 별개 지표다.
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

_FIRST_LAST_ZONE_KEYS = ["AA", "AB", "AC", "BB", "BC", "CC"]


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

    D1 [1,2,3,4,5,6]      → min=1(A), max=6(A)  → "AA", span=5
    D2 [1,10,20,30,40,45] → min=1(A), max=45(C) → "AC", span=44
    D3 [16,17,18,19,20,30]→ min=16(B), max=30(B)→ "BB", span=14
    D4 [16,20,25,30,35,40]→ min=16(B), max=40(C)→ "BC", span=24

    avg_span = (5+44+14+24)/4 = 87/4 = 21.75
    most_common_combo = "AA" (전부 동률 count=1 → 키 순서상 앞선 "AA")
    wide_span_pct = 1/4*100 = 25.0  ("AC": D2)
    distribution: AA=1, AB=0, AC=1, BB=1, BC=1, CC=0
    """
    return [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),
        _make_draw(2, [1, 10, 20, 30, 40, 45]),
        _make_draw(3, [16, 17, 18, 19, 20, 30]),
        _make_draw(4, [16, 20, 25, 30, 35, 40]),
    ]


# --------------------------------------------------------------------------- #
# 빈 데이터
# --------------------------------------------------------------------------- #


def test_empty_draws_zeros() -> None:
    """빈 draws → 0/기본값 (AC-01)."""
    r = wd.get_first_last_zone_stats([])
    assert r["total_draws"] == 0
    assert r["avg_span"] == 0.0
    assert r["most_common_combo"] == "AA"
    assert r["wide_span_pct"] == 0.0


def test_empty_draws_none_zeros() -> None:
    """None draws → 빈 구조, 6개 키 (AC-02)."""
    r = wd.get_first_last_zone_stats(None)
    assert r["total_draws"] == 0
    assert r["most_common_combo"] == "AA"
    assert len(r["first_last_zone_distribution"]) == 6


def test_empty_draws_all_keys_zero() -> None:
    """빈 draws → 6개 키 모두 count=0, pct=0.0, 키 순서 일치 (AC-03)."""
    r = wd.get_first_last_zone_stats([])
    dist = r["first_last_zone_distribution"]
    assert list(dist.keys()) == _FIRST_LAST_ZONE_KEYS
    for k in _FIRST_LAST_ZONE_KEYS:
        assert dist[k]["count"] == 0
        assert dist[k]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 조합 분류 (집계 경로)
# --------------------------------------------------------------------------- #


def test_combo_aa() -> None:
    """[1,2,3,4,5,6] → "AA", span=5 (AC-04)."""
    r = wd.get_first_last_zone_stats([_make_draw(1, [1, 2, 3, 4, 5, 6])])
    assert r["first_last_zone_distribution"]["AA"]["count"] == 1
    assert r["avg_span"] == 5.0


def test_combo_ac() -> None:
    """[1,10,20,30,40,45] → "AC", span=44 (AC-05)."""
    r = wd.get_first_last_zone_stats([_make_draw(1, [1, 10, 20, 30, 40, 45])])
    assert r["first_last_zone_distribution"]["AC"]["count"] == 1
    assert r["avg_span"] == 44.0


def test_combo_bb() -> None:
    """[16,17,18,19,20,30] → "BB", span=14 (AC-06)."""
    r = wd.get_first_last_zone_stats([_make_draw(1, [16, 17, 18, 19, 20, 30])])
    assert r["first_last_zone_distribution"]["BB"]["count"] == 1
    assert r["avg_span"] == 14.0


def test_combo_bc() -> None:
    """[16,20,25,30,35,40] → "BC", span=24 (AC-07)."""
    r = wd.get_first_last_zone_stats([_make_draw(1, [16, 20, 25, 30, 35, 40])])
    assert r["first_last_zone_distribution"]["BC"]["count"] == 1
    assert r["avg_span"] == 24.0


def test_combo_cc() -> None:
    """[31,35,38,40,42,45] → "CC", span=14 (AC-08)."""
    r = wd.get_first_last_zone_stats([_make_draw(1, [31, 35, 38, 40, 42, 45])])
    assert r["first_last_zone_distribution"]["CC"]["count"] == 1
    assert r["avg_span"] == 14.0


def test_combo_ab() -> None:
    """[1,5,10,15,20,25] → "AB" (min=1 A, max=25 B) (AC-09)."""
    r = wd.get_first_last_zone_stats([_make_draw(1, [1, 5, 10, 15, 20, 25])])
    assert r["first_last_zone_distribution"]["AB"]["count"] == 1


# --------------------------------------------------------------------------- #
# 경계값
# --------------------------------------------------------------------------- #


def test_min_boundary_zones() -> None:
    """최솟값 경계: 15→A, 16→B, 30→B, 31→C (AC-10).

    캐시 키가 str(len(draws))이므로 동일 회차 수(=1) 입력은 결과를 공유한다.
    경계별 독립 검증을 위해 각 호출 사이에 invalidate_cache()로 캐시를 비운다.
    """
    # min=15 → A, max=45 → C → "AC"
    r = wd.get_first_last_zone_stats([_make_draw(1, [15, 20, 25, 30, 40, 45])])
    assert r["first_last_zone_distribution"]["AC"]["count"] == 1
    wd.invalidate_cache()
    # min=16 → B, max=45 → C → "BC"
    r = wd.get_first_last_zone_stats([_make_draw(1, [16, 20, 25, 30, 40, 45])])
    assert r["first_last_zone_distribution"]["BC"]["count"] == 1
    wd.invalidate_cache()
    # min=30 → B, max=45 → C → "BC"
    r = wd.get_first_last_zone_stats([_make_draw(1, [30, 32, 36, 40, 43, 45])])
    assert r["first_last_zone_distribution"]["BC"]["count"] == 1
    wd.invalidate_cache()
    # min=31 → C, max=45 → C → "CC"
    r = wd.get_first_last_zone_stats([_make_draw(1, [31, 33, 36, 40, 43, 45])])
    assert r["first_last_zone_distribution"]["CC"]["count"] == 1


def test_max_boundary_zones() -> None:
    """최댓값 경계: 15→A, 16→B, 30→B, 31→C (AC-11).

    캐시 키가 str(len(draws))이므로 각 경계 검증 사이에 invalidate_cache()로 비운다.
    """
    # max=15 → A, min=1 → A → "AA"
    r = wd.get_first_last_zone_stats([_make_draw(1, [1, 5, 8, 10, 12, 15])])
    assert r["first_last_zone_distribution"]["AA"]["count"] == 1
    wd.invalidate_cache()
    # max=16 → B, min=1 → A → "AB"
    r = wd.get_first_last_zone_stats([_make_draw(1, [1, 5, 8, 10, 12, 16])])
    assert r["first_last_zone_distribution"]["AB"]["count"] == 1
    wd.invalidate_cache()
    # max=30 → B, min=1 → A → "AB"
    r = wd.get_first_last_zone_stats([_make_draw(1, [1, 5, 8, 10, 12, 30])])
    assert r["first_last_zone_distribution"]["AB"]["count"] == 1
    wd.invalidate_cache()
    # max=31 → C, min=1 → A → "AC"
    r = wd.get_first_last_zone_stats([_make_draw(1, [1, 5, 8, 10, 12, 31])])
    assert r["first_last_zone_distribution"]["AC"]["count"] == 1


# --------------------------------------------------------------------------- #
# 불가능 조합
# --------------------------------------------------------------------------- #


def test_impossible_combos_never_appear() -> None:
    """min ≤ max 이므로 BA/CA/CB 조합은 절대 나타나지 않는다 (AC-12)."""
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),       # AA
        _make_draw(2, [1, 10, 20, 30, 40, 45]),   # AC
        _make_draw(3, [16, 17, 18, 19, 20, 30]),  # BB
        _make_draw(4, [31, 35, 38, 40, 42, 45]),  # CC
        _make_draw(5, [16, 20, 25, 30, 35, 40]),  # BC
    ]
    r = wd.get_first_last_zone_stats(draws)
    # 분포 키에 불가능 조합이 없어야 한다
    assert set(r["first_last_zone_distribution"].keys()) == set(
        _FIRST_LAST_ZONE_KEYS
    )
    for impossible in ("BA", "CA", "CB"):
        assert impossible not in r["first_last_zone_distribution"]


# --------------------------------------------------------------------------- #
# 헬퍼 직접 검증
# --------------------------------------------------------------------------- #


def test_helper_zone_assignment() -> None:
    """_first_last_zone 직접 검증 (AC-16)."""
    assert wd._first_last_zone(1) == "A"
    assert wd._first_last_zone(15) == "A"
    assert wd._first_last_zone(16) == "B"
    assert wd._first_last_zone(30) == "B"
    assert wd._first_last_zone(31) == "C"
    assert wd._first_last_zone(45) == "C"


# --------------------------------------------------------------------------- #
# 구조 / 집계
# --------------------------------------------------------------------------- #


def test_distribution_has_six_keys() -> None:
    """분포는 정확히 6개 키 (AC-13)."""
    r = wd.get_first_last_zone_stats(_fixture_draws())
    assert set(r["first_last_zone_distribution"].keys()) == set(
        _FIRST_LAST_ZONE_KEYS
    )
    assert len(r["first_last_zone_distribution"]) == 6


def test_counts_sum_to_total() -> None:
    """모든 count 합 == total_draws (AC-14)."""
    r = wd.get_first_last_zone_stats(_fixture_draws())
    total = sum(c["count"] for c in r["first_last_zone_distribution"].values())
    assert total == r["total_draws"] == 4


def test_pct_rounded_2dp() -> None:
    """pct는 소수 2자리 (1/3 → 33.33) (AC-15)."""
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),       # AA
        _make_draw(2, [1, 10, 20, 30, 40, 45]),   # AC
        _make_draw(3, [16, 17, 18, 19, 20, 30]),  # BB
    ]
    r = wd.get_first_last_zone_stats(draws)
    assert r["first_last_zone_distribution"]["AA"]["pct"] == 33.33


def test_most_common_tie_break_first_key() -> None:
    """most_common_combo 동률 시 키 순서상 앞선 것 (AC-17)."""
    # "BC" 1개, "AC" 1개 동률 → 키 순서상 "AC" 가 앞섬
    draws = [
        _make_draw(1, [16, 20, 25, 30, 35, 40]),  # BC
        _make_draw(2, [1, 10, 20, 30, 40, 45]),   # AC
    ]
    r = wd.get_first_last_zone_stats(draws)
    assert r["most_common_combo"] == "AC"


def test_wide_span_pct_definition() -> None:
    """wide_span_pct = "AC" 조합 비율만 (AC-18)."""
    draws = [
        _make_draw(1, [1, 10, 20, 30, 40, 45]),   # AC (wide)
        _make_draw(2, [1, 5, 8, 11, 14, 15]),     # AA (not wide)
        _make_draw(3, [16, 17, 18, 19, 20, 30]),  # BB (not wide)
        _make_draw(4, [31, 35, 38, 40, 42, 45]),  # CC (not wide)
    ]
    r = wd.get_first_last_zone_stats(draws)
    # 1/4 = 25.0
    assert r["wide_span_pct"] == 25.0


def test_avg_span_rounded_2dp() -> None:
    """avg_span = (max-min) 평균, 소수 2자리 (AC-19)."""
    r = wd.get_first_last_zone_stats(_fixture_draws())
    assert r["avg_span"] == 21.75


# --------------------------------------------------------------------------- #
# 4-draw 픽스처
# --------------------------------------------------------------------------- #


def test_fixture_summary() -> None:
    """4-draw 픽스처 요약값 (AC-20)."""
    r = wd.get_first_last_zone_stats(_fixture_draws())
    assert r["total_draws"] == 4
    assert r["avg_span"] == 21.75
    assert r["most_common_combo"] == "AA"
    assert r["wide_span_pct"] == 25.0


def test_fixture_distribution() -> None:
    """4-draw 픽스처 분포 (AC-21)."""
    r = wd.get_first_last_zone_stats(_fixture_draws())
    dist = r["first_last_zone_distribution"]
    assert dist["AA"]["count"] == 1
    assert dist["AB"]["count"] == 0
    assert dist["AC"]["count"] == 1
    assert dist["BB"]["count"] == 1
    assert dist["BC"]["count"] == 1
    assert dist["CC"]["count"] == 0


def test_fixture_distribution_pct() -> None:
    """4-draw 픽스처 분포 pct (AC-22)."""
    r = wd.get_first_last_zone_stats(_fixture_draws())
    dist = r["first_last_zone_distribution"]
    assert dist["AA"]["pct"] == 25.0
    assert dist["AC"]["pct"] == 25.0
    assert dist["BB"]["pct"] == 25.0
    assert dist["BC"]["pct"] == 25.0
    assert dist["AB"]["pct"] == 0.0
    assert dist["CC"]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 캐시
# --------------------------------------------------------------------------- #


def test_cache_returns_same_object() -> None:
    """동일 회차 수 재호출 시 캐시 결과 반환 (AC-23)."""
    draws = _fixture_draws()
    r1 = wd.get_first_last_zone_stats(draws)
    r2 = wd.get_first_last_zone_stats(draws)
    assert r1 is r2


def test_invalidate_cache_clears() -> None:
    """invalidate_cache()가 _first_last_zone_cache를 비운다 (AC-24)."""
    wd.get_first_last_zone_stats(_fixture_draws())
    assert len(wd._first_last_zone_cache) > 0
    wd.invalidate_cache()
    assert len(wd._first_last_zone_cache) == 0


# --------------------------------------------------------------------------- #
# 라우트
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/first_last_zone → 200 + 키 구조 (AC-25)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/first_last_zone")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "avg_span",
        "most_common_combo",
        "wide_span_pct",
        "first_last_zone_distribution",
    ):
        assert key in body
    assert set(body["first_last_zone_distribution"].keys()) == set(
        _FIRST_LAST_ZONE_KEYS
    )


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/first_last_zone 은 데이터가 없어도 200 (AC-26)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/first_last_zone")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/first-last-zone → 200(HTML) (AC-27)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/first-last-zone")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/first-last-zone 은 데이터가 없어도 200 (AC-28)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/first-last-zone")
    assert resp.status_code == 200
