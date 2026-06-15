"""SPEC-LOTTO-089: 저·고 번호 균형 분포 분석 테스트.

각 회차 본번호 6개(보너스 제외)를 저(1~22)/고(23~45)로 분류하여
한 회차의 저/고 개수 조합("{low}저{high}고")이 이루는 7개 키 분포를 검증한다.
SPEC-061(고저 비율, 정수 키 분포)과는 출력 구조가 다른 별개 지표다.
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

_LOW_HIGH_KEYS = [
    "0저6고",
    "1저5고",
    "2저4고",
    "3저3고",
    "4저2고",
    "5저1고",
    "6저0고",
]


# --------------------------------------------------------------------------- #
# 헬퍼
# --------------------------------------------------------------------------- #


def _make_draw(drw_no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """6개 본번호로 DrawResult를 만든다 (bonus는 저/고 분류와 무관)."""
    n1, n2, n3, n4, n5, n6 = nums
    return DrawResult(
        drwNo=drw_no,
        date=date(2002, 12, 7) + timedelta(days=7 * drw_no),
        n1=n1, n2=n2, n3=n3, n4=n4, n5=n5, n6=n6, bonus=bonus,
    )


def _fixture_draws() -> list[DrawResult]:
    """4-draw 손계산 픽스처.

    D1 [1,2,3,4,5,6]        low=6 → "6저0고"
    D2 [23,24,25,26,27,28]  low=0 → "0저6고"
    D3 [1,2,3,23,24,25]     low=3 → "3저3고"
    D4 [1,22,23,24,25,45]   low=2 → "2저4고"

    avg_low_count     = (6+0+3+2)/4 = 2.75
    most_common_combo = "0저6고" (동률 count=1, 키 순서상 앞선)
    balanced_pct      = 1/4*100 = 25.0
    """
    return [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),
        _make_draw(2, [23, 24, 25, 26, 27, 28]),
        _make_draw(3, [1, 2, 3, 23, 24, 25]),
        _make_draw(4, [1, 22, 23, 24, 25, 45]),
    ]


# --------------------------------------------------------------------------- #
# 빈 데이터
# --------------------------------------------------------------------------- #


def test_empty_draws_zeros() -> None:
    """빈 draws → 0/기본값 (AC-01)."""
    r = wd.get_low_high_stats([])
    assert r["total_draws"] == 0
    assert r["avg_low_count"] == 0.0
    assert r["most_common_combo"] == "0저6고"
    assert r["balanced_pct"] == 0.0


def test_empty_draws_none_zeros() -> None:
    """None draws → 빈 구조, 7개 키 (AC-02)."""
    r = wd.get_low_high_stats(None)
    assert r["total_draws"] == 0
    assert r["most_common_combo"] == "0저6고"
    assert len(r["low_high_distribution"]) == 7


def test_empty_draws_all_keys_zero() -> None:
    """빈 draws → 7개 키 모두 count=0, pct=0.0, 키 순서 일치 (AC-03)."""
    r = wd.get_low_high_stats([])
    dist = r["low_high_distribution"]
    assert list(dist.keys()) == _LOW_HIGH_KEYS
    for k in _LOW_HIGH_KEYS:
        assert dist[k]["count"] == 0
        assert dist[k]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 헬퍼 _low_high_combo
# --------------------------------------------------------------------------- #


def test_combo_all_low() -> None:
    """[1,2,3,4,5,6] 전부 저 → "6저0고" (AC-04)."""
    assert wd._low_high_combo([1, 2, 3, 4, 5, 6]) == "6저0고"


def test_combo_all_high() -> None:
    """[23,24,25,26,27,28] 전부 고 → "0저6고" (AC-05)."""
    assert wd._low_high_combo([23, 24, 25, 26, 27, 28]) == "0저6고"


def test_combo_balanced() -> None:
    """[1,2,3,23,24,25] → "3저3고" (AC-06)."""
    assert wd._low_high_combo([1, 2, 3, 23, 24, 25]) == "3저3고"


def test_combo_2low_4high() -> None:
    """[1,22,23,24,25,45] → "2저4고" (저 1,22 / 고 23,24,25,45) (AC-07)."""
    assert wd._low_high_combo([1, 22, 23, 24, 25, 45]) == "2저4고"


def test_combo_boundary_22_low_23_high() -> None:
    """경계: 22는 저, 23은 고 → [1,2,22,23,24,25] = "3저3고" (AC-08)."""
    assert wd._low_high_combo([1, 2, 22, 23, 24, 25]) == "3저3고"


def test_combo_5low_1high() -> None:
    """[1,2,3,4,22,23] → 저 5 / 고 1 → "5저1고" (AC-09)."""
    assert wd._low_high_combo([1, 2, 3, 4, 22, 23]) == "5저1고"


# --------------------------------------------------------------------------- #
# 단일 회차 분류 (집계 경로)
# --------------------------------------------------------------------------- #


def test_single_all_low() -> None:
    """[1,2,3,4,5,6] → "6저0고" count=1 (AC-10)."""
    r = wd.get_low_high_stats([_make_draw(1, [1, 2, 3, 4, 5, 6])])
    assert r["low_high_distribution"]["6저0고"]["count"] == 1


def test_single_all_high() -> None:
    """[23,24,25,26,27,28] → "0저6고" count=1 (AC-11)."""
    r = wd.get_low_high_stats([_make_draw(1, [23, 24, 25, 26, 27, 28])])
    assert r["low_high_distribution"]["0저6고"]["count"] == 1


def test_single_balanced() -> None:
    """[1,2,3,23,24,25] → "3저3고" count=1 (AC-12)."""
    r = wd.get_low_high_stats([_make_draw(1, [1, 2, 3, 23, 24, 25])])
    assert r["low_high_distribution"]["3저3고"]["count"] == 1


def test_single_2low_4high() -> None:
    """[1,22,23,24,25,45] → "2저4고" count=1 (AC-13)."""
    r = wd.get_low_high_stats([_make_draw(1, [1, 22, 23, 24, 25, 45])])
    assert r["low_high_distribution"]["2저4고"]["count"] == 1


# --------------------------------------------------------------------------- #
# 구조 / 집계
# --------------------------------------------------------------------------- #


def test_distribution_has_seven_keys() -> None:
    """분포는 정확히 7개 키 (AC-14)."""
    r = wd.get_low_high_stats(_fixture_draws())
    assert set(r["low_high_distribution"].keys()) == set(_LOW_HIGH_KEYS)
    assert len(r["low_high_distribution"]) == 7


def test_counts_sum_to_total() -> None:
    """모든 count 합 == total_draws (AC-15)."""
    r = wd.get_low_high_stats(_fixture_draws())
    total = sum(c["count"] for c in r["low_high_distribution"].values())
    assert total == r["total_draws"] == 4


def test_pct_rounded_2dp() -> None:
    """pct는 소수 2자리 (1/3 → 33.33) (AC-16)."""
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),        # 6저0고
        _make_draw(2, [23, 24, 25, 26, 27, 28]),  # 0저6고
        _make_draw(3, [1, 2, 3, 23, 24, 25]),     # 3저3고
    ]
    r = wd.get_low_high_stats(draws)
    assert r["low_high_distribution"]["3저3고"]["pct"] == 33.33


def test_most_common_tie_break_first_key() -> None:
    """most_common_combo 동률 시 키 정의 순서상 앞선 조합 (AC-17)."""
    # "6저0고" 1개, "0저6고" 1개 동률 → "0저6고"
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),        # 6저0고
        _make_draw(2, [23, 24, 25, 26, 27, 28]),  # 0저6고
    ]
    r = wd.get_low_high_stats(draws)
    assert r["most_common_combo"] == "0저6고"


def test_balanced_pct_is_3lo_3hi_only() -> None:
    """balanced_pct = "3저3고" 조합 비율만 (AC-18)."""
    draws = [
        _make_draw(1, [1, 2, 3, 23, 24, 25]),     # 3저3고
        _make_draw(2, [1, 2, 22, 23, 24, 25]),    # 3저3고
        _make_draw(3, [1, 2, 3, 4, 5, 6]),        # 6저0고
        _make_draw(4, [23, 24, 25, 26, 27, 28]),  # 0저6고
    ]
    r = wd.get_low_high_stats(draws)
    # 2/4 = 50.0
    assert r["balanced_pct"] == 50.0


def test_avg_low_count_rounded_2dp() -> None:
    """avg_low_count는 소수 2자리 (AC-19)."""
    r = wd.get_low_high_stats(_fixture_draws())
    assert r["avg_low_count"] == 2.75


# --------------------------------------------------------------------------- #
# 4-draw 픽스처
# --------------------------------------------------------------------------- #


def test_fixture_summary() -> None:
    """4-draw 픽스처 요약값 (AC-20, AC-21, AC-22, AC-23)."""
    r = wd.get_low_high_stats(_fixture_draws())
    assert r["total_draws"] == 4
    assert r["avg_low_count"] == 2.75
    assert r["most_common_combo"] == "0저6고"
    assert r["balanced_pct"] == 25.0


def test_fixture_distribution() -> None:
    """4-draw 픽스처 분포 (AC-24)."""
    r = wd.get_low_high_stats(_fixture_draws())
    dist = r["low_high_distribution"]
    assert dist["0저6고"]["count"] == 1
    assert dist["1저5고"]["count"] == 0
    assert dist["2저4고"]["count"] == 1
    assert dist["3저3고"]["count"] == 1
    assert dist["4저2고"]["count"] == 0
    assert dist["5저1고"]["count"] == 0
    assert dist["6저0고"]["count"] == 1


def test_fixture_distribution_pct() -> None:
    """4-draw 픽스처 분포 pct (관측 조합 각 25.0)."""
    r = wd.get_low_high_stats(_fixture_draws())
    dist = r["low_high_distribution"]
    assert dist["0저6고"]["pct"] == 25.0
    assert dist["2저4고"]["pct"] == 25.0
    assert dist["3저3고"]["pct"] == 25.0
    assert dist["6저0고"]["pct"] == 25.0
    assert dist["1저5고"]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 캐시
# --------------------------------------------------------------------------- #


def test_cache_returns_same_object() -> None:
    """동일 회차 수 재호출 시 캐시 결과 반환 (AC-25)."""
    draws = _fixture_draws()
    r1 = wd.get_low_high_stats(draws)
    r2 = wd.get_low_high_stats(draws)
    assert r1 is r2


def test_invalidate_cache_clears() -> None:
    """invalidate_cache()가 _low_high_cache를 비운다 (AC-26)."""
    wd.get_low_high_stats(_fixture_draws())
    assert len(wd._low_high_cache) > 0
    wd.invalidate_cache()
    assert len(wd._low_high_cache) == 0


# --------------------------------------------------------------------------- #
# 라우트
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/low_high → 200 + 키 구조 (AC-27)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/low_high")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "avg_low_count",
        "most_common_combo",
        "balanced_pct",
        "low_high_distribution",
    ):
        assert key in body
    assert set(body["low_high_distribution"].keys()) == set(_LOW_HIGH_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/low_high 은 데이터가 없어도 200 (AC-28)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/low_high")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/low-high → 200(HTML) (AC-29)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/low-high")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/low-high 은 데이터가 없어도 200 (AC-30)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/low-high")
    assert resp.status_code == 200
