"""LottoAnalyzer — 4종 통계 분석 (빈도/최근패턴/연속패턴/동반쌍)."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any

import numpy as np

from lotto.models import (
    ConsecutivePattern,
    DrawResult,
    PairAnalysis,
    RecentPattern,
)

# SPEC-LOTTO-045: 명시적 재노출(PEP 484 redundant-alias). analyzer의 공개 출력 타입을
# 소비 모듈/테스트가 lotto.analyzer 경로로 임포트할 수 있도록 한다 (런타임 동작 무관).
from lotto.models import FrequencyStats as FrequencyStats
from lotto.models import Statistics as Statistics

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

DEFAULT_RECENT_WINDOW = 20
DEFAULT_TOP_PAIRS = 20
NUM_BALLS = 45


class LottoAnalyzer:
    """당첨 데이터로부터 4종 통계를 분석합니다."""

    def __init__(self, recent_window: int = DEFAULT_RECENT_WINDOW) -> None:
        self._recent_window = recent_window

    # @MX:ANCHOR: [AUTO] analyze() — 4종 통계 일괄 분석의 핵심 진입점
    # @MX:REASON: simulator, recommender, CLI에서 모두 호출 (fan_in >= 3)
    def analyze(self, draws: list[DrawResult]) -> Statistics:
        """4종 통계를 일괄 분석하여 Statistics를 반환합니다."""
        freq_data = self.compute_frequency(draws)
        recent_data = self.compute_recent_pattern(draws)
        consecutive_data = self.compute_consecutive_pattern(draws)
        pair_data = self.compute_pair_analysis(draws)
        # SPEC-LOTTO-003 REQ-BONUS-002: 보너스 빈도 계산
        bonus_freq_data = self.compute_bonus_frequency(draws)

        freq_stats = FrequencyStats(
            absolute={int(k): int(v) for k, v in freq_data["absolute"].items()},
            relative={int(k): float(v) for k, v in freq_data["relative"].items()},
        )
        recent_pattern = RecentPattern(
            window=int(recent_data.get("window", self._recent_window)),
            counts={int(k): int(v) for k, v in recent_data["counts"].items()},
        )
        consecutive_pattern = ConsecutivePattern(
            current_streak={int(k): int(v) for k, v in consecutive_data["current_streak"].items()},
        )
        pair_analysis = PairAnalysis(
            top_pairs=[(int(a), int(b), int(c)) for a, b, c in pair_data],
        )
        bonus_frequency = FrequencyStats(
            absolute={int(k): int(v) for k, v in bonus_freq_data["absolute"].items()},
            relative={int(k): float(v) for k, v in bonus_freq_data["relative"].items()},
        )

        return Statistics(
            frequency=freq_stats,
            recent_pattern=recent_pattern,
            consecutive_pattern=consecutive_pattern,
            pair_analysis=pair_analysis,
            total_rounds=len(draws),
            bonus_frequency=bonus_frequency,
        )

    def compute_bonus_frequency(self, draws: list[DrawResult]) -> dict[str, Any]:
        """보너스 번호 1~45 절대/상대 빈도를 계산합니다.

        SPEC-LOTTO-003 REQ-BONUS-002: 본 추첨 6개 번호와 독립적으로 계산.
        """
        absolute: dict[int, int] = dict.fromkeys(range(1, NUM_BALLS + 1), 0)
        for draw in draws:
            absolute[draw.bonus] += 1

        total = len(draws)
        relative: dict[int, float] = {}
        for n in range(1, NUM_BALLS + 1):
            relative[n] = absolute[n] / total if total > 0 else 0.0

        return {"absolute": absolute, "relative": relative}

    def compute_frequency(self, draws: list[DrawResult]) -> dict[str, Any]:
        """번호 1~45 절대/상대 빈도를 계산합니다."""
        absolute: dict[int, int] = dict.fromkeys(range(1, NUM_BALLS + 1), 0)
        total_numbers = 0

        for draw in draws:
            for n in draw.numbers():
                absolute[n] += 1
                total_numbers += 1

        relative: dict[int, float] = {}
        for n in range(1, NUM_BALLS + 1):
            relative[n] = absolute[n] / total_numbers if total_numbers > 0 else 0.0

        return {"absolute": absolute, "relative": relative}

    def compute_recent_pattern(
        self,
        draws: list[DrawResult],
        window: int | None = None,
    ) -> dict[str, Any]:
        """최근 N 회차 출현 패턴을 계산합니다."""
        effective_window = window if window is not None else self._recent_window
        result: dict[str, Any] = {}

        if effective_window > len(draws):
            msg = (
                f"window={effective_window}이 가용 회차 수 {len(draws)}보다 큽니다. "
                f"가용 회차 수로 계산합니다."
            )
            warnings.warn(msg, stacklevel=2)
            result["warning"] = msg
            effective_window = len(draws)

        recent = draws[-effective_window:] if effective_window > 0 else []
        counts: dict[int, int] = dict.fromkeys(range(1, NUM_BALLS + 1), 0)

        for draw in recent:
            for n in draw.numbers():
                counts[n] += 1

        result["window"] = effective_window
        result["counts"] = counts
        return result

    def compute_consecutive_pattern(self, draws: list[DrawResult]) -> dict[str, Any]:
        """연속 출현/제외 스트릭을 계산합니다."""
        streaks: dict[int, int] = dict.fromkeys(range(1, NUM_BALLS + 1), 0)

        if not draws:
            return {"current_streak": streaks}

        # 가장 최근 회차부터 거슬러 올라가며 스트릭 계산
        for n in range(1, NUM_BALLS + 1):
            last_round_appeared = False
            streak = 0
            for draw in reversed(draws):
                appeared = n in draw.numbers()
                if streak == 0:
                    # 첫 라운드에서 방향 결정
                    last_round_appeared = appeared
                    streak = 1 if appeared else -1
                elif appeared == last_round_appeared:
                    streak = streak + 1 if appeared else streak - 1
                else:
                    break
            streaks[n] = streak

        return {"current_streak": streaks}

    def compute_pair_analysis(
        self,
        draws: list[DrawResult],
        top_n: int = DEFAULT_TOP_PAIRS,
    ) -> list[tuple[int, int, int]]:
        """동반 출현 쌍 상위 N개를 numpy 행렬로 계산합니다."""
        matrix = np.zeros((NUM_BALLS + 1, NUM_BALLS + 1), dtype=np.int32)

        for draw in draws:
            nums = draw.numbers()
            for i in range(len(nums)):
                for j in range(i + 1, len(nums)):
                    a, b = nums[i], nums[j]
                    matrix[a][b] += 1
                    matrix[b][a] += 1

        # 상삼각 행렬에서 상위 top_n 추출
        pairs: list[tuple[int, int, int]] = []
        for a in range(1, NUM_BALLS + 1):
            for b in range(a + 1, NUM_BALLS + 1):
                count = int(matrix[a][b])
                if count > 0:
                    pairs.append((a, b, count))

        pairs.sort(key=lambda x: x[2], reverse=True)
        return pairs[:top_n]

    def save_stats(self, stats: Statistics, path: Path) -> None:
        """Statistics를 JSON으로 저장합니다."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(stats.model_dump_json(), encoding="utf-8")

    @staticmethod
    def load_stats(path: Path) -> Statistics:
        """JSON에서 Statistics를 로드합니다."""
        if not path.exists():
            msg = f"통계 파일을 찾을 수 없습니다: {path}"
            raise FileNotFoundError(msg)
        return Statistics.model_validate_json(path.read_text(encoding="utf-8"))
