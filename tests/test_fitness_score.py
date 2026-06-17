"""SPEC-LOTTO-100: 번호 조합 적합도 점수(Fitness Score) 테스트."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
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


# 테스트용 표준 회차 데이터 (총 100회차)
_STANDARD_DRAWS = _make_draws([
    [1, 2, 3, 4, 5, 6],
    [7, 8, 9, 10, 11, 12],
    [13, 14, 15, 16, 17, 18],
    [19, 20, 21, 22, 23, 24],
    [25, 26, 27, 28, 29, 30],
    [31, 32, 33, 34, 35, 36],
    [37, 38, 39, 40, 41, 42],
    [1, 7, 14, 21, 28, 35],
    [2, 9, 16, 23, 30, 37],
    [3, 10, 17, 24, 31, 38],
    [4, 11, 18, 25, 32, 39],
    [5, 12, 19, 26, 33, 40],
    [6, 13, 20, 27, 34, 41],
    [1, 8, 15, 22, 29, 36],
    [2, 10, 18, 26, 34, 42],
    [3, 11, 19, 27, 35, 43],
    [4, 12, 20, 28, 36, 44],
    [5, 13, 21, 29, 37, 45],
    [6, 14, 22, 30, 38, 43],
    [7, 15, 23, 31, 39, 44],
    [8, 16, 24, 32, 40, 45],
    [9, 17, 25, 33, 41, 43],
    [10, 18, 26, 34, 42, 44],
    [11, 19, 27, 35, 43, 45],
    [12, 20, 28, 36, 44, 1],
    [13, 21, 29, 37, 45, 2],
    [14, 22, 30, 38, 1, 3],
    [15, 23, 31, 39, 2, 4],
    [16, 24, 32, 40, 3, 5],
    [17, 25, 33, 41, 4, 6],
    [18, 26, 34, 42, 5, 7],
    [19, 27, 35, 43, 6, 8],
    [20, 28, 36, 44, 7, 9],
    [21, 29, 37, 45, 8, 10],
    [22, 30, 38, 1, 9, 11],
    [23, 31, 39, 2, 10, 12],
    [24, 32, 40, 3, 11, 13],
    [25, 33, 41, 4, 12, 14],
    [26, 34, 42, 5, 13, 15],
    [27, 35, 43, 6, 14, 16],
    [28, 36, 44, 7, 15, 17],
    [29, 37, 45, 8, 16, 18],
    [30, 38, 1, 9, 17, 19],
    [31, 39, 2, 10, 18, 20],
    [32, 40, 3, 11, 19, 21],
    [33, 41, 4, 12, 20, 22],
    [34, 42, 5, 13, 21, 23],
    [35, 43, 6, 14, 22, 24],
    [36, 44, 7, 15, 23, 25],
    [37, 45, 8, 16, 24, 26],
    [38, 1, 9, 17, 25, 27],
    [39, 2, 10, 18, 26, 28],
    [40, 3, 11, 19, 27, 29],
    [41, 4, 12, 20, 28, 30],
    [42, 5, 13, 21, 29, 31],
    [43, 6, 14, 22, 30, 32],
    [44, 7, 15, 23, 31, 33],
    [45, 8, 16, 24, 32, 34],
    [1, 10, 19, 28, 37, 45],
    [2, 11, 20, 29, 38, 44],
    [3, 12, 21, 30, 39, 43],
    [4, 13, 22, 31, 40, 42],
    [5, 14, 23, 32, 41, 45],
    [6, 15, 24, 33, 42, 44],
    [7, 16, 25, 34, 43, 1],
    [8, 17, 26, 35, 44, 2],
    [9, 18, 27, 36, 45, 3],
    [10, 19, 28, 37, 1, 4],
    [11, 20, 29, 38, 2, 5],
    [12, 21, 30, 39, 3, 6],
    [13, 22, 31, 40, 4, 7],
    [14, 23, 32, 41, 5, 8],
    [15, 24, 33, 42, 6, 9],
    [16, 25, 34, 43, 7, 10],
    [17, 26, 35, 44, 8, 11],
    [18, 27, 36, 45, 9, 12],
    [19, 28, 37, 1, 10, 13],
    [20, 29, 38, 2, 11, 14],
    [21, 30, 39, 3, 12, 15],
    [22, 31, 40, 4, 13, 16],
    [23, 32, 41, 5, 14, 17],
    [24, 33, 42, 6, 15, 18],
    [25, 34, 43, 7, 16, 19],
    [26, 35, 44, 8, 17, 20],
    [27, 36, 45, 9, 18, 21],
    [28, 37, 1, 10, 19, 22],
    [29, 38, 2, 11, 20, 23],
    [30, 39, 3, 12, 21, 24],
    [31, 40, 4, 13, 22, 25],
    [32, 41, 5, 14, 23, 26],
    [33, 42, 6, 15, 24, 27],
    [34, 43, 7, 16, 25, 28],
    [35, 44, 8, 17, 26, 29],
    [36, 45, 9, 18, 27, 30],
    [37, 1, 10, 19, 28, 31],
    [38, 2, 11, 20, 29, 32],
    [39, 3, 12, 21, 30, 33],
    [40, 4, 13, 22, 31, 34],
    [41, 5, 14, 23, 32, 35],
    [42, 6, 15, 24, 33, 36],
    [43, 7, 16, 25, 34, 37],
])


class TestFitnessScoreBasic:
    """기본 적합도 점수 계산 검증."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_get_fitness_score_valid_numbers(self) -> None:
        """정상 번호 6개 입력 시 0~100 점수 반환."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([1, 7, 14, 21, 35, 42], _STANDARD_DRAWS)
        assert "fitness_score" in result
        assert 0.0 <= result["fitness_score"] <= 100.0

    def test_get_fitness_score_returns_dict_with_required_keys(self) -> None:
        """반환 딕셔너리에 필수 키 포함 여부 검증."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([3, 11, 22, 30, 37, 44], _STANDARD_DRAWS)
        assert "numbers" in result
        assert "fitness_score" in result
        assert "grade" in result
        assert "disclaimer" in result
        assert "breakdown" in result

    def test_get_fitness_score_numbers_preserved(self) -> None:
        """반환 결과에 입력 번호가 그대로 포함되어야 한다."""
        from lotto.web.data import get_fitness_score
        nums = [5, 12, 19, 28, 36, 43]
        result = get_fitness_score(nums, _STANDARD_DRAWS)
        assert sorted(result["numbers"]) == sorted(nums)

    def test_get_fitness_score_empty_draws(self) -> None:
        """빈 draws 입력 시 점수 0.0 반환."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([1, 7, 14, 21, 35, 42], [])
        assert result["fitness_score"] == 0.0

    def test_get_fitness_score_none_draws(self) -> None:
        """None draws 입력 시 점수 0.0 반환."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([1, 7, 14, 21, 35, 42], None)
        assert result["fitness_score"] == 0.0

    def test_get_fitness_score_breakdown_has_15_items(self) -> None:
        """breakdown에 15개 항목이 있어야 한다."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([2, 9, 17, 25, 33, 41], _STANDARD_DRAWS)
        assert len(result["breakdown"]) == 15

    def test_get_fitness_score_breakdown_has_expected_keys(self) -> None:
        """breakdown 각 항목에 name, pct, label 키가 있어야 한다."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([4, 11, 19, 28, 36, 44], _STANDARD_DRAWS)
        for item in result["breakdown"]:
            assert "name" in item
            assert "pct" in item
            assert "label" in item

    def test_get_fitness_score_breakdown_pct_range(self) -> None:
        """breakdown 각 항목의 pct는 0.0~100.0 범위여야 한다."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([6, 13, 21, 29, 37, 45], _STANDARD_DRAWS)
        for item in result["breakdown"]:
            assert 0.0 <= item["pct"] <= 100.0

    def test_get_fitness_score_breakdown_contains_stat_names(self) -> None:
        """breakdown에 15개 통계 항목 이름이 포함되어야 한다."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([1, 9, 18, 27, 36, 45], _STANDARD_DRAWS)
        names = [item["name"] for item in result["breakdown"]]
        expected_names = [
            "odd_even", "high_low", "total_sum", "span", "consecutive",
            "ac_value", "quartile", "zone_coverage", "min_gap", "gap_median",
            "prime", "last_digit_sum", "sum_last_digit", "consecutive_pairs",
            "ac_value_dist",
        ]
        for name in expected_names:
            assert name in names, f"통계 항목 '{name}'이 breakdown에 없습니다."

    def test_get_fitness_score_disclaimer_is_string(self) -> None:
        """disclaimer가 비어있지 않은 문자열이어야 한다."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([2, 8, 16, 24, 32, 40], _STANDARD_DRAWS)
        assert isinstance(result["disclaimer"], str)
        assert len(result["disclaimer"]) > 0


class TestFitnessScoreGrades:
    """등급 판정 검증."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_grade_s_when_score_80_or_above(self) -> None:
        """점수 80 이상이면 S 등급."""
        from lotto.web.data import _get_fitness_grade
        assert _get_fitness_grade(80.0) == "S"
        assert _get_fitness_grade(95.5) == "S"
        assert _get_fitness_grade(100.0) == "S"

    def test_grade_a_when_score_60_to_79(self) -> None:
        """점수 60~79이면 A 등급."""
        from lotto.web.data import _get_fitness_grade
        assert _get_fitness_grade(60.0) == "A"
        assert _get_fitness_grade(75.0) == "A"
        assert _get_fitness_grade(79.9) == "A"

    def test_grade_b_when_score_40_to_59(self) -> None:
        """점수 40~59이면 B 등급."""
        from lotto.web.data import _get_fitness_grade
        assert _get_fitness_grade(40.0) == "B"
        assert _get_fitness_grade(55.0) == "B"
        assert _get_fitness_grade(59.9) == "B"

    def test_grade_c_when_score_20_to_39(self) -> None:
        """점수 20~39이면 C 등급."""
        from lotto.web.data import _get_fitness_grade
        assert _get_fitness_grade(20.0) == "C"
        assert _get_fitness_grade(30.0) == "C"
        assert _get_fitness_grade(39.9) == "C"

    def test_grade_d_when_score_below_20(self) -> None:
        """점수 20 미만이면 D 등급."""
        from lotto.web.data import _get_fitness_grade
        assert _get_fitness_grade(0.0) == "D"
        assert _get_fitness_grade(10.0) == "D"
        assert _get_fitness_grade(19.9) == "D"

    def test_grade_in_result(self) -> None:
        """get_fitness_score 반환값에 grade 필드가 있어야 한다."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([1, 7, 14, 21, 35, 42], _STANDARD_DRAWS)
        assert result["grade"] in ("S", "A", "B", "C", "D")

    def test_grade_matches_score(self) -> None:
        """grade가 fitness_score에 대응해야 한다."""
        from lotto.web.data import _get_fitness_grade, get_fitness_score
        result = get_fitness_score([3, 12, 22, 31, 38, 44], _STANDARD_DRAWS)
        assert result["grade"] == _get_fitness_grade(result["fitness_score"])


class TestFitnessScoreValidation:
    """입력 유효성 검증 — 잘못된 입력 시 ValueError 발생."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_validation_wrong_count_5(self) -> None:
        """5개 번호 입력 시 ValueError."""
        from lotto.web.data import get_fitness_score
        with pytest.raises(ValueError, match="6개"):
            get_fitness_score([1, 2, 3, 4, 5], _STANDARD_DRAWS)

    def test_validation_wrong_count_7(self) -> None:
        """7개 번호 입력 시 ValueError."""
        from lotto.web.data import get_fitness_score
        with pytest.raises(ValueError, match="6개"):
            get_fitness_score([1, 2, 3, 4, 5, 6, 7], _STANDARD_DRAWS)

    def test_validation_empty_list(self) -> None:
        """빈 리스트 입력 시 ValueError."""
        from lotto.web.data import get_fitness_score
        with pytest.raises(ValueError):
            get_fitness_score([], _STANDARD_DRAWS)

    def test_validation_number_out_of_range_low(self) -> None:
        """0 이하 번호 포함 시 ValueError."""
        from lotto.web.data import get_fitness_score
        with pytest.raises(ValueError, match="1~45"):
            get_fitness_score([0, 2, 3, 4, 5, 6], _STANDARD_DRAWS)

    def test_validation_number_out_of_range_high(self) -> None:
        """46 이상 번호 포함 시 ValueError."""
        from lotto.web.data import get_fitness_score
        with pytest.raises(ValueError, match="1~45"):
            get_fitness_score([1, 2, 3, 4, 5, 46], _STANDARD_DRAWS)

    def test_validation_duplicate_numbers(self) -> None:
        """중복 번호 포함 시 ValueError."""
        from lotto.web.data import get_fitness_score
        with pytest.raises(ValueError, match="중복"):
            get_fitness_score([1, 1, 3, 4, 5, 6], _STANDARD_DRAWS)

    def test_validation_boundary_1(self) -> None:
        """경계값 1은 유효하다."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([1, 7, 14, 21, 35, 42], _STANDARD_DRAWS)
        assert result["fitness_score"] >= 0.0

    def test_validation_boundary_45(self) -> None:
        """경계값 45는 유효하다."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([2, 9, 18, 27, 36, 45], _STANDARD_DRAWS)
        assert result["fitness_score"] >= 0.0


