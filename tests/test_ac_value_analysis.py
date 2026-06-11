"""SPEC-LOTTO-070: AC값(산술 복잡도) 분포 분석 테스트.

데이터 계층(get_ac_value_stats), 헬퍼(compute_ac_value),
캐시(_ac_value_cache), 페이지/API 라우트를 RED-GREEN-REFACTOR로 검증한다.

AC값(Arithmetic Complexity):
- 한 회차 본번호 6개(보너스 제외)의 C(6,2)=15개 쌍에 대한 절대 차이 중
  서로 다른(distinct) 값의 개수.
- 분포 키는 "0".."14" 15개 고정. AC>=14 회차는 "14" 오버플로 버킷에 합산(min(ac,14)).
- avg_ac_value·high_diversity_pct(AC>=9 판정)는 clamp 이전 원본 AC값으로 계산.
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


_AC_KEYS = [str(i) for i in range(15)]  # "0".."14"


def _mk(no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    bonus 기본값 7은 본번호와 인접해도 AC값 집계에서 제외됨을 검증하기 위함이다.
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# --------------------------------------------------------------------------- #
# compute_ac_value 헬퍼
# --------------------------------------------------------------------------- #


def test_compute_basic_example() -> None:
    """[1,2,3,10,11,12] → AC=7 (distinct {1,2,7,8,9,10,11})."""
    assert wd.compute_ac_value([1, 2, 3, 10, 11, 12]) == 7


def test_compute_six_consecutive() -> None:
    """[1,2,3,4,5,6] → AC=5 (distinct {1,2,3,4,5})."""
    assert wd.compute_ac_value([1, 2, 3, 4, 5, 6]) == 5


def test_compute_even_arithmetic() -> None:
    """[2,4,6,8,10,12] → AC=5 (distinct {2,4,6,8,10})."""
    assert wd.compute_ac_value([2, 4, 6, 8, 10, 12]) == 5


def test_compute_wide_arithmetic() -> None:
    """[5,10,15,20,25,30] → AC=5 (distinct {5,10,15,20,25})."""
    assert wd.compute_ac_value([5, 10, 15, 20, 25, 30]) == 5


def test_compute_high_diversity() -> None:
    """[3,9,17,28,36,44] → AC=11."""
    assert wd.compute_ac_value([3, 9, 17, 28, 36, 44]) == 11


def test_compute_overflow_raw_15() -> None:
    """[1,2,4,8,16,32] → 원본 AC=15 (clamp 이전 헬퍼는 15 그대로 반환)."""
    assert wd.compute_ac_value([1, 2, 4, 8, 16, 32]) == 15


def test_compute_overflow_raw_15_other() -> None:
    """[5,8,9,17,32,37] → 원본 AC=15."""
    assert wd.compute_ac_value([5, 8, 9, 17, 32, 37]) == 15


def test_compute_order_independent() -> None:
    """입력 순서가 달라도 AC값은 동일하다."""
    assert wd.compute_ac_value([12, 1, 11, 3, 2, 10]) == 7


# --------------------------------------------------------------------------- #
# get_ac_value_stats: 빈 데이터 / 기본 분포
# --------------------------------------------------------------------------- #


def test_empty_draws() -> None:
    """AC-070-001: 빈 draws → 0-값, 15 키 존재, most_common_ac=0."""
    result = wd.get_ac_value_stats([])
    assert result["total_draws"] == 0
    assert result["avg_ac_value"] == 0.0
    assert result["most_common_ac"] == 0
    assert result["high_diversity_pct"] == 0.0
    assert set(result["ac_distribution"].keys()) == set(_AC_KEYS)
    for cell in result["ac_distribution"].values():
        assert cell["count"] == 0
        assert cell["pct"] == 0.0


def test_basic_example_distribution() -> None:
    """AC-070-002: [1,2,3,10,11,12] → AC=7, "7" count=1, 나머지 0."""
    result = wd.get_ac_value_stats([_mk(1, [1, 2, 3, 10, 11, 12])])
    assert result["ac_distribution"]["7"]["count"] == 1
    for key in _AC_KEYS:
        if key != "7":
            assert result["ac_distribution"][key]["count"] == 0


def test_six_consecutive_ac5() -> None:
    """AC-070-003: [1,2,3,4,5,6] → AC=5."""
    result = wd.get_ac_value_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert result["ac_distribution"]["5"]["count"] == 1


def test_even_arithmetic_ac5() -> None:
    """AC-070-004: [2,4,6,8,10,12] → AC=5."""
    result = wd.get_ac_value_stats([_mk(1, [2, 4, 6, 8, 10, 12])])
    assert result["ac_distribution"]["5"]["count"] == 1


def test_wide_arithmetic_ac5() -> None:
    """AC-070-005: [5,10,15,20,25,30] → AC=5."""
    result = wd.get_ac_value_stats([_mk(1, [5, 10, 15, 20, 25, 30])])
    assert result["ac_distribution"]["5"]["count"] == 1


def test_high_diversity_ac11() -> None:
    """AC-070-006: [3,9,17,28,36,44] → AC=11."""
    result = wd.get_ac_value_stats([_mk(1, [3, 9, 17, 28, 36, 44])])
    assert result["ac_distribution"]["11"]["count"] == 1


# --------------------------------------------------------------------------- #
# 오버플로 버킷
# --------------------------------------------------------------------------- #


def test_overflow_bucket_14() -> None:
    """AC-070-007: 원본 AC=15 → "14" 버킷에 합산, "15" 키 없음."""
    result = wd.get_ac_value_stats([_mk(1, [1, 2, 4, 8, 16, 32])])
    assert result["ac_distribution"]["14"]["count"] == 1
    assert "15" not in result["ac_distribution"]


def test_overflow_bucket_14_other() -> None:
    """AC-070-008: 다른 원본 AC=15 조합도 "14" 버킷에 합산."""
    result = wd.get_ac_value_stats([_mk(1, [5, 8, 9, 17, 32, 37])])
    assert result["ac_distribution"]["14"]["count"] == 1


# --------------------------------------------------------------------------- #
# 보너스 제외 / 키 존재 보장
# --------------------------------------------------------------------------- #


def test_bonus_excluded() -> None:
    """AC-070-009: 본번호 [1,2,3,4,5,6] + bonus=7 → AC=5 (보너스 제외)."""
    result = wd.get_ac_value_stats([_mk(1, [1, 2, 3, 4, 5, 6], bonus=7)])
    assert result["ac_distribution"]["5"]["count"] == 1


def test_15_keys_always_present() -> None:
    """AC-070-010: 비어 있지 않은 draws → 15 키 항상 존재."""
    result = wd.get_ac_value_stats([_mk(1, [1, 2, 3, 10, 11, 12])])
    assert set(result["ac_distribution"].keys()) == set(_AC_KEYS)


def test_only_0_to_14_keys() -> None:
    """AC-070-017: 모든 키는 "0".."14" 범위 내, 그 외 키 없음."""
    draws = [
        _mk(1, [1, 2, 4, 8, 16, 32]),  # AC=15 → "14"
        _mk(2, [1, 2, 3, 4, 5, 6]),    # AC=5
    ]
    result = wd.get_ac_value_stats(draws)
    assert all(0 <= int(k) <= 14 for k in result["ac_distribution"])
    assert set(result["ac_distribution"].keys()) == set(_AC_KEYS)


# --------------------------------------------------------------------------- #
# avg_ac_value / high_diversity_pct
# --------------------------------------------------------------------------- #


def test_avg_ac_value() -> None:
    """AC-070-011: AC=5, AC=7 → avg=6.0."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),     # AC=5
        _mk(2, [1, 2, 3, 10, 11, 12]),  # AC=7
    ]
    result = wd.get_ac_value_stats(draws)
    assert result["avg_ac_value"] == 6.0


