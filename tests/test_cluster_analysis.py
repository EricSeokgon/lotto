"""SPEC-LOTTO-092: 번호 군집 수 분포 분석 테스트.

각 회차 본번호 6개(보너스 제외)를 오름차순 정렬한 뒤, 간격이 1인 연속 정수 묶음
("군집", 길이 2 이상)이 몇 개 존재하는지(0~3, cap)를 집계해 4개 고정 키 분포를
검증한다. 단일 고립 번호는 군집으로 세지 않는다. SPEC-069(연속 쌍 개수),
SPEC-062(연속 패턴), SPEC-078(3연속 묶음)과는 정의가 구별되는 별개 지표다.
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

_CLUSTER_KEYS = ["0", "1", "2", "3"]


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

    D1 [1,3,5,7,9,11]    → 간격 전부 2 → clusters=0 → "0"
    D2 [1,2,3,4,5,6]     → 한 묶음 → clusters=1 → "1"
    D3 [1,2,3,10,11,20]  → (1,2,3)+(10,11) → clusters=2 → "2"
    D4 [1,2,10,11,20,21] → (1,2)+(10,11)+(20,21) → clusters=3 → "3"

    avg_cluster_count = (0+1+2+3)/4 = 1.5
    most_common_count = "0" (전부 동률 count=1 → 가장 작은 키)
    has_cluster_pct   = 3/4*100 = 75.0  (clusters>=1: D2,D3,D4)
    """
    return [
        _make_draw(1, [1, 3, 5, 7, 9, 11]),
        _make_draw(2, [1, 2, 3, 4, 5, 6]),
        _make_draw(3, [1, 2, 3, 10, 11, 20]),
        _make_draw(4, [1, 2, 10, 11, 20, 21]),
    ]


# --------------------------------------------------------------------------- #
# 빈 데이터
# --------------------------------------------------------------------------- #


def test_empty_draws_zeros() -> None:
    """빈 draws → 0/기본값 (AC-01)."""
    r = wd.get_cluster_stats([])
    assert r["total_draws"] == 0
    assert r["avg_cluster_count"] == 0.0
    assert r["most_common_count"] == "0"
    assert r["has_cluster_pct"] == 0.0


def test_empty_draws_none_zeros() -> None:
    """None draws → 빈 구조, 4개 키 (AC-02)."""
    r = wd.get_cluster_stats(None)
    assert r["total_draws"] == 0
    assert r["most_common_count"] == "0"
    assert len(r["cluster_distribution"]) == 4


def test_empty_draws_all_keys_zero() -> None:
    """빈 draws → 4개 키 모두 count=0, pct=0.0, 키 순서 일치 (AC-03)."""
    r = wd.get_cluster_stats([])
    dist = r["cluster_distribution"]
    assert list(dist.keys()) == _CLUSTER_KEYS
    for k in _CLUSTER_KEYS:
        assert dist[k]["count"] == 0
        assert dist[k]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 군집 수 계산 (집계 경로)
# --------------------------------------------------------------------------- #


def test_no_gap1_count_0() -> None:
    """[1,3,5,7,9,11] → gap=1 없음 → "0" (AC-04)."""
    r = wd.get_cluster_stats([_make_draw(1, [1, 3, 5, 7, 9, 11])])
    assert r["cluster_distribution"]["0"]["count"] == 1


def test_one_big_cluster_count_1() -> None:
    """[1,2,3,4,5,6] → 한 묶음 → "1" (AC-05)."""
    r = wd.get_cluster_stats([_make_draw(1, [1, 2, 3, 4, 5, 6])])
    assert r["cluster_distribution"]["1"]["count"] == 1


def test_two_clusters_count_2() -> None:
    """[1,2,3,10,11,20] → (1,2,3)+(10,11) → "2" (AC-06)."""
    r = wd.get_cluster_stats([_make_draw(1, [1, 2, 3, 10, 11, 20])])
    assert r["cluster_distribution"]["2"]["count"] == 1