class TestFitnessScoreAlgorithm:
    """점수 계산 알고리즘 검증."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_score_is_average_of_15_pcts(self) -> None:
        """점수는 15개 통계 pct의 평균이어야 한다."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([3, 11, 22, 30, 37, 44], _STANDARD_DRAWS)
        pcts = [item["pct"] for item in result["breakdown"]]
        expected_avg = round(sum(pcts) / len(pcts), 2)
        assert result["fitness_score"] == expected_avg

    def test_score_rounded_to_2_decimal(self) -> None:
        """점수는 소수 2자리로 반올림된 float이어야 한다."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([5, 12, 21, 30, 38, 45], _STANDARD_DRAWS)
        score = result["fitness_score"]
        assert isinstance(score, float)
        assert score == round(score, 2)

    def test_score_is_float_type(self) -> None:
        """fitness_score가 float 타입이어야 한다."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([1, 8, 17, 26, 35, 44], _STANDARD_DRAWS)
        assert isinstance(result["fitness_score"], float)

    def test_different_numbers_may_give_different_scores(self) -> None:
        """다른 번호 조합은 서로 다른 점수를 가질 수 있다."""
        from lotto.web.data import get_fitness_score
        result1 = get_fitness_score([1, 2, 3, 4, 5, 6], _STANDARD_DRAWS)
        result2 = get_fitness_score([10, 20, 30, 40, 43, 45], _STANDARD_DRAWS)
        # 점수가 반드시 다를 필요는 없지만 타입/범위는 유효해야 함
        assert 0.0 <= result1["fitness_score"] <= 100.0
        assert 0.0 <= result2["fitness_score"] <= 100.0


