"""SPEC-LOTTO-013: 갭분석·앙상블 전략 및 _gap_scores 테스트.

갭분석·앙상블 전략이 추가된 이후 해당 경로에 대한 커버리지가 없었기 때문에
이 테스트로 검증한다.

@MX:SPEC: SPEC-LOTTO-013
"""

from __future__ import annotations

import random
from datetime import date
from unittest.mock import MagicMock

import pytest

from lotto.analyzer import LottoAnalyzer
from lotto.models import DrawResult
from lotto.recommender import STRATEGY_LABELS, LottoRecommender

# ---------------------------------------------------------------------------
# 픽스처
# ---------------------------------------------------------------------------


def _make_draws(n: int = 20, seed: int = 42) -> list[DrawResult]:
    """다양한 번호 조합의 DrawResult 목록을 생성한다."""
    rng = random.Random(seed)
    draws = []
    for i in range(1, n + 1):
        nums = sorted(rng.sample(range(1, 46), 6))
        draws.append(
            DrawResult(
                drwNo=i,
                date=date(2024, 1, ((i - 1) % 28) + 1),
                n1=nums[0],
                n2=nums[1],
                n3=nums[2],
                n4=nums[3],
                n5=nums[4],
                n6=nums[5],
                bonus=rng.randint(1, 45),
            )
        )
    return draws


@pytest.fixture()
def stats():
    """기본 통계 객체."""
    return LottoAnalyzer().analyze(_make_draws(20))


# ---------------------------------------------------------------------------
# _gap_scores 테스트
# ---------------------------------------------------------------------------


class TestGapScores:
    """LottoRecommender._gap_scores() 동작 검증."""

    def test_returns_all_45_keys(self, stats) -> None:
        """1~45 모든 번호에 대해 점수를 반환해야 한다."""
        recommender = LottoRecommender(stats)
        gap = recommender._gap_scores()

        assert set(gap.keys()) == set(range(1, 46))

    def test_scores_are_normalized_between_0_and_1(self, stats) -> None:
        """점수는 0.0~1.0 범위여야 한다."""
        recommender = LottoRecommender(stats)
        gap = recommender._gap_scores()

        for score in gap.values():
            assert 0.0 <= score <= 1.0

    def test_negative_streak_becomes_positive_gap(self) -> None:
        """음수 스트릭(미출현)이 양수 갭 점수로 변환된다."""
        mock_stats = MagicMock()
        mock_stats.consecutive_pattern.current_streak = {
            1: -10,  # 10회 미출현
            2: 3,  # 3회 연속 출현
            **dict.fromkeys(range(3, 46), 0),
        }

        recommender = LottoRecommender(mock_stats)
        gap = recommender._gap_scores()

        # 번호 1의 raw gap = max(0, -(-10)) = 10 → 정규화 후 1.0
        # 번호 2의 raw gap = max(0, -3) = 0 → 정규화 후 0.0
        assert gap[1] == pytest.approx(1.0)
        assert gap[2] == pytest.approx(0.0)

    def test_all_zero_streaks_returns_half(self) -> None:
        """모든 스트릭이 0이면 정규화 span=0 → 모든 점수가 0.5."""
        mock_stats = MagicMock()
        mock_stats.consecutive_pattern.current_streak = dict.fromkeys(range(1, 46), 0)

        recommender = LottoRecommender(mock_stats)
        gap = recommender._gap_scores()

        assert all(v == pytest.approx(0.5) for v in gap.values())

    def test_positive_only_streaks_all_zero_gap(self) -> None:
        """모든 스트릭이 양수(연속 출현)이면 gap_raw가 모두 0 → span=0 → 0.5."""
        mock_stats = MagicMock()
        mock_stats.consecutive_pattern.current_streak = {n: n for n in range(1, 46)}

        recommender = LottoRecommender(mock_stats)
        gap = recommender._gap_scores()

        # 모두 max(0, -n) = 0 → span=0 → normalize returns 0.5
        assert all(v == pytest.approx(0.5) for v in gap.values())


# ---------------------------------------------------------------------------
# 갭분석·앙상블 전략 테스트
# ---------------------------------------------------------------------------