def test_avg_ac_value_uses_raw_overflow() -> None:
    """AC-070-012: AC=5, 원본 AC=15 → avg=10.0 (clamp 이전 15 사용)."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),    # AC=5
        _mk(2, [1, 2, 4, 8, 16, 32]),  # raw AC=15
    ]
    result = wd.get_ac_value_stats(draws)
    assert result["avg_ac_value"] == 10.0


def test_high_diversity_pct() -> None:
    """AC-070-015: AC=5,8,9,12 → high_diversity_pct=50.0 (AC>=9 인 2/4)."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),      # AC=5
        _mk(2, [3, 4, 15, 26, 37, 38]),  # AC=8
        _mk(3, [12, 16, 20, 24, 30, 38]),  # AC=9
        _mk(4, [3, 9, 17, 28, 36, 44]),  # AC=11 (>=9)... need AC=12
    ]
    # 위 4번째는 AC=11; 임계값 검증에는 AC>=9 두 개면 충분
    result = wd.get_ac_value_stats(draws)
    assert result["high_diversity_pct"] == 50.0


def test_high_diversity_boundary() -> None:
    """AC-070-016: AC=8 제외, AC=9 포함 → high_diversity_pct=50.0."""
    draws = [
        _mk(1, [3, 4, 15, 26, 37, 38]),    # AC=8 (제외)
        _mk(2, [12, 16, 20, 24, 30, 38]),  # AC=9 (포함)
    ]
    result = wd.get_ac_value_stats(draws)
    assert result["high_diversity_pct"] == 50.0


