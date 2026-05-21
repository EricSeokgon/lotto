"""데이터 모델: DrawResult, Statistics, Recommendation."""

from __future__ import annotations

import datetime  # noqa: TC003
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DrawResult(BaseModel):
    """단일 추첨 결과."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    drwNo: int = Field(..., ge=1, description="추첨 회차 번호")  # noqa: N815
    date: datetime.date = Field(..., description="추첨 날짜")
    n1: int = Field(..., ge=1, le=45)
    n2: int = Field(..., ge=1, le=45)
    n3: int = Field(..., ge=1, le=45)
    n4: int = Field(..., ge=1, le=45)
    n5: int = Field(..., ge=1, le=45)
    n6: int = Field(..., ge=1, le=45)
    bonus: int = Field(..., ge=1, le=45)

    @field_validator("n1", "n2", "n3", "n4", "n5", "n6", "bonus")
    @classmethod
    def validate_number_range(cls, v: int) -> int:
        """번호가 1~45 범위인지 검증합니다."""
        if not 1 <= v <= 45:
            msg = f"번호는 1~45 범위여야 합니다: {v}"
            raise ValueError(msg)
        return v

    def numbers(self) -> list[int]:
        """당첨 번호 6개를 오름차순으로 반환합니다."""
        return sorted([self.n1, self.n2, self.n3, self.n4, self.n5, self.n6])


class FrequencyStats(BaseModel):
    """번호별 빈도 통계."""

    absolute: dict[int, int] = Field(default_factory=dict, description="절대 빈도")
    relative: dict[int, float] = Field(default_factory=dict, description="상대 빈도")


class RecentPattern(BaseModel):
    """최근 출현 패턴."""

    window: int = Field(default=20, description="분석 회차 수")
    counts: dict[int, int] = Field(default_factory=dict, description="최근 window 내 출현 횟수")


class ConsecutivePattern(BaseModel):
    """연속 출현/제외 스트릭."""

    current_streak: dict[int, int] = Field(
        default_factory=dict,
        description="현재 연속 출현 횟수 (양수=출현, 음수=미출현)",
    )


class PairAnalysis(BaseModel):
    """동반 출현 쌍 분석."""

    top_pairs: list[tuple[int, int, int]] = Field(
        default_factory=list,
        description="상위 20 쌍 [(번호A, 번호B, 동반횟수)]",
    )


class Statistics(BaseModel):
    """통계 분석 결과 (data/stats.json 저장 형식)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    frequency: FrequencyStats = Field(default_factory=FrequencyStats)
    recent_pattern: RecentPattern = Field(default_factory=RecentPattern)
    consecutive_pattern: ConsecutivePattern = Field(default_factory=ConsecutivePattern)
    pair_analysis: PairAnalysis = Field(default_factory=PairAnalysis)
    total_rounds: int = Field(default=0, description="분석에 사용된 총 회차 수")
    # SPEC-LOTTO-003 REQ-BONUS-001: 보너스 번호 빈도 통계 (본 추첨과 독립)
    bonus_frequency: FrequencyStats = Field(
        default_factory=FrequencyStats,
        description="보너스 번호 1~45 절대/상대 빈도",
    )


class Recommendation(BaseModel):
    """번호 추천 결과 단일 세트."""

    numbers: list[int] = Field(..., description="추천 번호 6개 (오름차순)")
    strategy_label: str = Field(..., description="전략 라벨 (고빈도/저빈도/균형/최근편향/동반패턴)")
    strategy_desc: str = Field(default="", description="전략 설명")
    scores: dict[int, float] = Field(default_factory=dict, description="번호별 가중 점수")

    @field_validator("numbers")
    @classmethod
    def validate_numbers(cls, v: list[int]) -> list[int]:
        """6개의 서로 다른 1~45 정수인지 검증합니다."""
        if len(v) != 6:  # noqa: PLR2004
            msg = "추천 번호는 6개여야 합니다"
            raise ValueError(msg)
        if len(set(v)) != 6:  # noqa: PLR2004
            msg = "추천 번호에 중복이 없어야 합니다"
            raise ValueError(msg)
        if not all(1 <= n <= 45 for n in v):
            msg = "추천 번호는 1~45 범위여야 합니다"
            raise ValueError(msg)
        return sorted(v)


class PurchaseTicket(BaseModel):
    """구매한 로또 티켓."""

    id: str = Field(..., description="UUID4 식별자")
    drwNo: int = Field(..., ge=1, description="구매 회차")  # noqa: N815
    numbers: list[int] = Field(..., description="구매 번호 6개 (오름차순)")
    bought_at: str = Field(..., description="구매일 (YYYY-MM-DD)")

    @field_validator("numbers")
    @classmethod
    def validate_numbers(cls, v: list[int]) -> list[int]:
        """6개의 서로 다른 1~45 정수인지 검증합니다."""
        if len(v) != 6:  # noqa: PLR2004
            msg = "번호는 6개여야 합니다."
            raise ValueError(msg)
        if len(set(v)) != 6:  # noqa: PLR2004
            msg = "번호에 중복이 있습니다."
            raise ValueError(msg)
        if not all(1 <= n <= 45 for n in v):
            msg = "번호는 1~45 범위여야 합니다."
            raise ValueError(msg)
        return sorted(v)


class TicketResult(BaseModel):
    """티켓 + 추첨 결과 비교."""

    ticket: PurchaseTicket
    draw_numbers: list[int] = Field(default_factory=list, description="당첨 번호")
    draw_bonus: int = Field(default=0)
    draw_date: str = Field(default="")
    matched: int = Field(default=0, description="일치 번호 수")
    bonus_match: bool = Field(default=False)
    prize: str = Field(default="미추첨", description="1등~5등 | 낙첨 | 미추첨")


class SimulationResult(BaseModel):
    """시뮬레이션 결과 요약."""

    total_rounds: int = Field(..., description="시뮬레이션 회차 수")
    prize_counts: dict[str, int] = Field(
        default_factory=dict,
        description="등수별 당첨 횟수 (1등/2등/3등/4등/5등)",
    )
    hit_rate: float = Field(default=0.0, description="전체 적중률 (5등 이상 / 총 시도)")
    details: list[dict[str, Any]] = Field(default_factory=list, description="회차별 상세 결과")
    per_round_hits: list[int] = Field(
        default_factory=list,
        description="회차별 누적 적중 횟수 (차트용)",
    )
