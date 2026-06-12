"""SPEC-LOTTO-072: 끝자리 유니크 수 분포 분석 테스트.

데이터 계층(get_last_digit_unique_stats), 캐시(_last_digit_unique_cache),
페이지/API 라우트를 RED-GREEN-REFACTOR로 검증한다.

유니크 끝자리 개수(unique last-digit count):
- 한 회차 본번호 6개(보너스 제외)의 끝자리(n % 10) 집합 크기.
- 값의 범위는 1(모두 같은 끝자리)~6(모두 다른 끝자리).
- 분포 키는 "1".."6" 6개 고정 버킷(미관측은 zero-fill).
- avg_unique_count / most_common_count(동률 시 작은 값) / all_different_pct(==6 비율).

SPEC-055(끝자리별 출현 빈도)·SPEC-063(끝자리 합계)과는 계산 대상이 다른 별개 기능.
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


_UNIQUE_DIGIT_KEYS = ["1", "2", "3", "4", "5", "6"]


def _mk(no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    bonus 기본값 7은 본번호와 끝자리가 같아도 유니크 집계에서 제외됨을 검증하기 위함이다.
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# 손계산 검증용 4개 회차 픽스처 (acceptance.md 표 그대로).
# D1 [3,7,12,25,38,44] → {2,3,4,5,7,8} → 6 (모두 다름)
# D2 [3,13,23,31,42,5] → {1,2,3,5}     → 4
# D3 [1,11,21,31,41,45]→ {1,5}         → 2
# D4 [2,12,22,32,42,5] → {2,5}         → 2
def _fixture_draws() -> list[DrawResult]:
    return [
        _mk(1, [3, 7, 12, 25, 38, 44]),
        _mk(2, [3, 13, 23, 31, 42, 5]),
        _mk(3, [1, 11, 21, 31, 41, 45]),
        _mk(4, [2, 12, 22, 32, 42, 5]),
    ]


# --------------------------------------------------------------------------- #
# 유니크 끝자리 개수 계산 정확성 (AC-072-001 ~ 004)
# --------------------------------------------------------------------------- #


def test_unique_count_all_different() -> None:
    """AC-072-001: [3,7,12,25,38,44] → 끝자리 {2,3,4,5,7,8} → 6종."""
    draws = [_mk(1, [3, 7, 12, 25, 38, 44])]
    stats = wd.get_last_digit_unique_stats(draws)
    assert stats["unique_distribution"]["6"]["count"] == 1
    assert stats["avg_unique_count"] == 6.0


def test_unique_count_four() -> None:
    """AC-072-002: [3,13,23,31,42,5] → 끝자리 {1,2,3,5} → 4종."""
    draws = [_mk(1, [3, 13, 23, 31, 42, 5])]
    stats = wd.get_last_digit_unique_stats(draws)
    assert stats["unique_distribution"]["4"]["count"] == 1
    assert stats["avg_unique_count"] == 4.0


def test_unique_count_two() -> None:
    """AC-072-003: [1,11,21,31,41,45] → 끝자리 {1,5} → 2종."""
    draws = [_mk(1, [1, 11, 21, 31, 41, 45])]
    stats = wd.get_last_digit_unique_stats(draws)
    assert stats["unique_distribution"]["2"]["count"] == 1
    assert stats["avg_unique_count"] == 2.0


def test_unique_count_one_boundary_min() -> None:
    """AC-072-004: 6개 끝자리가 모두 동일하면 1종(경계 최솟값)."""
    # [5,15,25,35,45,5] → 끝자리 모두 5 → {5} → 1종
    draws = [_mk(1, [5, 15, 25, 35, 45, 5])]
    stats = wd.get_last_digit_unique_stats(draws)
    assert stats["unique_distribution"]["1"]["count"] == 1
    assert stats["avg_unique_count"] == 1.0


# --------------------------------------------------------------------------- #
# 응답 구조 및 분포 (AC-072-006 ~ 010)
# --------------------------------------------------------------------------- #


def test_response_has_all_top_level_keys() -> None:
    """AC-072-006: 반환 dict는 5개 최상위 키를 모두 포함한다."""
    stats = wd.get_last_digit_unique_stats(_fixture_draws())
    for key in (
        "total_draws",
        "avg_unique_count",
        "most_common_count",
        "all_different_pct",
        "unique_distribution",
    ):
        assert key in stats


def test_distribution_always_has_six_keys() -> None:
    """AC-072-007: unique_distribution은 항상 '1'..'6' 6개 키를 포함한다."""
    stats = wd.get_last_digit_unique_stats(_fixture_draws())
    assert set(stats["unique_distribution"].keys()) == set(_UNIQUE_DIGIT_KEYS)


def test_distribution_cells_have_count_and_pct() -> None:
    """AC-072-008: 각 분포 항목은 count·pct 두 키를 가진다."""
    stats = wd.get_last_digit_unique_stats(_fixture_draws())
    for key in _UNIQUE_DIGIT_KEYS:
        cell = stats["unique_distribution"][key]
        assert "count" in cell
        assert "pct" in cell


def test_distribution_counts_match_fixture() -> None:
    """AC-072-009: D1~D4 분포 count는 {"1":0,"2":2,"3":0,"4":1,"5":0,"6":1}."""
    stats = wd.get_last_digit_unique_stats(_fixture_draws())
    dist = stats["unique_distribution"]
    assert dist["1"]["count"] == 0
    assert dist["2"]["count"] == 2
    assert dist["3"]["count"] == 0
    assert dist["4"]["count"] == 1
    assert dist["5"]["count"] == 0
    assert dist["6"]["count"] == 1


def test_bucket_counts_sum_to_total() -> None:
    """AC-072-010: 모든 버킷 count 합은 total_draws와 같다."""
    stats = wd.get_last_digit_unique_stats(_fixture_draws())
    total = sum(c["count"] for c in stats["unique_distribution"].values())
    assert total == stats["total_draws"] == 4


def test_distribution_pct_values() -> None:
    """AC-072-009/015: D1~D4 pct는 '2'=50.0, '4'=25.0, '6'=25.0, 나머지 0.0."""
    stats = wd.get_last_digit_unique_stats(_fixture_draws())
    dist = stats["unique_distribution"]
    assert dist["2"]["pct"] == 50.0
    assert dist["4"]["pct"] == 25.0
    assert dist["6"]["pct"] == 25.0
    assert dist["1"]["pct"] == 0.0
    assert dist["3"]["pct"] == 0.0
    assert dist["5"]["pct"] == 0.0


# --------------------------------------------------------------------------- #
# 파생 지표 (AC-072-005, 011 ~ 015)
# --------------------------------------------------------------------------- #


def test_avg_unique_count_fixture() -> None:
    """AC-072-005: D1~D4 → (6+4+2+2)/4 = 3.5."""
    stats = wd.get_last_digit_unique_stats(_fixture_draws())
    assert stats["avg_unique_count"] == 3.5


def test_most_common_count_fixture() -> None:
    """AC-072-011: D1~D4 → 키 '2'가 2회로 최다 → most_common_count == 2."""
    stats = wd.get_last_digit_unique_stats(_fixture_draws())
    assert stats["most_common_count"] == 2


def test_most_common_count_tie_smaller_wins() -> None:
    """AC-072-012: 동률 시 더 작은 유니크 값이 선택된다(고정 키 순서 선두 우선)."""
    # unique=2 1건, unique=6 1건 → 둘 다 count 1 동률 → 작은 2가 이긴다.
    draws = [
        _mk(1, [1, 11, 21, 31, 41, 45]),  # 2종
        _mk(2, [3, 7, 12, 25, 38, 44]),   # 6종
    ]
    stats = wd.get_last_digit_unique_stats(draws)
    assert stats["most_common_count"] == 2


def test_all_different_pct_fixture() -> None:
    """AC-072-013: D1~D4 → unique==6 인 D1 1건 / 4건 → 25.0."""
    stats = wd.get_last_digit_unique_stats(_fixture_draws())
    assert stats["all_different_pct"] == 25.0


def test_all_different_pct_zero_when_none() -> None:
    """AC-072-014: 모든 회차 unique<6 이면 all_different_pct == 0.0."""
    draws = [
        _mk(1, [1, 11, 21, 31, 41, 45]),  # 2종
        _mk(2, [3, 13, 23, 31, 42, 5]),   # 4종
    ]
    stats = wd.get_last_digit_unique_stats(draws)
    assert stats["all_different_pct"] == 0.0


def test_all_different_pct_hundred() -> None:
    """모든 회차 unique==6 이면 all_different_pct == 100.0."""
    draws = [
        _mk(1, [3, 7, 12, 25, 38, 44]),  # 6종
        _mk(2, [2, 3, 4, 5, 6, 17]),     # {2,3,4,5,6,7} → 6종
    ]
    stats = wd.get_last_digit_unique_stats(draws)
    assert stats["all_different_pct"] == 100.0


def test_numeric_fields_rounded_two_decimals() -> None:
    """AC-072-015: avg_unique_count·all_different_pct·각 pct는 소수 2자리 반올림."""
    # 3개 회차 → pct는 33.33.. 형태로 반올림 검증.
    draws = [
        _mk(1, [3, 7, 12, 25, 38, 44]),   # 6종
        _mk(2, [3, 13, 23, 31, 42, 5]),   # 4종
        _mk(3, [1, 11, 21, 31, 41, 45]),  # 2종
    ]
    stats = wd.get_last_digit_unique_stats(draws)
    # avg = (6+4+2)/3 = 4.0
    assert stats["avg_unique_count"] == 4.0
    assert stats["all_different_pct"] == 33.33
    assert stats["unique_distribution"]["6"]["pct"] == 33.33


# --------------------------------------------------------------------------- #
# 경계 및 예외 (AC-072-016, 017)
# --------------------------------------------------------------------------- #


def test_empty_draws_returns_consistent_zero_structure() -> None:
    """AC-072-016: 빈 draws → 예외 없이 일관된 zero 구조."""
    stats = wd.get_last_digit_unique_stats([])
    assert stats["total_draws"] == 0
    assert stats["avg_unique_count"] == 0.0
    assert stats["most_common_count"] == 1
    assert stats["all_different_pct"] == 0.0
    assert set(stats["unique_distribution"].keys()) == set(_UNIQUE_DIGIT_KEYS)
    for key in _UNIQUE_DIGIT_KEYS:
        assert stats["unique_distribution"][key]["count"] == 0
        assert stats["unique_distribution"][key]["pct"] == 0.0


def test_none_draws_returns_zero_structure() -> None:
    """None 입력도 빈 입력과 동일하게 처리된다(예외 없음)."""
    stats = wd.get_last_digit_unique_stats(None)
    assert stats["total_draws"] == 0
    assert stats["most_common_count"] == 1


def test_bonus_excluded_from_unique_count() -> None:
    """AC-072-017: 보너스 번호는 유니크 끝자리 계산에 포함되지 않는다."""
    # 본번호 [3,7,12,25,38,44] → 6종. bonus=44(끝자리 4, 본번호와 겹침)이어도
    # 본번호 6개만으로 6종이 유지되어야 한다.
    draws = [_mk(1, [3, 7, 12, 25, 38, 44], bonus=14)]
    stats = wd.get_last_digit_unique_stats(draws)
    assert stats["unique_distribution"]["6"]["count"] == 1
    assert stats["avg_unique_count"] == 6.0


def test_single_draw() -> None:
    """단일 회차도 정상 집계된다."""
    stats = wd.get_last_digit_unique_stats([_mk(1, [3, 13, 23, 31, 42, 5])])
    assert stats["total_draws"] == 1
    assert stats["most_common_count"] == 4
    assert stats["unique_distribution"]["4"]["count"] == 1


# --------------------------------------------------------------------------- #
# 캐시 동작 (AC-072-020)
# --------------------------------------------------------------------------- #


def test_cache_populated_and_hit() -> None:
    """동일 입력 재호출 시 캐시된 동일 객체를 반환한다."""
    draws = _fixture_draws()
    first = wd.get_last_digit_unique_stats(draws)
    second = wd.get_last_digit_unique_stats(draws)
    assert first is second


def test_cache_invalidated() -> None:
    """AC-072-020: invalidate_cache 후에는 새 결과 객체를 생성한다."""
    draws = _fixture_draws()
    first = wd.get_last_digit_unique_stats(draws)
    wd.invalidate_cache()
    second = wd.get_last_digit_unique_stats(draws)
    assert first is not second
    assert first == second


def test_cache_empty_key_separate() -> None:
    """빈 입력도 캐시되며 비어있지 않은 입력과 충돌하지 않는다."""
    empty = wd.get_last_digit_unique_stats([])
    nonempty = wd.get_last_digit_unique_stats(_fixture_draws())
    assert empty["total_draws"] == 0
    assert nonempty["total_draws"] == 4


def test_invalidate_cache_clears_unique_cache() -> None:
    """invalidate_cache가 _last_digit_unique_cache를 비운다."""
    wd.get_last_digit_unique_stats(_fixture_draws())
    assert len(wd._last_digit_unique_cache) > 0
    wd.invalidate_cache()
    assert len(wd._last_digit_unique_cache) == 0


# --------------------------------------------------------------------------- #
# 라우트 (AC-072-018, 019)
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """AC-072-018: GET /api/stats/last_digit_unique → 200 + 키 구조."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/last_digit_unique")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "avg_unique_count",
        "most_common_count",
        "all_different_pct",
        "unique_distribution",
    ):
        assert key in body
    assert set(body["unique_distribution"].keys()) == set(_UNIQUE_DIGIT_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/last_digit_unique 은 데이터가 없어도 200을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/last_digit_unique")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """AC-072-019: GET /stats/last-digit-unique → 200(HTML, "끝자리유니크" 포함)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/last-digit-unique")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "끝자리유니크" in resp.text


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/last-digit-unique 은 데이터가 없어도 200(빈 상태)을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/last-digit-unique")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 실데이터 스모크
# --------------------------------------------------------------------------- #


def test_real_data_smoke() -> None:
    """실제 데이터가 있으면 total_draws>0, avg_unique_count는 1~6 범위."""
    draws = wd.get_draws()
    if not draws:
        return  # 데이터 미수집 환경에서는 스킵
    result = wd.get_last_digit_unique_stats(draws)
    assert result["total_draws"] > 0
    assert 1.0 <= result["avg_unique_count"] <= 6.0
    assert 1 <= result["most_common_count"] <= 6
