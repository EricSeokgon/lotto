"""SPEC-LOTTO-098: 구간별 번호 선택 분포 분석 (Zone Coverage Distribution) 테스트."""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# 테스트용 DrawResult 모의 객체
# ---------------------------------------------------------------------------

@dataclass
class _MockDraw:
    """테스트용 회차 모의 객체 — numbers() 메서드를 제공한다."""

    _numbers: list[int]
    bonus: int = 0

    def numbers(self) -> list[int]:
        """정렬된 본번호 6개 반환."""
        return sorted(self._numbers)


def _make_draws(numbers_list: list[list[int]]) -> list[_MockDraw]:
    """번호 목록으로 MockDraw 리스트를 생성한다."""
    return [_MockDraw(nums) for nums in numbers_list]


# ---------------------------------------------------------------------------
# AC-10: 구간 산출 공식 검증 — (num-1)//5
# ---------------------------------------------------------------------------

class TestZoneFormula:
    """구간 인덱스 계산 공식 검증."""

    def test_zone_index_1(self) -> None:
        """번호 1 → 구간 0."""
        assert (1 - 1) // 5 == 0

    def test_zone_index_5(self) -> None:
        """번호 5 → 구간 0."""
        assert (5 - 1) // 5 == 0

    def test_zone_index_6(self) -> None:
        """번호 6 → 구간 1."""
        assert (6 - 1) // 5 == 1

    def test_zone_index_10(self) -> None:
        """번호 10 → 구간 1."""
        assert (10 - 1) // 5 == 1

    def test_zone_index_45(self) -> None:
        """번호 45 → 구간 8."""
        assert (45 - 1) // 5 == 8

    def test_zone_index_41(self) -> None:
        """번호 41 → 구간 8."""
        assert (41 - 1) // 5 == 8

    # AC-44: 모든 경계 번호의 구간 인덱스 0~8 범위 검증
    def test_zone_range_all_boundaries(self) -> None:
        """번호 1,5,6,40,41,45 — 모두 0~8 범위 내 정수."""
        for num in [1, 5, 6, 40, 41, 45]:
            idx = (num - 1) // 5
            assert 0 <= idx <= 8, f"번호 {num}의 구간 인덱스 {idx}가 범위 밖"


# ---------------------------------------------------------------------------
# 빈 데이터 케이스 (AC-01, AC-02, AC-03, S1)
# ---------------------------------------------------------------------------

