"""LottoAnalyzer 4종 통계 분석 TDD 테스트."""

from __future__ import annotations

import datetime
import time
from pathlib import Path

import pytest

from lotto.analyzer import LottoAnalyzer
from lotto.models import DrawResult


class TestFrequency:
    """빈도 분석 테스트."""

    def test_absolute_frequency_mini_dataset(self, mini_draws: list[DrawResult]) -> None:
        """mini-dataset 3회차: 번호 1 빈도=3, 번호 10=3, 번호 7=0 테스트."""
        analyzer = LottoAnalyzer()
        freq = analyzer.compute_frequency(mini_draws)
        absolute = freq["absolute"]
        assert absolute[1] == 3
        assert absolute[10] == 3
        assert absolute[7] == 0

    def test_relative_frequency_sums_to_one(self, mini_draws: list[DrawResult]) -> None:
        """상대 빈도 합계가 1.0에 근사하는지 테스트."""
        analyzer = LottoAnalyzer()
        freq = analyzer.compute_frequency(mini_draws)
        relative = freq["relative"]
        total = sum(relative.values())
        assert abs(total - 1.0) < 1e-6

    def test_all_45_numbers_present(self, mini_draws: list[DrawResult]) -> None:
        """번호 1~45 모두 결과에 포함되는지 테스트 (0이라도)."""
        analyzer = LottoAnalyzer()
        freq = analyzer.compute_frequency(mini_draws)
        absolute = freq["absolute"]
        for n in range(1, 46):
            assert n in absolute


class TestRecentPattern:
    """최근 패턴 분석 테스트."""

    def test_recent_window_default(self, mini_draws: list[DrawResult]) -> None:
        """기본 window=20, 3회차만 있으면 3회차로 계산 테스트."""
        analyzer = LottoAnalyzer()
        result = analyzer.compute_recent_pattern(mini_draws)
        counts = result["counts"]
        # 3회차 모두 번호 1 출현
        assert counts[1] == 3

    def test_recent_window_exceeds_available(self, mini_draws: list[DrawResult]) -> None:
        """window > 가용 회차 시 경고 후 가용 회차로 계산 테스트 (REQ-ANALYZE-07)."""
        analyzer = LottoAnalyzer(recent_window=50)
        # 경고가 발생해도 결과는 반환됨 (3회차 데이터로 계산)
        result = analyzer.compute_recent_pattern(mini_draws)
        counts = result["counts"]
        # window=50이지만 3회차만 있으니 3회차 기준
        assert counts[1] == 3
        assert result.get("warning") is not None

    def test_custom_window(self, mini_draws: list[DrawResult]) -> None:
        """--recent-window 2 설정 시 최근 2회차만 분석 테스트."""
        analyzer = LottoAnalyzer(recent_window=2)
        result = analyzer.compute_recent_pattern(mini_draws)
        counts = result["counts"]
        # 최근 2회차(2,3회차): 번호 1은 2회, 번호 20은 0회
        assert counts[1] == 2
        assert counts.get(20, 0) == 0


class TestConsecutivePattern:
    """연속 출현/제외 스트릭 테스트."""

    def test_consecutive_appearance(self, mini_draws: list[DrawResult]) -> None:
        """3회 연속 출현 번호의 스트릭 값 테스트."""
        analyzer = LottoAnalyzer()
        result = analyzer.compute_consecutive_pattern(mini_draws)
        streaks = result["current_streak"]
        # 번호 1은 모든 3회차에 출현 → streak = 3
        assert streaks[1] == 3
        # 번호 10도 모든 3회차에 출현 → streak = 3
        assert streaks[10] == 3

    def test_never_appeared(self, mini_draws: list[DrawResult]) -> None:
        """한 번도 출현하지 않은 번호의 음수 스트릭 테스트."""
        analyzer = LottoAnalyzer()
        result = analyzer.compute_consecutive_pattern(mini_draws)
        streaks = result["current_streak"]
        # 번호 7은 한 번도 출현 안 함 → streak = -3
        assert streaks[7] == -3


class TestPairAnalysis:
    """동반 출현 쌍 분석 테스트."""

    def test_top_pairs_returned(self, mini_draws: list[DrawResult]) -> None:
        """mini-dataset에서 동반 출현 상위 쌍이 기록되는지 테스트."""
        analyzer = LottoAnalyzer()
        pairs = analyzer.compute_pair_analysis(mini_draws)
        assert len(pairs) > 0
        # 각 쌍은 (번호A, 번호B, 동반횟수) 형태
        for pair in pairs:
            assert len(pair) == 3
            assert 1 <= pair[0] <= 45
            assert 1 <= pair[1] <= 45
            assert pair[2] > 0
        # 번호 1과 10은 모든 3회차에서 함께 출현 → count=3
        top_pair_nums = {(p[0], p[1]) for p in pairs}
        assert (1, 10) in top_pair_nums

    def test_pair_count_limit(self, mini_draws: list[DrawResult]) -> None:
        """top_n 제한이 적용되는지 테스트."""
        analyzer = LottoAnalyzer()
        pairs = analyzer.compute_pair_analysis(mini_draws, top_n=5)
        assert len(pairs) <= 5


class TestPerformance:
    """성능 벤치마크 테스트."""

    def test_analyze_1200_rounds_under_5s(self) -> None:
        """1200회차 analyze가 5초 이내 완료 테스트 (REQ-ANALYZE)."""
        draws = []
        for i in range(1, 1201):
            draws.append(
                DrawResult(
                    drwNo=i,
                    date=datetime.date(2002, 12, 7),
                    n1=1, n2=2, n3=3, n4=4, n5=5, n6=6,
                    bonus=7,
                )
            )
        analyzer = LottoAnalyzer()
        start = time.time()
        analyzer.analyze(draws)
        elapsed = time.time() - start
        assert elapsed < 5.0


class TestStatsPersistence:
    """통계 저장/로드 테스트."""

    def test_save_and_load_json(self, mini_draws: list[DrawResult], tmp_data_dir: Path) -> None:
        """Statistics JSON 저장 후 로드 일관성 테스트."""
        analyzer = LottoAnalyzer()
        stats = analyzer.analyze(mini_draws)
        path = tmp_data_dir / "stats.json"
        analyzer.save_stats(stats, path)
        loaded = LottoAnalyzer.load_stats(path)
        assert loaded.total_rounds == stats.total_rounds
        assert loaded.frequency.absolute[1] == stats.frequency.absolute[1]

    def test_missing_csv_raises(self) -> None:
        """draws.csv 없을 때 적절한 예외 발생 테스트 (REQ-ANALYZE-06)."""
        from pathlib import Path
        path = Path("/nonexistent/stats.json")
        with pytest.raises((FileNotFoundError, OSError, ValueError)):
            LottoAnalyzer.load_stats(path)
