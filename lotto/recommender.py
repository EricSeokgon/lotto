"""LottoRecommender — 가중 점수 기반 번호 추천."""

from __future__ import annotations

import random
import warnings
from dataclasses import dataclass

from lotto.config import settings
from lotto.models import Recommendation, Statistics

# SPEC-LOTTO-002: 추천 가중치 외부화 — LOTTO_RECOMMENDER_WEIGHTS 환경 변수로 오버라이드 가능
DEFAULT_WEIGHTS = settings.recommender_weights
STRATEGY_LABELS = [
    "고빈도", "저빈도", "균형", "최근편향",
    "동반패턴", "홀짝균형", "번호대균형", "핫콜드혼합",
    "갭분석", "앙상블",
]
STRATEGY_DESCRIPTIONS = {
    "고빈도": "역대 가장 자주 나온 번호를 중심으로 선택합니다.",
    "저빈도": "상대적으로 덜 나온 번호로 역발상 조합을 만듭니다.",
    "균형": "전체 번호 범위에서 고르게 선택합니다.",
    "최근편향": "최근 20회 출현이 많은 번호를 우선합니다.",
    "동반패턴": "함께 자주 나온 번호 쌍을 반영합니다.",
    "홀짝균형": "홀수 3개, 짝수 3개로 균형 잡힌 조합을 만듭니다.",
    "번호대균형": "1~45 구간을 5개 영역으로 나눠 고르게 선택합니다.",
    "핫콜드혼합": "자주 나온 번호 3개와 오랫동안 안 나온 번호 3개를 섞습니다.",
    "갭분석": "오랫동안 출현하지 않은 번호(갭 분석)를 중심으로 선택합니다.",
    "앙상블": "빈도·최근·갭·동반 패턴을 균등하게 조합한 복합 전략입니다.",
}
MIN_COUNT = 1
MAX_COUNT = 20
NUM_BALLS = 45

# 전략별 (freq, recent, pair, gap) 가중치 테이블
_STRATEGY_WEIGHTS: dict[str, tuple[float, float, float, float]] = {
    "고빈도":     (0.60, 0.25, 0.10, 0.05),
    "저빈도":     (0.60, 0.20, 0.10, 0.10),  # freq를 역전하여 적용
    "균형":       (0.35, 0.30, 0.20, 0.15),
    "최근편향":   (0.15, 0.65, 0.10, 0.10),
    "동반패턴":   (0.15, 0.15, 0.65, 0.05),
    "홀짝균형":   (0.35, 0.30, 0.20, 0.15),
    "번호대균형": (0.35, 0.30, 0.20, 0.15),
    "핫콜드혼합": (0.35, 0.25, 0.15, 0.25),
    "갭분석":     (0.10, 0.10, 0.10, 0.70),
    "앙상블":     (0.25, 0.25, 0.25, 0.25),
}


