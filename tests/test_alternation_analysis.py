"""SPEC-LOTTO-094: 홀짝 교차 패턴 분포 분석 테스트.

각 회차 본번호 6개(보너스 제외)를 오름차순 정렬한 뒤 인접 쌍의 홀짝 교차 횟수
(0~5)를 세어 교차 단계("교차0"~"교차5", 6개)로 분류한다. SPEC-084
(get_parity_transition_stats: 정수 키 + 고빈도(>=4) 비율)와는 출력 구조와 요약
지표(full_alternation_pct = 교차5 비율)가 다른 별개 지표다.
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

_ALTERNATION_KEYS = ["교차0", "교차1", "교차2", "교차3", "교차4", "교차5"]


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

    D1 [1,2,3,4,5,6]   → O,E,O,E,O,E → 5회 교차 → "교차5"
    D2 [1,3,5,7,9,11]  → 전부 홀수    → 0회 교차 → "교차0"
    D3 [2,4,6,8,10,12] → 전부 짝수    → 0회 교차 → "교차0"
    D4 [1,2,3,5,7,9]   → O,E,O,O,O,O → 2회 교차 → "교차2"
    D5 [2,4,6,7,9,11]  → E,E,E,O,O,O → 1회 교차 → "교차1"

    avg_alternation = (5+0+0+2+1)/5 = 1.6
    most_common_level = "교차0" (count=2)
    full_alternation_pct = 1/5*100 = 20.0  ("교차5": D1)
    distribution: 교차0=2, 교차1=1, 교차2=1, 교차3=0, 교차4=0, 교차5=1
    """
    return [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),
        _make_draw(2, [1, 3, 5, 7, 9, 11]),
        _make_draw(3, [2, 4, 6, 8, 10, 12]),
        _make_draw(4, [1, 2, 3, 5, 7, 9]),
        _make_draw(5, [2, 4, 6, 7, 9, 11]),
    ]


# --------------------------------------------------------------------------- #
# 헬퍼 _count_alternations
# --------------------------------------------------------------------------- #


def test_count_all_odd_zero() -> None:
    """[1,3,5,7,9,11] 전부 홀수 → 0 (AC-01)."""
    assert wd._count_alternations([1, 3, 5, 7, 9, 11]) == 0


def test_count_all_even_zero() -> None:
    """[2,4,6,8,10,12] 전부 짝수 → 0 (AC-02)."""
    assert wd._count_alternations([2, 4, 6, 8, 10, 12]) == 0


def test_count_full_alternation() -> None:
    """[1,2,3,4,5,6] → 5 완전 교차 (AC-03)."""
    assert wd._count_alternations([1, 2, 3, 4, 5, 6]) == 5


def test_count_sorts_input() -> None:
    """[2,1,4,3,6,5] 정렬 후 [1,2,3,4,5,6] → 5 (AC-04)."""
    assert wd._count_alternations([2, 1, 4, 3, 6, 5]) == 5


def test_count_two() -> None:
    """[1,2,3,5,7,9] → 2 (AC-05)."""
    assert wd._count_alternations([1, 2, 3, 5, 7, 9]) == 2


def test_count_one() -> None:
    """[2,4,6,7,9,11] → 1 (AC-06)."""
    assert wd._count_alternations([2, 4, 6, 7, 9, 11]) == 1


# --------------------------------------------------------------------------- #
# 빈 데이터
# --------------------------------------------------------------------------- #


def test_empty_draws_zeros() -> None:
    """빈 draws → 0/기본값 (AC-07)."""
    r = wd.get_alternation_stats([])
    assert r["total_draws"] == 0
    assert r["avg_alternation"] == 0.0
    assert r["most_common_level"] == "교차0"
    assert r["full_alternation_pct"] == 0.0


def test_empty_draws_none() -> None:
    """None draws → 빈 구조, 6개 키 (AC-08)."""
    r = wd.get_alternation_stats(None)
    assert r["total_draws"] == 0
    assert r["most_common_level"] == "교차0"
    assert len(r["alternation_distribution"]) == 6


def test_empty_draws_all_keys_zero() -> None:
    """빈 draws → 6개 키 모두 count=0, pct=0.0, 키 순서 일치 (AC-09, AC-10)."""
    r = wd.get_alternation_stats([])
    dist = r["alternation_distribution"]
    assert list(dist.keys()) == _ALTERNATION_KEYS
    for k in _ALTERNATION_KEYS:
        assert dist[k]["count"] == 0
        assert dist[k]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 단일 회차 분류 (집계 경로)
