"""SPEC-LOTTO-003 REQ-BONUS-001/002: 보너스 빈도 통계 TDD 테스트."""

from __future__ import annotations

from datetime import date

from lotto.analyzer import LottoAnalyzer
from lotto.models import DrawResult, FrequencyStats, Statistics


class TestBonusFrequencyField:
    """REQ-BONUS-001: Statistics 모델에 bonus_frequency 필드 존재."""

    def test_default_statistics_has_bonus_frequency(self) -> None:
        """빈 Statistics에도 bonus_frequency 필드가 존재한다."""
        stats = Statistics()
        assert hasattr(stats, "bonus_frequency")

    def test_bonus_frequency_is_frequency_stats_instance(self) -> None:
        """bonus_frequency는 FrequencyStats 타입이다."""
        stats = Statistics()
        assert isinstance(stats.bonus_frequency, FrequencyStats)

    def test_bonus_frequency_default_empty(self) -> None:
        """기본값은 absolute/relative 모두 빈 dict 이다."""
        stats = Statistics()
        assert stats.bonus_frequency.absolute == {}
        assert stats.bonus_frequency.relative == {}

    def test_bonus_frequency_serializes_in_model_dump(self) -> None:
        """model_dump 결과에 bonus_frequency 키가 포함된다."""
        stats = Statistics()
        data = stats.model_dump()
        assert "bonus_frequency" in data
        assert "absolute" in data["bonus_frequency"]
        assert "relative" in data["bonus_frequency"]


class TestAnalyzerBonusFrequency:
    """REQ-BONUS-002: analyzer.analyze()가 bonus_frequency를 채운다."""

    def test_analyze_populates_bonus_frequency_from_mini_dataset(
        self, mini_draws: list[DrawResult]
    ) -> None:
        """mini_draws의 보너스 5, 3, 7이 각 1회씩 카운트된다."""
        analyzer = LottoAnalyzer()
        stats = analyzer.analyze(mini_draws)
        # mini_draws 보너스: 5, 3, 7
        assert stats.bonus_frequency.absolute[5] == 1
        assert stats.bonus_frequency.absolute[3] == 1
        assert stats.bonus_frequency.absolute[7] == 1

    def test_analyze_bonus_frequency_zero_for_unused_numbers(
        self, mini_draws: list[DrawResult]
    ) -> None:
        """보너스로 등장하지 않은 번호는 0회이다."""
        analyzer = LottoAnalyzer()
        stats = analyzer.analyze(mini_draws)
        # mini_draws 보너스는 5, 3, 7뿐 → 번호 1은 0회
        assert stats.bonus_frequency.absolute[1] == 0

    def test_analyze_bonus_frequency_sum_equals_draw_count(
        self, mini_draws: list[DrawResult]
    ) -> None:
        """절대 빈도 합계가 전체 회차 수와 같다."""
        analyzer = LottoAnalyzer()
        stats = analyzer.analyze(mini_draws)
        total = sum(stats.bonus_frequency.absolute.values())
        assert total == len(mini_draws)

    def test_analyze_bonus_frequency_includes_all_45_numbers(
        self, mini_draws: list[DrawResult]
    ) -> None:
        """1~45 모든 번호가 키로 포함된다(0 포함)."""
        analyzer = LottoAnalyzer()
        stats = analyzer.analyze(mini_draws)
        for n in range(1, 46):
            assert n in stats.bonus_frequency.absolute

    def test_analyze_bonus_frequency_relative_sums_to_one(
        self, mini_draws: list[DrawResult]
    ) -> None:
        """상대 빈도 합계 ≈ 1.0 이다."""
        analyzer = LottoAnalyzer()
        stats = analyzer.analyze(mini_draws)
        total = sum(stats.bonus_frequency.relative.values())
        assert abs(total - 1.0) < 1e-6

    def test_analyze_empty_draws_bonus_frequency(self) -> None:
        """빈 draws에서도 예외 없이 처리되며 모든 빈도가 0이다."""
        analyzer = LottoAnalyzer()
        stats = analyzer.analyze([])
        assert sum(stats.bonus_frequency.absolute.values()) == 0
        # 빈 데이터에서 상대 빈도는 모두 0
        assert all(v == 0.0 for v in stats.bonus_frequency.relative.values())

    def test_analyze_bonus_frequency_is_independent_of_main_frequency(self) -> None:
        """보너스 빈도는 본 추첨 6개 번호와 독립적으로 계산된다."""
        # 같은 번호 5가 본 추첨에 3회, 보너스에 0회 등장하는 시나리오
        draws = [
            DrawResult(
                drwNo=i,
                date=date(2024, 1, i + 1),
                n1=5, n2=10, n3=20, n4=30, n5=40, n6=45,
                bonus=11,
            )
            for i in range(1, 4)
        ]
        analyzer = LottoAnalyzer()
        stats = analyzer.analyze(draws)
        # 본 추첨 빈도: 5는 3회
        assert stats.frequency.absolute[5] == 3
        # 보너스 빈도: 5는 0회, 11은 3회
        assert stats.bonus_frequency.absolute[5] == 0
        assert stats.bonus_frequency.absolute[11] == 3