class TestGapAndEnsembleStrategies:
    """갭분석·앙상블 전략 경로 검증."""

    @pytest.mark.parametrize("strategy", ["갭분석", "앙상블"])
    def test_recommend_by_strategy_returns_valid_set(self, stats, strategy) -> None:
        """갭분석·앙상블 전략으로 단일 세트를 추천할 수 있어야 한다."""
        recommender = LottoRecommender(stats)
        rec = recommender.recommend_by_strategy(strategy)

        assert rec.strategy_label == strategy
        assert len(rec.numbers) == 6
        assert len(set(rec.numbers)) == 6
        assert all(1 <= n <= 45 for n in rec.numbers)
        assert rec.strategy_desc != ""

    @pytest.mark.parametrize("strategy", ["갭분석", "앙상블"])
    def test_strategy_scores_include_all_numbers(self, stats, strategy) -> None:
        """갭분석·앙상블 전략 점수에 1~45 모두 포함되어야 한다."""
        recommender = LottoRecommender(stats)
        scores = recommender._strategy_scores(strategy)

        assert set(scores.keys()) == set(range(1, 46))

    def test_recommend_cycles_through_all_strategies(self, stats) -> None:
        """recommend(count=N)으로 N가지 전략이 한 번씩 순환되어야 한다."""
        recommender = LottoRecommender(stats)
        recs = recommender.recommend(count=len(STRATEGY_LABELS))

        assert len(recs) == len(STRATEGY_LABELS)
        labels = [r.strategy_label for r in recs]
        assert labels == STRATEGY_LABELS

    def test_recommend_count_20_covers_strategies_in_order(self, stats) -> None:
        """count=20이면 전략 순환 순서대로 20개 레이블이 반환된다."""
        recommender = LottoRecommender(stats)
        recs = recommender.recommend(count=20)

        assert len(recs) == 20
        labels = [r.strategy_label for r in recs]
        expected = [STRATEGY_LABELS[i % len(STRATEGY_LABELS)] for i in range(20)]
        assert labels == expected

    def test_gap_strategy_candidates_size(self, stats) -> None:
        """갭분석 전략의 candidates는 상위 22개 번호여야 한다."""
        recommender = LottoRecommender(stats)
        scores = recommender._strategy_scores("갭분석")
        sorted_nums = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)
        expected_candidates = sorted_nums[:22]

        # recommend_by_strategy가 이 후보에서 6개를 선택해야 한다
        rec = recommender.recommend_by_strategy("갭분석")
        assert all(n in expected_candidates for n in rec.numbers)

    def test_ensemble_strategy_candidates_size(self, stats) -> None:
        """앙상블 전략의 candidates는 상위 25개 번호여야 한다."""
        recommender = LottoRecommender(stats)
        scores = recommender._strategy_scores("앙상블")
        sorted_nums = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)
        expected_candidates = sorted_nums[:25]

        rec = recommender.recommend_by_strategy("앙상블")
        assert all(n in expected_candidates for n in rec.numbers)

    def test_gap_strategy_weight_dominates_gap_signal(self) -> None:
        """갭분석 전략은 갭 가중치(0.70)가 가장 높아 미출현 번호를 우선해야 한다."""
        # 번호 1이 -20회 미출현, 나머지는 연속 출현
        mock_stats = MagicMock()
        mock_stats.consecutive_pattern.current_streak = {
            1: -20,
            **{n: n for n in range(2, 46)},
        }
        mock_stats.frequency.absolute = dict.fromkeys(range(1, 46), 5)
        mock_stats.recent_pattern.counts = dict.fromkeys(range(1, 46), 2)
        mock_stats.pair_analysis.top_pairs = []

        recommender = LottoRecommender(mock_stats)
        scores = recommender._strategy_scores("갭분석")

        # 번호 1의 점수가 가장 높아야 한다 (갭이 가장 큼)
        assert scores[1] == max(scores.values())

    def test_ensemble_weights_are_equal(self, stats) -> None:
        """앙상블 전략의 내부 가중치는 (0.25, 0.25, 0.25, 0.25)여야 한다."""
        from lotto.recommender import _STRATEGY_WEIGHTS

        wf, wr, wp, wg = _STRATEGY_WEIGHTS["앙상블"]
        assert wf == pytest.approx(0.25)
        assert wr == pytest.approx(0.25)
        assert wp == pytest.approx(0.25)
        assert wg == pytest.approx(0.25)

    def test_recommend_by_strategy_invalid_label_raises(self, stats) -> None:
        """알 수 없는 전략 레이블은 ValueError를 발생시켜야 한다."""
        recommender = LottoRecommender(stats)
        with pytest.raises(ValueError, match="알 수 없는 전략"):
            recommender.recommend_by_strategy("존재하지않는전략")


