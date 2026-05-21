"""SPEC-LOTTO-007 REQ-SYNC-002: append_draws 신규 회차 append 모드 테스트."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

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


class TestAppendDraws:
    """append_draws 메서드 동작을 검증한다."""

    def test_append_new_draws_only(self, tmp_data_dir: Path) -> None:
        """기존 10건 + 신규 2건이 12건이 되며, save_csv 전체 재작성은 호출되지 않는다."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        existing = [_make_draw(i) for i in range(1, 11)]
        collector.save_csv(existing)

        new_draws = [_make_draw(11), _make_draw(12)]
        with patch.object(
            LottoCollector, "save_csv", side_effect=AssertionError("save_csv must not be called")
        ):
            collector.append_draws(new_draws)

        loaded = collector.load_existing()
        assert len(loaded) == 12
        assert [d.drwNo for d in loaded] == list(range(1, 13))

    def test_append_creates_file_if_missing(self, tmp_data_dir: Path) -> None:
        """CSV가 없을 때 append_draws 호출 시 신규 파일을 생성한다."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        assert not (tmp_data_dir / "draws.csv").exists()

        collector.append_draws([_make_draw(1)])

        assert (tmp_data_dir / "draws.csv").exists()
        loaded = collector.load_existing()
        assert len(loaded) == 1
        assert loaded[0].drwNo == 1

    def test_append_deduplicates(self, tmp_data_dir: Path) -> None:
        """이미 존재하는 회차는 추가하지 않는다."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        existing = [_make_draw(1), _make_draw(2), _make_draw(3)]
        collector.save_csv(existing)

        # drwNo=3은 중복, drwNo=4는 신규
        collector.append_draws([_make_draw(3), _make_draw(4)])

        loaded = collector.load_existing()
        assert [d.drwNo for d in loaded] == [1, 2, 3, 4]

    def test_append_empty_is_noop(self, tmp_data_dir: Path) -> None:
        """빈 입력은 파일을 전혀 수정하지 않는다."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        existing = [_make_draw(1), _make_draw(2)]
        collector.save_csv(existing)

        csv_path = tmp_data_dir / "draws.csv"
        original_mtime = csv_path.stat().st_mtime_ns

        collector.append_draws([])

        # 파일이 수정되지 않아야 한다 (mtime 동일)
        assert csv_path.stat().st_mtime_ns == original_mtime
        loaded = collector.load_existing()
        assert len(loaded) == 2

    def test_append_all_duplicates_is_noop(self, tmp_data_dir: Path) -> None:
        """모두 중복일 경우에도 파일 쓰기가 발생하지 않는다."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        existing = [_make_draw(1), _make_draw(2)]
        collector.save_csv(existing)

        csv_path = tmp_data_dir / "draws.csv"
        original_mtime = csv_path.stat().st_mtime_ns

        collector.append_draws([_make_draw(1), _make_draw(2)])

        assert csv_path.stat().st_mtime_ns == original_mtime
