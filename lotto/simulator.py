"""LottoSimulator — causal-safe 백테스팅 (look-ahead bias 방지)."""

from __future__ import annotations

import warnings
from typing import Any

from lotto.analyzer import LottoAnalyzer
from lotto.models import DrawResult, SimulationResult
from lotto.recommender import LottoRecommender


# @MX:ANCHOR: [AUTO] HistoricalView — causal-safe 데이터 경계 어댑터
# @MX:REASON: simulator, test, 통합 파이프라인에서 호출 (fan_in >= 3). 미래 데이터 누설 방지 핵심.
class HistoricalView:
    """회차 R 이전 데이터만 노출하는 어댑터 (look-ahead bias 방지).

    이 클래스를 통하지 않으면 미래 데이터 접근이 불가능해야 합니다.
    """

    def __init__(self, draws: list[DrawResult], cutoff_round: int) -> None:
        """cutoff_round 이전 회차만 포함하는 뷰를 생성합니다."""
        self._draws = [d for d in draws if d.drwNo < cutoff_round]
        self._cutoff = cutoff_round

    @property
    def draws(self) -> list[DrawResult]:
        """cutoff_round 미만 회차 목록을 반환합니다."""
        return list(self._draws)

    def __len__(self) -> int:
        return len(self._draws)


class LottoSimulator:
    """역대 당첨 데이터로 causal-safe 백테스팅을 수행합니다."""

    def __init__(self, draws: list[DrawResult]) -> None:
        self._draws = draws

    def simulate(self, rounds: int = 10) -> SimulationResult:
        """최근 rounds 회차를 대상으로 시뮬레이션을 실행합니다."""
        if not self._draws:
            return SimulationResult(
                total_rounds=0,
                prize_counts={"1등": 0, "2등": 0, "3등": 0, "4등": 0, "5등": 0, "낙첨": 0},
                hit_rate=0.0,
                details=[],
            )

        # 최근 rounds 회차 선택
        target_rounds = self._draws[-rounds:] if len(self._draws) >= rounds else self._draws
        actual_rounds = len(target_rounds)

        prize_counts: dict[str, int] = {
            "1등": 0, "2등": 0, "3등": 0, "4등": 0, "5등": 0, "낙첨": 0
        }
        details: list[dict[str, Any]] = []
        hits = 0

        for target in target_rounds:
            view = HistoricalView(self._draws, cutoff_round=target.drwNo)
            detail = self._run_round(view, target)
            prize = str(detail.get("prize", "낙첨"))
            prize_counts[prize] = prize_counts.get(prize, 0) + 1
            if prize != "낙첨":
                hits += 1
            details.append(detail)

        hit_rate = hits / actual_rounds if actual_rounds > 0 else 0.0

        return SimulationResult(
            total_rounds=actual_rounds,
            prize_counts=prize_counts,
            hit_rate=hit_rate,
            details=details,
        )

    def _evaluate_round(
        self,
        prediction_numbers: list[int],
        actual: DrawResult,
    ) -> str:
        """단일 회차 매칭 결과를 반환합니다 (1등/2등/3등/4등/5등/낙첨)."""
        predicted_set = set(prediction_numbers)
        actual_set = set(actual.numbers())
        bonus = actual.bonus

        matched = len(predicted_set & actual_set)
        has_bonus = bonus in predicted_set

        if matched == 6:  # noqa: PLR2004
            return "1등"
        elif matched == 5 and has_bonus:  # noqa: PLR2004
            return "2등"
        elif matched == 5:  # noqa: PLR2004
            return "3등"
        elif matched == 4:  # noqa: PLR2004
            return "4등"
        elif matched == 3:  # noqa: PLR2004
            return "5등"
        else:
            return "낙첨"

    def _run_round(self, view: HistoricalView, target_round: DrawResult) -> dict[str, Any]:
        """단일 회차에 대해 HistoricalView로 추천 후 매칭을 평가합니다."""
        prior_draws = view.draws
        if len(prior_draws) < 3:  # noqa: PLR2004
            # 데이터 부족 시 무작위로 대체
            import random
            predicted = sorted(random.sample(range(1, 46), 6))
        else:
            try:
                analyzer = LottoAnalyzer()
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    stats = analyzer.analyze(prior_draws)
                recommender = LottoRecommender(stats)
                recommendations = recommender.recommend(count=1)
                predicted = recommendations[0].numbers
            except Exception:
                import random
                predicted = sorted(random.sample(range(1, 46), 6))

        prize = self._evaluate_round(predicted, target_round)
        return {
            "round": target_round.drwNo,
            "predicted": predicted,
            "actual": target_round.numbers(),
            "bonus": target_round.bonus,
            "prize": prize,
        }