# ---------------------------------------------------------------------------
# 데이터스마트 전략 테스트 (SPEC-LOTTO-050)
# ---------------------------------------------------------------------------


class TestDataSmartStrategy:
    """REQ-SMART-001~040: 데이터스마트 전략 검증."""

    def test_strategy_labels_includes_datasmart(self) -> None:
        """STRATEGY_LABELS에 '데이터스마트'가 포함되어야 한다 (REQ-SMART-001)."""
        assert "데이터스마트" in STRATEGY_LABELS

    def test_strategy_descriptions_includes_datasmart(self) -> None:
        """STRATEGY_DESCRIPTIONS에 '데이터스마트' 키가 있어야 한다 (REQ-SMART-002)."""
        from lotto.recommender import STRATEGY_DESCRIPTIONS

        assert "데이터스마트" in STRATEGY_DESCRIPTIONS
        assert STRATEGY_DESCRIPTIONS["데이터스마트"] != ""

    def test_recommend_by_strategy_datasmart_returns_valid_set(self, stats) -> None:
        """데이터스마트 전략으로 유효한 세트를 추천해야 한다 (REQ-SMART-010)."""
        recommender = LottoRecommender(stats)
        rec = recommender.recommend_by_strategy("데이터스마트")

        assert rec.strategy_label == "데이터스마트"
        assert len(rec.numbers) == 6
        assert len(set(rec.numbers)) == 6
        assert all(1 <= n <= 45 for n in rec.numbers)
        assert rec.strategy_desc != ""

    def test_recommend_by_strategy_datasmart_scores_has_6_entries(self, stats) -> None:
        """추천 결과의 scores 딕셔너리는 정확히 6개여야 한다 (REQ-SMART-011)."""
        recommender = LottoRecommender(stats)
        rec = recommender.recommend_by_strategy("데이터스마트")

        assert len(rec.scores) == 6

    def test_recommend_cycles_include_datasmart(self, stats) -> None:
        """recommend()의 순환에 '데이터스마트'가 포함되어야 한다 (REQ-SMART-012)."""
        recommender = LottoRecommender(stats)
        recs = recommender.recommend(count=len(STRATEGY_LABELS))
        labels = [r.strategy_label for r in recs]

        assert "데이터스마트" in labels

    def test_smart_scores_is_deterministic(self, stats) -> None:
        """_smart_scores()는 동일한 statistics로 같은 결과를 반환해야 한다 (REQ-SMART-020)."""
        recommender = LottoRecommender(stats)
        scores_a = recommender._strategy_scores("데이터스마트")
        scores_b = recommender._strategy_scores("데이터스마트")

        assert scores_a == scores_b

    def test_existing_strategies_unchanged(self, stats) -> None:
        """기존 10가지 전략이 데이터스마트 추가 후에도 동작해야 한다 (REQ-SMART-030)."""
        existing = [
            "고빈도",
            "저빈도",
            "균형",
            "최근편향",
            "동반패턴",
            "홀짝균형",
            "번호대균형",
            "핫콜드혼합",
            "갭분석",
            "앙상블",
        ]
        recommender = LottoRecommender(stats)
        for label in existing:
            rec = recommender.recommend_by_strategy(label)
            assert rec.strategy_label == label
            assert len(rec.numbers) == 6

    def test_smart_strategy_scores_cover_all_numbers(self, stats) -> None:
        """_smart_scores()는 1~45 모든 번호에 대해 점수를 반환해야 한다."""
        recommender = LottoRecommender(stats)
        scores = recommender._strategy_scores("데이터스마트")

        assert set(scores.keys()) == set(range(1, 46))

    def test_smart_strategy_all_scores_in_valid_range(self, stats) -> None:
        """_smart_scores()의 다양성 페널티 전 기본 점수는 0 이상이어야 한다."""
        recommender = LottoRecommender(stats)
        scores = recommender._strategy_scores("데이터스마트")

        # 다양성 페널티 미적용 시 점수는 0.0 이상
        for v in scores.values():
            assert v >= -0.12  # 최대 페널티 0.12 적용 후에도 -0.12 이상
