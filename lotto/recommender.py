"""LottoRecommender — 가중 점수 기반 번호 추천."""

from __future__ import annotations

import random
import warnings
from dataclasses import dataclass

from lotto.models import Recommendation, Statistics

DEFAULT_WEIGHTS = (0.4, 0.3, 0.2, 0.1)
STRATEGY_LABELS = ["고빈도", "저빈도", "균형", "최근편향", "동반패턴"]
MIN_COUNT = 1
MAX_COUNT = 20
NUM_BALLS = 45


@dataclass(frozen=True)
class Weights:
    """가중치 설정 (w_freq, w_recent, w_pair, w_consec)."""

    w_freq: float = 0.4
    w_recent: float = 0.3
    w_pair: float = 0.2
    w_consec: float = 0.1

    def __post_init__(self) -> None:
        """모든 가중치가 음수가 아니고 합이 0보다 큰지 검증합니다."""
        if any(w < 0 for w in [self.w_freq, self.w_recent, self.w_pair, self.w_consec]):
            msg = "가중치는 음수일 수 없습니다"
            raise ValueError(msg)
        if self.w_freq + self.w_recent + self.w_pair + self.w_consec <= 0:
            msg = "가중치 합이 0보다 커야 합니다"
            raise ValueError(msg)


def _normalize(values: dict[int, float]) -> dict[int, float]:
    """딕셔너리 값을 0~1 범위로 정규화합니다."""
    min_v = min(values.values()) if values else 0.0
    max_v = max(values.values()) if values else 0.0
    span = max_v - min_v
    if span == 0:
        return dict.fromkeys(values, 0.5)
    return {k: (v - min_v) / span for k, v in values.items()}


class LottoRecommender:
    """가중 점수 공식으로 번호 세트를 추천합니다."""

    def __init__(self, stats: Statistics, weights: Weights | None = None) -> None:
        self._stats = stats
        self._weights = weights or Weights()

    def compute_scores(self) -> dict[int, float]:
        """번호 1~45 각각의 가중 점수를 계산합니다."""
        w = self._weights
        freq_abs = self._stats.frequency.absolute
        recent_counts = self._stats.recent_pattern.counts
        streaks = self._stats.consecutive_pattern.current_streak
        top_pairs = self._stats.pair_analysis.top_pairs

        # 빈도 정규화
        freq_norm = _normalize({n: float(freq_abs.get(n, 0)) for n in range(1, NUM_BALLS + 1)})

        # 최근 패턴 정규화
        recent_norm = _normalize(
            {n: float(recent_counts.get(n, 0)) for n in range(1, NUM_BALLS + 1)}
        )

        # 동반 패턴 점수: 동반 횟수 합계
        pair_scores: dict[int, float] = dict.fromkeys(range(1, NUM_BALLS + 1), 0.0)
        for a, b, count in top_pairs:
            pair_scores[a] = pair_scores.get(a, 0.0) + count
            pair_scores[b] = pair_scores.get(b, 0.0) + count
        pair_norm = _normalize(pair_scores)

        # 연속 패턴 페널티: 음수 스트릭(장기 미출현)은 패널티
        consec_penalty: dict[int, float] = {}
        for n in range(1, NUM_BALLS + 1):
            streak = streaks.get(n, 0)
            # 음수면 패널티, 양수면 0
            consec_penalty[n] = float(max(0, -streak))
        consec_norm = _normalize(consec_penalty)

        scores: dict[int, float] = {}
        for n in range(1, NUM_BALLS + 1):
            scores[n] = (
                w.w_freq * freq_norm.get(n, 0.0)
                + w.w_recent * recent_norm.get(n, 0.0)
                + w.w_pair * pair_norm.get(n, 0.0)
                - w.w_consec * consec_norm.get(n, 0.0)
            )
        return scores

    # @MX:ANCHOR: [AUTO] recommend() — 번호 추천 핵심 메서드
    # @MX:REASON: CLI(main.py), simulator, test에서 호출 (fan_in >= 3)
    def recommend(self, count: int = 5) -> list[Recommendation]:
        """count 개의 번호 세트를 추천합니다 (1 ≤ count ≤ 20)."""
        if not (MIN_COUNT <= count <= MAX_COUNT):
            msg = f"count는 {MIN_COUNT}~{MAX_COUNT} 범위여야 합니다: {count}"
            raise ValueError(msg)

        scores = self.compute_scores()
        used_sets: set[frozenset[int]] = set()
        results: list[Recommendation] = []

        for _ in range(count):
            numbers, label = self._pick_set(scores, used_sets)
            used_sets.add(frozenset(numbers))
            results.append(
                Recommendation(
                    numbers=numbers,
                    strategy_label=label,
                    scores={n: scores.get(n, 0.0) for n in numbers},
                )
            )
        return results

    def _pick_set(
        self,
        scores: dict[int, float],
        excluded: set[frozenset[int]],
    ) -> tuple[list[int], str]:
        """점수 기반으로 6개 번호를 선택하고 전략 라벨을 반환합니다."""
        # 전략 순환: 이미 사용된 세트 수에 따라 라벨 결정
        strategy_idx = len(excluded) % len(STRATEGY_LABELS)
        label = STRATEGY_LABELS[strategy_idx]

        sorted_nums = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)

        if label == "고빈도":
            # 상위 번호에서 선택
            candidates = sorted_nums[:20]
        elif label == "저빈도":
            # 하위 번호에서 선택
            candidates = sorted_nums[-20:]
        elif label == "균형":
            # 고른 분포
            candidates = list(range(1, NUM_BALLS + 1))
        elif label == "최근편향":
            # 최근 패턴 반영 (이미 scores에 포함됨)
            candidates = sorted_nums[:25]
        else:  # 동반패턴
            candidates = sorted_nums[:20]

        # 중복 세트 방지: 최대 100회 시도
        for _ in range(100):
            if len(candidates) < 6:  # noqa: PLR2004
                warnings.warn("후보 번호 부족: 전체 범위에서 무작위 선택합니다.", stacklevel=2)
                candidates = list(range(1, NUM_BALLS + 1))
            picked = sorted(random.sample(candidates, 6))
            if frozenset(picked) not in excluded:
                return picked, label

        # 모든 시도 실패 시 전체에서 무작위
        warnings.warn("중복 없는 세트 생성 실패. 전체 범위에서 무작위 선택합니다.", stacklevel=2)
        all_nums = list(range(1, NUM_BALLS + 1))
        for _ in range(1000):
            picked = sorted(random.sample(all_nums, 6))
            if frozenset(picked) not in excluded:
                return picked, label
        msg = "추천 세트를 생성할 수 없습니다"
        raise RuntimeError(msg)
