"""LottoRecommender 가중 점수 추천 TDD 테스트."""

from __future__ import annotations

import time

import pytest

from lotto.models import DrawResult, Statistics
from lotto.recommender import LottoRecommender, Weights


@pytest.fixture
def sample_stats(mini_draws: list[DrawResult]) -> Statistics:
    """mini-dataset 기반 Statistics 픽스처."""
    from lotto.analyzer import LottoAnalyzer
    return LottoAnalyzer().analyze(mini_draws)


class TestRecommendationIntegrity:
    """추천 무결성 테스트 (REQ-RECOMMEND-01)."""

    def test_five_sets_by_default(self, sample_stats: Statistics) -> None:
        """기본 5세트 반환 테스트."""
        rec = LottoRecommender(sample_stats)
        results = rec.recommend()
        assert len(results) == 5

    def test_each_set_has_six_numbers(self, sample_stats: Statistics) -> None:
        """각 세트가 정확히 6개 번호를 가지는지 테스트."""
        rec = LottoRecommender(sample_stats)
        for r in rec.recommend():
            assert len(r.numbers) == 6

    def test_numbers_in_range_1_to_45(self, sample_stats: Statistics) -> None:
        """번호가 모두 1~45 범위인지 테스트."""
        rec = LottoRecommender(sample_stats)
        for r in rec.recommend():
            for n in r.numbers:
                assert 1 <= n <= 45

    def test_no_duplicates_within_set(self, sample_stats: Statistics) -> None:
        """세트 내 중복 없음 테스트."""
        rec = LottoRecommender(sample_stats)
        for r in rec.recommend():
            assert len(set(r.numbers)) == 6

    def test_no_duplicate_sets(self, sample_stats: Statistics) -> None:
        """세트 간 중복 없음 테스트."""
        rec = LottoRecommender(sample_stats)
        results = rec.recommend()
        frozen_sets = [frozenset(r.numbers) for r in results]
        assert len(set(frozen_sets)) == len(frozen_sets)

    def test_numbers_ascending(self, sample_stats: Statistics) -> None:
        """번호가 오름차순 정렬되어 있는지 테스트."""
        rec = LottoRecommender(sample_stats)
        for r in rec.recommend():
            assert r.numbers == sorted(r.numbers)

    def test_strategy_label_present(self, sample_stats: Statistics) -> None:
        """각 세트에 전략 라벨이 있는지 테스트."""
        from lotto.recommender import STRATEGY_LABELS
        rec = LottoRecommender(sample_stats)
        for r in rec.recommend():
            assert r.strategy_label in STRATEGY_LABELS


class TestCountOption:
    """--count 옵션 테스트 (REQ-RECOMMEND-03)."""

    def test_count_10(self, sample_stats: Statistics) -> None:
        """--count 10 시 정확히 10세트 반환 테스트."""
        rec = LottoRecommender(sample_stats)
        results = rec.recommend(count=10)
        assert len(results) == 10

    def test_count_1(self, sample_stats: Statistics) -> None:
        """--count 1 시 1세트 반환 테스트."""
        rec = LottoRecommender(sample_stats)
        results = rec.recommend(count=1)
        assert len(results) == 1


class TestWeightsValidation:
    """가중치 검증 테스트 (REQ-RECOMMEND-04)."""

    def test_negative_weight_rejected(self) -> None:
        """음수 가중치 거부 테스트."""
        with pytest.raises(ValueError):
            Weights(w_freq=-0.1, w_recent=0.3, w_pair=0.2, w_consec=0.1)

    def test_zero_sum_weight_rejected(self) -> None:
        """합이 0인 가중치 거부 테스트."""
        with pytest.raises(ValueError):
            Weights(w_freq=0.0, w_recent=0.0, w_pair=0.0, w_consec=0.0)

    def test_custom_valid_weights(self, sample_stats: Statistics) -> None:
        """유효한 커스텀 가중치 적용 테스트."""
        weights = Weights(w_freq=0.5, w_recent=0.2, w_pair=0.2, w_consec=0.1)
        rec = LottoRecommender(sample_stats, weights=weights)
        results = rec.recommend()
        assert len(results) == 5


class TestMissingStats:
    """stats.json 부재 테스트 (REQ-RECOMMEND-06)."""

    def test_missing_stats_json_raises(self) -> None:
        """stats.json 없을 때 적절한 예외 발생 테스트."""
        from pathlib import Path

        from lotto.analyzer import LottoAnalyzer
        with pytest.raises((FileNotFoundError, OSError)):
            LottoAnalyzer.load_stats(Path("/nonexistent/stats.json"))


class TestPerformance:
    """추천 성능 테스트."""

    def test_recommend_5_sets_under_2s(self, sample_stats: Statistics) -> None:
        """5세트 추천이 2초 이내 완료 테스트."""
        rec = LottoRecommender(sample_stats)
        start = time.time()
        rec.recommend(count=5)
        elapsed = time.time() - start
        assert elapsed < 2.0
