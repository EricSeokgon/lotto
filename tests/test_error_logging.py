"""SPEC-LOTTO-002 REQ-ERR: 무음 예외를 구조화 로깅으로 전환했는지 검증.

@MX:SPEC: SPEC-LOTTO-002 REQ-ERR-001..004
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

# === REQ-ERR-002: web/data.py 캐시 로드 실패 로깅 ===


def test_get_draws_logs_warning_on_load_failure(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """REQ-ERR-002: get_draws()의 except 블록에서 logger.warning 호출이 발생해야 한다."""
    from lotto.web import data as data_module

    # draws.csv 가 존재하지만 LottoCollector.load_existing() 가 예외를 던지도록 mock
    fake_csv = tmp_path / "draws.csv"
    fake_csv.write_text("invalid,csv,data\n", encoding="utf-8")

    with patch.object(data_module, "DRAWS_PATH", fake_csv), patch(
        "lotto.collector.LottoCollector.load_existing",
        side_effect=RuntimeError("simulated load failure"),
    ), caplog.at_level(logging.WARNING, logger="lotto.web.data"):
        result = data_module.get_draws()

    assert result is None, "예외 발생 시 None을 반환해야 함"
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, "load 실패 시 최소 1개의 warning 로그가 있어야 함"
    assert any("simulated load failure" in r.getMessage() or "cached" in r.getMessage().lower()
               for r in warnings), \
        f"로그 메시지에 예외 정보가 포함되어야 함. 받은 로그: {[r.getMessage() for r in warnings]}"


# === REQ-ERR-003: web/routes/api.py 체크포인트 저장 실패 로깅 ===


def test_collect_worker_logs_warning_on_checkpoint_failure(
    caplog: pytest.LogCaptureFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REQ-ERR-003: 체크포인트 save_csv 실패 시 logger.warning 호출이 발생해야 한다."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)

    from datetime import date

    from lotto.models import DrawResult
    from lotto.web.routes import api as api_module

    # 더미 fetch_draw — 항상 성공 반환
    def _fake_fetch(self, drw_no: int):  # noqa: ANN001, ANN202, ARG001
        return DrawResult(
            drwNo=drw_no, date=date(2024, 1, 1),
            n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7,
        )

    # save_csv가 체크포인트 시점에서 실패하도록 강제
    call_count = {"n": 0}

    def _failing_save(self, draws):  # noqa: ANN001, ANN202, ARG001
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise OSError("simulated checkpoint failure")

    monkeypatch.setattr("lotto.collector.LottoCollector.fetch_draw", _fake_fetch)
    monkeypatch.setattr("lotto.collector.LottoCollector.save_csv", _failing_save)
    # 체크포인트 간격을 작게 (테스트 빠름)
    monkeypatch.setattr(api_module, "_CHECKPOINT_INTERVAL", 2)
    monkeypatch.setattr("time.sleep", lambda *_: None)

    with caplog.at_level(logging.WARNING, logger="lotto.web.routes.api"):
        # full=False, start_from=1, max_drw_no=3 (체크포인트 1번 발생 후 마지막 저장)
        api_module._collect_worker(full=False, start_from=1, max_drw_no=3)

    warnings = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING and "checkpoint" in r.getMessage().lower()
    ]
    assert warnings, \
        f"체크포인트 실패 시 'checkpoint' 키워드를 포함한 warning 로그 필요. " \
        f"받은 로그: {[r.getMessage() for r in caplog.records]}"


# === REQ-ERR-004: simulator.py 분석 실패 -> 무작위 폴백 로깅 ===


def test_simulator_logs_warning_on_random_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """REQ-ERR-004: 분석 실패로 무작위 폴백 시 logger.warning 호출이 발생해야 한다."""
    from datetime import date

    from lotto.models import DrawResult
    from lotto.simulator import HistoricalView, LottoSimulator

    # 분석에 충분한 draws를 만들지만 LottoAnalyzer.analyze 가 강제로 예외를 던지도록 mock
    draws = [
        DrawResult(
            drwNo=i, date=date(2024, 1, i),
            n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7,
        )
        for i in range(1, 11)
    ]
    sim = LottoSimulator(draws)
    view = HistoricalView(draws, cutoff_round=10)

    with patch(
        "lotto.analyzer.LottoAnalyzer.analyze",
        side_effect=RuntimeError("simulated analysis failure"),
    ), caplog.at_level(logging.WARNING, logger="lotto.simulator"):
        result = sim._run_round(view, draws[-1])

    assert result is not None
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, \
        f"분석 실패 시 warning 로그 필요. 받은 로그: {[r.getMessage() for r in caplog.records]}"
    assert any("fallback" in r.getMessage().lower() or "random" in r.getMessage().lower()
               or "분석" in r.getMessage() or "무작위" in r.getMessage()
               for r in warnings), \
        f"폴백 로그 메시지에 폴백 정보 포함 필요. " \
        f"받은 로그: {[r.getMessage() for r in warnings]}"
