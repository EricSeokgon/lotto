"""SPEC-LOTTO-004 REQ-INT-003: Recommender 엣지케이스 폴백 경로 테스트.

후보 소진, 폴백 경로, 보너스 회피 가중치 활성 분기를 검증한다.

@MX:SPEC: SPEC-LOTTO-004 REQ-INT-003
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from lotto.analyzer import LottoAnalyzer
from lotto.models import DrawResult
from lotto.recommender import LottoRecommender


def _make_skewed_draws() -> list[DrawResult]:
    """동일한 번호 조합이 반복되어 점수가 극단적으로 편향된 데이터셋."""
    return [
        DrawResult(
            drwNo=i,
            date=date(2024, 1, ((i - 1) % 28) + 1),
            n1=1, n2=2, n3=3, n4=4, n5=5, n6=6,
            bonus=7,
        )
        for i in range(1, 11)
    ]


def _make_diverse_draws(n: int = 30) -> list[DrawResult]:
    """다양한 번호 조합으로 보너스 빈도가 채워진 데이터셋."""
    import random as _rnd
    rng = _rnd.Random(42)
    draws = []
    for i in range(1, n + 1):
        nums = rng.sample(range(1, 46), 7)
        body = sorted(nums[:6])
        draws.append(
            DrawResult(
                drwNo=i,
                date=date(2024, 1, ((i - 1) % 28) + 1),
                n1=body[0], n2=body[1], n3=body[2],
                n4=body[3], n5=body[4], n6=body[5],
                bonus=nums[6],
            )
        )
    return draws


class TestRecommenderFallback:
    """REQ-INT-003: 후보 소진 시 폴백 경로 검증."""

    def test_recommender_returns_20_sets_with_skewed_stats(self) -> None:
        """Scenario 3.1: 극단적으로 편향된 통계에서도 20개 세트 반환."""
        draws = _make_skewed_draws()
        stats = LottoAnalyzer().analyze(draws)

        recs = LottoRecommender(stats).recommend(count=20)

        assert len(recs) == 20
        for rec in recs:
            assert len(rec.numbers) == 6
            assert len(set(rec.numbers)) == 6
            assert all(1 <= n <= 45 for n in rec.numbers)

    def test_recommender_handles_empty_pair_analysis(self) -> None:
        """동반패턴이 비어있어도 추천이 동작해야 한다."""
        # 1회차만으로는 pair_analysis가 채워지지만 동반 점수는 모두 0에 가까움
        draws = [_make_skewed_draws()[0]]
        stats = LottoAnalyzer().analyze(draws)

        # ValueError나 RuntimeError 없이 호출 가능해야 한다
        recs = LottoRecommender(stats).recommend(count=3)
        assert len(recs) == 3


class TestRecommenderBonusAvoidanceActive:
    """REQ-INT-003: 보너스 회피 가중치 활성 분기 검증."""

    def test_bonus_avoidance_active_branch_executes(self) -> None:
        """Scenario 3.2: bonus_avoidance_weight > 0 시 분기가 실행된다."""
        draws = _make_diverse_draws(30)
        stats = LottoAnalyzer().analyze(draws)

        with patch("lotto.recommender.settings") as mock_settings:
            mock_settings.bonus_avoidance_weight = 0.5
            mock_settings.recommender_weights = (0.4, 0.3, 0.2, 0.1)

            scores = LottoRecommender(stats).compute_scores()

        # 45개 번호 모두에 대한 점수가 계산되어야 한다
        assert len(scores) == 45
        assert set(scores.keys()) == set(range(1, 46))

    def test_bonus_avoidance_recommend_with_active_weight(self) -> None:
        """보너스 회피 가중치 활성 상태로 recommend()가 정상 동작한다."""
        draws = _make_diverse_draws(30)
        stats = LottoAnalyzer().analyze(draws)

        with patch("lotto.recommender.settings") as mock_settings:
            mock_settings.bonus_avoidance_weight = 0.3
            mock_settings.recommender_weights = (0.4, 0.3, 0.2, 0.1)

            recs = LottoRecommender(stats).recommend(count=5)

        assert len(recs) == 5

    def test_bonus_avoidance_penalty_lowers_high_bonus_number_score(self) -> None:
        """보너스 빈도가 가장 높은 번호의 점수는 페널티 적용 시 더 낮아져야 한다."""
        draws = _make_diverse_draws(30)
        stats = LottoAnalyzer().analyze(draws)

        # 보너스 빈도가 최대인 번호 찾기
        max_bonus_num = max(
            stats.bonus_frequency.absolute.keys(),
            key=lambda k: stats.bonus_frequency.absolute[k],
        )
        # 빈도가 1 이상인지 확인 (의미있는 비교를 위해)
        assert stats.bonus_frequency.absolute[max_bonus_num] >= 1

        with patch("lotto.recommender.settings") as mock_settings:
            mock_settings.bonus_avoidance_weight = 0.0
            mock_settings.recommender_weights = (0.4, 0.3, 0.2, 0.1)
            scores_zero = LottoRecommender(stats).compute_scores()

        with patch("lotto.recommender.settings") as mock_settings:
            mock_settings.bonus_avoidance_weight = 0.5
            mock_settings.recommender_weights = (0.4, 0.3, 0.2, 0.1)
            scores_penalty = LottoRecommender(stats).compute_scores()

        # 보너스 빈도가 가장 높은 번호의 점수가 낮아져야 한다
        assert scores_penalty[max_bonus_num] < scores_zero[max_bonus_num]