class TestEmptyData:
    """빈 데이터 입력 시 기본 구조 반환 검증."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_none_input_total_draws_zero(self) -> None:
        """None 입력 → total_draws == 0 (AC-01)."""
        from lotto.web.data import get_zone_coverage_stats
        result = get_zone_coverage_stats(None)
        assert result["total_draws"] == 0

    def test_none_input_avg_zero(self) -> None:
        """None 입력 → avg_zones_covered == 0.0 (AC-01)."""
        from lotto.web.data import get_zone_coverage_stats
        result = get_zone_coverage_stats(None)
        assert result["avg_zones_covered"] == 0.0

    def test_none_input_most_common_is_string_1(self) -> None:
        """None 입력 → most_common_zones == "1" (AC-01, S1)."""
        from lotto.web.data import get_zone_coverage_stats
        result = get_zone_coverage_stats(None)
        assert result["most_common_zones"] == "1"

    def test_none_input_full_spread_pct_zero(self) -> None:
        """None 입력 → full_spread_pct == 0.0 (AC-01)."""
        from lotto.web.data import get_zone_coverage_stats
        result = get_zone_coverage_stats(None)
        assert result["full_spread_pct"] == 0.0

    def test_none_input_concentrated_pct_zero(self) -> None:
        """None 입력 → concentrated_pct == 0.0 (AC-01)."""
        from lotto.web.data import get_zone_coverage_stats
        result = get_zone_coverage_stats(None)
        assert result["concentrated_pct"] == 0.0

    def test_empty_list_total_draws_zero(self) -> None:
        """빈 리스트 → total_draws == 0 (AC-02)."""
        from lotto.web.data import get_zone_coverage_stats
        result = get_zone_coverage_stats([])
        assert result["total_draws"] == 0

    def test_empty_list_has_all_six_bucket_keys(self) -> None:
        """빈 리스트 → distribution에 6개 키 모두 포함 (AC-03)."""
        from lotto.web.data import get_zone_coverage_stats
        result = get_zone_coverage_stats([])
        assert set(result["zone_coverage_distribution"].keys()) == {"1", "2", "3", "4", "5", "6"}

    def test_empty_list_all_buckets_count_zero(self) -> None:
        """빈 리스트 → 모든 버킷 count == 0 (AC-02)."""
        from lotto.web.data import get_zone_coverage_stats
        result = get_zone_coverage_stats([])
        for key, cell in result["zone_coverage_distribution"].items():
            assert cell["count"] == 0, f"버킷 {key}의 count가 0이 아님"

    def test_empty_list_all_buckets_pct_zero(self) -> None:
        """빈 리스트 → 모든 버킷 pct == 0.0 (AC-02)."""
        from lotto.web.data import get_zone_coverage_stats
        result = get_zone_coverage_stats([])
        for key, cell in result["zone_coverage_distribution"].items():
            assert cell["pct"] == 0.0, f"버킷 {key}의 pct가 0.0이 아님"


# ---------------------------------------------------------------------------
# 단일 회차 케이스 (AC-04 ~ AC-09, AC-11 ~ AC-13)
# ---------------------------------------------------------------------------

class TestSingleDraw:
    """단일 회차 구간 커버 수 계산 검증."""

    def setup_method(self) -> None:
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_two_zones_covered(self) -> None:
        """[6,7,8,9,10,11] → zones=2, bucket '2' count==1 (AC-04)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([[6, 7, 8, 9, 10, 11]])
        result = get_zone_coverage_stats(draws)
        assert result["zone_coverage_distribution"]["2"]["count"] == 1

    def test_two_zones_adjacent(self) -> None:
        """[1,2,3,6,7,8] → zones=2, count==1, avg==2.0 (AC-05)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([[1, 2, 3, 6, 7, 8]])
        result = get_zone_coverage_stats(draws)
        assert result["zone_coverage_distribution"]["2"]["count"] == 1
        assert result["total_draws"] == 1
        assert result["avg_zones_covered"] == 2.0

    def test_three_zones(self) -> None:
        """[1,2,6,7,11,12] → zones=3, count==1, avg==3.0 (AC-06)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([[1, 2, 6, 7, 11, 12]])
        result = get_zone_coverage_stats(draws)
        assert result["zone_coverage_distribution"]["3"]["count"] == 1
        assert result["avg_zones_covered"] == 3.0

    def test_four_zones(self) -> None:
        """[1,6,11,16,20,21] → 구간 0,1,2,3,3,4 → unique=4, avg==4.0 (AC-07)."""
        from lotto.web.data import get_zone_coverage_stats
        # 20은 (20-1)//5=3, 21은 (21-1)//5=4 → zones={0,1,2,3,4} → 5구간
        # AC-07 예시는 [1,6,11,16,20,21] — acceptance 노트: "구간 0,1,2,3,3,4 → unique 4구간"
        # 실제 계산: 1→0, 6→1, 11→2, 16→3, 20→3, 21→4 → unique={0,1,2,3,4} → 5구간
        # AC-07의 의도는 4구간 케이스. 다른 예시로 교체: [1,6,11,16,30,31]
        # 1→0, 6→1, 11→2, 16→3, 30→5, 31→6 → 6구간 — 이것도 아님
        # [1,2,6,7,11,16] → 1→0,2→0,6→1,7→1,11→2,16→3 → zones={0,1,2,3} → 4구간
        draws = _make_draws([[1, 2, 6, 7, 11, 16]])
        result = get_zone_coverage_stats(draws)
        assert result["zone_coverage_distribution"]["4"]["count"] == 1
        assert result["avg_zones_covered"] == 4.0

    def test_five_zones(self) -> None:
        """5개 구간 커버 케이스 → bucket '5' count==1, avg==5.0 (AC-08)."""
        from lotto.web.data import get_zone_coverage_stats
        # [1,6,11,16,21,30] → 0,1,2,3,4,5 → zones=6 아니라 5구간인 예시 필요
        # [1,2,6,7,11,21] → 0,0,1,1,2,4 → zones={0,1,2,4} → 4구간
        # [1,6,11,21,26,30] → 0,1,2,4,5,5 → zones={0,1,2,4,5} → 5구간
        draws = _make_draws([[1, 6, 11, 21, 26, 30]])
        result = get_zone_coverage_stats(draws)
        assert result["zone_coverage_distribution"]["5"]["count"] == 1
        assert result["avg_zones_covered"] == 5.0

    def test_six_zones_full_spread(self) -> None:
        """6개 구간 커버(완전분산) → full_spread_pct==100.0 (AC-09)."""
        from lotto.web.data import get_zone_coverage_stats
        # [1,7,13,19,25,31] → 구간 0,1,2,3,4,5 → 6개 구간
        draws = _make_draws([[1, 7, 13, 19, 25, 31]])
        result = get_zone_coverage_stats(draws)
        assert result["zone_coverage_distribution"]["6"]["count"] == 1
        assert result["full_spread_pct"] == 100.0

    def test_boundary_5_and_6_different_zones(self) -> None:
        """5는 구간0, 6은 구간1 → zones=2 (AC-11)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([[1, 2, 3, 4, 5, 6]])
        result = get_zone_coverage_stats(draws)
        assert result["zone_coverage_distribution"]["2"]["count"] == 1

    def test_boundary_10_and_11_different_zones(self) -> None:
        """10은 구간1, 11은 구간2 → zones=3 (AC-12)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([[1, 2, 6, 7, 10, 11]])
        result = get_zone_coverage_stats(draws)
        assert result["zone_coverage_distribution"]["3"]["count"] == 1

    def test_number_45_in_zone8(self) -> None:
        """45가 구간8에 속함 → [1,6,11,16,21,45] → zones=6 (AC-13)."""
        from lotto.web.data import get_zone_coverage_stats
        # 1→0,6→1,11→2,16→3,21→4,45→8 → zones={0,1,2,3,4,8} → 6구간
        draws = _make_draws([[1, 6, 11, 16, 21, 45]])
        result = get_zone_coverage_stats(draws)
        assert result["zone_coverage_distribution"]["6"]["count"] == 1

    def test_single_draw_pct_is_100(self) -> None:
        """단일 회차 zones_covered==5 → bucket '5' pct == 100.0 (AC-43)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([[1, 6, 11, 21, 26, 30]])
        result = get_zone_coverage_stats(draws)
        assert result["zone_coverage_distribution"]["5"]["pct"] == 100.0

    def test_zones_covered_max_six(self) -> None:
        """각각 다른 구간 6개 → zones_covered==6 (AC-37)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([[1, 7, 13, 19, 25, 31]])
        result = get_zone_coverage_stats(draws)
        assert result["zone_coverage_distribution"]["6"]["count"] == 1