# --------------------------------------------------------------------------- #


def test_single_full_alternation() -> None:
    """[1,2,3,4,5,6] → 교차5 (AC-03 집계 경로)."""
    r = wd.get_alternation_stats([_make_draw(1, [1, 2, 3, 4, 5, 6])])
    assert r["alternation_distribution"]["교차5"]["count"] == 1
    assert r["avg_alternation"] == 5.0
    assert r["full_alternation_pct"] == 100.0


def test_single_all_odd() -> None:
    """[1,3,5,7,9,11] → 교차0 (AC-01 집계 경로)."""
    r = wd.get_alternation_stats([_make_draw(1, [1, 3, 5, 7, 9, 11])])
    assert r["alternation_distribution"]["교차0"]["count"] == 1
    assert r["most_common_level"] == "교차0"


def test_single_all_even() -> None:
    """[2,4,6,8,10,12] → 교차0 (AC-02 집계 경로)."""
    r = wd.get_alternation_stats([_make_draw(1, [2, 4, 6, 8, 10, 12])])
    assert r["alternation_distribution"]["교차0"]["count"] == 1


def test_single_level_two() -> None:
    """[1,2,3,5,7,9] → 교차2 (AC-05 집계 경로)."""
    r = wd.get_alternation_stats([_make_draw(1, [1, 2, 3, 5, 7, 9])])
    assert r["alternation_distribution"]["교차2"]["count"] == 1


def test_single_level_one() -> None:
    """[2,4,6,7,9,11] → 교차1 (AC-06 집계 경로)."""
    r = wd.get_alternation_stats([_make_draw(1, [2, 4, 6, 7, 9, 11])])
    assert r["alternation_distribution"]["교차1"]["count"] == 1


def test_aggregation_sorts_input() -> None:
    """정렬되지 않은 입력도 집계 경로에서 정렬된다 (AC-04 집계 경로)."""
    r = wd.get_alternation_stats([_make_draw(1, [2, 1, 4, 3, 6, 5])])
    assert r["alternation_distribution"]["교차5"]["count"] == 1


# --------------------------------------------------------------------------- #
# 구조 불변식
# --------------------------------------------------------------------------- #


def test_distribution_has_six_keys() -> None:
    """alternation_distribution 은 정확히 6개 키 (AC-09)."""
    r = wd.get_alternation_stats(_fixture_draws())
    assert len(r["alternation_distribution"]) == 6


def test_distribution_key_order() -> None:
    """키 순서는 교차0~교차5 (AC-10)."""
    r = wd.get_alternation_stats(_fixture_draws())
    assert list(r["alternation_distribution"].keys()) == _ALTERNATION_KEYS


def test_cell_has_count_and_pct() -> None:
    """각 셀은 count, pct 를 가진다 (AC-11)."""
    r = wd.get_alternation_stats(_fixture_draws())
    for k in _ALTERNATION_KEYS:
        cell = r["alternation_distribution"][k]
        assert "count" in cell
        assert "pct" in cell


def test_counts_sum_to_total() -> None:
    """분포 count 합계 == total_draws (AC-12)."""
    r = wd.get_alternation_stats(_fixture_draws())
    total = sum(r["alternation_distribution"][k]["count"] for k in _ALTERNATION_KEYS)
    assert total == r["total_draws"]


def test_pct_rounded_two_decimals() -> None:
    """모든 pct 는 소수 2자리 이내 (AC-13)."""
    # 3-draw → pct 가 33.33 형태로 반올림되는지 확인
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),
        _make_draw(2, [1, 3, 5, 7, 9, 11]),
        _make_draw(3, [2, 4, 6, 8, 10, 12]),
    ]
    r = wd.get_alternation_stats(draws)
    assert r["alternation_distribution"]["교차0"]["pct"] == 66.67
    assert r["alternation_distribution"]["교차5"]["pct"] == 33.33


def test_avg_alternation_rounded() -> None:
    """avg_alternation 은 소수 2자리로 반올림 (AC-14)."""
    # 3-draw alt=5,0,0 → 5/3 = 1.6666... → 1.67
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),
        _make_draw(2, [1, 3, 5, 7, 9, 11]),
        _make_draw(3, [2, 4, 6, 8, 10, 12]),
    ]
    r = wd.get_alternation_stats(draws)
    assert r["avg_alternation"] == 1.67


