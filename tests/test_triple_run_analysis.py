"""SPEC-LOTTO-078: 3연속 이상 번호 포함 분포 분석 테스트.

데이터 계층(get_triple_run_stats), 헬퍼(_count_triple_runs/_max_run_length),
캐시(_triple_run_cache), 페이지/API 라우트를 RED-GREEN-REFACTOR로 검증한다.

triple run(3연속 이상 묶음):
- 한 회차 본번호 6개(보너스 제외)에서 3개 이상 연속한 정수 그룹.
- 6개 번호이므로 묶음 수의 범위는 0~2(예: 3+3=6).
- 분포 키는 "0","1","2" 3개 고정 버킷(미관측은 zero-fill).
- has_triple_pct(>=1 묶음 비율) / most_common_group_count(동률 시 작은 값)
  / avg_max_run(회차별 최대 연속 길이 평균).

SPEC-062(연속 패턴)·SPEC-069(연속 쌍)와는 계산 대상이 다른 별개 기능이다.
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


_TRIPLE_RUN_KEYS = ["0", "1", "2"]


def _mk(no: int, nums: list[int], bonus: int = 45) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    bonus 기본값 45는 본번호 연속 묶음 계산에 포함되지 않아야 함을 별도 검증한다.
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# 손계산 검증용 4개 회차 픽스처.
# D1 [1,2,3,4,5,6]       → 묶음 1(전체 6연속)         → max_run 6
# D2 [1,2,5,6,7,10]      → 묶음 1({5,6,7})            → max_run 3
# D3 [1,5,10,20,30,40]   → 묶음 0(모두 고립)          → max_run 1
# D4 [1,2,3,7,8,9]       → 묶음 2({1,2,3},{7,8,9})    → max_run 3
def _fixture_draws() -> list[DrawResult]:
    return [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [1, 2, 5, 6, 7, 10]),
        _mk(3, [1, 5, 10, 20, 30, 40]),
        _mk(4, [1, 2, 3, 7, 8, 9]),
    ]


# --------------------------------------------------------------------------- #
# 헬퍼 함수 (_count_triple_runs / _max_run_length)
# --------------------------------------------------------------------------- #


def test_count_triple_runs_two_groups() -> None:
    """[1,2,3,7,8,9] → {1,2,3}, {7,8,9} 2개 묶음 (AC-24)."""
    assert wd._count_triple_runs([1, 2, 3, 7, 8, 9]) == 2


def test_count_triple_runs_single_full_run() -> None:
    """[1,2,3,4,5,6] → 전체가 1개 묶음."""
    assert wd._count_triple_runs([1, 2, 3, 4, 5, 6]) == 1


def test_count_triple_runs_pair_not_counted() -> None:
    """[3,4,10,20,30,40] → {3,4}는 2연속이므로 묶음 0 (AC-27)."""
    assert wd._count_triple_runs([3, 4, 10, 20, 30, 40]) == 0


def test_count_triple_runs_exactly_three_is_one() -> None:
    """정확히 3개 연속(경계)은 1개 묶음으로 인정 (AC-10)."""
    assert wd._count_triple_runs([5, 6, 7, 12, 20, 30]) == 1


def test_count_triple_runs_handles_unsorted_input() -> None:
    """정렬되지 않은 입력도 정렬 후 올바르게 계산한다."""
    assert wd._count_triple_runs([9, 7, 8, 3, 1, 2]) == 2


def test_max_run_length_six() -> None:
    """[1,2,3,4,5,6] → 최대 연속 길이 6 (AC-25)."""
    assert wd._max_run_length([1, 2, 3, 4, 5, 6]) == 6


def test_max_run_length_one() -> None:
    """[1,5,10,20,30,40] → 모두 고립이므로 최대 길이 1 (AC-26)."""
    assert wd._max_run_length([1, 5, 10, 20, 30, 40]) == 1


def test_max_run_length_pair() -> None:
    """[3,4,10,20,30,40] → {3,4}만 연속이므로 최대 길이 2."""
    assert wd._max_run_length([3, 4, 10, 20, 30, 40]) == 2


# --------------------------------------------------------------------------- #
# 단일 회차 묶음 수 분류
# --------------------------------------------------------------------------- #


def test_full_consecutive_one_group() -> None:
    """[1,2,3,4,5,6] → 묶음 1 (AC-05)."""
    stats = wd.get_triple_run_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert stats["triple_distribution"]["1"]["count"] == 1


def test_one_inner_group() -> None:
    """[1,2,5,6,7,10] → {5,6,7} 묶음 1 (AC-06)."""
    stats = wd.get_triple_run_stats([_mk(1, [1, 2, 5, 6, 7, 10])])
    assert stats["triple_distribution"]["1"]["count"] == 1


def test_no_group_all_isolated() -> None:
    """[1,5,10,20,30,40] → 묶음 0 (AC-07)."""
    stats = wd.get_triple_run_stats([_mk(1, [1, 5, 10, 20, 30, 40])])
    assert stats["triple_distribution"]["0"]["count"] == 1


def test_two_groups() -> None:
    """[1,2,3,7,8,9] → 묶음 2 (AC-08)."""
    stats = wd.get_triple_run_stats([_mk(1, [1, 2, 3, 7, 8, 9])])
    assert stats["triple_distribution"]["2"]["count"] == 1


def test_pair_only_no_group() -> None:
    """[3,4,10,20,30,40] → {3,4}는 2연속이라 묶음 0 (AC-09)."""
    stats = wd.get_triple_run_stats([_mk(1, [3, 4, 10, 20, 30, 40])])
    assert stats["triple_distribution"]["0"]["count"] == 1


def test_bonus_excluded() -> None:
    """보너스 번호는 묶음 계산에 포함되지 않는다 (REQ-TR-030)."""
    # 본번호 [1,2,5,6,7,10] → 묶음 1. bonus=3·4 어떤 값이어도 동일해야 한다.
    stats = wd.get_triple_run_stats([_mk(1, [1, 2, 5, 6, 7, 10], bonus=3)])
    assert stats["triple_distribution"]["1"]["count"] == 1


# --------------------------------------------------------------------------- #
# 응답 구조 및 분포
# --------------------------------------------------------------------------- #


def test_response_has_all_top_level_keys() -> None:
    """반환 dict는 5개 최상위 키를 모두 포함한다."""
    stats = wd.get_triple_run_stats(_fixture_draws())
    for key in (
        "total_draws",
        "has_triple_pct",
        "most_common_group_count",
        "avg_max_run",
        "triple_distribution",
    ):
        assert key in stats


def test_distribution_always_has_three_keys() -> None:
    """triple_distribution은 항상 '0','1','2' 3개 키만 포함한다 (AC-11)."""
    stats = wd.get_triple_run_stats(_fixture_draws())
    assert set(stats["triple_distribution"].keys()) == set(_TRIPLE_RUN_KEYS)


def test_distribution_cells_have_count_and_pct() -> None:
    """각 분포 항목은 count·pct 두 키를 가진다 (REQ-TR-002)."""
    stats = wd.get_triple_run_stats(_fixture_draws())
    for key in _TRIPLE_RUN_KEYS:
        cell = stats["triple_distribution"][key]
        assert "count" in cell
        assert "pct" in cell


def test_distribution_counts_match_fixture() -> None:
    """D1~D4 분포 count는 '0'=1, '1'=2, '2'=1 (AC-14)."""
    dist = wd.get_triple_run_stats(_fixture_draws())["triple_distribution"]
    assert dist["0"]["count"] == 1
    assert dist["1"]["count"] == 2
    assert dist["2"]["count"] == 1


def test_bucket_counts_sum_to_total() -> None:
    """모든 버킷 count 합은 total_draws와 같다 (AC-12)."""
    stats = wd.get_triple_run_stats(_fixture_draws())
    total = sum(c["count"] for c in stats["triple_distribution"].values())
    assert total == stats["total_draws"] == 4


def test_distribution_pct_values() -> None:
    """D1~D4 pct는 '0'=25.0, '1'=50.0, '2'=25.0 (AC-15)."""
    dist = wd.get_triple_run_stats(_fixture_draws())["triple_distribution"]
    assert dist["0"]["pct"] == 25.0
    assert dist["1"]["pct"] == 50.0
    assert dist["2"]["pct"] == 25.0


# --------------------------------------------------------------------------- #
# 파생 지표
# --------------------------------------------------------------------------- #


def test_has_triple_pct_fixture() -> None:
    """D1~D4 → 묶음>=1 인 D1·D2·D4 3건 / 4건 → 75.0 (AC-16)."""
    stats = wd.get_triple_run_stats(_fixture_draws())
    assert stats["has_triple_pct"] == 75.0


def test_most_common_group_count_fixture() -> None:
    """D1~D4 → 묶음 1이 2회로 최빈 → 1 (AC-17)."""
    stats = wd.get_triple_run_stats(_fixture_draws())
    assert stats["most_common_group_count"] == 1


def test_avg_max_run_fixture() -> None:
    """D1~D4 → (6+3+1+3)/4 = 3.25 (AC-18)."""
    stats = wd.get_triple_run_stats(_fixture_draws())
    assert stats["avg_max_run"] == 3.25


def test_most_common_group_count_tie_smaller_wins() -> None:
    """동률 시 더 작은 묶음 수가 선택된다 (AC-19).

    묶음 0(D1), 1(D2) 각 1회 동률 → 더 작은 0이 이긴다.
    """
    draws = [
        _mk(1, [1, 5, 10, 20, 30, 40]),   # 묶음 0
        _mk(2, [1, 2, 3, 10, 20, 30]),    # 묶음 1
    ]
    stats = wd.get_triple_run_stats(draws)
    assert stats["most_common_group_count"] == 0


def test_pct_rounded_two_decimals() -> None:
    """3개 회차 → pct는 33.33 형태로 소수 2자리 반올림된다 (AC-13)."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),       # 묶음 1
        _mk(2, [1, 5, 10, 20, 30, 40]),   # 묶음 0
        _mk(3, [1, 2, 3, 7, 8, 9]),       # 묶음 2
    ]
    dist = wd.get_triple_run_stats(draws)["triple_distribution"]
    assert dist["0"]["pct"] == 33.33
    assert dist["1"]["pct"] == 33.33
    assert dist["2"]["pct"] == 33.33


