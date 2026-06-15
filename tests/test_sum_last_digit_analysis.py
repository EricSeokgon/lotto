"""SPEC-LOTTO-090: 번호 합산 끝자리 분포 분석 테스트.

각 회차 본번호 6개(보너스 제외)의 합계를 구한 뒤 그 합계의 일의 자리(0~9)를
기준으로 회차를 분류해 10개 고정 키 분포를 검증한다. SPEC-063(개별 번호 끝자리 합,
low/mid/high 3구간)·SPEC-079(끝자리합 6키)와는 출력 구조가 다른 별개 지표다.
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

_SUM_LAST_DIGIT_KEYS = [str(d) for d in range(10)]


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

    D1 [1,2,3,4,5,6]        sum=21  → "1"
    D2 [40,41,42,43,44,45]  sum=255 → "5"
    D3 [10,20,30,1,2,3]     sum=66  → "6"
    D4 [5,10,15,20,25,30]   sum=105 → "5"

    avg_sum           = (21+255+66+105)/4 = 447/4 = 111.75
    most_common_digit = "5" (count=2)
    even_digit_pct    = 1/4*100 = 25.0  ("6"만 짝수 끝자리)
    """
    return [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),
        _make_draw(2, [40, 41, 42, 43, 44, 45]),
        _make_draw(3, [10, 20, 30, 1, 2, 3]),
        _make_draw(4, [5, 10, 15, 20, 25, 30]),
    ]


# --------------------------------------------------------------------------- #
# 빈 데이터
# --------------------------------------------------------------------------- #


def test_empty_draws_zeros() -> None:
    """빈 draws → 0/기본값 (AC-01)."""
    r = wd.get_sum_last_digit_stats([])
    assert r["total_draws"] == 0
    assert r["avg_sum"] == 0.0
    assert r["most_common_digit"] == "0"
    assert r["even_digit_pct"] == 0.0


def test_empty_draws_none_zeros() -> None:
    """None draws → 빈 구조, 10개 키 (AC-02)."""
    r = wd.get_sum_last_digit_stats(None)
    assert r["total_draws"] == 0
    assert r["most_common_digit"] == "0"
    assert len(r["sum_last_digit_distribution"]) == 10


def test_empty_draws_all_keys_zero() -> None:
    """빈 draws → 10개 키 모두 count=0, pct=0.0, 키 순서 일치 (AC-03)."""
    r = wd.get_sum_last_digit_stats([])
    dist = r["sum_last_digit_distribution"]
    assert list(dist.keys()) == _SUM_LAST_DIGIT_KEYS
    for k in _SUM_LAST_DIGIT_KEYS:
        assert dist[k]["count"] == 0
        assert dist[k]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 끝자리 계산 (집계 경로)
# --------------------------------------------------------------------------- #


def test_single_sum_21_digit_1() -> None:
    """[1,2,3,4,5,6] → sum=21 → "1" (AC-04)."""
    r = wd.get_sum_last_digit_stats([_make_draw(1, [1, 2, 3, 4, 5, 6])])
    assert r["sum_last_digit_distribution"]["1"]["count"] == 1


def test_single_sum_255_digit_5() -> None:
    """[40,41,42,43,44,45] → sum=255 → "5" (AC-05)."""
    r = wd.get_sum_last_digit_stats([_make_draw(1, [40, 41, 42, 43, 44, 45])])
    assert r["sum_last_digit_distribution"]["5"]["count"] == 1


def test_single_sum_66_digit_6() -> None:
    """[10,20,30,1,2,3] → sum=66 → "6" (AC-06)."""
    r = wd.get_sum_last_digit_stats([_make_draw(1, [10, 20, 30, 1, 2, 3])])
    assert r["sum_last_digit_distribution"]["6"]["count"] == 1


def test_single_sum_105_digit_5() -> None:
    """[5,10,15,20,25,30] → sum=105 → "5" (AC-07)."""
    r = wd.get_sum_last_digit_stats([_make_draw(1, [5, 10, 15, 20, 25, 30])])
    assert r["sum_last_digit_distribution"]["5"]["count"] == 1


def test_single_sum_30_digit_0() -> None:
    """[1,2,3,4,5,15] → sum=30 → "0" (AC-08)."""
    r = wd.get_sum_last_digit_stats([_make_draw(1, [1, 2, 3, 4, 5, 15])])
    assert r["sum_last_digit_distribution"]["0"]["count"] == 1


def test_single_sum_29_digit_9() -> None:
    """[1,2,3,4,5,14] → sum=29 → "9" (AC-09)."""
    r = wd.get_sum_last_digit_stats([_make_draw(1, [1, 2, 3, 4, 5, 14])])
    assert r["sum_last_digit_distribution"]["9"]["count"] == 1


# --------------------------------------------------------------------------- #
# 구조 / 집계
# --------------------------------------------------------------------------- #


def test_distribution_has_ten_keys() -> None:
    """분포는 정확히 10개 키 (AC-10)."""
    r = wd.get_sum_last_digit_stats(_fixture_draws())
    assert set(r["sum_last_digit_distribution"].keys()) == set(_SUM_LAST_DIGIT_KEYS)
    assert len(r["sum_last_digit_distribution"]) == 10


