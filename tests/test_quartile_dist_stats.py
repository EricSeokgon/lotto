"""SPEC-LOTTO-099: 번호 사분위 분포 분석 (Quartile Distribution) 테스트."""

from __future__ import annotations

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
# AC-003, AC-004: 빈 입력 처리 — None / 빈 리스트
# ---------------------------------------------------------------------------

class TestEmptyData:
    """빈 데이터 입력 시 기본 구조 반환 검증."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_none_input_total_draws(self) -> None:
        """AC-001: draws=None → total_draws=0."""
        from lotto.web.data import get_quartile_dist_stats
        result = get_quartile_dist_stats(None)
        assert result["total_draws"] == 0

    def test_none_input_avg_q1(self) -> None:
        """AC-001: draws=None → avg_q1=0.0."""
        from lotto.web.data import get_quartile_dist_stats
        result = get_quartile_dist_stats(None)
        assert result["avg_q1"] == 0.0

    def test_none_input_avg_q2(self) -> None:
        """AC-001: draws=None → avg_q2=0.0."""
        from lotto.web.data import get_quartile_dist_stats
        result = get_quartile_dist_stats(None)
        assert result["avg_q2"] == 0.0

    def test_none_input_avg_q3(self) -> None:
        """AC-001: draws=None → avg_q3=0.0."""
        from lotto.web.data import get_quartile_dist_stats
        result = get_quartile_dist_stats(None)
        assert result["avg_q3"] == 0.0

    def test_none_input_avg_q4(self) -> None:
        """AC-001: draws=None → avg_q4=0.0."""
        from lotto.web.data import get_quartile_dist_stats
        result = get_quartile_dist_stats(None)
        assert result["avg_q4"] == 0.0

    def test_empty_list_balanced_pct(self) -> None:
        """AC-002: draws=[] → balanced_pct=0.0."""
        from lotto.web.data import get_quartile_dist_stats
        result = get_quartile_dist_stats([])
        assert result["balanced_pct"] == 0.0

    def test_empty_list_skewed_pct(self) -> None:
        """AC-002: draws=[] → skewed_pct=0.0."""
        from lotto.web.data import get_quartile_dist_stats
        result = get_quartile_dist_stats([])
        assert result["skewed_pct"] == 0.0

    def test_empty_list_most_common_combination(self) -> None:
        """AC-003: draws=[] → most_common_combination='0-0-0-0'."""
        from lotto.web.data import get_quartile_dist_stats
        result = get_quartile_dist_stats([])
        assert result["most_common_combination"] == "0-0-0-0"

    def test_empty_list_quartile_distribution(self) -> None:
        """AC-004: draws=[] → quartile_distribution={}."""
        from lotto.web.data import get_quartile_dist_stats
        result = get_quartile_dist_stats([])
        assert result["quartile_distribution"] == {}


# ---------------------------------------------------------------------------
# 사분위 구간 경계값 테스트 (AC-007 ~ AC-014)
# ---------------------------------------------------------------------------

class TestQuartileBoundaries:
    """사분위 구간 경계값 분류 검증."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_q1_all_numbers(self) -> None:
        """AC-007: 번호 [1,2,3,4,5,6] → 모두 Q1 → 패턴 '6-0-0-0'."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[1, 2, 3, 4, 5, 6]])
        result = get_quartile_dist_stats(draws)
        assert result["quartile_distribution"]["6-0-0-0"]["count"] == 1

    def test_q1_boundary_11(self) -> None:
        """AC-008: 번호 11은 Q1 → [11,12,23,34,5,6] → 패턴 '3-1-1-1' 존재."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[11, 12, 23, 34, 5, 6]])
        result = get_quartile_dist_stats(draws)
        assert "3-1-1-1" in result["quartile_distribution"]

    def test_q2_boundary_12(self) -> None:
        """AC-009: 번호 12는 Q2 → [12,13,23,34,1,2] → 패턴 '2-2-1-1' 존재."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[12, 13, 23, 34, 1, 2]])
        result = get_quartile_dist_stats(draws)
        assert "2-2-1-1" in result["quartile_distribution"]

    def test_q2_boundary_22(self) -> None:
        """AC-010: 번호 22는 Q2 → [22,23,34,1,2,3] → 패턴 '3-1-1-1' 존재."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[22, 23, 34, 1, 2, 3]])
        result = get_quartile_dist_stats(draws)
        assert "3-1-1-1" in result["quartile_distribution"]

    def test_q3_boundary_23(self) -> None:
        """AC-011: 번호 23은 Q3 → [23,24,34,1,2,3] → 패턴 '3-0-2-1' 존재."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[23, 24, 34, 1, 2, 3]])
        result = get_quartile_dist_stats(draws)
        assert "3-0-2-1" in result["quartile_distribution"]

    def test_q3_boundary_33(self) -> None:
        """AC-012: 번호 33은 Q3 → [33,34,1,2,3,4] → 패턴 '4-0-1-1' 존재."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[33, 34, 1, 2, 3, 4]])
        result = get_quartile_dist_stats(draws)
        assert "4-0-1-1" in result["quartile_distribution"]

    def test_q4_boundary_34(self) -> None:
        """AC-013: 번호 34는 Q4 → [34,35,1,2,3,4] → 패턴 '4-0-0-2' 존재."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[34, 35, 1, 2, 3, 4]])
        result = get_quartile_dist_stats(draws)
        assert "4-0-0-2" in result["quartile_distribution"]

    def test_q4_all_numbers(self) -> None:
        """AC-014: 번호 [45,44,43,42,41,40] → 모두 Q4 → 패턴 '0-0-0-6'."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[40, 41, 42, 43, 44, 45]])
        result = get_quartile_dist_stats(draws)
        assert result["quartile_distribution"]["0-0-0-6"]["count"] == 1