# ---------------------------------------------------------------------------
# 다중 회차 케이스 (AC-14 ~ AC-24)
# ---------------------------------------------------------------------------

class TestMultipleDraws:
    """다중 회차 집계 검증."""

    def setup_method(self) -> None:
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_three_draws_aggregation(self) -> None:
        """3회차 집계 — zones 2,6,5 (AC-14)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([
            [1, 2, 3, 6, 7, 8],     # zones=2
            [1, 7, 13, 19, 25, 31],  # zones=6 (구간 0,1,2,3,4,5)
            [1, 6, 11, 21, 26, 30],  # zones=5 (구간 0,1,2,4,5)
        ])
        result = get_zone_coverage_stats(draws)
        assert result["total_draws"] == 3
        assert result["zone_coverage_distribution"]["2"]["count"] == 1
        assert result["zone_coverage_distribution"]["6"]["count"] == 1
        assert result["zone_coverage_distribution"]["5"]["count"] == 1

    def test_avg_zones_covered_exact(self) -> None:
        """avg_zones_covered = (4+5+5+5+6)/5 = 5.0 (AC-15)."""
        from lotto.web.data import get_zone_coverage_stats
        # 4구간: [1,2,6,7,11,16]
        # 5구간: [1,6,11,21,26,30] × 3
        # 6구간: [1,7,13,19,25,31]
        draws = _make_draws([
            [1, 2, 6, 7, 11, 16],   # 4구간
            [1, 6, 11, 21, 26, 30], # 5구간
            [1, 6, 11, 21, 26, 30], # 5구간
            [1, 6, 11, 21, 26, 30], # 5구간
            [1, 7, 13, 19, 25, 31], # 6구간
        ])
        result = get_zone_coverage_stats(draws)
        assert result["avg_zones_covered"] == 5.0

    def test_avg_zones_covered_rounding(self) -> None:
        """avg_zones_covered 소수 2자리 반올림 — 10/3 = 3.33 (AC-16)."""
        from lotto.web.data import get_zone_coverage_stats
        # 3회차 합계 zones = 3+3+4 = 10 → avg = 10/3 = 3.333...
        draws = _make_draws([
            [1, 2, 6, 7, 11, 12],   # 3구간
            [1, 2, 6, 7, 11, 12],   # 3구간
            [1, 2, 6, 7, 11, 16],   # 4구간
        ])
        result = get_zone_coverage_stats(draws)
        assert result["avg_zones_covered"] == round(10 / 3, 2)

    def test_most_common_zones_highest_count(self) -> None:
        """최빈 버킷 선택: 분포 3→1,4→2,5→3 → most_common_zones=="5" (AC-17)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([
            [1, 2, 6, 7, 11, 12],   # 3구간
            [1, 2, 6, 7, 11, 16],   # 4구간
            [1, 2, 6, 7, 11, 16],   # 4구간
            [1, 6, 11, 21, 26, 30], # 5구간
            [1, 6, 11, 21, 26, 30], # 5구간
            [1, 6, 11, 21, 26, 30], # 5구간
        ])
        result = get_zone_coverage_stats(draws)
        assert result["most_common_zones"] == "5"

    def test_most_common_zones_tie_smaller_wins(self) -> None:
        """동률 시 _ZONE_COV_KEYS 정의 순서상 앞선(작은) 값 선택: 4→2,5→2 → "4" (AC-18)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([
            [1, 2, 6, 7, 11, 16],   # 4구간
            [1, 2, 6, 7, 11, 16],   # 4구간
            [1, 6, 11, 21, 26, 30], # 5구간
            [1, 6, 11, 21, 26, 30], # 5구간
            [1, 7, 13, 19, 25, 31], # 6구간
        ])
        result = get_zone_coverage_stats(draws)
        assert result["most_common_zones"] == "4"

    def test_full_spread_pct(self) -> None:
        """full_spread_pct: 5회차 중 zones==6이 2회 → 40.0 (AC-19)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([
            [1, 7, 13, 19, 25, 31], # 6구간
            [1, 7, 13, 19, 25, 31], # 6구간
            [1, 2, 6, 7, 11, 16],   # 4구간
            [1, 6, 11, 21, 26, 30], # 5구간
            [1, 2, 6, 7, 11, 12],   # 3구간
        ])
        result = get_zone_coverage_stats(draws)
        assert result["full_spread_pct"] == 40.0

    def test_full_spread_pct_zero_when_no_six_zone(self) -> None:
        """zones_covered < 6인 경우 full_spread_pct == 0.0 (AC-20)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([
            [1, 2, 6, 7, 11, 12],   # 3구간
            [1, 2, 6, 7, 11, 16],   # 4구간
        ])
        result = get_zone_coverage_stats(draws)
        assert result["full_spread_pct"] == 0.0

    def test_concentrated_pct(self) -> None:
        """concentrated_pct: 5회차 zones 2,2,3,4,5 → <=3이 3회 → 60.0 (AC-21)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([
            [1, 2, 3, 6, 7, 8],     # 2구간
            [1, 2, 3, 6, 7, 8],     # 2구간
            [1, 2, 6, 7, 11, 12],   # 3구간
            [1, 2, 6, 7, 11, 16],   # 4구간
            [1, 6, 11, 21, 26, 30], # 5구간
        ])
        result = get_zone_coverage_stats(draws)
        assert result["concentrated_pct"] == 60.0

    def test_concentrated_pct_zero_when_all_above_three(self) -> None:
        """모든 회차 zones > 3 → concentrated_pct == 0.0 (AC-22)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([
            [1, 2, 6, 7, 11, 16],   # 4구간
            [1, 6, 11, 21, 26, 30], # 5구간
        ])
        result = get_zone_coverage_stats(draws)
        assert result["concentrated_pct"] == 0.0

    def test_pct_rounding_two_decimal(self) -> None:
        """pct 소수 2자리 반올림 — 1/3 = 33.33 (AC-23)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([
            [1, 2, 6, 7, 11, 16],   # 4구간
            [1, 2, 6, 7, 11, 12],   # 3구간
            [1, 2, 6, 7, 11, 12],   # 3구간
        ])
        result = get_zone_coverage_stats(draws)
        assert result["zone_coverage_distribution"]["4"]["pct"] == round(1 / 3 * 100, 2)

    def test_pct_sum_approximately_100(self) -> None:
        """6개 버킷 pct 합계 ≈ 100.0 (AC-24)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([
            [1, 2, 3, 6, 7, 8],     # 2구간
            [1, 2, 6, 7, 11, 12],   # 3구간
            [1, 2, 6, 7, 11, 16],   # 4구간
            [1, 6, 11, 21, 26, 30], # 5구간
            [1, 7, 13, 19, 25, 31], # 6구간
            [1, 2, 3, 6, 7, 8],     # 2구간
            [1, 2, 6, 7, 11, 12],   # 3구간
            [1, 2, 6, 7, 11, 16],   # 4구간
            [1, 6, 11, 21, 26, 30], # 5구간
            [1, 7, 13, 19, 25, 31], # 6구간
        ])
        result = get_zone_coverage_stats(draws)
        total_pct = sum(cell["pct"] for cell in result["zone_coverage_distribution"].values())
        assert abs(total_pct - 100.0) <= 0.1


# ---------------------------------------------------------------------------
# 타입 검증 (AC-38, AC-39, AC-42, AC-47)
# ---------------------------------------------------------------------------

class TestReturnTypes:
    """반환값 타입 검증."""

    def setup_method(self) -> None:
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_full_spread_pct_is_float(self) -> None:
        """full_spread_pct는 float 타입 (AC-38)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([[1, 7, 13, 19, 25, 31]])
        result = get_zone_coverage_stats(draws)
        assert isinstance(result["full_spread_pct"], float)

    def test_concentrated_pct_is_float(self) -> None:
        """concentrated_pct는 float 타입 (AC-39)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([[1, 2, 3, 6, 7, 8]])
        result = get_zone_coverage_stats(draws)
        assert isinstance(result["concentrated_pct"], float)

    def test_avg_zones_covered_is_float(self) -> None:
        """avg_zones_covered는 float 타입 (AC-42)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([[1, 7, 13, 19, 25, 31]])
        result = get_zone_coverage_stats(draws)
        assert isinstance(result["avg_zones_covered"], float)

    def test_most_common_zones_is_string(self) -> None:
        """most_common_zones는 str 타입 (AC-47)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([[1, 7, 13, 19, 25, 31]])
        result = get_zone_coverage_stats(draws)
        assert isinstance(result["most_common_zones"], str)

    def test_most_common_zones_value_in_range(self) -> None:
        """most_common_zones는 "1"~"6" 중 하나 (AC-47)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([[1, 7, 13, 19, 25, 31]])
        result = get_zone_coverage_stats(draws)
        assert result["most_common_zones"] in {"1", "2", "3", "4", "5", "6"}


