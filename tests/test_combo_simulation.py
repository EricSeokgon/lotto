"""SPEC-LOTTO-102: 번호 조합 시뮬레이션 (회차별 백테스트) 테스트."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult

# ---------------------------------------------------------------------------
# 테스트용 회차 데이터 픽스처
# ---------------------------------------------------------------------------

@pytest.fixture
def combo_draws() -> list[DrawResult]:
    """검증용 3회차 데이터.

    회차 1: 본번호 1,10,20,30,40,45 / 보너스 5
    회차 2: 본번호 1,10,15,25,35,44 / 보너스 3
    회차 3: 본번호 1,2,3,10,11,12 / 보너스 7
    """
    return [
        DrawResult(
            drwNo=1, date=date(2002, 12, 7), n1=1, n2=10, n3=20, n4=30, n5=40, n6=45, bonus=5
        ),
        DrawResult(
            drwNo=2, date=date(2002, 12, 14), n1=1, n2=10, n3=15, n4=25, n5=35, n6=44, bonus=3
        ),
        DrawResult(
            drwNo=3, date=date(2002, 12, 21), n1=1, n2=2, n3=3, n4=10, n5=11, n6=12, bonus=7
        ),
    ]


_GRADES = ["1등", "2등", "3등", "4등", "5등", "꽝"]


# ---------------------------------------------------------------------------
# _judge_grade 단위 테스트 (REQ-SIM-U02, U03, N04)
# ---------------------------------------------------------------------------

class TestJudgeGrade:
    """등급 판정 헬퍼 _judge_grade 검증."""

    def test_six_match_is_first_grade(self):
        from lotto.web.data import _judge_grade
        assert _judge_grade(6, False) == "1등"

    def test_six_match_with_bonus_still_first_grade(self):
        from lotto.web.data import _judge_grade
        # 6개 일치면 보너스 여부 무관하게 1등
        assert _judge_grade(6, True) == "1등"

    def test_five_match_with_bonus_is_second_grade(self):
        from lotto.web.data import _judge_grade
        # REQ-SIM-U03: 5개 + 보너스 = 2등
        assert _judge_grade(5, True) == "2등"

    def test_five_match_without_bonus_is_third_grade(self):
        from lotto.web.data import _judge_grade
        # REQ-SIM-U03: 5개 + 보너스 불일치 = 3등
        assert _judge_grade(5, False) == "3등"

    def test_four_match_is_fourth_grade(self):
        from lotto.web.data import _judge_grade
        assert _judge_grade(4, False) == "4등"
        # 보너스 일치는 4등 판정에 영향 없음
        assert _judge_grade(4, True) == "4등"

    def test_three_match_is_fifth_grade(self):
        from lotto.web.data import _judge_grade
        assert _judge_grade(3, False) == "5등"
        assert _judge_grade(3, True) == "5등"

    def test_two_match_is_blank(self):
        from lotto.web.data import _judge_grade
        assert _judge_grade(2, False) == "꽝"

    def test_zero_match_is_blank(self):
        from lotto.web.data import _judge_grade
        assert _judge_grade(0, False) == "꽝"


# ---------------------------------------------------------------------------
# get_combo_simulation 핵심 함수 테스트
# ---------------------------------------------------------------------------

class TestGetComboSimulation:
    """get_combo_simulation 핵심 로직 검증."""

    def test_empty_draws_returns_zero_rounds(self):
        """REQ-SIM-S01: draws 빈 리스트면 total_rounds=0."""
        from lotto.web.data import get_combo_simulation
        result = get_combo_simulation([1, 2, 3, 4, 5, 6], [])
        assert result["summary"]["total_rounds"] == 0

    def test_none_draws_returns_zero_rounds(self):
        """REQ-SIM-S01: draws None이면 total_rounds=0, rounds 빈 배열."""
        from lotto.web.data import get_combo_simulation
        result = get_combo_simulation([1, 2, 3, 4, 5, 6], None)
        assert result["summary"]["total_rounds"] == 0
        assert result["rounds"] == []

    def test_empty_draws_all_grade_counts_zero(self):
        """REQ-SIM-S01: 빈 회차면 모든 grade_counts 0."""
        from lotto.web.data import get_combo_simulation
        result = get_combo_simulation([1, 2, 3, 4, 5, 6], None)
        for g in _GRADES:
            assert result["summary"]["grade_counts"][g] == 0
            assert result["summary"]["grade_percentages"][g] == 0.0

    def test_response_has_all_top_level_keys(self, combo_draws):
        """REQ-SIM-E01: 응답에 numbers, summary, rounds, fitness, disclaimer 포함."""
        from lotto.web.data import get_combo_simulation
        result = get_combo_simulation([1, 10, 20, 30, 40, 45], combo_draws)
        for key in ("numbers", "summary", "rounds", "fitness", "disclaimer"):
            assert key in result

    def test_summary_has_required_keys(self, combo_draws):
        """REQ-SIM-E02: summary에 total_rounds, grade_counts, grade_percentages."""
        from lotto.web.data import get_combo_simulation
        result = get_combo_simulation([1, 10, 20, 30, 40, 45], combo_draws)
        summary = result["summary"]
        assert "total_rounds" in summary
        assert "grade_counts" in summary
        assert "grade_percentages" in summary

    def test_grade_counts_has_all_six_keys(self, combo_draws):
        """REQ-SIM-U05: 발생 0인 등급도 6개 키 모두 포함."""
        from lotto.web.data import get_combo_simulation
        result = get_combo_simulation([1, 10, 20, 30, 40, 45], combo_draws)
        assert set(result["summary"]["grade_counts"].keys()) == set(_GRADES)
        assert set(result["summary"]["grade_percentages"].keys()) == set(_GRADES)

    def test_total_rounds_equals_draws_count(self, combo_draws):
        """REQ-SIM-S02: total_rounds는 전체 회차 수."""
        from lotto.web.data import get_combo_simulation
        result = get_combo_simulation([1, 10, 20, 30, 40, 45], combo_draws)
        assert result["summary"]["total_rounds"] == 3

    def test_first_grade_counted(self, combo_draws):
        """6개 일치 조합은 1등으로 집계된다."""
        from lotto.web.data import get_combo_simulation
        # 회차1 본번호와 정확히 일치
        result = get_combo_simulation([1, 10, 20, 30, 40, 45], combo_draws)
        counts = result["summary"]["grade_counts"]
        assert counts["1등"] == 1
        # 회차2, 회차3은 2개 일치 → 꽝
        assert counts["꽝"] == 2

    def test_second_grade_with_bonus(self, combo_draws):
        """REQ-SIM-U03: 5개 일치 + 보너스 일치 = 2등."""
        from lotto.web.data import get_combo_simulation
        # 회차1 본번호 5개(1,10,20,30,40) + 회차1 보너스 5 포함
        result = get_combo_simulation([5, 1, 10, 20, 30, 40], combo_draws)
        counts = result["summary"]["grade_counts"]
        assert counts["2등"] == 1
        assert counts["1등"] == 0
        assert counts["3등"] == 0

    def test_third_grade_without_bonus(self, combo_draws):
        """REQ-SIM-U03: 5개 일치 + 보너스 불일치 = 3등."""
        from lotto.web.data import get_combo_simulation
        # 회차1 본번호 5개(1,10,20,30,40) + 2 (회차1 보너스 5 미포함)
        result = get_combo_simulation([1, 2, 10, 20, 30, 40], combo_draws)
        counts = result["summary"]["grade_counts"]
        assert counts["3등"] == 1
        assert counts["2등"] == 0
        # 회차3 [1,2,3,10,11,12]와는 {1,2,10}=3개 일치 → 5등
        assert counts["5등"] == 1

    def test_bonus_not_counted_in_match_count(self, combo_draws):
        """REQ-SIM-N04: 보너스 번호는 match_count에 포함되지 않는다."""
        from lotto.web.data import get_combo_simulation
        # 회차1 본번호 5개 + 보너스 5 → match_count는 5여야 함(6 아님)
        result = get_combo_simulation([5, 1, 10, 20, 30, 40], combo_draws)
        round1 = next(r for r in result["rounds"] if r["draw_no"] == 1)
        assert round1["match_count"] == 5
        assert round1["bonus_match"] is True
        assert round1["grade"] == "2등"

    def test_rounds_detail_keys(self, combo_draws):
        """REQ-SIM-E03: rounds 각 항목에 draw_no, date, match_count, bonus_match, grade."""
        from lotto.web.data import get_combo_simulation
        result = get_combo_simulation([1, 10, 20, 30, 40, 45], combo_draws)
        assert len(result["rounds"]) == 3
        for r in result["rounds"]:
            for key in ("draw_no", "date", "match_count", "bonus_match", "grade"):
                assert key in r

    def test_grade_percentages_sum_to_100(self, combo_draws):
        """REQ-SIM-U04: grade_percentages 합은 100에 근사."""
        from lotto.web.data import get_combo_simulation
        result = get_combo_simulation([1, 10, 20, 30, 40, 45], combo_draws)
        total_pct = sum(result["summary"]["grade_percentages"].values())
        assert abs(total_pct - 100.0) < 0.1

    def test_input_order_independent(self, combo_draws):
        """REQ-SIM-U07: 입력 순서가 결과에 영향을 주지 않는다."""
        from lotto.web.data import get_combo_simulation
        r1 = get_combo_simulation([1, 10, 20, 30, 40, 45], combo_draws)
        r2 = get_combo_simulation([45, 40, 30, 20, 10, 1], combo_draws)
        assert r1["summary"]["grade_counts"] == r2["summary"]["grade_counts"]
        assert r1["numbers"] == r2["numbers"]

    def test_numbers_returned_sorted(self, combo_draws):
        """REQ-SIM-U07: 반환된 numbers는 정렬된 상태."""
        from lotto.web.data import get_combo_simulation
        result = get_combo_simulation([45, 3, 1, 10, 6, 5], combo_draws)
        assert result["numbers"] == [1, 3, 5, 6, 10, 45]

    def test_fitness_has_score_and_grade(self, combo_draws):
        """REQ-SIM-E04, U06: fitness에 fitness_score, grade 포함."""
        from lotto.web.data import get_combo_simulation
        result = get_combo_simulation([1, 10, 20, 30, 40, 45], combo_draws)
        assert "fitness_score" in result["fitness"]
        assert "grade" in result["fitness"]
        assert isinstance(result["fitness"]["fitness_score"], float)

    def test_disclaimer_present(self, combo_draws):
        """REQ-SIM-N05: 면책 고지 포함."""
        from lotto.web.data import get_combo_simulation
        result = get_combo_simulation([1, 10, 20, 30, 40, 45], combo_draws)
        assert isinstance(result["disclaimer"], str)
        assert len(result["disclaimer"]) > 0

    # 입력 검증 (REQ-SIM-N01, N02, N03)
    def test_too_few_numbers_raises(self, combo_draws):
        from lotto.web.data import get_combo_simulation
        with pytest.raises(ValueError):
            get_combo_simulation([1, 2, 3, 4, 5], combo_draws)

    def test_too_many_numbers_raises(self, combo_draws):
        from lotto.web.data import get_combo_simulation
        with pytest.raises(ValueError):
            get_combo_simulation([1, 2, 3, 4, 5, 6, 7], combo_draws)

    def test_out_of_range_low_raises(self, combo_draws):
        from lotto.web.data import get_combo_simulation
        with pytest.raises(ValueError):
            get_combo_simulation([0, 2, 3, 4, 5, 6], combo_draws)

    def test_out_of_range_high_raises(self, combo_draws):
        from lotto.web.data import get_combo_simulation
        with pytest.raises(ValueError):
            get_combo_simulation([1, 2, 3, 4, 5, 46], combo_draws)

    def test_duplicate_numbers_raises(self, combo_draws):
        from lotto.web.data import get_combo_simulation
        with pytest.raises(ValueError):
            get_combo_simulation([1, 1, 3, 4, 5, 6], combo_draws)


# ---------------------------------------------------------------------------
# API 엔드포인트 테스트: POST /api/stats/simulate
# ---------------------------------------------------------------------------

class TestSimulateApi:
    """POST /api/stats/simulate 엔드포인트 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app
        return TestClient(app)

    def test_valid_request_returns_200(self):
        """REQ-SIM-E01: 유효한 6개 번호 → 200."""
        client = self._client()
        resp = client.post("/api/stats/simulate", json={"numbers": [1, 7, 14, 21, 35, 42]})
        assert resp.status_code == 200

    def test_response_has_required_keys(self):
        """REQ-SIM-E01: 응답에 numbers, summary, rounds, fitness 포함."""
        client = self._client()
        resp = client.post("/api/stats/simulate", json={"numbers": [1, 7, 14, 21, 35, 42]})
        assert resp.status_code == 200
        data = resp.json()
        for key in ("numbers", "summary", "rounds", "fitness"):
            assert key in data

    def test_summary_structure(self):
        """REQ-SIM-E02: summary에 등급 키 6개 포함."""
        client = self._client()
        resp = client.post("/api/stats/simulate", json={"numbers": [1, 7, 14, 21, 35, 42]})
        data = resp.json()
        assert set(data["summary"]["grade_counts"].keys()) == set(_GRADES)
        assert set(data["summary"]["grade_percentages"].keys()) == set(_GRADES)

    def test_fitness_structure(self):
        """REQ-SIM-E04: fitness에 fitness_score, grade."""
        client = self._client()
        resp = client.post("/api/stats/simulate", json={"numbers": [1, 7, 14, 21, 35, 42]})
        data = resp.json()
        assert "fitness_score" in data["fitness"]
        assert "grade" in data["fitness"]

    def test_too_few_numbers_returns_422(self):
        """REQ-SIM-N01: 6개 미만 → 422."""
        client = self._client()
        resp = client.post("/api/stats/simulate", json={"numbers": [1, 2, 3, 4, 5]})
        assert resp.status_code == 422

    def test_too_many_numbers_returns_422(self):
        """REQ-SIM-N01: 6개 초과 → 422."""
        client = self._client()
        resp = client.post("/api/stats/simulate", json={"numbers": [1, 2, 3, 4, 5, 6, 7]})
        assert resp.status_code == 422

    def test_zero_number_returns_422(self):
        """REQ-SIM-N02: 0 번호 → 422."""
        client = self._client()
        resp = client.post("/api/stats/simulate", json={"numbers": [0, 2, 3, 4, 5, 6]})
        assert resp.status_code == 422

    def test_over_45_number_returns_422(self):
        """REQ-SIM-N02: 46 번호 → 422."""
        client = self._client()
        resp = client.post("/api/stats/simulate", json={"numbers": [1, 2, 3, 4, 5, 46]})
        assert resp.status_code == 422

    def test_duplicate_numbers_returns_422(self):
        """REQ-SIM-N03: 중복 번호 → 422."""
        client = self._client()
        resp = client.post("/api/stats/simulate", json={"numbers": [1, 1, 3, 4, 5, 6]})
        assert resp.status_code == 422

    def test_empty_body_returns_422(self):
        """numbers 키 누락 → 422."""
        client = self._client()
        resp = client.post("/api/stats/simulate", json={})
        assert resp.status_code == 422

    def test_does_not_affect_existing_simulate(self):
        """REQ-SIM-N07: 기존 POST /api/stats/simulate가 GET /simulate 페이지에 영향 없음."""
        client = self._client()
        # 기존 몬테카를로 페이지 라우트는 그대로 동작
        resp = client.get("/simulate")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 페이지 라우트 테스트: GET /stats/simulate
