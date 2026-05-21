"""SPEC-LOTTO-007 REQ-SYNC-001: save_csv 원자적 저장 테스트."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from lotto.collector import LottoCollector
from lotto.models import DrawResult


def _make_draws(count: int = 3) -> list[DrawResult]:
    """count개의 임시 DrawResult를 생성합니다."""
    return [
        DrawResult(
            drwNo=i,
            date=date(2024, 1, 1),
            n1=1,
            n2=2,
            n3=3,
            n4=4,
            n5=5,
            n6=6,
            bonus=7,
        )
        for i in range(1, count + 1)
    ]


class TestSaveCsvAtomic:
    """원자적 저장 동작을 검증한다."""

    def test_save_csv_atomic_success(self, tmp_data_dir: Path) -> None:
        """정상적으로 임시파일→교체 흐름으로 저장되고 로드도 일관된다."""
        collector = LottoCollector(data_dir=tmp_data_dir)
        draws = _make_draws(3)

        collector.save_csv(draws)

        csv_path = tmp_data_dir / "draws.csv"
        assert csv_path.exists()
        # 잔여 .tmp 파일이 남아있지 않아야 한다
        leftover = list(tmp_data_dir.glob("*.tmp"))
        assert leftover == []

        loaded = collector.load_existing()
        assert len(loaded) == 3
        assert [d.drwNo for d in loaded] == [1, 2, 3]

    def test_save_csv_atomic_no_partial_write(self, tmp_data_dir: Path) -> None:
        """os.replace 실패 시 원본 CSV가 유지되고 임시파일도 정리된다."""
        collector = LottoCollector(data_dir=tmp_data_dir)

        # 1) 원본 CSV 먼저 저장
        original = _make_draws(2)
        collector.save_csv(original)
        original_bytes = (tmp_data_dir / "draws.csv").read_bytes()

        # 2) os.replace가 실패하도록 모킹하고 재저장 시도
        new_draws = _make_draws(5)
        with patch("lotto.collector.os.replace", side_effect=OSError("replace failed")):
            with pytest.raises(OSError, match="replace failed"):
                collector.save_csv(new_draws)

        # 3) 원본 CSV가 그대로 보존되어야 한다
        assert (tmp_data_dir / "draws.csv").read_bytes() == original_bytes
        # 4) 임시 파일이 디렉토리에 남아 있으면 안 된다
        leftover = list(tmp_data_dir.glob("*.tmp"))
        assert leftover == []

    def test_save_csv_creates_dir_if_missing(self, tmp_path: Path) -> None:
        """존재하지 않는 중첩 디렉토리도 자동 생성한다."""
        nested = tmp_path / "nested" / "data"
        assert not nested.exists()
        collector = LottoCollector(data_dir=nested)

        draws = _make_draws(1)
        collector.save_csv(draws)

        assert (nested / "draws.csv").exists()
        loaded = collector.load_existing()
        assert len(loaded) == 1