def test_three_clusters_count_3() -> None:
    """[1,2,10,11,20,21] → (1,2)+(10,11)+(20,21) → "3" (AC-07)."""
    r = wd.get_cluster_stats([_make_draw(1, [1, 2, 10, 11, 20, 21])])
    assert r["cluster_distribution"]["3"]["count"] == 1


def test_all_isolated_count_0() -> None:
    """[1,5,10,20,30,40] → 전부 고립 → "0" (AC-08)."""
    r = wd.get_cluster_stats([_make_draw(1, [1, 5, 10, 20, 30, 40])])
    assert r["cluster_distribution"]["0"]["count"] == 1


def test_one_pair_count_1() -> None:
    """[1,2,10,20,30,40] → 쌍 1개 → "1" (AC-09)."""
    r = wd.get_cluster_stats([_make_draw(1, [1, 2, 10, 20, 30, 40])])
    assert r["cluster_distribution"]["1"]["count"] == 1


def test_two_pairs_count_2() -> None:
    """[1,2,10,11,20,30] → 쌍 2개 → "2" (AC-10)."""
    r = wd.get_cluster_stats([_make_draw(1, [1, 2, 10, 11, 20, 30])])
    assert r["cluster_distribution"]["2"]["count"] == 1


def test_single_number_runs_not_counted() -> None:
    """단일 고립 번호는 군집 아님 — 쌍 하나만 있으면 군집 1개 (AC-11)."""
    # [3,4,10,22,35,41]: (3,4) 쌍만 군집 → clusters=1
    assert wd._count_clusters([3, 4, 10, 22, 35, 41]) == 1
    # 고립만: clusters=0
    assert wd._count_clusters([2, 8, 14, 25, 33, 44]) == 0


def test_cap_at_3() -> None:
    """cap 동작 — min(clusters, 3) (AC-12)."""
    # 3쌍 → 3 그대로
    assert wd._count_clusters([1, 2, 10, 11, 20, 21]) == 3
    # 가능한 최대(6개로 3쌍)도 3을 넘지 않음
    assert wd._count_clusters([1, 2, 4, 5, 7, 8]) == 3


# --------------------------------------------------------------------------- #
# 헬퍼 직접 검증
# --------------------------------------------------------------------------- #


def test_helper_count_clusters() -> None:
    """_count_clusters 직접 검증 (AC-13)."""
    assert wd._count_clusters([1, 3, 5, 7, 9, 11]) == 0
    assert wd._count_clusters([1, 2, 3, 4, 5, 6]) == 1
    assert wd._count_clusters([1, 2, 3, 10, 11, 20]) == 2
    assert wd._count_clusters([1, 2, 10, 11, 20, 21]) == 3


def test_helper_unsorted_input() -> None:
    """_count_clusters는 입력을 내부 정렬한다."""
    assert wd._count_clusters([11, 10, 2, 1, 21, 20]) == 3
    assert wd._count_clusters([6, 1, 5, 2, 4, 3]) == 1


# --------------------------------------------------------------------------- #
# 구조 / 집계
# --------------------------------------------------------------------------- #


def test_distribution_has_four_keys() -> None:
    """분포는 정확히 4개 키 (AC-14)."""
    r = wd.get_cluster_stats(_fixture_draws())
    assert set(r["cluster_distribution"].keys()) == set(_CLUSTER_KEYS)
    assert len(r["cluster_distribution"]) == 4


def test_counts_sum_to_total() -> None:
    """모든 count 합 == total_draws (AC-15)."""
    r = wd.get_cluster_stats(_fixture_draws())
    total = sum(c["count"] for c in r["cluster_distribution"].values())
    assert total == r["total_draws"] == 4


def test_pct_rounded_2dp() -> None:
    """pct는 소수 2자리 (1/3 → 33.33) (AC-16)."""
    draws = [
        _make_draw(1, [1, 3, 5, 7, 9, 11]),   # clusters=0
        _make_draw(2, [1, 2, 3, 4, 5, 6]),    # clusters=1
        _make_draw(3, [1, 2, 3, 10, 11, 20]),  # clusters=2
    ]
    r = wd.get_cluster_stats(draws)
    assert r["cluster_distribution"]["0"]["pct"] == 33.33


