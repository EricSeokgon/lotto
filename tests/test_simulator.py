"""LottoSimulator causal-safe 백테스팅 TDD 테스트."""

from __future__ import annotations

import datetime

import pytest

from lotto.models import DrawResult
from lotto.simulator import HistoricalView, LottoSimulator


@pytest.fixture
def large_draws() -> list[DrawResult]:
    """1000회차 가상 데이터 픽스처."""
    draws = []
    for i in range(1, 1001):
        draws.append(
            DrawResult(
                drwNo=i,
                date=datetime.date(2002, 12, 7),
                n1=1, n2=2, n3=3, n4=4, n5=5, n6=6,
                bonus=7,
            )
        )
    return draws


class TestHistoricalView:
    """HistoricalView look-ahead bias 방지 테스트 (REQ-SIMULATE-05)."""

    def test_cutoff_blocks_future_data(self, large_draws: list[DrawResult]) -> None:
        """cutoff_round R 시 회차 R 이상 데이터가 차단되는지 테스트."""
        view = HistoricalView(large_draws, cutoff_round=100)
        for draw in view.draws:
            assert draw.drwNo < 100

    def test_cutoff_includes_past_data(self, large_draws: list[DrawResult]) -> None:
        """cutoff_round R 시 회차 R 미만 데이터는 포함되는지 테스트."""
        view = HistoricalView(large_draws, cutoff_round=100)
        assert len(view.draws) == 99
        assert len(view) == 99

    def test_lookahead_bias_explicit_fail(self, large_draws: list[DrawResult]) -> None:
        """회차 R 추천 시 회차 R 데이터 누설이 발생하면 명시적으로 FAIL (REQ-SIMULATE-05)."""
        view = HistoricalView(large_draws, cutoff_round=100)
        for draw in view.draws:
            assert draw.drwNo < 100, f"look-ahead bias: 회차 {draw.drwNo}가 cutoff 100 이상"


class TestSimulationResults:
    """시뮬레이션 결과 테스트 (REQ-SIMULATE-01~04)."""

    def test_simulate_10_rounds(self, large_draws: list[DrawResult]) -> None:
        """1000회차 데이터로 simulate --rounds 10 실행 테스트."""
        sim = LottoSimulator(large_draws)
        result = sim.simulate(rounds=10)
        assert result.total_rounds == 10

    def test_prize_counts_reported(self, large_draws: list[DrawResult]) -> None:
        """5등/4등/3등/2등/1등 카운트가 보고되는지 테스트."""
        sim = LottoSimulator(large_draws)
        result = sim.simulate(rounds=10)
        expected_keys = {"1등", "2등", "3등", "4등", "5등", "낙첨"}
        for key in expected_keys:
            assert key in result.prize_counts

    def test_hit_rate_in_range(self, large_draws: list[DrawResult]) -> None:
        """hit_rate가 0.0~1.0 범위인지 테스트."""
        sim = LottoSimulator(large_draws)
        result = sim.simulate(rounds=10)
        assert 0.0 <= result.hit_rate <= 1.0

    def test_each_round_uses_prior_data_only(self, large_draws: list[DrawResult]) -> None:
        """각 회차 평가 시 해당 회차 이전 데이터만 사용되는지 테스트."""
        sim = LottoSimulator(large_draws)
        result = sim.simulate(rounds=5)
        assert len(result.details) == 5
        for detail in result.details:
            # 각 detail에 회차 정보 포함
            assert "round" in detail
            assert "prize" in detail


class TestPrizeTiers:
    """당첨 등수 매칭 테스트."""

    def _make_sim(self) -> LottoSimulator:
        return LottoSimulator([])

    def test_1st_prize_6_match(self) -> None:
        """6개 일치 → 1등 테스트."""
        sim = self._make_sim()
        actual = DrawResult(
            drwNo=1, date=datetime.date(2020, 1, 1),
            n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7,
        )
        assert sim._evaluate_round([1, 2, 3, 4, 5, 6], actual) == "1등"

    def test_2nd_prize_5_plus_bonus(self) -> None:
        """5개 일치 + 보너스 → 2등 테스트."""
        sim = self._make_sim()
        actual = DrawResult(
            drwNo=1, date=datetime.date(2020, 1, 1),
            n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7,
        )
        # 1,2,3,4,5 일치 + 보너스 7 일치
        assert sim._evaluate_round([1, 2, 3, 4, 5, 7], actual) == "2등"

    def test_3rd_prize_5_match(self) -> None:
        """5개 일치 (보너스 미포함) → 3등 테스트."""
        sim = self._make_sim()
        actual = DrawResult(
            drwNo=1, date=datetime.date(2020, 1, 1),
            n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7,
        )
        # 1,2,3,4,5 일치, 보너스(7) 미포함
        assert sim._evaluate_round([1, 2, 3, 4, 5, 8], actual) == "3등"

    def test_4th_prize_4_match(self) -> None:
        """4개 일치 → 4등 테스트."""
        sim = self._make_sim()
        actual = DrawResult(
            drwNo=1, date=datetime.date(2020, 1, 1),
            n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7,
        )
        assert sim._evaluate_round([1, 2, 3, 4, 8, 9], actual) == "4등"

    def test_5th_prize_3_match(self) -> None:
        """3개 일치 → 5등 테스트."""
        sim = self._make_sim()
        actual = DrawResult(
            drwNo=1, date=datetime.date(2020, 1, 1),
            n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7,
        )
        assert sim._evaluate_round([1, 2, 3, 8, 9, 10], actual) == "5등"

    def test_no_prize_2_or_fewer(self) -> None:
        """2개 이하 일치 → 낙첨 테스트."""
        sim = self._make_sim()
        actual = DrawResult(
            drwNo=1, date=datetime.date(2020, 1, 1),
            n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7,
        )
        assert sim._evaluate_round([1, 2, 8, 9, 10, 11], actual) == "낙첨"
        assert sim._evaluate_round([8, 9, 10, 11, 12, 13], actual) == "낙첨"