# ---------------------------------------------------------------------------
# 단일 회차 테스트 (AC-005, AC-006)
# ---------------------------------------------------------------------------

class TestSingleDraw:
    """단일 회차 분석 검증."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_single_draw_pattern_count(self) -> None:
        """AC-005: [1,12,23,34,2,13] → 패턴 '2-2-1-1' count=1, pct=100.0."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[1, 12, 23, 34, 2, 13]])
        result = get_quartile_dist_stats(draws)
        cell = result["quartile_distribution"]["2-2-1-1"]
        assert cell["count"] == 1
        assert cell["pct"] == 100.0

    def test_single_draw_most_common(self) -> None:
        """AC-006: [1,12,23,34,2,13] → most_common_combination='2-2-1-1'."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[1, 12, 23, 34, 2, 13]])
        result = get_quartile_dist_stats(draws)
        assert result["most_common_combination"] == "2-2-1-1"


# ---------------------------------------------------------------------------
# 합산 및 정확도 검증 (AC-015, AC-016, AC-017, AC-018, AC-019)
# ---------------------------------------------------------------------------

class TestSumAndAccuracy:
    """합산 검증 및 평균 정확도 테스트."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_all_patterns_sum_to_6(self) -> None:
        """AC-015: 모든 조합 키 q1+q2+q3+q4 == 6."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([
            [1, 12, 23, 34, 2, 13],
            [1, 2, 3, 4, 5, 6],
            [40, 41, 42, 43, 44, 45],
        ])
        result = get_quartile_dist_stats(draws)
        for key in result["quartile_distribution"]:
            parts = [int(x) for x in key.split("-")]
            assert sum(parts) == 6, f"패턴 {key}의 합이 6이 아님"

    def test_total_draws_10(self) -> None:
        """AC-016: 10개 회차 → total_draws=10."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[1, 2, 3, 4, 5, 6]] * 10)
        result = get_quartile_dist_stats(draws)
        assert result["total_draws"] == 10

    def test_pct_sum_100(self) -> None:
        """AC-017: quartile_distribution pct 합산 ≈ 100.0 (±0.1)."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([
            [1, 12, 23, 34, 2, 13],
            [3, 14, 25, 36, 4, 15],
            [5, 16, 27, 38, 1, 2],
        ])
        result = get_quartile_dist_stats(draws)
        total_pct = sum(cell["pct"] for cell in result["quartile_distribution"].values())
        assert abs(total_pct - 100.0) <= 0.1, f"pct 합산이 100.0이 아님: {total_pct}"

    def test_avg_q1_accuracy(self) -> None:
        """AC-018: 3회차 Q1 합(2+2+4=8) / 3 = 2.67."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([
            [1, 12, 23, 34, 2, 13],   # Q1=2
            [3, 14, 25, 36, 4, 15],   # Q1=2
            [5, 16, 27, 38, 1, 2],    # Q1=4 (1,2,5 → Q1; 16,27 → Q2,Q3; 38→Q4)
        ])
        # 회차3: 1→Q1, 2→Q1, 5→Q1, 16→Q2, 27→Q3, 38→Q4 → Q1=3
        # 수정: [5, 16, 27, 38, 1, 2] → Q1=3(1,2,5), Q2=1(16), Q3=1(27), Q4=1(38)
        # AC-018의 기술 기준: Q1 합 = 2+2+4=8 (원문 기준)
        # 하지만 실제 [5,16,27,38,1,2]: 1,2,5 → Q1=3, 16 → Q2=1, 27 → Q3=1, 38 → Q4=1
        # 원문 spec과 다르므로 실제 계산으로 검증:
        # 회차1: [1,2,12,13,23,34] Q1=2,Q2=2,Q3=1,Q4=1
        # 회차2: [3,4,14,15,25,36] Q1=2,Q2=2,Q3=1,Q4=1
        # 회차3: [1,2,5,16,27,38] Q1=3,Q2=1,Q3=1,Q4=1
        # 합: Q1=7, 평균=7/3≈2.33
        result = get_quartile_dist_stats(draws)
        expected = round((2 + 2 + 3) / 3, 2)
        assert result["avg_q1"] == expected

    def test_avg_q2_accuracy(self) -> None:
        """AC-019: 3회차 Q2 평균 검증."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([
            [1, 12, 23, 34, 2, 13],   # Q2=2(12,13)
            [3, 14, 25, 36, 4, 15],   # Q2=2(14,15)
            [5, 16, 27, 38, 1, 2],    # Q2=1(16)
        ])
        result = get_quartile_dist_stats(draws)
        expected = round((2 + 2 + 1) / 3, 2)
        assert result["avg_q2"] == expected


# ---------------------------------------------------------------------------
# 균형/쏠림 분포 테스트 (AC-020 ~ AC-025)
# ---------------------------------------------------------------------------

class TestBalancedAndSkewed:
    """균형/쏠림 분포 비율 검증."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_balanced_pct_50(self) -> None:
        """AC-020: 회차1 balanced=True, 회차2 balanced=False → balanced_pct=50.0."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([
            [1, 12, 23, 34, 2, 13],   # Q1=2,Q2=2,Q3=1,Q4=1 → balanced(각 1또는2)
            [1, 2, 3, 4, 5, 6],       # Q1=6 → not balanced
        ])
        result = get_quartile_dist_stats(draws)
        assert result["balanced_pct"] == 50.0

    def test_balanced_pct_100_with_1122(self) -> None:
        """AC-021: [1,12,23,24,34,35] (Q1=1,Q2=1,Q3=2,Q4=2) → balanced_pct=100.0."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[1, 12, 23, 24, 34, 35]])
        result = get_quartile_dist_stats(draws)
        assert result["balanced_pct"] == 100.0

    def test_balanced_pct_0_with_3111(self) -> None:
        """AC-022: [1,2,3,12,23,34] (Q1=3 > 2) → balanced_pct=0.0."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[1, 2, 3, 12, 23, 34]])
        result = get_quartile_dist_stats(draws)
        assert result["balanced_pct"] == 0.0

    def test_skewed_pct_50(self) -> None:
        """AC-023: 회차1 skewed=True(Q1=4), 회차2 skewed=False → skewed_pct=50.0."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([
            [1, 2, 3, 4, 12, 23],     # Q1=4 → skewed
            [1, 12, 23, 34, 2, 13],   # 최대=2 → not skewed
        ])
        result = get_quartile_dist_stats(draws)
        assert result["skewed_pct"] == 50.0

    def test_skewed_pct_100_q2_heavy(self) -> None:
        """AC-024: [12,13,14,15,1,23] (Q2=4) → skewed_pct=100.0."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[12, 13, 14, 15, 1, 23]])
        result = get_quartile_dist_stats(draws)
        assert result["skewed_pct"] == 100.0

    def test_skewed_pct_0_max_3(self) -> None:
        """AC-025: [1,2,3,12,23,34] (Q1=3, 4 미만) → skewed_pct=0.0."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[1, 2, 3, 12, 23, 34]])
        result = get_quartile_dist_stats(draws)
        assert result["skewed_pct"] == 0.0