# --------------------------------------------------------------------------- #
# 경계 및 예외
# --------------------------------------------------------------------------- #


def test_empty_draws_returns_consistent_zero_structure() -> None:
    """빈 draws → 예외 없이 일관된 zero 구조 (AC-01~03)."""
    stats = wd.get_triple_run_stats([])
    assert stats["total_draws"] == 0
    assert stats["has_triple_pct"] == 0.0
    assert stats["most_common_group_count"] == 0
    assert stats["avg_max_run"] == 0.0
    assert set(stats["triple_distribution"].keys()) == set(_TRIPLE_RUN_KEYS)
    for key in _TRIPLE_RUN_KEYS:
        assert stats["triple_distribution"][key]["count"] == 0
        assert stats["triple_distribution"][key]["pct"] == 0.0


def test_none_draws_returns_zero_structure() -> None:
    """None 입력도 예외 없이 빈 구조를 반환한다 (AC-04)."""
    stats = wd.get_triple_run_stats(None)
    assert stats["total_draws"] == 0
    assert set(stats["triple_distribution"].keys()) == set(_TRIPLE_RUN_KEYS)


def test_single_draw() -> None:
    """단일 회차도 정상 집계된다."""
    stats = wd.get_triple_run_stats([_mk(1, [1, 2, 3, 7, 8, 9])])
    assert stats["total_draws"] == 1
    assert stats["most_common_group_count"] == 2
    assert stats["triple_distribution"]["2"]["count"] == 1