def test_counts_sum_to_total() -> None:
    """모든 count 합 == total_draws (AC-11)."""
    r = wd.get_sum_last_digit_stats(_fixture_draws())
    total = sum(c["count"] for c in r["sum_last_digit_distribution"].values())
    assert total == r["total_draws"] == 4


def test_pct_rounded_2dp() -> None:
    """pct는 소수 2자리 (1/3 → 33.33) (AC-12)."""
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),    # sum=21 → "1"
        _make_draw(2, [10, 20, 30, 1, 2, 3]),  # sum=66 → "6"
        _make_draw(3, [1, 2, 3, 4, 5, 15]),    # sum=30 → "0"
    ]
    r = wd.get_sum_last_digit_stats(draws)
    assert r["sum_last_digit_distribution"]["1"]["pct"] == 33.33


def test_most_common_tie_break_smallest_key() -> None:
    """most_common_digit 동률 시 가장 작은 키 (AC-13)."""
    # "1" 1개, "6" 1개 동률 → "1"
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),     # "1"
        _make_draw(2, [10, 20, 30, 1, 2, 3]),  # "6"
    ]
    r = wd.get_sum_last_digit_stats(draws)
    assert r["most_common_digit"] == "1"


def test_even_digit_pct_definition() -> None:
    """even_digit_pct = 짝수 끝자리(0,2,4,6,8) count 합 / total * 100 (AC-14)."""
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 15]),    # sum=30 → "0" (짝수)
        _make_draw(2, [10, 20, 30, 1, 2, 3]),  # sum=66 → "6" (짝수)
        _make_draw(3, [1, 2, 3, 4, 5, 6]),     # sum=21 → "1" (홀수)
        _make_draw(4, [1, 2, 3, 4, 5, 14]),    # sum=29 → "9" (홀수)
    ]
    r = wd.get_sum_last_digit_stats(draws)
    # 2/4 = 50.0
    assert r["even_digit_pct"] == 50.0


def test_avg_sum_rounded_2dp() -> None:
    """avg_sum은 소수 2자리 (AC-15)."""
    r = wd.get_sum_last_digit_stats(_fixture_draws())
    assert r["avg_sum"] == 111.75


# --------------------------------------------------------------------------- #
# 4-draw 픽스처
# --------------------------------------------------------------------------- #


def test_fixture_summary() -> None:
    """4-draw 픽스처 요약값 (AC-16, AC-17, AC-18)."""
    r = wd.get_sum_last_digit_stats(_fixture_draws())
    assert r["total_draws"] == 4
    assert r["avg_sum"] == 111.75
    assert r["most_common_digit"] == "5"
    assert r["even_digit_pct"] == 25.0


def test_fixture_distribution() -> None:
    """4-draw 픽스처 분포 (AC-19)."""
    r = wd.get_sum_last_digit_stats(_fixture_draws())
    dist = r["sum_last_digit_distribution"]
    assert dist["1"]["count"] == 1
    assert dist["5"]["count"] == 2
    assert dist["6"]["count"] == 1
    for k in ("0", "2", "3", "4", "7", "8", "9"):
        assert dist[k]["count"] == 0


def test_fixture_distribution_pct() -> None:
    """4-draw 픽스처 분포 pct (AC-20)."""
    r = wd.get_sum_last_digit_stats(_fixture_draws())
    dist = r["sum_last_digit_distribution"]
    assert dist["1"]["pct"] == 25.0
    assert dist["5"]["pct"] == 50.0
    assert dist["6"]["pct"] == 25.0
    assert dist["0"]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 캐시
# --------------------------------------------------------------------------- #


def test_cache_returns_same_object() -> None:
    """동일 회차 수 재호출 시 캐시 결과 반환 (AC-21)."""
    draws = _fixture_draws()
    r1 = wd.get_sum_last_digit_stats(draws)
    r2 = wd.get_sum_last_digit_stats(draws)
    assert r1 is r2


def test_invalidate_cache_clears() -> None:
    """invalidate_cache()가 _sum_last_digit_cache를 비운다 (AC-22)."""
    wd.get_sum_last_digit_stats(_fixture_draws())
    assert len(wd._sum_last_digit_cache) > 0
    wd.invalidate_cache()
    assert len(wd._sum_last_digit_cache) == 0


# --------------------------------------------------------------------------- #
# 라우트
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/sum_last_digit → 200 + 키 구조 (AC-23)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/sum_last_digit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "avg_sum",
        "most_common_digit",
        "even_digit_pct",
        "sum_last_digit_distribution",
    ):
        assert key in body
    assert set(body["sum_last_digit_distribution"].keys()) == set(_SUM_LAST_DIGIT_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/sum_last_digit 은 데이터가 없어도 200 (AC-24)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/sum_last_digit")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/sum-last-digit → 200(HTML) (AC-25)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/sum-last-digit")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/sum-last-digit 은 데이터가 없어도 200 (AC-26)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/sum-last-digit")
    assert resp.status_code == 200
