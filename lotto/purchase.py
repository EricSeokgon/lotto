"""SPEC-LOTTO-014: 구매 이력 관리 — Pydantic 모델, JSON CRUD, 등수 계산.

# @MX:ANCHOR: [AUTO] 구매 이력 CRUD 및 등수 계산 핵심 모듈
# @MX:REASON: purchases API 라우터, 페이지 라우터에서 호출되는 공개 경계 (fan_in >= 2)
# @MX:SPEC: SPEC-LOTTO-014 REQ-014-001~033
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator

from lotto.config import settings

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from lotto.models import DrawResult

_log = logging.getLogger(__name__)

# 등수별 고정 당첨금 (1등/2등은 변동이므로 0)
_PRIZE_AMOUNTS: dict[str, int] = {
    "1st": 0,
    "2nd": 0,
    "3rd": 1_500_000,
    "4th": 50_000,
    "5th": 5_000,
    "none": 0,
    "pending": 0,
}

# @MX:NOTE: [AUTO] 테스트에서 monkeypatch.setattr("lotto.purchase._PURCHASES_PATH", ...) 로 패치
_PURCHASES_PATH: Path = settings.data_dir / "purchases.json"


class PurchaseCreate(BaseModel):
    """구매 번호 입력 모델."""

    drwNo: int = Field(..., ge=1, description="추첨 회차 번호")  # noqa: N815
    numbers: list[int] = Field(..., description="구매 번호 6개")

    @field_validator("numbers")
    @classmethod
    def validate_numbers(cls, v: list[int]) -> list[int]:
        """번호 유효성 검사: 6개, 1~45 범위, 중복 없음."""
        if len(v) != 6:  # noqa: PLR2004
            msg = f"번호는 6개여야 합니다: {len(v)}개 입력됨"
            raise ValueError(msg)
        if not all(1 <= n <= 45 for n in v):  # noqa: PLR2004
            msg = "번호는 1~45 범위여야 합니다"
            raise ValueError(msg)
        if len(set(v)) != 6:  # noqa: PLR2004
            msg = "번호에 중복이 있습니다"
            raise ValueError(msg)
        return sorted(v)


class PurchaseRecord(BaseModel):
    """저장되는 구매 이력 레코드."""

    id: int
    drwNo: int  # noqa: N815
    numbers: list[int]
    purchased_at: str


class PurchaseResponse(BaseModel):
    """API 응답용 구매 이력 (등수 정보 포함)."""

    id: int
    drwNo: int  # noqa: N815
    numbers: list[int]
    purchased_at: str
    prize_rank: str
    prize_amount: int
    matched_count: int
    matched_bonus: bool


def calc_prize(
    numbers: list[int],
    draw: DrawResult | None,
) -> tuple[str, int, int, bool]:
    """등수, 당첨금, 일치 수, 보너스 일치 여부를 계산합니다.

    Args:
        numbers: 구매 번호 6개
        draw: 추첨 결과 (None이면 pending)

    Returns:
        (prize_rank, prize_amount, matched_count, matched_bonus)
    """
    if draw is None:
        return "pending", 0, 0, False

    draw_numbers = set(draw.numbers())
    purchase_set = set(numbers)
    matched = len(purchase_set & draw_numbers)
    bonus_match = draw.bonus in purchase_set

    if matched == 6:  # noqa: PLR2004
        rank = "1st"
    elif matched == 5 and bonus_match:  # noqa: PLR2004
        rank = "2nd"
    elif matched == 5:  # noqa: PLR2004
        rank = "3rd"
    elif matched == 4:  # noqa: PLR2004
        rank = "4th"
    elif matched == 3:  # noqa: PLR2004
        rank = "5th"
    else:
        rank = "none"

    return rank, _PRIZE_AMOUNTS[rank], matched, bonus_match


def load_purchases(path: Path) -> list[PurchaseRecord]:
    """JSON 파일에서 구매 이력을 불러옵니다.

    파일 없음, 파싱 오류, 형식 오류 시 빈 목록 반환.
    """
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _log.warning("purchases.json 파싱 실패 — 빈 목록 반환")
        return []
    if not isinstance(data, list):
        _log.warning("purchases.json 최상위가 list 아님 — 빈 목록 반환")
        return []
    try:
        return [PurchaseRecord.model_validate(item) for item in data]
    except Exception:  # noqa: BLE001
        _log.warning("purchases.json ValidationError — 빈 목록 반환")
        return []


def save_purchases(path: Path, records: list[PurchaseRecord]) -> None:
    """구매 이력을 JSON 파일에 원자적으로 저장합니다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps([r.model_dump() for r in records], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def add_purchase(path: Path, drw_no: int, numbers: list[int]) -> PurchaseRecord:
    """구매 이력을 추가하고 새 레코드를 반환합니다."""
    records = load_purchases(path)
    next_id = max((r.id for r in records), default=0) + 1
    record = PurchaseRecord(
        id=next_id,
        drwNo=drw_no,
        numbers=sorted(numbers),
        purchased_at=datetime.datetime.now().isoformat(timespec="seconds"),
    )
    records.append(record)
    save_purchases(path, records)
    return record


def delete_purchase(path: Path, purchase_id: int) -> bool:
    """구매 이력을 삭제합니다. 존재하면 True, 없으면 False 반환."""
    records = load_purchases(path)
    filtered = [r for r in records if r.id != purchase_id]
    if len(filtered) == len(records):
        return False
    save_purchases(path, filtered)
    return True


def build_responses(
    records: list[PurchaseRecord],
    draws_by_drw_no: dict[int, DrawResult],
) -> list[PurchaseResponse]:
    """레코드 목록을 등수 정보가 포함된 응답 목록으로 변환합니다 (id 역순)."""
    result = []
    for r in sorted(records, key=lambda x: x.id, reverse=True):
        draw = draws_by_drw_no.get(r.drwNo)
        rank, amount, matched, bonus = calc_prize(r.numbers, draw)
        result.append(
            PurchaseResponse(
                id=r.id,
                drwNo=r.drwNo,
                numbers=r.numbers,
                purchased_at=r.purchased_at,
                prize_rank=rank,
                prize_amount=amount,
                matched_count=matched,
                matched_bonus=bonus,
            )
        )
    return result