class TestFitnessScoreAPIRoute:
    """API 엔드포인트 /api/stats/fitness 검증."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_api_fitness_200_with_valid_numbers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """유효한 numbers 파라미터 전달 시 200 반환."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/api/stats/fitness?numbers=1,7,14,21,35,42")
        assert resp.status_code == 200

    def test_api_fitness_response_has_required_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """응답 JSON에 필수 키 포함 여부 검증."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/api/stats/fitness?numbers=1,7,14,21,35,42")
        data = resp.json()
        assert "fitness_score" in data
        assert "grade" in data
        assert "breakdown" in data
        assert "numbers" in data

    def test_api_fitness_400_wrong_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """번호 5개 입력 시 400 반환."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/api/stats/fitness?numbers=1,2,3,4,5")
        assert resp.status_code == 400

    def test_api_fitness_400_out_of_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """범위 밖 번호 입력 시 400 반환."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/api/stats/fitness?numbers=0,7,14,21,35,42")
        assert resp.status_code == 400

    def test_api_fitness_400_duplicates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """중복 번호 입력 시 400 반환."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/api/stats/fitness?numbers=1,1,14,21,35,42")
        assert resp.status_code == 400

    def test_api_fitness_400_invalid_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """파싱 불가능한 numbers 파라미터 시 400 반환."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/api/stats/fitness?numbers=abc,def")
        assert resp.status_code == 400

    def test_api_fitness_missing_numbers_param(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """numbers 파라미터 미전달 시 400 반환."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/api/stats/fitness")
        assert resp.status_code == 400

    def test_api_fitness_score_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API 응답 fitness_score가 0~100 범위여야 한다."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/api/stats/fitness?numbers=3,11,22,30,37,44")
        data = resp.json()
        assert 0.0 <= data["fitness_score"] <= 100.0

    def test_api_fitness_grade_in_valid_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API 응답 grade가 S/A/B/C/D 중 하나여야 한다."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/api/stats/fitness?numbers=3,11,22,30,37,44")
        data = resp.json()
        assert data["grade"] in ("S", "A", "B", "C", "D")

    def test_api_fitness_breakdown_length(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """API 응답 breakdown에 15개 항목 포함."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/api/stats/fitness?numbers=3,11,22,30,37,44")
        data = resp.json()
        assert len(data["breakdown"]) == 15


class TestFitnessScorePageRoute:
    """페이지 라우트 /stats/fitness 검증."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_page_renders_without_numbers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """numbers 파라미터 없이 접근 시 200 반환."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/stats/fitness")
        assert resp.status_code == 200

    def test_page_renders_with_valid_numbers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """유효한 numbers 파라미터 전달 시 200 반환."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/stats/fitness?numbers=1,7,14,21,35,42")
        assert resp.status_code == 200

    def test_page_content_type_html(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """응답 Content-Type이 text/html이어야 한다."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/stats/fitness")
        assert "text/html" in resp.headers.get("content-type", "")

    def test_page_contains_title(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """페이지에 '적합도' 관련 텍스트가 포함되어야 한다."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/stats/fitness")
        assert "적합도" in resp.text

    def test_page_renders_with_invalid_numbers_gracefully(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """잘못된 numbers 파라미터 전달 시도 시 오류 없이 200 반환 (오류를 페이지에 표시)."""
        from lotto.web import data as wd
        monkeypatch.setattr(wd, "get_draws", lambda: _STANDARD_DRAWS)

        from lotto.web.app import app
        client = TestClient(app)
        resp = client.get("/stats/fitness?numbers=abc")
        # 잘못된 형식은 400이 아닌 200 반환 (페이지에서 오류 표시)
        assert resp.status_code == 200


class TestFitnessScoreEdgeCases:
    """엣지 케이스 테스트."""

    def setup_method(self) -> None:
        """캐시 초기화."""
        from lotto.web.data import invalidate_cache
        invalidate_cache()

    def test_single_draw(self) -> None:
        """단 1회차 데이터에서도 정상 계산되어야 한다."""
        from lotto.web.data import get_fitness_score
        draws = _make_draws([[1, 7, 14, 21, 35, 42]])
        result = get_fitness_score([1, 7, 14, 21, 35, 42], draws)
        assert 0.0 <= result["fitness_score"] <= 100.0

    def test_two_draws(self) -> None:
        """2개 회차 데이터에서도 정상 계산되어야 한다."""
        from lotto.web.data import get_fitness_score
        draws = _make_draws([[1, 7, 14, 21, 35, 42], [2, 9, 16, 23, 30, 37]])
        result = get_fitness_score([1, 7, 14, 21, 35, 42], draws)
        assert 0.0 <= result["fitness_score"] <= 100.0

    def test_all_same_draws(self) -> None:
        """모든 회차가 동일한 번호일 때 그 번호의 점수가 최대여야 한다."""
        from lotto.web.data import get_fitness_score
        fixed = [3, 11, 22, 30, 37, 44]
        draws = _make_draws([fixed] * 50)
        result_same = get_fitness_score(fixed, draws)
        result_other = get_fitness_score([1, 7, 14, 21, 35, 42], draws)
        # 동일한 번호 조합은 적어도 다른 조합보다 높거나 같은 점수여야 한다
        assert result_same["fitness_score"] >= result_other["fitness_score"]

    def test_minimum_boundary_numbers(self) -> None:
        """최소 경계 번호 조합(1,2,3,4,5,6) 정상 처리."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([1, 2, 3, 4, 5, 6], _STANDARD_DRAWS)
        assert 0.0 <= result["fitness_score"] <= 100.0

    def test_maximum_boundary_numbers(self) -> None:
        """최대 경계 번호 조합(40,41,42,43,44,45) 정상 처리."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([40, 41, 42, 43, 44, 45], _STANDARD_DRAWS)
        assert 0.0 <= result["fitness_score"] <= 100.0

    def test_breakdown_item_types(self) -> None:
        """breakdown 각 항목의 타입이 올바르다."""
        from lotto.web.data import get_fitness_score
        result = get_fitness_score([1, 9, 18, 27, 36, 45], _STANDARD_DRAWS)
        for item in result["breakdown"]:
            assert isinstance(item["name"], str)
            assert isinstance(item["pct"], float)
            assert isinstance(item["label"], str)