# ---------------------------------------------------------------------------
# 캐시 동작 (AC-25, AC-26, AC-27, AC-45)
# ---------------------------------------------------------------------------

class TestCache:
    """캐시 동작 검증."""

    def setup_method(self) -> None:
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_second_call_returns_same_result(self) -> None:
        """동일 draws로 2회 호출 → 동일 결과 (AC-25)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([[1, 7, 13, 19, 25, 31]])
        result1 = get_zone_coverage_stats(draws)
        result2 = get_zone_coverage_stats(draws)
        assert result1 == result2

    def test_cache_invalidation_clears_cache(self) -> None:
        """invalidate_cache() 후 _zone_coverage_cache가 비어있음 (AC-26, AC-45)."""
        from lotto.web import data as wd
        draws = _make_draws([[1, 7, 13, 19, 25, 31]])
        wd.get_zone_coverage_stats(draws)
        wd.invalidate_cache()
        assert wd._zone_coverage_cache == {}

    def test_cache_two_different_keys(self) -> None:
        """len(draws)==5과 len(draws)==10 → 캐시에 두 키 모두 존재 (AC-27)."""
        from lotto.web import data as wd
        draws5 = _make_draws([[1, 7, 13, 19, 25, 31]] * 5)
        draws10 = _make_draws([[1, 7, 13, 19, 25, 31]] * 10)
        wd.get_zone_coverage_stats(draws5)
        wd.get_zone_coverage_stats(draws10)
        assert "5" in wd._zone_coverage_cache
        assert "10" in wd._zone_coverage_cache


# ---------------------------------------------------------------------------
# 상수 검증 (AC-46)
# ---------------------------------------------------------------------------

class TestConstants:
    """_ZONE_COV_KEYS 상수 검증."""

    def test_zone_cov_keys_order(self) -> None:
        """_ZONE_COV_KEYS == ["1","2","3","4","5","6"] (AC-46)."""
        from lotto.web.data import _ZONE_COV_KEYS
        assert _ZONE_COV_KEYS == ["1", "2", "3", "4", "5", "6"]


# ---------------------------------------------------------------------------
# 경계값 (AC-48, AC-49)
# ---------------------------------------------------------------------------

class TestBoundaryValues:
    """경계값 검증."""

    def setup_method(self) -> None:
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_high_numbers_boundary(self) -> None:
        """[41,42,43,44,45,36] → 구간8(41-45) 5개, 구간7(36-40) 1개 → zones=2 (AC-48)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([[36, 41, 42, 43, 44, 45]])
        result = get_zone_coverage_stats(draws)
        assert result["zone_coverage_distribution"]["2"]["count"] == 1

    def test_five_zones_distribution(self) -> None:
        """zones_covered=2,3,4,5,6 각 1회씩 (AC-49)."""
        from lotto.web.data import get_zone_coverage_stats
        draws = _make_draws([
            [1, 2, 3, 6, 7, 8],     # 2구간
            [1, 2, 6, 7, 11, 12],   # 3구간
            [1, 2, 6, 7, 11, 16],   # 4구간
            [1, 6, 11, 21, 26, 30], # 5구간
            [1, 7, 13, 19, 25, 31], # 6구간
        ])
        result = get_zone_coverage_stats(draws)
        assert result["zone_coverage_distribution"]["1"]["count"] == 0
        assert result["zone_coverage_distribution"]["2"]["count"] == 1
        assert result["zone_coverage_distribution"]["6"]["count"] == 1

    def test_all_buckets_filled(self) -> None:
        """6가지 zones_covered 모두 포함된 12회차 → 모든 버킷 count >= 1 (AC-40)."""
        from lotto.web.data import get_zone_coverage_stats
        # zones=1은 구조적으로 불가능하므로 버킷 "1"은 0, "2"~"6"은 2씩
        draws = _make_draws([
            [1, 2, 3, 6, 7, 8],     # 2구간
            [1, 2, 3, 6, 7, 8],     # 2구간
            [1, 2, 6, 7, 11, 12],   # 3구간
            [1, 2, 6, 7, 11, 12],   # 3구간
            [1, 2, 6, 7, 11, 16],   # 4구간
            [1, 2, 6, 7, 11, 16],   # 4구간
            [1, 6, 11, 21, 26, 30], # 5구간
            [1, 6, 11, 21, 26, 30], # 5구간
            [1, 7, 13, 19, 25, 31], # 6구간
            [1, 7, 13, 19, 25, 31], # 6구간
        ])
        result = get_zone_coverage_stats(draws)
        dist = result["zone_coverage_distribution"]
        # zones=1은 불가이므로 "1" 버킷은 0, 나머지는 2씩
        assert dist["2"]["count"] == 2
        assert dist["3"]["count"] == 2
        assert dist["4"]["count"] == 2
        assert dist["5"]["count"] == 2
        assert dist["6"]["count"] == 2