@dataclass(frozen=True)
class Weights:
    """가중치 설정 (w_freq, w_recent, w_pair, w_consec).

    SPEC-LOTTO-002: 기본값은 LOTTO_RECOMMENDER_WEIGHTS 환경 변수에서 결정됨.
    """

    w_freq: float = DEFAULT_WEIGHTS[0]
    w_recent: float = DEFAULT_WEIGHTS[1]
    w_pair: float = DEFAULT_WEIGHTS[2]
    w_consec: float = DEFAULT_WEIGHTS[3]

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

    def _gap_scores(self) -> dict[int, float]:
        """장기 미출현(갭) 점수를 계산합니다.

        consecutive_pattern.current_streak 음수 값(미출현 회차)을 갭 지표로 사용.
        값이 클수록 오랫동안 출현하지 않은 번호.
        """
        streaks = self._stats.consecutive_pattern.current_streak
        gap_raw: dict[int, float] = {}
        for n in range(1, NUM_BALLS + 1):
            streak = streaks.get(n, 0)
            gap_raw[n] = float(max(0, -streak))
        return _normalize(gap_raw)

    def _strategy_scores(
        self,
        label: str,
        used_numbers: set[int] | None = None,
    ) -> dict[int, float]:
        """전략별 맞춤 가중치로 점수를 계산합니다.

        각 전략이 중시하는 신호(빈도·최근·동반·갭)의 비중을 달리하여
        추천 세트 간 다양성을 높입니다. used_numbers에 있는 번호에는
        다양성 페널티를 적용합니다.
        """
        freq_abs = self._stats.frequency.absolute
        recent_counts = self._stats.recent_pattern.counts
        top_pairs = self._stats.pair_analysis.top_pairs

        freq_base = _normalize(
            {n: float(freq_abs.get(n, 0)) for n in range(1, NUM_BALLS + 1)}
        )
        recent_norm = _normalize(
            {n: float(recent_counts.get(n, 0)) for n in range(1, NUM_BALLS + 1)}
        )

        pair_raw: dict[int, float] = dict.fromkeys(range(1, NUM_BALLS + 1), 0.0)
        for a, b, count in top_pairs:
            pair_raw[a] = pair_raw.get(a, 0.0) + count
            pair_raw[b] = pair_raw.get(b, 0.0) + count
        pair_norm = _normalize(pair_raw)

        gap_norm = self._gap_scores()

        wf, wr, wp, wg = _STRATEGY_WEIGHTS.get(label, (0.35, 0.30, 0.20, 0.15))

        # 저빈도 전략: 빈도 신호를 역전하여 덜 나온 번호에 높은 점수 부여
        freq_norm = (
            {n: 1.0 - v for n, v in freq_base.items()}
            if label == "저빈도"
            else freq_base
        )

        scores: dict[int, float] = {}
        for n in range(1, NUM_BALLS + 1):
            scores[n] = (
                wf * freq_norm.get(n, 0.0)
                + wr * recent_norm.get(n, 0.0)
                + wp * pair_norm.get(n, 0.0)
                + wg * gap_norm.get(n, 0.0)
            )

        # 다양성 페널티: 직전 세트에 사용된 번호의 점수를 낮춰 번호 분산 유도
        if used_numbers:
            for n in used_numbers:
                if n in scores:
                    scores[n] = max(0.0, scores[n] - 0.12)

        return scores

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

        # SPEC-LOTTO-003 REQ-BONUS-004: 보너스 회피 페널티 (가중치 > 0 일 때만 계산)
        bonus_avoidance = float(getattr(settings, "bonus_avoidance_weight", 0.0))
        bonus_norm: dict[int, float] = dict.fromkeys(range(1, NUM_BALLS + 1), 0.0)
        if bonus_avoidance > 0:
            bonus_abs = self._stats.bonus_frequency.absolute
            bonus_norm = _normalize(
                {n: float(bonus_abs.get(n, 0)) for n in range(1, NUM_BALLS + 1)}
            )

        scores: dict[int, float] = {}
        for n in range(1, NUM_BALLS + 1):
            scores[n] = (
                w.w_freq * freq_norm.get(n, 0.0)
                + w.w_recent * recent_norm.get(n, 0.0)
                + w.w_pair * pair_norm.get(n, 0.0)
                - w.w_consec * consec_norm.get(n, 0.0)
                - bonus_avoidance * bonus_norm.get(n, 0.0)
            )
        return scores

    def recommend_by_strategy(self, strategy_label: str) -> Recommendation:
        """지정한 전략으로 번호 세트 1개를 추천합니다."""
        if strategy_label not in STRATEGY_LABELS:
            msg = f"알 수 없는 전략: {strategy_label}"
            raise ValueError(msg)
        scores = self._strategy_scores(strategy_label)
        numbers, label = self._pick_set(scores, set(), force_label=strategy_label)
        return Recommendation(
            numbers=numbers,
            strategy_label=label,
            strategy_desc=STRATEGY_DESCRIPTIONS.get(label, ""),
            scores={n: scores.get(n, 0.0) for n in numbers},
        )

    # @MX:ANCHOR: [AUTO] recommend() — 번호 추천 핵심 메서드
    # @MX:REASON: CLI(main.py), simulator, test에서 호출 (fan_in >= 3)
    def recommend(self, count: int = 5) -> list[Recommendation]:
        """count 개의 번호 세트를 추천합니다 (1 ≤ count ≤ 20)."""
        if not (MIN_COUNT <= count <= MAX_COUNT):
            msg = f"count는 {MIN_COUNT}~{MAX_COUNT} 범위여야 합니다: {count}"
            raise ValueError(msg)

        used_sets: set[frozenset[int]] = set()
        used_numbers: set[int] = set()
        results: list[Recommendation] = []

        for i in range(count):
            label = STRATEGY_LABELS[i % len(STRATEGY_LABELS)]
            scores = self._strategy_scores(label, used_numbers)
            numbers, actual_label = self._pick_set(scores, used_sets, force_label=label)
            used_sets.add(frozenset(numbers))
            used_numbers.update(numbers)
            results.append(
                Recommendation(
                    numbers=numbers,
                    strategy_label=actual_label,
                    strategy_desc=STRATEGY_DESCRIPTIONS.get(actual_label, ""),
                    scores={n: scores.get(n, 0.0) for n in numbers},
                )
            )
        return results

    # @MX:WARN: [AUTO] _pick_set — 전략 분기 10개로 복잡도 임계치 초과
    # @MX:REASON: 전략 수 증가(8→10)로 if-branches >= 10; 전략 추가 시 주의
    def _pick_set(
        self,
        scores: dict[int, float],
        excluded: set[frozenset[int]],
        force_label: str | None = None,
    ) -> tuple[list[int], str]:
        """점수 기반으로 6개 번호를 선택하고 전략 라벨을 반환합니다."""
        # 전략 순환: force_label이 주어지면 그대로, 아니면 excluded 수 기반 순환
        if force_label is not None:
            label = force_label
        else:
            strategy_idx = len(excluded) % len(STRATEGY_LABELS)
            label = STRATEGY_LABELS[strategy_idx]

        sorted_nums = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)

        if label == "고빈도":
            candidates = sorted_nums[:20]
        elif label == "저빈도":
            # _strategy_scores에서 freq 역전 → sorted_nums[:20]이 저빈도 번호
            candidates = sorted_nums[:20]
        elif label == "균형":
            candidates = list(range(1, NUM_BALLS + 1))
        elif label == "최근편향":
            candidates = sorted_nums[:25]
        elif label == "동반패턴":
            candidates = sorted_nums[:20]
        elif label == "갭분석":
            candidates = sorted_nums[:22]
        elif label == "앙상블":
            candidates = sorted_nums[:25]
        elif label == "홀짝균형":
            odds = [n for n in range(1, 46) if n % 2 == 1]
            evens = [n for n in range(1, 46) if n % 2 == 0]
            for _ in range(100):
                half_o = sorted(random.sample(odds, 3))
                half_e = sorted(random.sample(evens, 3))
                picked = sorted(half_o + half_e)
                if frozenset(picked) not in excluded:
                    return picked, label
            candidates = list(range(1, NUM_BALLS + 1))
        elif label == "번호대균형":
            zones = [(1, 9), (10, 19), (20, 29), (30, 39), (40, 45)]
            for _ in range(100):
                zone_list = list(zones)
                random.shuffle(zone_list)
                zone_picks = []
                for z_start, z_end in zone_list[:4]:
                    zone_picks.append(random.randint(z_start, z_end))
                remaining_pool = [n for n in range(1, 46) if n not in zone_picks]
                zone_picks += random.sample(remaining_pool, 2)
                picked = sorted(zone_picks)
                if len(set(picked)) == 6 and frozenset(picked) not in excluded:  # noqa: PLR2004
                    return picked, label
            candidates = list(range(1, NUM_BALLS + 1))
        else:  # 핫콜드혼합
            sorted_by_freq = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)
            hot = sorted_by_freq[:15]
            cold = sorted_by_freq[-15:]
            for _ in range(100):
                hot_pick = random.sample(hot, 3)
                cold_pick = random.sample(cold, 3)
                picked = sorted(set(hot_pick + cold_pick))
                if len(picked) == 6 and frozenset(picked) not in excluded:  # noqa: PLR2004
                    return picked, label
            candidates = list(range(1, NUM_BALLS + 1))

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