# --------------------------------------------------------------------------- #
# 캐시 동작
# --------------------------------------------------------------------------- #


def test_cache_populated_and_hit() -> None:
    """동일 입력 재호출 시 캐시된 동일 객체를 반환한다 (AC-20)."""
    draws = _fixture_draws()
    first = wd.get_triple_run_stats(draws)
    second = wd.get_triple_run_stats(draws)
    assert first is second


def test_cache_invalidated() -> None:
    """invalidate_cache 후에는 새 결과 객체를 생성한다."""
    draws = _fixture_draws()
    first = wd.get_triple_run_stats(draws)
    wd.invalidate_cache()
    second = wd.get_triple_run_stats(draws)
    assert first is not second
    assert first == second


def test_invalidate_cache_clears_triple_run_cache() -> None:
    """invalidate_cache가 _triple_run_cache를 비운다 (AC-21)."""
    wd.get_triple_run_stats(_fixture_draws())
    assert len(wd._triple_run_cache) > 0
    wd.invalidate_cache()
    assert len(wd._triple_run_cache) == 0


# --------------------------------------------------------------------------- #
# 라우트
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/triple_run → 200 + 키 구조 (AC-22)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/triple_run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "has_triple_pct",
        "most_common_group_count",
        "avg_max_run",
        "triple_distribution",
    ):
        assert key in body
    assert set(body["triple_distribution"].keys()) == set(_TRIPLE_RUN_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/triple_run 은 데이터가 없어도 200을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/triple_run")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/triple-run → 200(HTML) (AC-23)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/triple-run")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/triple-run 은 데이터가 없어도 200(빈 상태)을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/triple-run")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 실데이터 스모크
# --------------------------------------------------------------------------- #


def test_real_data_smoke() -> None:
    """실제 데이터가 있으면 total_draws>0, avg_max_run은 1~6 범위."""
    draws = wd.get_draws()
    if not draws:
        return  # 데이터 미수집 환경에서는 스킵
    result = wd.get_triple_run_stats(draws)
    assert result["total_draws"] > 0
    assert 1.0 <= result["avg_max_run"] <= 6.0
    assert 0 <= result["most_common_group_count"] <= 2
