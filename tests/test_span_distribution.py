"""SPEC-LOTTO-095: 번호 스팬 분포 분석 테스트.

각 회차 본번호 6개(보너스 제외)의 스팬(max - min)을 산출하여 7개 고정 버킷
("10 이하"~"41 이상")으로 분류한다. SPEC-064(최솟값·최댓값 값/범위)와는 출력
구조와 요약 지표(narrow_pct=스팬≤20 비율 / wide_pct=스팬≥36 비율)가 다른 별개
지표다.
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

_SPAN_KEYS = [
    "10 이하",
    "11-20",
    "21-25",
    "26-30",
    "31-35",
    "36-40",
    "41 이상",
]


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
    """5-draw 손계산 픽스처.

    D1 [1,2,3,4,5,6]      span = 6-1   = 5   → "10 이하"
    D2 [1,5,10,15,18,20]  span = 20-1  = 19  → "11-20"
    D3 [1,8,15,20,23,26]  span = 26-1  = 25  → "21-25"
    D4 [2,12,22,30,38,44] span = 44-2  = 42  → "41 이상"
    D5 [1,10,20,30,37,40] span = 40-1  = 39  → "36-40"

    avg_span = (5+19+25+42+39)/5 = 130/5 = 26.0
    most_common_range = "10 이하" (모두 count=1 → 정의 순서상 앞선 키)
    narrow_pct (span≤20) = 2/5*100 = 40.0  (D1, D2)
    wide_pct   (span≥36) = 2/5*100 = 40.0  (D4, D5)
    distribution: 10이하=1, 11-20=1, 21-25=1, 26-30=0, 31-35=0, 36-40=1, 41이상=1
    """
    return [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),
        _make_draw(2, [1, 5, 10, 15, 18, 20]),
        _make_draw(3, [1, 8, 15, 20, 23, 26]),
        _make_draw(4, [2, 12, 22, 30, 38, 44]),
        _make_draw(5, [1, 10, 20, 30, 37, 40]),
    ]


# --------------------------------------------------------------------------- #
# 버킷 경계 _span_bucket (AC-01~14)
# --------------------------------------------------------------------------- #


def test_bucket_span_10_lower() -> None:
    """span=10 → "10 이하" (AC-01)."""
    assert wd._span_bucket(10) == "10 이하"


def test_bucket_span_11_first_band() -> None:
    """span=11 → "11-20" (AC-02)."""
    assert wd._span_bucket(11) == "11-20"


def test_bucket_span_20_upper() -> None:
    """span=20 → "11-20" (AC-03)."""
    assert wd._span_bucket(20) == "11-20"


def test_bucket_span_21() -> None:
    """span=21 → "21-25" (AC-04)."""
    assert wd._span_bucket(21) == "21-25"


def test_bucket_span_25() -> None:
    """span=25 → "21-25" (AC-05)."""
    assert wd._span_bucket(25) == "21-25"


def test_bucket_span_26() -> None:
    """span=26 → "26-30" (AC-06)."""
    assert wd._span_bucket(26) == "26-30"


def test_bucket_span_30() -> None:
    """span=30 → "26-30" (AC-07)."""
    assert wd._span_bucket(30) == "26-30"


def test_bucket_span_31() -> None:
    """span=31 → "31-35" (AC-08)."""
    assert wd._span_bucket(31) == "31-35"


def test_bucket_span_35() -> None:
    """span=35 → "31-35" (AC-09)."""
    assert wd._span_bucket(35) == "31-35"


def test_bucket_span_36() -> None:
    """span=36 → "36-40" (AC-10)."""
    assert wd._span_bucket(36) == "36-40"


def test_bucket_span_40() -> None:
    """span=40 → "36-40" (AC-11)."""
    assert wd._span_bucket(40) == "36-40"


def test_bucket_span_41_upper() -> None:
    """span=41 → "41 이상" (AC-12)."""
    assert wd._span_bucket(41) == "41 이상"


def test_bucket_span_5_low() -> None:
    """span=5 → "10 이하" (AC-13)."""
    assert wd._span_bucket(5) == "10 이하"


def test_bucket_span_44_high() -> None:
    """span=44 → "41 이상" (AC-14)."""
    assert wd._span_bucket(44) == "41 이상"


# --------------------------------------------------------------------------- #
# 빈 데이터 (AC-19~20)
# --------------------------------------------------------------------------- #


def test_empty_draws_zeros() -> None:
    """빈 draws → 0/기본값 (AC-19)."""
    r = wd.get_span_stats([])
    assert r["total_draws"] == 0
    assert r["avg_span"] == 0.0
    assert r["most_common_range"] == "10 이하"
    assert r["narrow_pct"] == 0.0
    assert r["wide_pct"] == 0.0


def test_empty_draws_none() -> None:
    """None draws → 빈 구조, 7개 키 (AC-20)."""
    r = wd.get_span_stats(None)
    assert r["total_draws"] == 0
    assert r["most_common_range"] == "10 이하"
    assert len(r["span_distribution"]) == 7


def test_empty_draws_all_keys_zero() -> None:
    """빈 draws → 7개 키 모두 count=0, pct=0.0, 키 순서 일치 (AC-20)."""
    r = wd.get_span_stats([])
    dist = r["span_distribution"]
    assert list(dist.keys()) == _SPAN_KEYS
    for k in _SPAN_KEYS:
        assert dist[k]["count"] == 0
        assert dist[k]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 단일 회차 분류 (집계 경로)
# --------------------------------------------------------------------------- #


def test_single_narrow() -> None:
    """[1,2,3,4,5,6] span=5 → "10 이하"."""
    r = wd.get_span_stats([_make_draw(1, [1, 2, 3, 4, 5, 6])])
    assert r["span_distribution"]["10 이하"]["count"] == 1
    assert r["avg_span"] == 5.0
    assert r["most_common_range"] == "10 이하"


def test_single_wide() -> None:
    """[2,12,22,30,38,44] span=42 → "41 이상"."""
    r = wd.get_span_stats([_make_draw(1, [2, 12, 22, 30, 38, 44])])
    assert r["span_distribution"]["41 이상"]["count"] == 1
    assert r["avg_span"] == 42.0


def test_aggregation_uses_min_max() -> None:
    """정렬 무관, max-min 으로 스팬 산출 ([20,1,...] → max45 min1)."""
    r = wd.get_span_stats([_make_draw(1, [20, 1, 45, 8, 30, 15])])
    # span = 45 - 1 = 44 → "41 이상"
    assert r["span_distribution"]["41 이상"]["count"] == 1


# --------------------------------------------------------------------------- #
# 구조 불변식
# --------------------------------------------------------------------------- #


def test_distribution_has_seven_keys() -> None:
    """span_distribution 은 정확히 7개 키."""
    r = wd.get_span_stats(_fixture_draws())
    assert len(r["span_distribution"]) == 7


def test_distribution_key_order() -> None:
    """키 순서는 정의 순서대로."""
    r = wd.get_span_stats(_fixture_draws())
    assert list(r["span_distribution"].keys()) == _SPAN_KEYS


def test_cell_has_count_and_pct() -> None:
    """각 셀은 count, pct 를 가진다."""
    r = wd.get_span_stats(_fixture_draws())
    for k in _SPAN_KEYS:
        cell = r["span_distribution"][k]
        assert "count" in cell
        assert "pct" in cell


def test_counts_sum_to_total() -> None:
    """분포 count 합계 == total_draws."""
    r = wd.get_span_stats(_fixture_draws())
    total = sum(r["span_distribution"][k]["count"] for k in _SPAN_KEYS)
    assert total == r["total_draws"]


def test_pct_rounded_two_decimals() -> None:
    """모든 pct 는 소수 2자리 이내 (3-draw → 33.33/66.67 형태)."""
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),       # span 5 → "10 이하"
        _make_draw(2, [1, 5, 10, 15, 18, 20]),   # span 19 → "11-20"
        _make_draw(3, [1, 8, 15, 20, 23, 26]),   # span 25 → "21-25"
    ]
    r = wd.get_span_stats(draws)
    assert r["span_distribution"]["10 이하"]["pct"] == 33.33
    assert r["span_distribution"]["11-20"]["pct"] == 33.33
    assert r["span_distribution"]["21-25"]["pct"] == 33.33


def test_avg_span_rounded() -> None:
    """avg_span 은 소수 2자리로 반올림 (span 5,19,26 → 50/3 = 16.67)."""
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),       # span 5
        _make_draw(2, [1, 5, 10, 15, 18, 20]),   # span 19
        _make_draw(3, [1, 8, 15, 20, 23, 27]),   # span 26
    ]
    r = wd.get_span_stats(draws)
    assert r["avg_span"] == 16.67


# --------------------------------------------------------------------------- #
# 5-회차 픽스처 (손계산, AC-33~44)
# --------------------------------------------------------------------------- #


def test_fixture_total() -> None:
    """total_draws == 5 (AC-33)."""
    assert wd.get_span_stats(_fixture_draws())["total_draws"] == 5


def test_fixture_avg() -> None:
    """avg_span == 26.0 (AC-34)."""
    assert wd.get_span_stats(_fixture_draws())["avg_span"] == 26.0


def test_fixture_most_common() -> None:
    """most_common_range == "10 이하" (모두 동률 → 첫 키) (AC-35)."""
    assert wd.get_span_stats(_fixture_draws())["most_common_range"] == "10 이하"


def test_fixture_narrow_pct() -> None:
    """narrow_pct == 40.0 (span≤20: D1, D2) (AC-36)."""
    assert wd.get_span_stats(_fixture_draws())["narrow_pct"] == 40.0


def test_fixture_wide_pct() -> None:
    """wide_pct == 40.0 (span≥36: D4, D5) (AC-37)."""
    assert wd.get_span_stats(_fixture_draws())["wide_pct"] == 40.0


def test_fixture_distribution_counts() -> None:
    """분포 count/pct 손계산 일치 (AC-38~44)."""
    dist = wd.get_span_stats(_fixture_draws())["span_distribution"]
    assert dist["10 이하"] == {"count": 1, "pct": 20.0}
    assert dist["11-20"] == {"count": 1, "pct": 20.0}
    assert dist["21-25"] == {"count": 1, "pct": 20.0}
    assert dist["26-30"] == {"count": 0, "pct": 0.0}
    assert dist["31-35"] == {"count": 0, "pct": 0.0}
    assert dist["36-40"] == {"count": 1, "pct": 20.0}
    assert dist["41 이상"] == {"count": 1, "pct": 20.0}


# --------------------------------------------------------------------------- #
# 요약 지표 의미
# --------------------------------------------------------------------------- #


def test_most_common_tie_break_first_key() -> None:
    """동률 시 키 정의 순서상 앞선 값 선택."""
    # "21-25"(1) vs "41 이상"(1) 동률 → 앞선 "21-25"
    draws = [
        _make_draw(1, [1, 8, 15, 20, 23, 26]),    # span 25 → "21-25"
        _make_draw(2, [2, 12, 22, 30, 38, 44]),   # span 42 → "41 이상"
    ]
    assert wd.get_span_stats(draws)["most_common_range"] == "21-25"


def test_narrow_pct_includes_boundary_20() -> None:
    """narrow_pct 는 span≤20 (경계 20 포함)."""
    # span 20 1건, span 21 1건 → narrow_pct = 50.0 (span20만)
    draws = [
        _make_draw(1, [1, 5, 10, 15, 18, 21]),    # span 20 → "11-20"
        _make_draw(2, [1, 8, 15, 20, 21, 22]),    # span 21 → "21-25"
    ]
    r = wd.get_span_stats(draws)
    assert r["narrow_pct"] == 50.0


def test_wide_pct_includes_boundary_36() -> None:
    """wide_pct 는 span≥36 (경계 36 포함)."""
    # span 35 1건, span 36 1건 → wide_pct = 50.0 (span36만)
    draws = [
        _make_draw(1, [1, 10, 20, 30, 34, 36]),   # span 35 → "31-35"
        _make_draw(2, [1, 10, 20, 30, 35, 37]),   # span 36 → "36-40"
    ]
    r = wd.get_span_stats(draws)
    assert r["wide_pct"] == 50.0


# --------------------------------------------------------------------------- #
# 캐시 / 무효화 (AC-48~49)
# --------------------------------------------------------------------------- #


def test_cache_returns_same_object() -> None:
    """동일 길이 재호출 시 캐시된 동일 객체 반환 (AC-48)."""
    draws = _fixture_draws()
    r1 = wd.get_span_stats(draws)
    r2 = wd.get_span_stats(draws)
    assert r1 is r2


def test_invalidate_cache_clears() -> None:
    """invalidate_cache() 가 _span_cache 를 비운다 (AC-49)."""
    wd.get_span_stats(_fixture_draws())
    assert len(wd._span_cache) > 0
    wd.invalidate_cache()
    assert len(wd._span_cache) == 0


# --------------------------------------------------------------------------- #
# API / 페이지 (AC-50~51)
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/span → 200 + 키 구조 (AC-50)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/span")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 5
    for key in (
        "total_draws",
        "avg_span",
        "most_common_range",
        "narrow_pct",
        "wide_pct",
        "span_distribution",
    ):
        assert key in body
    assert set(body["span_distribution"].keys()) == set(_SPAN_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/span 은 데이터가 없어도 200 (AC-50)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/span")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/span → 200(HTML) (AC-51)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/span")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/span 은 데이터가 없어도 200 (AC-51)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/span")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