# --------------------------------------------------------------------------- #
# 5-회차 픽스처 (손계산)
# --------------------------------------------------------------------------- #


def test_fixture_total() -> None:
    """total_draws == 5 (AC-15)."""
    assert wd.get_alternation_stats(_fixture_draws())["total_draws"] == 5


def test_fixture_avg() -> None:
    """avg_alternation == 1.6 (AC-16)."""
    assert wd.get_alternation_stats(_fixture_draws())["avg_alternation"] == 1.6


def test_fixture_most_common() -> None:
    """most_common_level == "교차0" (AC-17)."""
    assert wd.get_alternation_stats(_fixture_draws())["most_common_level"] == "교차0"


def test_fixture_full_alternation_pct() -> None:
    """full_alternation_pct == 20.0 (AC-18)."""
    assert wd.get_alternation_stats(_fixture_draws())["full_alternation_pct"] == 20.0


def test_fixture_distribution_counts() -> None:
    """분포 count/pct 손계산 일치 (AC-19~AC-24)."""
    dist = wd.get_alternation_stats(_fixture_draws())["alternation_distribution"]
    assert dist["교차0"] == {"count": 2, "pct": 40.0}
    assert dist["교차1"] == {"count": 1, "pct": 20.0}
    assert dist["교차2"] == {"count": 1, "pct": 20.0}
    assert dist["교차3"] == {"count": 0, "pct": 0.0}
    assert dist["교차4"] == {"count": 0, "pct": 0.0}
    assert dist["교차5"] == {"count": 1, "pct": 20.0}


# --------------------------------------------------------------------------- #
# 요약 지표 의미
# --------------------------------------------------------------------------- #


def test_most_common_tie_break_first_key() -> None:
    """동률 시 키 정의 순서상 앞선 값 선택 (AC-25)."""
    # 교차0(1) vs 교차5(1) 동률 → 앞선 "교차0"
    draws = [
        _make_draw(1, [1, 3, 5, 7, 9, 11]),  # 교차0
        _make_draw(2, [1, 2, 3, 4, 5, 6]),   # 교차5
    ]
    assert wd.get_alternation_stats(draws)["most_common_level"] == "교차0"


def test_full_alternation_pct_excludes_level_four() -> None:
    """full_alternation_pct 는 교차5 만의 비율, 교차4 미포함 (AC-26)."""
    # 교차4 1건, 교차5 1건 → full_alternation_pct = 50.0 (교차5 1건만)
    # [1,2,3,4,5,7] → O,E,O,E,O,O → 4회 교차
    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 7]),   # 교차4
        _make_draw(2, [1, 2, 3, 4, 5, 6]),   # 교차5
    ]
    r = wd.get_alternation_stats(draws)
    assert r["alternation_distribution"]["교차4"]["count"] == 1
    assert r["full_alternation_pct"] == 50.0


# --------------------------------------------------------------------------- #
# 캐시 / 무효화
# --------------------------------------------------------------------------- #


def test_cache_returns_same_object() -> None:
    """동일 길이 재호출 시 캐시된 동일 객체 반환 (AC-27)."""
    draws = _fixture_draws()
    r1 = wd.get_alternation_stats(draws)
    r2 = wd.get_alternation_stats(draws)
    assert r1 is r2


def test_invalidate_cache_clears() -> None:
    """invalidate_cache() 가 _alternation_cache 를 비운다 (AC-28)."""
    wd.get_alternation_stats(_fixture_draws())
    assert len(wd._alternation_cache) > 0
    wd.invalidate_cache()
    assert len(wd._alternation_cache) == 0


# --------------------------------------------------------------------------- #
# API / 페이지
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/alternation → 200 + 키 구조 (AC-29)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/alternation")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 5
    for key in (
        "total_draws",
        "avg_alternation",
        "most_common_level",
        "full_alternation_pct",
        "alternation_distribution",
    ):
        assert key in body
    assert set(body["alternation_distribution"].keys()) == set(_ALTERNATION_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/alternation 은 데이터가 없어도 200 (AC-29)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/alternation")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/alternation → 200(HTML) (AC-30)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/alternation")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/alternation 은 데이터가 없어도 200 (AC-30)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/alternation")
    assert resp.status_code == 200