def test_most_common_tie_break_smallest_key() -> None:
    """most_common_count 동률 시 가장 작은 키 (AC-17)."""
    # "0" 1개, "3" 1개 동률 → "0"
    draws = [
        _make_draw(1, [1, 3, 5, 7, 9, 11]),    # clusters=0
        _make_draw(2, [1, 2, 10, 11, 20, 21]),  # clusters=3
    ]
    r = wd.get_cluster_stats(draws)
    assert r["most_common_count"] == "0"


def test_has_cluster_pct_definition() -> None:
    """has_cluster_pct = clusters>=1 회차 비율 (AC-18)."""
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),     # clusters=1 (>=1)
        _make_draw(2, [1, 2, 10, 11, 20, 21]),  # clusters=3 (>=1)
        _make_draw(3, [1, 3, 5, 7, 9, 11]),    # clusters=0 (<1)
        _make_draw(4, [1, 5, 10, 20, 30, 40]),  # clusters=0 (<1)
    ]
    r = wd.get_cluster_stats(draws)
    # 2/4 = 50.0
    assert r["has_cluster_pct"] == 50.0


def test_avg_cluster_count_rounded_2dp() -> None:
    """avg_cluster_count는 소수 2자리 (AC-19)."""
    r = wd.get_cluster_stats(_fixture_draws())
    assert r["avg_cluster_count"] == 1.5


# --------------------------------------------------------------------------- #
# 4-draw 픽스처
# --------------------------------------------------------------------------- #


def test_fixture_summary() -> None:
    """4-draw 픽스처 요약값 (AC-20)."""
    r = wd.get_cluster_stats(_fixture_draws())
    assert r["total_draws"] == 4
    assert r["avg_cluster_count"] == 1.5
    assert r["most_common_count"] == "0"
    assert r["has_cluster_pct"] == 75.0


def test_fixture_distribution() -> None:
    """4-draw 픽스처 분포 (AC-21)."""
    r = wd.get_cluster_stats(_fixture_draws())
    dist = r["cluster_distribution"]
    assert dist["0"]["count"] == 1
    assert dist["1"]["count"] == 1
    assert dist["2"]["count"] == 1
    assert dist["3"]["count"] == 1


def test_fixture_distribution_pct() -> None:
    """4-draw 픽스처 분포 pct (AC-21)."""
    r = wd.get_cluster_stats(_fixture_draws())
    dist = r["cluster_distribution"]
    assert dist["0"]["pct"] == 25.0
    assert dist["1"]["pct"] == 25.0
    assert dist["2"]["pct"] == 25.0
    assert dist["3"]["pct"] == 25.0


# --------------------------------------------------------------------------- #
# 캐시
# --------------------------------------------------------------------------- #


def test_cache_returns_same_object() -> None:
    """동일 회차 수 재호출 시 캐시 결과 반환 (AC-22)."""
    draws = _fixture_draws()
    r1 = wd.get_cluster_stats(draws)
    r2 = wd.get_cluster_stats(draws)
    assert r1 is r2


def test_invalidate_cache_clears() -> None:
    """invalidate_cache()가 _cluster_cache를 비운다 (AC-23)."""
    wd.get_cluster_stats(_fixture_draws())
    assert len(wd._cluster_cache) > 0
    wd.invalidate_cache()
    assert len(wd._cluster_cache) == 0


# --------------------------------------------------------------------------- #
# 라우트
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/cluster_count → 200 + 키 구조 (AC-24)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/cluster_count")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "avg_cluster_count",
        "most_common_count",
        "has_cluster_pct",
        "cluster_distribution",
    ):
        assert key in body
    assert set(body["cluster_distribution"].keys()) == set(_CLUSTER_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/cluster_count 은 데이터가 없어도 200 (AC-25)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/cluster_count")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/cluster-count → 200(HTML) (AC-26)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/cluster-count")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/cluster-count 은 데이터가 없어도 200 (AC-27)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/cluster-count")
    assert resp.status_code == 200
