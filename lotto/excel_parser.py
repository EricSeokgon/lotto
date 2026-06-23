"""엑셀 당첨번호 파일 파서."""
import datetime
import re
from pathlib import Path
from typing import Any, List, Optional  # noqa: UP035

import openpyxl

from lotto.models import DrawResult


def _drw_no_to_date(drw_no: int) -> datetime.date:
    """회차 번호로 추첨 날짜 계산 (1회: 2002-12-07 토요일)."""
    origin = datetime.date(2002, 12, 7)
    return origin + datetime.timedelta(days=(drw_no - 1) * 7)


def _parse_prize_amount(raw: Any) -> Optional[int]:  # noqa: ANN401,UP045 — Python 3.9 호환
    """'3,519,759,000 원' 형태 문자열을 정수로 변환."""
    if raw is None:
        return None
    s = str(raw).replace(",", "").replace("원", "").strip()
    try:
        return int(s)
    except ValueError:
        return None


def _parse_prize_winners(raw: Any) -> Optional[int]:  # noqa: ANN401,UP045 — Python 3.9 호환
    """'8 명' 형태 문자열을 정수로 변환."""
    if raw is None:
        return None
    m = re.search(r"\d+", str(raw))
    return int(m.group()) if m else None


def parse_excel(path: Path) -> List[DrawResult]:  # noqa: UP006 — Python 3.9 호환
    """동행복권 엑셀 파일을 파싱하여 DrawResult 목록 반환.

    Args:
        path: 엑셀 파일 경로

    Returns:
        DrawResult 목록 (유효한 행만 포함)
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    results: List[DrawResult] = []  # noqa: UP006 — Python 3.9 호환

    for row in ws.iter_rows(min_row=2, values_only=True):  # 헤더 스킵
        if not row or row[1] is None:
            continue
        try:
            drw_no = int(row[1])
            nums = [int(row[c]) for c in range(2, 8)]
            bonus = int(row[8])
            prize_amount = _parse_prize_amount(row[11])
            prize_winners = _parse_prize_winners(row[10])
            results.append(DrawResult(
                drwNo=drw_no,
                date=_drw_no_to_date(drw_no),
                n1=nums[0], n2=nums[1], n3=nums[2],
                n4=nums[3], n5=nums[4], n6=nums[5],
                bonus=bonus,
                prize1Amount=prize_amount,
                prize1Winners=prize_winners,
            ))
        except (TypeError, ValueError, IndexError):
            continue  # 파싱 불가 행 스킵

    wb.close()
    return results
