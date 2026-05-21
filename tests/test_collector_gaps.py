"""SPEC-LOTTO-007 REQ-SYNC-004: 데이터 갭(누락 회차) 감지 테스트."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from lotto.collector import LottoCollector
from lotto.models import DrawResult


def _make_draw(drw_no: int) -> DrawResult:
    """단일 임시 DrawResult를 생성합니다."""
    return DrawResult(
        drwNo=drw_no,
        date=date(2024, 1, 1),
        n1=1,
        n2=2,
        n3=3,
        n4=4,
        n5=5,
        n6=6,
        bonus=7,
    )


class TestDetectGaps:
    """detect_gaps 메서드 동작을 검증한다."""

    def test_detect_gaps_no_gaps(self, tmp_data_dir: Path) -> None:
        """연속된 회차는 갭이 없다."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        draws = [_make_draw(i) for i in range(1, 6)]  # 1,2,3,4,5
        assert collector.detect_gaps(draws) == []

    def test_detect_gaps_single_gap(self, tmp_data_dir: Path) -> None:
        """단일 갭을 감지한다."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        draws = [_make_draw(1), _make_draw(2), _make_draw(4), _make_draw(5)]  # 3 누락
        assert collector.detect_gaps(draws) == [3]

    def test_detect_gaps_multiple_gaps(self, tmp_data_dir: Path) -> None:
        """다중 갭을 오름차순으로 감지한다."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        draws = [_make_draw(1), _make_draw(3), _make_draw(5)]  # 2, 4 누락
        assert collector.detect_gaps(draws) == [2, 4]

    def test_detect_gaps_empty(self, tmp_data_dir: Path) -> None:
        """빈 입력은 빈 리스트를 반환한다."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        assert collector.detect_gaps([]) == []

    def test_detect_gaps_single_draw(self, tmp_data_dir: Path) -> None:
        """단일 회차는 갭이 있을 수 없다."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        assert collector.detect_gaps([_make_draw(42)]) == []

    def test_detect_gaps_uses_load_existing_when_none(self, tmp_data_dir: Path) -> None:
        """인자가 None일 때 load_existing()을 사용한다."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        # CSV에 1, 3, 5 저장 → 2, 4 갭
        collector.save_csv([_make_draw(1), _make_draw(3), _make_draw(5)])

        assert collector.detect_gaps() == [2, 4]

    def test_detect_gaps_unsorted_input(self, tmp_data_dir: Path) -> None:
        """입력이 순서 없이 들어와도 갭을 정확히 계산한다."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        draws = [_make_draw(5), _make_draw(1), _make_draw(3)]  # 2, 4 누락
        assert collector.detect_gaps(draws) == [2, 4]
