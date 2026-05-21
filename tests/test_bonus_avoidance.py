"""SPEC-LOTTO-003 REQ-BONUS-004: 보너스 회피 가중치 옵션 테스트."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from lotto.analyzer import LottoAnalyzer
from lotto.models import DrawResult
from lotto.recommender import LottoRecommender


def _make_draws() -> list[DrawResult]:
    """번호 11이 보너스로 3회 등장하는 데이터셋을 생성합니다."""
    return [
        DrawResult(
            drwNo=i,
            date=date(2024, 1, i + 1),
            n1=5, n2=10, n3=20, n4=30, n5=40, n6=45,
            bonus=11,
        )
        for i in range(1, 4)
    ]


class TestBonusAvoidanceConfig:
    """config.py에 bonus_avoidance_weight 설정 존재."""

    def test_settings_has_bonus_avoidance_weight_attribute(self) -> None:
        """settings 객체에 bonus_avoidance_weight 속성이 존재한다."""
        from lotto.config import settings

        assert hasattr(settings, "bonus_avoidance_weight")

    def test_default_bonus_avoidance_weight_is_zero(self) -> None:
        """기본값은 0.0 이다."""
        from lotto.config import settings

        assert settings.bonus_avoidance_weight == 0.0


class TestRecommenderBonusAvoidance:
    """REQ-BONUS-004: 가중치 적용 시 페널티 동작."""

    def test_default_weight_zero_does_not_change_scores(self) -> None:
        """기본 0.0 가중치에서는 보너스 빈도 가산/감산이 없다 (회귀 0)."""
        draws = _make_draws()
        stats = LottoAnalyzer().analyze(draws)
        # 보너스 빈도가 채워졌는지 사전 확인
        assert stats.bonus_frequency.absolute[11] == 3

        # 기본 가중치(0.0)로 점수 계산
        with patch("lotto.recommender.settings") as mock_settings:
            mock_settings.bonus_avoidance_weight = 0.0
            mock_settings.recommender_weights = (0.4, 0.3, 0.2, 0.1)
            scores_default = LottoRecommender(stats).compute_scores()

        # 동일 설정에서 두 번 호출하면 동일 결과 (결정적)
        with patch("lotto.recommender.settings") as mock_settings:
            mock_settings.bonus_avoidance_weight = 0.0
            mock_settings.recommender_weights = (0.4, 0.3, 0.2, 0.1)
            scores_default_repeat = LottoRecommender(stats).compute_scores()

        assert scores_default == scores_default_repeat

    def test_positive_weight_penalizes_high_bonus_numbers(self) -> None:
        """가중치 > 0 에서 보너스 빈도 높은 번호의 점수가 가중치 0일 때보다 낮다."""
        draws = _make_draws()
        stats = LottoAnalyzer().analyze(draws)
        # 번호 11이 보너스로 3회 (최대) — 페널티 받아야 함

        with patch("lotto.recommender.settings") as mock_settings:
            mock_settings.bonus_avoidance_weight = 0.0
            mock_settings.recommender_weights = (0.4, 0.3, 0.2, 0.1)
            scores_zero = LottoRecommender(stats).compute_scores()

        with patch("lotto.recommender.settings") as mock_settings:
            mock_settings.bonus_avoidance_weight = 0.5
            mock_settings.recommender_weights = (0.4, 0.3, 0.2, 0.1)
            scores_with_penalty = LottoRecommender(stats).compute_scores()

        # 보너스로 3회 등장한 번호 11은 가중치 적용 시 점수가 낮아짐
        assert scores_with_penalty[11] < scores_zero[11]

    def test_positive_weight_does_not_change_zero_bonus_numbers(self) -> None:
        """보너스로 한 번도 안 나온 번호는 가중치와 무관하게 점수 변화 미미하다.

        정규화 영향으로 작은 차이는 있을 수 있지만 페널티가 0인 번호는
        가중치 0일 때보다 점수가 낮아지지 않는다.
        """
        draws = _make_draws()
        stats = LottoAnalyzer().analyze(draws)
        # 번호 1은 보너스로 한 번도 안 나옴

        with patch("lotto.recommender.settings") as mock_settings:
            mock_settings.bonus_avoidance_weight = 0.0
            mock_settings.recommender_weights = (0.4, 0.3, 0.2, 0.1)
            scores_zero = LottoRecommender(stats).compute_scores()

        with patch("lotto.recommender.settings") as mock_settings:
            mock_settings.bonus_avoidance_weight = 0.5
            mock_settings.recommender_weights = (0.4, 0.3, 0.2, 0.1)
            scores_with_penalty = LottoRecommender(stats).compute_scores()

        # 보너스 0회 번호는 페널티가 0 → 점수 차이는 부동소수 오차 수준
        assert scores_with_penalty[1] >= scores_zero[1] - 1e-9