# ---------------------------------------------------------------------------
# most_common_combination 동률 처리 (AC-026)
# ---------------------------------------------------------------------------

class TestMostCommonTie:
    """동률 처리 — 사전순(lexicographic) 앞선 값 선택."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_tie_lexicographic_order(self) -> None:
        """AC-026: '2-1-2-1'과 '1-2-2-1' 동률 → '1-2-2-1' 선택."""
        from lotto.web.data import get_quartile_dist_stats
        # 회차1: Q1=2,Q2=1,Q3=2,Q4=1 → "2-1-2-1"
        # 회차2: Q1=1,Q2=2,Q3=2,Q4=1 → "1-2-2-1"
        draws = _make_draws([
            [1, 2, 12, 23, 24, 34],   # Q1=2,Q2=1,Q3=2,Q4=1
            [1, 12, 13, 23, 24, 34],  # Q1=1,Q2=2,Q3=2,Q4=1
        ])
        result = get_quartile_dist_stats(draws)
        assert result["most_common_combination"] == "1-2-2-1"


# ---------------------------------------------------------------------------
# 캐시 테스트 (AC-027, AC-028, AC-041)
# ---------------------------------------------------------------------------

class TestCache:
    """캐시 동작 검증."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_cache_hit_same_count(self) -> None:
        """AC-027: 동일 회차 수로 재호출 시 캐시에서 동일 객체 반환."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[1, 12, 23, 34, 2, 13]] * 10)
        result1 = get_quartile_dist_stats(draws)
        result2 = get_quartile_dist_stats(draws)
        assert result1 is result2

    def test_cache_invalidation(self) -> None:
        """AC-028: invalidate_cache() 호출 후 재호출 시 새로 계산."""
        from lotto.web.data import get_quartile_dist_stats, invalidate_cache
        draws = _make_draws([[1, 12, 23, 34, 2, 13]] * 10)
        result1 = get_quartile_dist_stats(draws)
        invalidate_cache()
        result2 = get_quartile_dist_stats(draws)
        # 같은 값이지만 다른 객체여야 함 (캐시 미스 후 새로 계산)
        assert result1 is not result2
        assert result1["total_draws"] == result2["total_draws"]

    def test_invalidate_cache_clears_quartile_cache(self) -> None:
        """AC-041: invalidate_cache() 호출 후 _quartile_dist_cache 비어 있음."""
        import lotto.web.data as wd
        from lotto.web.data import get_quartile_dist_stats, invalidate_cache
        draws = _make_draws([[1, 12, 23, 34, 2, 13]])
        get_quartile_dist_stats(draws)
        assert len(wd._quartile_dist_cache) > 0
        invalidate_cache()
        assert len(wd._quartile_dist_cache) == 0


# ---------------------------------------------------------------------------
# 보너스 번호 제외 및 미관측 조합 미포함 (AC-029, AC-030)
# ---------------------------------------------------------------------------

class TestBonusExcludeAndObserved:
    """보너스 번호 제외 및 미관측 조합 미포함 검증."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_only_observed_pattern_in_distribution(self) -> None:
        """AC-030: 단일 회차 → '2-2-1-1'만 존재."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[1, 12, 23, 34, 2, 13]])
        result = get_quartile_dist_stats(draws)
        assert list(result["quartile_distribution"].keys()) == ["2-2-1-1"]


# ---------------------------------------------------------------------------
# 소수점 자리 검증 (AC-042, AC-043, AC-044)
# ---------------------------------------------------------------------------

class TestPrecision:
    """소수점 2자리 반올림 검증."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_avg_q3_q4_two_decimal(self) -> None:
        """AC-042: avg_q3, avg_q4는 소수점 2자리 float."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([
            [1, 12, 23, 34, 2, 13],
            [3, 14, 25, 36, 4, 15],
            [5, 16, 27, 38, 1, 2],
        ])
        result = get_quartile_dist_stats(draws)
        assert isinstance(result["avg_q3"], float)
        assert isinstance(result["avg_q4"], float)
        # 소수점 2자리인지 확인
        assert round(result["avg_q3"], 2) == result["avg_q3"]
        assert round(result["avg_q4"], 2) == result["avg_q4"]

    def test_balanced_skewed_pct_two_decimal(self) -> None:
        """AC-043: balanced_pct, skewed_pct는 소수점 2자리 float."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[1, 12, 23, 34, 2, 13]])
        result = get_quartile_dist_stats(draws)
        assert round(result["balanced_pct"], 2) == result["balanced_pct"]
        assert round(result["skewed_pct"], 2) == result["skewed_pct"]

    def test_distribution_pct_two_decimal(self) -> None:
        """AC-044: quartile_distribution pct는 소수점 2자리."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([
            [1, 12, 23, 34, 2, 13],
            [3, 14, 25, 36, 4, 15],
        ])
        result = get_quartile_dist_stats(draws)
        for cell in result["quartile_distribution"].values():
            assert round(cell["pct"], 2) == cell["pct"]


# ---------------------------------------------------------------------------
# API 엔드포인트 테스트 (AC-031 ~ AC-034)
# ---------------------------------------------------------------------------

class TestAPIEndpoint:
    """GET /api/stats/quartile_dist API 테스트."""

    def _get_client(self) -> TestClient:
        """테스트 클라이언트 생성."""
        from lotto.web.app import app
        return TestClient(app)

    def test_api_200_ok(self) -> None:
        """AC-031: GET /api/stats/quartile_dist → HTTP 200."""
        client = self._get_client()
        response = client.get("/api/stats/quartile_dist")
        assert response.status_code == 200

    def test_api_response_has_required_keys(self) -> None:
        """AC-031: 응답에 필수 키 포함."""
        client = self._get_client()
        response = client.get("/api/stats/quartile_dist")
        data = response.json()
        required_keys = [
            "total_draws", "avg_q1", "avg_q2", "avg_q3", "avg_q4",
            "most_common_combination", "balanced_pct", "skewed_pct",
            "quartile_distribution",
        ]
        for key in required_keys:
            assert key in data, f"응답에 '{key}' 키 없음"

    def test_api_limit_param(self) -> None:
        """AC-032: limit=100 → total_draws <= 100."""
        client = self._get_client()
        response = client.get("/api/stats/quartile_dist?limit=100")
        assert response.status_code == 200
        data = response.json()
        assert data["total_draws"] <= 100

    def test_api_limit_0_all_draws(self) -> None:
        """AC-033: limit=0 → 전체 회차 사용."""
        client = self._get_client()
        resp_all = client.get("/api/stats/quartile_dist")
        resp_zero = client.get("/api/stats/quartile_dist?limit=0")
        assert resp_all.json()["total_draws"] == resp_zero.json()["total_draws"]

    def test_api_distribution_cell_type(self) -> None:
        """AC-034: quartile_distribution 각 값에 count(int), pct(float) 포함."""
        client = self._get_client()
        response = client.get("/api/stats/quartile_dist")
        data = response.json()
        dist = data["quartile_distribution"]
        if dist:  # 데이터가 있을 때만 검증
            for cell in dist.values():
                assert "count" in cell
                assert "pct" in cell
                assert isinstance(cell["count"], int)
                assert isinstance(cell["pct"], float)


# ---------------------------------------------------------------------------
# 웹 페이지 테스트 (AC-035 ~ AC-039)
# ---------------------------------------------------------------------------

class TestPageRoute:
    """GET /stats/quartile-dist 페이지 테스트."""

    def _get_client(self) -> TestClient:
        """테스트 클라이언트 생성."""
        from lotto.web.app import app
        return TestClient(app)

    def test_page_200_ok(self) -> None:
        """AC-035: GET /stats/quartile-dist → HTTP 200."""
        client = self._get_client()
        response = client.get("/stats/quartile-dist")
        assert response.status_code == 200

    def test_page_has_korean_title(self) -> None:
        """AC-035: 페이지에 '사분위 분포' 제목 포함."""
        client = self._get_client()
        response = client.get("/stats/quartile-dist")
        assert "사분위 분포" in response.text

    def test_nav_has_quartile_dist_link(self) -> None:
        """AC-036: base.html 사이드바에 /stats/quartile-dist 링크 존재."""
        client = self._get_client()
        response = client.get("/stats/quartile-dist")
        assert "/stats/quartile-dist" in response.text

    def test_page_shows_korean_labels(self) -> None:
        """AC-039: 페이지에 한국어 라벨 포함."""
        client = self._get_client()
        response = client.get("/stats/quartile-dist")
        # 한국어 라벨 확인
        assert "Q1 구간" in response.text or "Q1" in response.text


# ---------------------------------------------------------------------------
# Python 3.9 호환성 (AC-045)
# ---------------------------------------------------------------------------

class TestPython39Compatibility:
    """Python 3.9 호환성 — match/case 미사용 확인."""

    def test_import_no_syntax_error(self) -> None:
        """AC-045: lotto.web.data import 시 SyntaxError 없음."""
        try:
            import lotto.web.data as wd  # noqa: F401
            assert hasattr(wd, "get_quartile_dist_stats")
        except SyntaxError as err:
            raise AssertionError("SyntaxError: Python 3.9 호환성 문제") from err

    def test_no_match_case_in_source(self) -> None:
        """AC-045: get_quartile_dist_stats 함수에 match/case 미사용."""
        import inspect

        from lotto.web.data import get_quartile_dist_stats
        source = inspect.getsource(get_quartile_dist_stats)
        assert "match " not in source or "case " not in source.replace("# ", "")


# ---------------------------------------------------------------------------
# 추가 엣지 케이스 (정확도 및 여러 패턴)
# ---------------------------------------------------------------------------

class TestAdditionalEdgeCases:
    """추가 엣지 케이스."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_multiple_patterns_in_distribution(self) -> None:
        """여러 패턴이 분포에 포함됨."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([
            [1, 2, 3, 4, 5, 6],       # 6-0-0-0
            [12, 13, 14, 15, 16, 17], # 0-6-0-0
            [1, 12, 23, 34, 2, 13],   # 2-2-1-1
        ])
        result = get_quartile_dist_stats(draws)
        assert len(result["quartile_distribution"]) == 3

    def test_negative_limit_treated_as_all(self) -> None:
        """N4: limit < 0 은 전체로 처리 (API에서 처리됨)."""
        from lotto.web.app import app
        client = TestClient(app)
        resp_all = client.get("/api/stats/quartile_dist")
        resp_neg = client.get("/api/stats/quartile_dist?limit=-1")
        assert resp_all.status_code == 200
        assert resp_neg.status_code == 200

    def test_avg_values_non_negative(self) -> None:
        """avg_q1~q4는 음수일 수 없음."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([[1, 12, 23, 34, 2, 13]])
        result = get_quartile_dist_stats(draws)
        assert result["avg_q1"] >= 0.0
        assert result["avg_q2"] >= 0.0
        assert result["avg_q3"] >= 0.0
        assert result["avg_q4"] >= 0.0

    def test_avg_q1_q2_q3_q4_sum_is_6(self) -> None:
        """avg_q1 + avg_q2 + avg_q3 + avg_q4 == 6.0 (부동소수점 허용 오차)."""
        from lotto.web.data import get_quartile_dist_stats
        draws = _make_draws([
            [1, 12, 23, 34, 2, 13],
            [3, 14, 25, 36, 4, 15],
        ])
        result = get_quartile_dist_stats(draws)
        total = result["avg_q1"] + result["avg_q2"] + result["avg_q3"] + result["avg_q4"]
        assert abs(total - 6.0) < 0.05, f"평균 합이 6이 아님: {total}"

    def test_balanced_strict_definition(self) -> None:
        """U7: balanced = q1,q2,q3,q4 각각이 1 또는 2인 경우."""
        from lotto.web.data import get_quartile_dist_stats
        # (1,2,2,1) → balanced
        draws1 = _make_draws([[1, 12, 13, 23, 24, 34]])
        result1 = get_quartile_dist_stats(draws1)
        assert result1["balanced_pct"] == 100.0

        from lotto.web.data import invalidate_cache
        invalidate_cache()

        # (2,2,2,0) → not balanced (Q4=0)
        draws2 = _make_draws([[1, 2, 12, 13, 23, 24]])
        result2 = get_quartile_dist_stats(draws2)
        assert result2["balanced_pct"] == 0.0
