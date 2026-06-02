"""SPEC-LOTTO-014: 구매 이력 REST API 라우터."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

import lotto.purchase as _pm
from lotto.web.data import get_draws

if TYPE_CHECKING:  # pragma: no cover
    from lotto.models import DrawResult

router = APIRouter(prefix="/api", tags=["purchases"])


@router.post("/purchases", status_code=HTTPStatus.CREATED)
async def create_purchase(body: _pm.PurchaseCreate) -> _pm.PurchaseRecord:
    """구매 번호를 등록합니다."""
    return _pm.add_purchase(_pm._PURCHASES_PATH, body.drwNo, body.numbers)


@router.get("/purchases")
async def list_purchases() -> list[_pm.PurchaseResponse]:
    """구매 이력 전체를 등수 정보와 함께 반환합니다."""
    records = _pm.load_purchases(_pm._PURCHASES_PATH)
    draws = get_draws()
    # SPEC-LOTTO-045: get_draws()는 데이터 부재 시 None 반환. pages.py:listings 와 동일하게
    # None이면 빈 매핑으로 처리하여 등수 정보 없이 구매 이력을 반환한다 (동작 보존).
    draws_by_drw_no: dict[int, DrawResult] = {d.drwNo: d for d in draws} if draws else {}
    return _pm.build_responses(records, draws_by_drw_no)


@router.delete("/purchases/{purchase_id}", status_code=HTTPStatus.NO_CONTENT)
async def remove_purchase(purchase_id: int) -> None:
    """구매 이력을 삭제합니다."""
    deleted = _pm.delete_purchase(_pm._PURCHASES_PATH, purchase_id)
    if not deleted:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="구매 이력을 찾을 수 없습니다",
        )
