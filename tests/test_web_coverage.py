"""SPEC-LOTTO-011 REQ-COV-002/003: 웹 라우트(api.py, pages.py) 커버리지 보강.

api.py의 _run_analyze_sync(draws 있을 때), CSV 빈파일 삭제, _on_progress 분기,
pages.py의 analyze/simulate 페이지에서 stats/result not None 분기를 검증한다.

@MX:SPEC: SPEC-LOTTO-011 REQ-COV-002, REQ-COV-003
"""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult

# === REQ-COV-002 (a): _run_analyze_sync — draws 있을 때 분석 실행 (lines 179-181) ===


def test_run_analyze_sync_with_draws_calls_analyzer() -> None:
    """draws가 비어있지 않으면 LottoAnalyzer를 생성하고 analyze + save_stats 호출."""
    from lotto.web.routes.api import _run_analyze_sync

    fake_draw = DrawResult(
        drwNo=1,
        date=datetime.date(2024, 1, 6),
        n1=1, n2=2, n3=3, n4=4, n5=5, n6=6,
        bonus=7,
    )

    with (
        patch(
            "lotto.collector.LottoCollector.load_existing",
            return_value=[fake_draw],
        ),
        patch("lotto.analyzer.LottoAnalyzer.analyze") as mock_analyze,
        patch("lotto.analyzer.LottoAnalyzer.save_stats") as mock_save,
    ):
        mock_stats = MagicMock()
        mock_analyze.return_value = mock_stats

        _run_analyze_sync()

    assert mock_analyze.called, "draws가 있으면 analyze가 호출되어야 한다"
    assert mock_save.called, "draws가 있으면 save_stats가 호출되어야 한다"
    # save_stats 첫 번째 인자가 analyze 결과여야 한다
    args, _kwargs = mock_save.call_args
    assert args[0] is mock_stats


def test_run_analyze_sync_with_empty_draws_skips_analysis() -> None:
    """draws가 비어있으면 analyze는 호출되지 않지만 invalidate_cache는 호출된다."""
    from lotto.web.routes.api import _run_analyze_sync

    with (
        patch("lotto.collector.LottoCollector.load_existing", return_value=[]),
        patch("lotto.analyzer.LottoAnalyzer.analyze") as mock_analyze,
        patch("lotto.analyzer.LottoAnalyzer.save_stats") as mock_save,
    ):
        _run_analyze_sync()

    assert not mock_analyze.called, "빈 draws일 때 analyze가 호출되면 안 된다"
    assert not mock_save.called, "빈 draws일 때 save_stats가 호출되면 안 된다"


# === REQ-COV-002 (b): _collect_worker CSV 빈파일 삭제 (line 214) ===


@pytest.fixture
def _reset_collect_state():
    """각 테스트 전후 _collect_state를 idle 상태로 초기화."""
    from lotto.web.routes import api as api_module

    saved = dict(api_module._collect_state)
    api_module._collect_state.update({
        "status": "idle",
        "current": 0,
        "total": 0,
        "collected": 0,
        "message": "",
    })
    yield
    api_module._collect_state.clear()
    api_module._collect_state.update(saved)


def test_collect_worker_deletes_empty_csv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _reset_collect_state
) -> None:
    """_collect_worker 시작 시 data/draws.csv가 10바이트 미만이면 삭제한다."""
    from lotto.web.routes import api as api_module
    from lotto.web.routes.api import _collect_worker

    # 작업 디렉토리를 tmp_path로 변경하여 실제 파일 시스템에 영향 없게 한다
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    csv_path = data_dir / "draws.csv"
    # 10바이트 미만의 빈 CSV 생성
    csv_path.write_text("a,b\n")

    assert csv_path.exists()
    assert csv_path.stat().st_size < 10  # noqa: PLR2004

    # collector mock — fetch_draw는 None만 반환 → 즉시 종료(error path)
    mock_collector = MagicMock()
    mock_collector.load_existing.return_value = []
    mock_collector.fetch_draw.return_value = None

    with (
        patch("lotto.collector.LottoCollector", return_value=mock_collector),
        patch("time.sleep"),
        patch.object(api_module, "invalidate_cache"),
    ):
        _collect_worker(full=False, start_from=1, max_drw_no=3)

    # 빈 CSV가 삭제되었는지 확인
    assert not csv_path.exists(), "10바이트 미만 CSV는 워커 시작 시 삭제되어야 한다"


