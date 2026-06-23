"""엑셀 파서 테스트 (SPEC-LOTTO-112)."""
import datetime
from pathlib import Path

import pytest

from lotto.excel_parser import (
    _drw_no_to_date,
    _parse_prize_amount,
    _parse_prize_winners,
    parse_excel,
)

# 실제 엑셀 파일 경로 (프로젝트 루트)
EXCEL_PATH = Path(__file__).parent.parent / "로또 회차별 당첨번호_20260623082042.xlsx"


class TestDrwNoToDate:
    """_drw_no_to_date 날짜 계산 테스트."""

    def test_drw_no_1_is_2002_12_07(self) -> None:
        """1회차는 2002-12-07 토요일이어야 합니다."""
        result = _drw_no_to_date(1)
        assert result == datetime.date(2002, 12, 7)
        assert result.weekday() == 5  # 토요일

    def test_drw_no_1229_is_2026_06_20(self) -> None:
        """1229회차는 2026-06-20이어야 합니다."""
        result = _drw_no_to_date(1229)
        assert result == datetime.date(2026, 6, 20)
        assert result.weekday() == 5  # 토요일


class TestParsePrizeAmount:
    """_parse_prize_amount 파싱 테스트."""

    def test_parse_prize_amount_korean_format(self) -> None:
        """'3,519,759,000 원' 형태를 정수로 변환합니다."""
        result = _parse_prize_amount("3,519,759,000 원")
        assert result == 3_519_759_000

    def test_parse_prize_amount_none(self) -> None:
        """None 입력은 None을 반환합니다."""
        assert _parse_prize_amount(None) is None

    def test_parse_prize_amount_invalid_string(self) -> None:
        """변환 불가 문자열은 None을 반환합니다."""
        assert _parse_prize_amount("N/A") is None

    def test_parse_prize_amount_plain_integer(self) -> None:
        """쉼표 없는 순수 숫자 문자열도 처리합니다."""
        assert _parse_prize_amount("1000000") == 1_000_000


class TestParsePrizeWinners:
    """_parse_prize_winners 파싱 테스트."""

    def test_parse_prize_winners_korean_format(self) -> None:
        """'8 명' 형태를 정수로 변환합니다."""
        result = _parse_prize_winners("8 명")
        assert result == 8

    def test_parse_prize_winners_none(self) -> None:
        """None 입력은 None을 반환합니다."""
        assert _parse_prize_winners(None) is None

    def test_parse_prize_winners_no_digit(self) -> None:
        """숫자가 없는 문자열은 None을 반환합니다."""
        assert _parse_prize_winners("없음") is None


class TestParseExcel:
    """parse_excel 통합 테스트."""

    def test_parse_excel_success(self) -> None:
        """실제 엑셀 파일을 파싱하여 DrawResult 목록을 반환합니다."""
        if not EXCEL_PATH.exists():
            pytest.skip(f"엑셀 파일 없음: {EXCEL_PATH}")

        results = parse_excel(EXCEL_PATH)

        assert len(results) > 0
        # 모든 항목이 DrawResult 필드를 올바르게 포함해야 합니다
        for draw in results:
            assert draw.drwNo >= 1
            assert 1 <= draw.n1 <= 45
            assert 1 <= draw.bonus <= 45
            assert isinstance(draw.date, datetime.date)

    def test_parse_excel_date_calculation(self) -> None:
        """parse_excel 결과의 날짜가 회차 기반 계산과 일치합니다."""
        if not EXCEL_PATH.exists():
            pytest.skip(f"엑셀 파일 없음: {EXCEL_PATH}")

        results = parse_excel(EXCEL_PATH)
        by_drw_no = {d.drwNo: d for d in results}

        if 1 in by_drw_no:
            assert by_drw_no[1].date == datetime.date(2002, 12, 7)
        if 1229 in by_drw_no:
            assert by_drw_no[1229].date == datetime.date(2026, 6, 20)

    def test_parse_excel_incremental(self) -> None:
        """1226~1229회차가 파싱 결과에 포함됩니다."""
        if not EXCEL_PATH.exists():
            pytest.skip(f"엑셀 파일 없음: {EXCEL_PATH}")

        results = parse_excel(EXCEL_PATH)
        drw_nos = {d.drwNo for d in results}

        for expected in [1226, 1227, 1228, 1229]:
            assert expected in drw_nos, f"{expected}회차가 파싱 결과에 없습니다."

    def test_parse_excel_skips_invalid_rows(self, tmp_path: Path) -> None:
        """None/잘못된 데이터가 있는 행은 조용히 스킵합니다."""
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        # 헤더 행
        ws.append(["No", "회차", "당첨번호", None, None, None, None, None, "보너스", "순위", "당첨게임수", "1게임당 당첨금액"])  # noqa: E501
        # 유효한 행
        ws.append([1, 1.0, 10.0, 23.0, 29.0, 33.0, 37.0, 40.0, 16.0, "1등", "8 명", "3,519,759,000 원"])  # noqa: E501
        # 잘못된 행 (회차가 None)
        ws.append([2, None, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, "1등", "1 명", "1,000 원"])
        # 잘못된 행 (번호가 문자열)
        ws.append([3, 2.0, "X", 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, "1등", "1 명", "1,000 원"])

        xlsx_path = tmp_path / "test.xlsx"
        wb.save(xlsx_path)

        results = parse_excel(xlsx_path)
        # 유효한 행 1개만 파싱되어야 합니다
        assert len(results) == 1
        assert results[0].drwNo == 1