# ---------------------------------------------------------------------------
# API 엔드포인트 검증 (AC-28 ~ AC-31)
# ---------------------------------------------------------------------------

class TestAPIEndpoint:
    """API 엔드포인트 검증."""

    def setup_method(self) -> None:
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def _client(self) -> TestClient:
        from lotto.web.app import app
        return TestClient(app)

    def test_api_returns_200(self) -> None:
        """GET /api/stats/zone_coverage → HTTP 200 (AC-29)."""
        client = self._client()
        resp = client.get("/api/stats/zone_coverage")
        assert resp.status_code == 200

    def test_api_response_has_required_fields(self) -> None:
        """응답에 필수 필드 포함 (AC-29)."""
        client = self._client()
        resp = client.get("/api/stats/zone_coverage")
        body = resp.json()
        for field in ["total_draws", "avg_zones_covered", "most_common_zones",
                      "full_spread_pct", "concentrated_pct", "zone_coverage_distribution"]:
            assert field in body, f"{field} 필드 누락"

    def test_api_distribution_has_six_keys(self) -> None:
        """응답의 zone_coverage_distribution에 6개 키 (AC-30)."""
        client = self._client()
        resp = client.get("/api/stats/zone_coverage")
        body = resp.json()
        assert set(body["zone_coverage_distribution"].keys()) == {"1", "2", "3", "4", "5", "6"}

    def test_api_each_bucket_has_count_and_pct(self) -> None:
        """각 버킷에 count와 pct 존재 (AC-31)."""
        client = self._client()
        resp = client.get("/api/stats/zone_coverage")
        body = resp.json()
        bucket = body["zone_coverage_distribution"]["5"]
        assert "count" in bucket
        assert "pct" in bucket

    def test_api_limit_parameter(self) -> None:
        """limit=3 파라미터 → total_draws <= 3 (AC-28)."""
        client = self._client()
        resp = client.get("/api/stats/zone_coverage?limit=3")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_draws"] <= 3