# --------------------------------------------------------------------------- #
# most_common_ac
# --------------------------------------------------------------------------- #


def test_most_common_ac() -> None:
    """AC-070-013: AC=5 2개, AC=7 1개 → most_common_ac=5 (정수)."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),     # AC=5
        _mk(2, [2, 4, 6, 8, 10, 12]),   # AC=5
        _mk(3, [1, 2, 3, 10, 11, 12]),  # AC=7
    ]
    result = wd.get_ac_value_stats(draws)
    assert result["most_common_ac"] == 5
    assert isinstance(result["most_common_ac"], int)


def test_most_common_ac_tie_smaller_wins() -> None:
    """AC-070-014: AC=5 1개, AC=7 1개 (동점) → most_common_ac=5 (더 작은 값)."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),     # AC=5
        _mk(2, [1, 2, 3, 10, 11, 12]),  # AC=7
    ]
    result = wd.get_ac_value_stats(draws)
    assert result["most_common_ac"] == 5


# --------------------------------------------------------------------------- #
# pct 합계 / count 합계
# --------------------------------------------------------------------------- #


def test_pct_sums_to_100() -> None:
    """AC-070-018: 15개 키 pct 합 ≈ 100.0."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [1, 2, 3, 10, 11, 12]),
        _mk(3, [3, 9, 17, 28, 36, 44]),
    ]
    result = wd.get_ac_value_stats(draws)
    total_pct = sum(cell["pct"] for cell in result["ac_distribution"].values())
    assert abs(total_pct - 100.0) < 0.1


def test_count_sum_equals_total() -> None:
    """AC-070-019: 15개 키 count 합 = total_draws."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [1, 2, 3, 10, 11, 12]),
        _mk(3, [1, 2, 4, 8, 16, 32]),  # overflow → "14"
    ]
    result = wd.get_ac_value_stats(draws)
    total_count = sum(cell["count"] for cell in result["ac_distribution"].values())
    assert total_count == result["total_draws"] == 3


# --------------------------------------------------------------------------- #
# 캐시
# --------------------------------------------------------------------------- #


def test_cache_hit_same_object() -> None:
    """AC-070-020: 동일 len(draws) 두 번째 호출 → 동일 객체(id)."""
    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    first = wd.get_ac_value_stats(draws)
    second = wd.get_ac_value_stats(draws)
    assert first is second


def test_cache_miss_different_length() -> None:
    """AC-070-021: 다른 len(draws) → 새로 계산한 결과."""
    draws1 = [_mk(1, [1, 2, 3, 4, 5, 6])]
    draws2 = [_mk(1, [1, 2, 3, 4, 5, 6]), _mk(2, [1, 2, 3, 10, 11, 12])]
    first = wd.get_ac_value_stats(draws1)
    second = wd.get_ac_value_stats(draws2)
    assert first is not second
    assert second["total_draws"] == 2


def test_invalidate_cache_clears() -> None:
    """AC-070-022: invalidate_cache() → _ac_value_cache 비워짐."""
    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    wd.get_ac_value_stats(draws)
    assert wd._ac_value_cache  # 채워진 상태
    wd.invalidate_cache()
    assert wd._ac_value_cache == {}


# --------------------------------------------------------------------------- #
# 라우트: API / 페이지
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """AC-070-023: GET /api/stats/ac_value 는 200 + 키 구조(15 분포 키)를 반환한다."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [1, 2, 3, 10, 11, 12]),
        _mk(3, [3, 9, 17, 28, 36, 44]),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = _client().get("/api/stats/ac_value")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 3
    for key in (
        "total_draws",
        "avg_ac_value",
        "most_common_ac",
        "high_diversity_pct",
        "ac_distribution",
    ):
        assert key in body
    assert set(body["ac_distribution"].keys()) == set(_AC_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/ac_value 는 데이터가 없어도 200 을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/ac_value")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """AC-070-024: GET /stats/ac-value 는 200(HTML, "AC" 텍스트 포함)을 반환한다."""
    draws = [_mk(1, [1, 2, 3, 10, 11, 12])]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = _client().get("/stats/ac-value")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "AC" in resp.text


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/ac-value 는 데이터가 없어도 200(빈 상태)을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/ac-value")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 실데이터 스모크
# --------------------------------------------------------------------------- #


def test_real_data_smoke() -> None:
    """AC-070-024(smoke): 실제 데이터가 있으면 total_draws>0, avg_ac_value>0."""
    draws = wd.get_draws()
    if not draws:
        return  # 데이터 미수집 환경에서는 스킵
    result = wd.get_ac_value_stats(draws)
    assert result["total_draws"] > 0
    assert result["avg_ac_value"] > 0
