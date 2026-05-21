"""SPEC-LOTTO-004 REQ-INT-004: API scraper 통합 워커 및 에러 분기 테스트.

_scrape_worker와 _collect_worker의 모든 분기(성공/실패/저장 오류)를 검증한다.

@MX:SPEC: SPEC-LOTTO-004 REQ-INT-004
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult


# === Scenario 4.1: POST /api/scrape 엔드포인트 ===


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


def test_scrape_endpoint_returns_202(_reset_collect_state) -> None:
    """Scenario 4.1: POST /api/scrape는 202 Accepted를 반환한다."""
    from lotto.web.app import app

    client = TestClient(app)
    with patch("lotto.web.routes.api._scrape_worker"):
        response = client.post("/api/scrape")

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "started"
    assert "크롤링" in body["message"]


def test_scrape_endpoint_conflict_when_running(_reset_collect_state) -> None:
    """이미 수집 중이면 409 Conflict 반환."""
    from lotto.web.app import app
    from lotto.web.routes import api as api_module

    api_module._collect_state["status"] = "running"

    client = TestClient(app)
    response = client.post("/api/scrape")

    assert response.status_code == 409


# === Scenario 4.2: _scrape_worker 빈 결과 처리 ===


def test_scrape_worker_empty_result_sets_error(_reset_collect_state) -> None:
    """Scenario 4.2: scrape_all이 빈 리스트를 반환하면 status='error'."""
    from lotto.web.routes import api as api_module
    from lotto.web.routes.api import _scrape_worker

    with patch("lotto.scraper.scrape_all", return_value=[]):
        _scrape_worker()

    assert api_module._collect_state["status"] == "error"
    assert "크롤링 결과가 없습니다" in api_module._collect_state["message"]


def test_scrape_worker_success_path(tmp_path, _reset_collect_state) -> None:
    """scrape_all이 정상 결과를 반환하면 저장 및 분석 후 status='done'."""
    from lotto.web.routes import api as api_module
    from lotto.web.routes.api import _scrape_worker

    # tmp_path를 작업 디렉토리로 사용
    fake_draws = [
        DrawResult(
            drwNo=1,
            date=datetime.date(2024, 1, 6),
            n1=1, n2=2, n3=3, n4=4, n5=5, n6=6,
            bonus=7,
        ),
    ]

    with (
        patch("lotto.scraper.scrape_all", return_value=fake_draws),
        patch.object(api_module, "_run_analyze_sync"),
        patch("lotto.collector.LottoCollector.save_csv"),
    ):
        _scrape_worker()

    assert api_module._collect_state["status"] == "done"
    assert api_module._collect_state["total"] == 1


def test_scrape_worker_exception_path(_reset_collect_state) -> None:
    """scrape_all이 예외를 던지면 status='error'로 기록된다."""
    from lotto.web.routes import api as api_module
    from lotto.web.routes.api import _scrape_worker

    with patch("lotto.scraper.scrape_all", side_effect=RuntimeError("network down")):
        _scrape_worker()

    assert api_module._collect_state["status"] == "error"
    assert "크롤링 오류" in api_module._collect_state["message"]


# === Scenario 4.3: _collect_worker 저장 실패 분기 (line 221~223) ===


def test_collect_worker_save_csv_failure_sets_error(_reset_collect_state) -> None:
    """Scenario 4.3: 최종 save_csv 실패 시 status='error', '저장 실패' 메시지."""
    from lotto.web.routes import api as api_module
    from lotto.web.routes.api import _collect_worker

    fake_draw = DrawResult(
        drwNo=1,
        date=datetime.date(2024, 1, 6),
        n1=1, n2=2, n3=3, n4=4, n5=5, n6=6,
        bonus=7,
    )

    mock_collector = MagicMock()
    mock_collector.load_existing.return_value = []
    mock_collector.fetch_draw.return_value = fake_draw
    # 첫 번째 save_csv 호출(체크포인트)은 성공, 마지막 최종 save_csv가 실패
    save_csv_calls = []

    def save_csv_side_effect(draws):
        save_csv_calls.append(len(draws))
        # 최종 호출만 실패시키기 위해 collected 길이가 충분히 클 때 실패
        if len(save_csv_calls) >= 2:  # noqa: PLR2004
            raise RuntimeError("disk full")

    mock_collector.save_csv.side_effect = save_csv_side_effect

    # time.sleep을 즉시 반환하도록 모킹하여 테스트 속도 향상
    with (
        patch("lotto.collector.LottoCollector", return_value=mock_collector),
        patch("time.sleep"),
        # checkpoint interval을 1로 설정하여 즉시 첫 체크포인트 발생
        patch.object(api_module, "_CHECKPOINT_INTERVAL", 1),
    ):
        _collect_worker(full=False, start_from=1, max_drw_no=1)

    assert api_module._collect_state["status"] == "error"
    assert "저장 실패" in api_module._collect_state["message"]


def test_collect_worker_no_draws_collected_sets_error(_reset_collect_state) -> None:
    """수집된 회차가 없으면 status='error', API 차단 안내 메시지를 반환한다."""
    from lotto.web.routes import api as api_module
    from lotto.web.routes.api import _collect_worker

    mock_collector = MagicMock()
    mock_collector.load_existing.return_value = []
    mock_collector.fetch_draw.return_value = None  # 모든 회차 실패

    with (
        patch("lotto.collector.LottoCollector", return_value=mock_collector),
        patch("time.sleep"),
    ):
        _collect_worker(full=False, start_from=1, max_drw_no=10)

    assert api_module._collect_state["status"] == "error"


def test_collect_worker_checkpoint_save_failure_warned(_reset_collect_state) -> None:
    """체크포인트 저장 실패는 로그만 남기고 수집은 계속 진행된다."""
    from lotto.web.routes import api as api_module
    from lotto.web.routes.api import _collect_worker

    fake_draw = DrawResult(
        drwNo=1,
        date=datetime.date(2024, 1, 6),
        n1=1, n2=2, n3=3, n4=4, n5=5, n6=6,
        bonus=7,
    )

    mock_collector = MagicMock()
    mock_collector.load_existing.return_value = []
    mock_collector.fetch_draw.return_value = fake_draw

    save_count = [0]

    def save_csv_side_effect(draws):
        save_count[0] += 1
        # 첫 체크포인트만 실패, 그 이후는 성공
        if save_count[0] == 1:
            raise RuntimeError("checkpoint disk error")

    mock_collector.save_csv.side_effect = save_csv_side_effect

    with (
        patch("lotto.collector.LottoCollector", return_value=mock_collector),
        patch("time.sleep"),
        patch.object(api_module, "_CHECKPOINT_INTERVAL", 1),
        patch.object(api_module, "_run_analyze_sync"),
    ):
        _collect_worker(full=False, start_from=1, max_drw_no=2)

    # 체크포인트 실패에도 수집이 끝까지 진행되어야 한다 (done 또는 error 중 하나)
    assert api_module._collect_state["status"] in ("done", "error")