# ---------------------------------------------------------------------------

class TestSimulateComboPage:
    """GET /stats/simulate 페이지 라우트 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app
        return TestClient(app)

    def test_page_returns_200(self):
        """REQ-SIM-E05: 페이지 200 응답."""
        client = self._client()
        resp = client.get("/stats/simulate")
        assert resp.status_code == 200

    def test_page_renders_html(self):
        """REQ-SIM-E05: HTML 응답 (폼 포함)."""
        client = self._client()
        resp = client.get("/stats/simulate")
        assert "text/html" in resp.headers["content-type"]

    def test_page_active_tab_heading(self):
        """active_tab=combo_simulate 헤딩 표시."""
        client = self._client()
        resp = client.get("/stats/simulate")
        assert "조합 시뮬레이션" in resp.text

    def test_nav_contains_combo_simulate_link(self):
        """base.html 내비게이션에 /stats/simulate 링크 포함."""
        client = self._client()
        resp = client.get("/stats/simulate")
        assert "/stats/simulate" in resp.text

    def test_existing_monte_carlo_simulate_untouched(self):
        """REQ-SIM-N07: 기존 /simulate (몬테카를로) 라우트 정상."""
        client = self._client()
        resp = client.get("/simulate")
        assert resp.status_code == 200

    def test_existing_simulation_history_untouched(self):
        """REQ-SIM-N07: 기존 /simulation-history 라우트 정상."""
        client = self._client()
        resp = client.get("/simulation-history")
        assert resp.status_code == 200