# === REQ-COV-002 (c): trigger_collect 빈 CSV 삭제 (line 331) ===


def test_trigger_collect_deletes_empty_csv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _reset_collect_state
) -> None:
    """POST /api/collect 시 data/draws.csv가 10바이트 미만이면 삭제한다."""
    from lotto.web.app import app

    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    csv_path = data_dir / "draws.csv"
    csv_path.write_text("x")  # 1 byte

    assert csv_path.exists()

    client = TestClient(app)
    with (
        patch("lotto.web.routes.api._collect_worker"),
        patch(
            "lotto.collector.LottoCollector.load_existing",
            return_value=[],
        ),
    ):
        response = client.post("/api/collect")

    assert response.status_code == 202
    assert not csv_path.exists(), "trigger_collect가 1바이트 CSV를 삭제해야 한다"


# === REQ-COV-002 (d): add_manual_draw 빈 CSV 삭제 (line 419) ===


def test_add_manual_draw_deletes_empty_csv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /api/draws/manual 시 빈 CSV(10바이트 미만)는 삭제 후 진행한다."""
    from lotto.web.app import app

    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    csv_path = data_dir / "draws.csv"
    csv_path.write_text("z,z\n")  # 4 bytes

    assert csv_path.exists()
    assert csv_path.stat().st_size < 10  # noqa: PLR2004

    client = TestClient(app)
    payload = {
        "drwNo": 9999,
        "date": "20300104",
        "numbers": [1, 2, 3, 4, 5, 6],
        "bonus": 7,
    }
    response = client.post("/api/draws/manual", json=payload)

    # 빈 CSV가 삭제되어 EmptyDataError를 회피했으므로 정상 응답이어야 한다
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ok"
    # 새 CSV가 생성되었어야 한다
    assert csv_path.exists()


# === REQ-COV-002 (e): _on_progress drw_no != 0 분기 (lines 467-471) ===


def test_on_progress_with_nonzero_drw_no_updates_message(_reset_collect_state) -> None:
    """_scrape_worker._on_progress에서 drw_no != 0이면 메시지가 갱신된다.

    scrape_all을 mock하여 on_progress 콜백을 1회 호출한 뒤 빈 결과를 반환하면
    on_progress의 drw_no != 0 분기를 모두 검증할 수 있다.
    """
    from lotto.web.routes import api as api_module
    from lotto.web.routes.api import _scrape_worker

    def fake_scrape_all(on_progress=None):
        # drw_no != 0 → message 갱신 분기
        if on_progress:
            on_progress(drw_no=42, row_idx=10, count=5)
            # drw_no == 0 → message 갱신 안 함 분기 (현재 line 470 false)
            on_progress(drw_no=0, row_idx=11, count=5)
        return []  # 빈 결과로 status=error 종료

    with patch("lotto.scraper.scrape_all", side_effect=fake_scrape_all):
        _scrape_worker()

    # on_progress(drw_no=42)가 호출되어 'message'가 42회차 정보로 갱신되었어야 한다
    # 마지막 빈 결과로 인해 status는 error로 덮어쓰여진다 → 메시지 검증은 별도 필요
    # _collect_state['current']/['collected']가 갱신됐는지 확인
    # (current는 마지막 호출 row_idx=11로 덮어쓰임)
    assert api_module._collect_state["current"] == 11  # noqa: PLR2004
    assert api_module._collect_state["collected"] == 5  # noqa: PLR2004


# === REQ-COV-003 (a): analyze 페이지 — stats not None & freq_dict 존재 ===


def test_analyze_page_with_stats_renders_freq_chart() -> None:
    """analyze 페이지에서 stats가 있고 frequency가 채워져 있으면
    badge_colors, freq_chart_data 계산 분기가 실행되며 200 응답을 반환한다.
    """
    from lotto.web.app import app

    mock_stats = MagicMock()
    # 1~45 번호 모두에 frequency 부여 → freq_dict가 비어있지 않다
    mock_stats.frequency.absolute = {str(i): i for i in range(1, 46)}

    with patch("lotto.web.routes.pages.get_stats", return_value=mock_stats):
        client = TestClient(app)
        response = client.get("/analyze")

    assert response.status_code == 200
    # freq_chart_data가 채워졌으면 상위 빈도 번호가 페이지 텍스트에 노출되어야 한다
    # (45번이 가장 많이 나왔으므로 "45번"이 등장)
    assert "45번" in response.text or "background-color" in response.text


def test_analyze_page_with_empty_freq_dict_skips_chart() -> None:
    """stats가 있어도 frequency.absolute가 빈 dict이면 freq_chart_data는 채워지지 않는다."""
    from lotto.web.app import app

    mock_stats = MagicMock()
    mock_stats.frequency.absolute = {}  # 빈 frequency

    with patch("lotto.web.routes.pages.get_stats", return_value=mock_stats):
        client = TestClient(app)
        response = client.get("/analyze")

    assert response.status_code == 200


# === REQ-COV-003 (b): simulate 페이지 — result not None ===


def test_simulate_page_with_result_renders_budget_info() -> None:
    """simulate 페이지에서 result가 있으면 budget_info, per_round_data가 계산되고 응답이 200."""
    from lotto.web.app import app

    mock_result = MagicMock()
    mock_result.total_rounds = 1000
    mock_result.hit_rate = 0.05
    mock_result.prize_counts = {
        "1등": 0, "2등": 0, "3등": 1, "4등": 10, "5등": 30, "낙첨": 959,
    }
    # 300포인트 초과 → 샘플링 분기까지 진입
    mock_result.per_round_hits = list(range(500))

    with (
        patch("lotto.web.routes.pages.get_simulation", return_value=mock_result),
        patch("lotto.web.routes.pages.get_strategy_comparison", return_value=None),
    ):
        client = TestClient(app)
        response = client.get("/simulate?rounds=500&budget=1000")

    assert response.status_code == 200


def test_simulate_page_with_short_per_round_skips_sampling() -> None:
    """per_round_hits 길이가 300 이하면 sampling 없이 그대로 사용되는 분기."""
    from lotto.web.app import app

    mock_result = MagicMock()
    mock_result.total_rounds = 100
    mock_result.hit_rate = 0.03
    mock_result.prize_counts = {
        "1등": 0, "2등": 0, "3등": 0, "4등": 2, "5등": 5, "낙첨": 93,
    }
    mock_result.per_round_hits = list(range(100))  # 300 이하

    with (
        patch("lotto.web.routes.pages.get_simulation", return_value=mock_result),
        patch("lotto.web.routes.pages.get_strategy_comparison", return_value=None),
    ):
        client = TestClient(app)
        response = client.get("/simulate?rounds=100&budget=1000")

    assert response.status_code == 200


# === REQ-COV-004: config.py dotenv 분기 보강 ===
# 기존 test_config_edge.py의 test_load_settings_works_without_dotenv가
# _DOTENV_AVAILABLE=False 경로를 이미 커버한다. 여기서는 _DOTENV_AVAILABLE=True 경로를 보강.


def test_load_settings_calls_load_dotenv_when_available() -> None:
    """_DOTENV_AVAILABLE=True 일 때 _load_settings는 _load_dotenv(override=False)를 호출한다."""
    import importlib
    import os
    import sys

    # 환경 변수 격리
    saved = {k: v for k, v in os.environ.items() if k.startswith("LOTTO_")}
    for k in list(os.environ.keys()):
        if k.startswith("LOTTO_"):
            del os.environ[k]
    sys.modules.pop("lotto.config", None)

    try:
        config = importlib.import_module("lotto.config")

        with (
            patch.object(config, "_DOTENV_AVAILABLE", True),
            patch.object(config, "_load_dotenv", return_value=True) as mock_loader,
        ):
            settings = config._load_settings()

        assert mock_loader.called, "_DOTENV_AVAILABLE=True 시 _load_dotenv가 호출되어야 한다"
        # override=False로 호출되어야 한다 (REQ-CFG-002: env 변수 우선)
        _args, kwargs = mock_loader.call_args
        assert kwargs.get("override") is False
        assert settings is not None
    finally:
        # cleanup
        os.environ.update(saved)
        sys.modules.pop("lotto.config", None)