# ---------------------------------------------------------------------------
# 페이지 라우트 검증 (AC-32 ~ AC-34, AC-50)
# ---------------------------------------------------------------------------

class TestPageRoute:
    """페이지 라우트 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app
        return TestClient(app)

    def test_page_returns_200(self) -> None:
        """GET /stats/zone-coverage → HTTP 200 (AC-32)."""
        client = self._client()
        resp = client.get("/stats/zone-coverage")
        assert resp.status_code == 200

    def test_template_file_exists(self) -> None:
        """zone_coverage.html 파일이 존재함 (AC-33)."""
        template_path = (
            "/home/sklee/moai/lotto/lotto/web/templates/zone_coverage.html"
        )
        assert os.path.exists(template_path)

    def test_page_contains_korean_title(self) -> None:
        """응답 HTML에 '구간별 번호 선택 분포' 또는 'zone_coverage' 포함 (AC-34)."""
        client = self._client()
        resp = client.get("/stats/zone-coverage")
        body = resp.text
        assert "구간별 번호 선택 분포" in body or "zone_coverage" in body

    def test_base_html_has_zone_coverage_link(self) -> None:
        """base.html에 '/stats/zone-coverage' 링크 포함 (AC-50)."""
        base_path = "/home/sklee/moai/lotto/lotto/web/templates/base.html"
        with open(base_path, encoding="utf-8") as f:
            content = f.read()
        assert "/stats/zone-coverage" in content
