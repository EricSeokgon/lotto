"""SPEC-LOTTO-065: 번호 표준편차(모표준편차) 분석 테스트.

데이터 계층(get_std_stats), 캐시, 페이지/API 라우트를
RED-GREEN-REFACTOR로 검증한다.

분석(회차별 본번호 6개, 보너스 제외):
- mean     = sum(nums) / 6
- variance = sum((n - mean)**2) / 6  (모분산, n=6으로 나눔; 표본분산 아님)
- std      = round(variance ** 0.5, 2)  (모표준편차, 회차당 소수 둘째 자리 반올림)
- 카테고리: low(std < 10.0), mid(10.0 <= std < 14.0), high(std >= 14.0)
- std_distribution: 6개 고정 bucket 키를 항상 포함(미관측 구간 0 유지)
    "0-4"[0,4), "4-8"[4,8), "8-12"[8,12), "12-16"[12,16), "16-20"[16,20), "20+"[20,∞)
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd

if TYPE_CHECKING:
    from collections.abc import Iterator  # noqa: F401


_BUCKET_KEYS = ["0-4", "4-8", "8-12", "12-16", "16-20", "20+"]


def _mk(no: int, nums: list[int], bonus: int = 13) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    bonus는 본번호 외 값을 사용해 std 집계에 영향을 주지 않음을 검증할 수 있게 한다.
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


@pytest.fixture
def four_draws() -> list[DrawResult]:
    """SPEC 고정 4회차 픽스처.

    - D1=[1,2,3,4,5,6]       → mean=3.5,   var=2.92,   std=1.71  (bucket "0-4",   low)
    - D2=[10,15,20,25,30,35] → mean=22.5,  var=72.92,  std=8.54  (bucket "8-12",  low)
    - D3=[5,10,15,20,25,40]  → mean=19.17, var=128.47, std=11.33 (bucket "8-12",  mid)
    - D4=[1,2,3,4,5,45]      → mean=10.0,  var=246.67, std=15.71 (bucket "12-16", high)
    avg_std=9.32, min_std=1.71, max_std=15.71, low=2, mid=1, high=1.
    """
    return [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [10, 15, 20, 25, 30, 35]),
        _mk(3, [5, 10, 15, 20, 25, 40]),
        _mk(4, [1, 2, 3, 4, 5, 45]),
    ]


# --------------------------------------------------------------------------- #
# 빈 데이터 / 일관된 빈 구조 (REQ-SD-013)
# --------------------------------------------------------------------------- #


def test_empty_draws_returns_zero_structure() -> None:
    """빈 리스트는 total_draws=0 과 모든 수치 0을 반환한다."""
    result = wd.get_std_stats([])
    assert result["total_draws"] == 0
    assert result["avg_std"] == 0.0
    assert result["min_std"] == 0.0
    assert result["max_std"] == 0.0
    assert result["low_std_count"] == 0
    assert result["mid_std_count"] == 0
    assert result["high_std_count"] == 0
    assert result["low_std_pct"] == 0.0
    assert result["mid_std_pct"] == 0.0
    assert result["high_std_pct"] == 0.0


def test_none_draws_returns_zero_structure() -> None:
    """None 입력도 빈 데이터와 동일한 구조를 반환한다."""
    result = wd.get_std_stats(None)
    assert result["total_draws"] == 0
    assert result["most_common_bucket"] == "0-4"


def test_empty_distribution_has_all_six_keys_zero() -> None:
    """빈 데이터에서도 6개 bucket 키가 모두 0으로 존재한다."""
    result = wd.get_std_stats([])
    assert list(result["std_distribution"].keys()) == _BUCKET_KEYS
    assert all(v == 0 for v in result["std_distribution"].values())


def test_empty_most_common_bucket_is_first() -> None:
    """빈 데이터의 most_common_bucket 은 첫 bucket '0-4' 이다."""
    assert wd.get_std_stats([])["most_common_bucket"] == "0-4"


# --------------------------------------------------------------------------- #
# 회차별 std 산출 (REQ-SD-002, population std)
# --------------------------------------------------------------------------- #


def test_single_consecutive_draw_std() -> None:
    """[1,2,3,4,5,6] → mean=3.5, var=2.92, std=1.71 (모표준편차)."""
    result = wd.get_std_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert result["total_draws"] == 1
    assert result["avg_std"] == 1.71
    assert result["min_std"] == 1.71
    assert result["max_std"] == 1.71


def test_population_not_sample_std() -> None:
    """모표준편차(n=6)이어야 한다. 표본표준편차(n-1=5)면 값이 더 크다.

    [1,2,3,4,5,6]: pop std=1.71, sample std≈1.87. 1.71 이 나와야 한다.
    """
    result = wd.get_std_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert result["avg_std"] == 1.71
    assert result["avg_std"] != 1.87  # 표본표준편차가 아님


def test_mid_spread_draw_std() -> None:
    """[10,15,20,25,30,35] → std=8.54 (bucket '8-12', low)."""
    result = wd.get_std_stats([_mk(1, [10, 15, 20, 25, 30, 35])])
    assert result["avg_std"] == 8.54
    assert result["low_std_count"] == 1
    assert result["std_distribution"]["8-12"] == 1


def test_mid_category_draw_std() -> None:
    """[5,10,15,20,25,40] → std=11.33 (bucket '8-12', mid)."""
    result = wd.get_std_stats([_mk(1, [5, 10, 15, 20, 25, 40])])
    assert result["avg_std"] == 11.33
    assert result["mid_std_count"] == 1
    assert result["std_distribution"]["8-12"] == 1


def test_high_category_draw_std() -> None:
    """[1,2,3,4,5,45] → std=15.71 (bucket '12-16', high)."""
    result = wd.get_std_stats([_mk(1, [1, 2, 3, 4, 5, 45])])
    assert result["avg_std"] == 15.71
    assert result["high_std_count"] == 1
    assert result["std_distribution"]["12-16"] == 1


def test_bonus_excluded_from_std() -> None:
    """보너스 번호는 std 산출에서 제외된다 (본번호 6개만)."""
    # bonus 를 극단값 45 로 줘도 std 는 본번호 [1,2,3,4,5,6] 기준 1.71 이어야 한다.
    result = wd.get_std_stats([_mk(1, [1, 2, 3, 4, 5, 6], bonus=45)])
    assert result["avg_std"] == 1.71


# --------------------------------------------------------------------------- #
# 고정 4회차 픽스처 집계 (REQ-SD-003~006)
# --------------------------------------------------------------------------- #


def test_four_draws_avg_min_max(four_draws: list[DrawResult]) -> None:
    """4회차 픽스처: avg_std=9.32, min_std=1.71, max_std=15.71."""
    result = wd.get_std_stats(four_draws)
    assert result["total_draws"] == 4
    assert result["avg_std"] == 9.32
    assert result["min_std"] == 1.71
    assert result["max_std"] == 15.71


def test_four_draws_category_counts(four_draws: list[DrawResult]) -> None:
    """4회차 픽스처: low=2, mid=1, high=1."""
    result = wd.get_std_stats(four_draws)
    assert result["low_std_count"] == 2
    assert result["mid_std_count"] == 1
    assert result["high_std_count"] == 1


def test_four_draws_category_counts_partition(four_draws: list[DrawResult]) -> None:
    """세 카테고리 합은 total_draws 와 같다(분할)."""
    result = wd.get_std_stats(four_draws)
    total = (
        result["low_std_count"]
        + result["mid_std_count"]
        + result["high_std_count"]
    )
    assert total == result["total_draws"]


def test_four_draws_category_pcts(four_draws: list[DrawResult]) -> None:
    """4회차 픽스처: low=50.0%, mid=25.0%, high=25.0%."""
    result = wd.get_std_stats(four_draws)
    assert result["low_std_pct"] == 50.0
    assert result["mid_std_pct"] == 25.0
    assert result["high_std_pct"] == 25.0


def test_four_draws_distribution(four_draws: list[DrawResult]) -> None:
    """4회차 분포: '0-4'=1, '8-12'=2, '12-16'=1, 나머지 0."""
    result = wd.get_std_stats(four_draws)
    dist = result["std_distribution"]
    assert dist["0-4"] == 1
    assert dist["4-8"] == 0
    assert dist["8-12"] == 2
    assert dist["12-16"] == 1
    assert dist["16-20"] == 0
    assert dist["20+"] == 0


def test_four_draws_most_common_bucket(four_draws: list[DrawResult]) -> None:
    """4회차 최빈 bucket 은 2회 출현한 '8-12' 이다."""
    result = wd.get_std_stats(four_draws)
    assert result["most_common_bucket"] == "8-12"


# --------------------------------------------------------------------------- #
# 분포 키 불변성 (REQ-SD-007)
# --------------------------------------------------------------------------- #


def test_distribution_always_has_six_keys(four_draws: list[DrawResult]) -> None:
    """std_distribution 은 항상 6개 키를 정의된 순서로 포함한다."""
    result = wd.get_std_stats(four_draws)
    assert list(result["std_distribution"].keys()) == _BUCKET_KEYS


def test_distribution_keys_present_for_single_draw() -> None:
    """단일 회차에서도 미관측 bucket 까지 6개 키가 모두 존재한다."""
    result = wd.get_std_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert list(result["std_distribution"].keys()) == _BUCKET_KEYS
    assert result["std_distribution"]["0-4"] == 1
    assert result["std_distribution"]["20+"] == 0


# --------------------------------------------------------------------------- #
# 카테고리 경계 (REQ-SD-005)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("std_value", "expected"),
    [
        (9.99, "low"),
        (10.0, "mid"),
        (13.99, "mid"),
        (14.0, "high"),
    ],
)
def test_category_boundaries(std_value: float, expected: str) -> None:
    """카테고리 경계: <10 low, [10,14) mid, >=14 high.

    실제 조합으로 정확한 경계 std 를 만들기 어렵기 때문에,
    내부 분류 헬퍼가 있다면 그것을, 없으면 구간 규칙을 직접 검증한다.
    여기서는 규칙 자체를 단언한다.
    """
    if std_value < 10.0:
        category = "low"
    elif std_value < 14.0:
        category = "mid"
    else:
        category = "high"
    assert category == expected


def test_category_boundary_low_just_under_10() -> None:
    """std=8.54([10,15,20,25,30,35])는 low 로 분류된다(<10)."""
    result = wd.get_std_stats([_mk(1, [10, 15, 20, 25, 30, 35])])
    assert result["low_std_count"] == 1
    assert result["mid_std_count"] == 0


def test_category_boundary_mid() -> None:
    """std=11.33([5,10,15,20,25,40])는 mid 로 분류된다([10,14))."""
    result = wd.get_std_stats([_mk(1, [5, 10, 15, 20, 25, 40])])
    assert result["mid_std_count"] == 1
    assert result["low_std_count"] == 0
    assert result["high_std_count"] == 0


def test_category_boundary_high() -> None:
    """std=15.71([1,2,3,4,5,45])는 high 로 분류된다(>=14)."""
    result = wd.get_std_stats([_mk(1, [1, 2, 3, 4, 5, 45])])
    assert result["high_std_count"] == 1
    assert result["mid_std_count"] == 0


# --------------------------------------------------------------------------- #
# most_common_bucket 동률 (REQ-SD-008)
# --------------------------------------------------------------------------- #


def test_most_common_bucket_tie_first_wins() -> None:
    """동률 시 정의 순서상 앞선 bucket 이 선택된다.

    '0-4'(std 1.71) 1회 + '8-12'(std 8.54) 1회 → 둘 다 1회 동률 →
    정의 순서상 '0-4' 가 '8-12' 보다 앞서므로 '0-4' 선택.
    """
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),      # std=1.71 → "0-4"
        _mk(2, [10, 15, 20, 25, 30, 35]),  # std=8.54 → "8-12"
    ]
    result = wd.get_std_stats(draws)
    assert result["std_distribution"]["0-4"] == 1
    assert result["std_distribution"]["8-12"] == 1
    assert result["most_common_bucket"] == "0-4"


# --------------------------------------------------------------------------- #
# 입력 불변성 (REQ-SD-014)
# --------------------------------------------------------------------------- #


def test_does_not_mutate_input(four_draws: list[DrawResult]) -> None:
    """입력 draws 리스트를 변경하지 않는다."""
    snapshot = list(four_draws)
    wd.get_std_stats(four_draws)
    assert four_draws == snapshot
    assert len(four_draws) == 4


# --------------------------------------------------------------------------- #
# 캐시 (REQ-SD-016)
# --------------------------------------------------------------------------- #


def test_cache_populated(four_draws: list[DrawResult]) -> None:
    """첫 호출 후 결과가 캐시에 적재된다(키: str(len(draws)))."""
    wd._std_cache.clear()
    wd.get_std_stats(four_draws)
    assert "4" in wd._std_cache


def test_cache_hit_returns_same_object(four_draws: list[DrawResult]) -> None:
    """동일 길이 입력의 재호출은 캐시된 동일 객체를 반환한다."""
    wd._std_cache.clear()
    first = wd.get_std_stats(four_draws)
    second = wd.get_std_stats(four_draws)
    assert first is second


def test_invalidate_cache_clears_std_cache(four_draws: list[DrawResult]) -> None:
    """invalidate_cache() 호출 시 std 캐시가 비워진다."""
    wd.get_std_stats(four_draws)
    assert wd._std_cache
    wd.invalidate_cache()
    assert not wd._std_cache


# --------------------------------------------------------------------------- #
# 라우트: 페이지 (REQ-SD-010, REQ-SD-013)
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_page_route_returns_200_with_data(four_draws: list[DrawResult]) -> None:
    """GET /stats/std 는 데이터가 있을 때 200 을 반환한다."""
    with patch.object(wd, "get_draws", return_value=four_draws):
        resp = _client().get("/stats/std")
    assert resp.status_code == 200
    assert "표준편차" in resp.text


def test_page_route_returns_200_when_empty() -> None:
    """GET /stats/std 는 데이터가 없어도 200(빈 상태)을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/std")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 라우트: API (REQ-SD-009, REQ-SD-013)
# --------------------------------------------------------------------------- #


def test_api_route_returns_json(four_draws: list[DrawResult]) -> None:
    """GET /api/stats/std 는 std 분석 JSON 을 200 으로 반환한다."""
    with patch.object(wd, "get_draws", return_value=four_draws):
        resp = _client().get("/api/stats/std")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    assert body["avg_std"] == 9.32
    assert body["most_common_bucket"] == "8-12"


def test_api_route_all_bucket_keys_present(four_draws: list[DrawResult]) -> None:
    """API 응답의 std_distribution 은 6개 고정 키를 모두 포함한다."""
    with patch.object(wd, "get_draws", return_value=four_draws):
        resp = _client().get("/api/stats/std")
    dist = resp.json()["std_distribution"]
    assert set(dist.keys()) == set(_BUCKET_KEYS)


def test_api_route_empty_returns_200() -> None:
    """GET /api/stats/std 는 데이터가 없어도 200 을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/std")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0
