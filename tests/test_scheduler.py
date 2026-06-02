"""SPEC-LOTTO-023: 주간 자동 수집 스케줄러 테스트.

REQ-SCHED-001~004 의 핵심 동작 검증:
- 상태 API 응답 shape (활성/비활성)
- 수동 트리거 API 동작
- Settings 비활성 시 스케줄러 미시작
- Graceful shutdown
- 인덱스 페이지 next_run 표시

@MX:SPEC: SPEC-LOTTO-023 REQ-SCHED-001~004
"""

from __future__ import annotations

import contextlib
import dataclasses
import importlib
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@contextlib.contextmanager
def _override_settings(**overrides):
    """frozen dataclass Settings 를 일시적으로 치환하는 헬퍼.

    sched_mod.settings, lotto.web.routes.pages 내 _sched.settings 등은
    동일한 객체를 공유하므로 모듈 속성 자체를 swap 한다.
    """
    from lotto.web import scheduler as sched_mod

    original = sched_mod.settings
    replaced = dataclasses.replace(original, **overrides)
    sched_mod.settings = replaced
    try:
        yield replaced
    finally:
        sched_mod.settings = original


@pytest.fixture(autouse=True)
def _reset_scheduler_module():
    """각 테스트 시작/종료 시 스케줄러 상태를 초기화한다."""
    from lotto.web import scheduler as sched_mod

    # 시작 전 정리
    sched_mod.shutdown_scheduler(wait=False)
    with sched_mod._state_lock:
        sched_mod._last_run_state.update({
            "last_run_at": None,
            "last_run_result": None,
            "last_run_error": None,
        })
    yield
    sched_mod.shutdown_scheduler(wait=False)


# === REQ-SCHED-002: Settings 외부화 ===


def test_settings_default_values_for_schedule() -> None:
    """기본값: enabled=True, cron='10 21 * * 6', tz='Asia/Seoul'."""
    # 환경 변수 미설정 상태로 settings 재로드
    keys = ("LOTTO_SCHEDULE_ENABLED", "LOTTO_SCHEDULE_CRON", "LOTTO_SCHEDULE_TZ")
    with patch.dict(os.environ, dict.fromkeys(keys, ""), clear=False):
        for k in keys:
            os.environ.pop(k, None)
        import lotto.config as cfg

        importlib.reload(cfg)
        assert cfg.settings.schedule_enabled is True
        assert cfg.settings.schedule_cron == "10 21 * * 6"
        assert cfg.settings.schedule_tz == "Asia/Seoul"
    # 다음 테스트에 영향 없도록 다시 reload
    importlib.reload(__import__("lotto.config", fromlist=["settings"]))


def test_settings_disabled_via_env_var() -> None:
    """LOTTO_SCHEDULE_ENABLED=false 면 schedule_enabled=False."""
    with patch.dict(os.environ, {"LOTTO_SCHEDULE_ENABLED": "false"}):
        import lotto.config as cfg

        importlib.reload(cfg)
        assert cfg.settings.schedule_enabled is False
    importlib.reload(__import__("lotto.config", fromlist=["settings"]))


# === REQ-SCHED-001/003: 스케줄러 시작/상태 ===


def test_start_scheduler_returns_false_when_disabled() -> None:
    """schedule_enabled=False 면 start_scheduler() 가 False 반환 + 스케줄러 미시작."""
    from lotto.web import scheduler as sched_mod

    with _override_settings(schedule_enabled=False):
        result = sched_mod.start_scheduler()
    assert result is False
    assert sched_mod._scheduler is None


def test_start_scheduler_returns_true_when_enabled() -> None:
    """schedule_enabled=True 면 스케줄러가 시작되고 next_run 이 채워진다."""
    from lotto.web import scheduler as sched_mod

    with _override_settings(
        schedule_enabled=True,
        schedule_cron="10 21 * * 6",
        schedule_tz="Asia/Seoul",
    ):
        result = sched_mod.start_scheduler()
        assert result is True
        assert sched_mod._scheduler is not None
        assert sched_mod._scheduler.running is True
        status = sched_mod.get_status()
        assert status["enabled"] is True
        assert status["running"] is True
        assert status["next_run"] is not None  # 토요일 21:10 예정 시각
        assert status["cron"] == "10 21 * * 6"
        assert status["tz"] == "Asia/Seoul"


def test_start_scheduler_idempotent() -> None:
    """이미 동작 중인 스케줄러를 재시작해도 중복 등록 없이 True 반환."""
    from lotto.web import scheduler as sched_mod

    with _override_settings(schedule_enabled=True):
        assert sched_mod.start_scheduler() is True
        assert sched_mod.start_scheduler() is True
        # job 은 정확히 1개여야 함
        assert sched_mod._scheduler is not None
        jobs = sched_mod._scheduler.get_jobs()
        assert len(jobs) == 1


def test_start_scheduler_invalid_cron_returns_false() -> None:
    """잘못된 크론 표현식이면 스케줄러 시작 실패 + False 반환."""
    from lotto.web import scheduler as sched_mod

    with _override_settings(
        schedule_enabled=True,
        schedule_cron="not a cron",
    ):
        result = sched_mod.start_scheduler()
    assert result is False
    assert sched_mod._scheduler is None


# === REQ-SCHED-001: Graceful shutdown ===


def test_shutdown_scheduler_stops_running_scheduler() -> None:
    """shutdown_scheduler() 호출 시 BackgroundScheduler 가 정상 종료된다."""
    from lotto.web import scheduler as sched_mod

    with _override_settings(schedule_enabled=True):
        sched_mod.start_scheduler()
        assert sched_mod._scheduler is not None
        sched_mod.shutdown_scheduler(wait=False)
    assert sched_mod._scheduler is None


def test_shutdown_scheduler_safe_when_not_started() -> None:
    """미시작 상태에서 shutdown 호출해도 예외 없이 통과한다."""
    from lotto.web import scheduler as sched_mod

    # 시작 안 한 상태에서 종료 호출 — 예외 없어야 함
    sched_mod.shutdown_scheduler(wait=False)
    assert sched_mod._scheduler is None


# === REQ-SCHED-003: 상태 API ===


def test_status_api_shape_when_disabled() -> None:
    """스케줄러 비활성 상태: 모든 키 존재 + running=False, next_run=None."""
    from lotto.web.app import app

    with _override_settings(schedule_enabled=False):
        client = TestClient(app)
        with client:
            response = client.get("/api/scheduler/status")
        assert response.status_code == 200
        body = response.json()
        # 응답 shape 검증
        for key in (
            "enabled", "running", "next_run",
            "last_run_at", "last_run_result", "last_run_error",
            "cron", "tz",
        ):
            assert key in body, f"missing key: {key}"
        assert body["enabled"] is False
        assert body["running"] is False
        assert body["next_run"] is None


def test_status_api_returns_next_run_when_enabled() -> None:
    """스케줄러 활성 상태: next_run 이 ISO-8601 문자열로 채워진다."""
    from lotto.web.app import app

    with _override_settings(schedule_enabled=True):
        client = TestClient(app)
        with client:
            response = client.get("/api/scheduler/status")
        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is True
        assert body["running"] is True
        assert body["next_run"] is not None
        # ISO-8601 포맷 검증 (T 구분자 포함)
        assert "T" in body["next_run"]


# === REQ-SCHED-003: 수동 트리거 API ===


def test_trigger_api_returns_200_and_starts_job() -> None:
    """POST /api/scheduler/trigger 가 200 응답 + 백그라운드 스레드 기동."""
    from lotto.web import scheduler as sched_mod
    from lotto.web.app import app

    # _scheduled_collect_job 을 모킹하여 실제 수집 차단
    with (
        _override_settings(schedule_enabled=True),
        patch.object(sched_mod, "_scheduled_collect_job") as mock_job,
    ):
        client = TestClient(app)
        with client:
            response = client.post("/api/scheduler/trigger")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "started"
        assert "message" in body
        # 스레드 실행 완료 대기 (최대 1초)
        import time

        for _ in range(20):
            if mock_job.called:
                break
            time.sleep(0.05)
        assert mock_job.called


# === REQ-SCHED-001: Job 동작 검증 ===


def test_scheduled_collect_job_records_success_state() -> None:
    """_scheduled_collect_job 정상 종료 시 last_run_result='success' 기록."""
    from lotto.web import scheduler as sched_mod

    # 모든 부수효과 모킹: collector / api routes / cache
    with (
        patch("lotto.collector.LottoCollector") as mock_collector_cls,
        patch("lotto.web.routes.api._collect_worker"),
        patch("lotto.web.routes.api._update_prizes_worker"),
        patch("lotto.web.routes.api._estimate_latest_drw_no", return_value=1100),
        patch("lotto.web.data.invalidate_cache") as mock_invalidate,
    ):
        mock_collector_cls.return_value.load_existing.return_value = []
        sched_mod._scheduled_collect_job()

    # invalidate_cache 가 호출되어야 한다 (REQ-SCHED-001)
    mock_invalidate.assert_called_once()
    status = sched_mod.get_status()
    assert status["last_run_result"] == "success"
    assert status["last_run_error"] is None
    assert status["last_run_at"] is not None


def test_scheduled_collect_job_records_failure_state() -> None:
    """job 내부 예외 시 last_run_result='failed' + 에러 메시지 기록."""
    from lotto.web import scheduler as sched_mod

    with (
        patch("lotto.collector.LottoCollector") as mock_collector_cls,
        patch(
            "lotto.web.routes.api._collect_worker",
            side_effect=RuntimeError("boom"),
        ),
        patch("lotto.web.routes.api._estimate_latest_drw_no", return_value=1100),
    ):
        mock_collector_cls.return_value.load_existing.return_value = []
        # 예외는 스케줄러가 흡수해야 함 — 호출 자체는 성공
        sched_mod._scheduled_collect_job()

    status = sched_mod.get_status()
    assert status["last_run_result"] == "failed"
    assert "boom" in (status["last_run_error"] or "")


# === REQ-SCHED-004: 인덱스 페이지에 next_run 노출 ===


def test_index_page_shows_next_run_when_scheduler_enabled() -> None:
    """스케줄러 활성 시 인덱스 페이지에 '다음 자동 수집 예정' 텍스트 노출."""
    from lotto.web.app import app

    with _override_settings(schedule_enabled=True):
        client = TestClient(app)
        with client:
            response = client.get("/")
        assert response.status_code == 200
        assert "다음 자동 수집 예정" in response.text


def test_index_page_hides_next_run_when_scheduler_disabled() -> None:
    """스케줄러 비활성 시 '다음 자동 수집 예정' 텍스트 미노출."""
    from lotto.web.app import app

    with _override_settings(schedule_enabled=False):
        client = TestClient(app)
        with client:
            response = client.get("/")
        assert response.status_code == 200
        assert "다음 자동 수집 예정" not in response.text


# === Graceful shutdown via lifespan ===


def test_lifespan_starts_and_shuts_down_scheduler() -> None:
    """lifespan 진입 시 start_scheduler, 종료 시 shutdown_scheduler 호출."""
    from lotto.web import scheduler as sched_mod
    from lotto.web.app import app

    with (
        patch.object(sched_mod, "start_scheduler") as mock_start,
        patch.object(sched_mod, "shutdown_scheduler") as mock_shutdown,
    ):
        client = TestClient(app)
        with client:
            # lifespan startup 트리거
            client.get("/health")
        # 컨텍스트 종료 시 shutdown 호출
        assert mock_start.called
        assert mock_shutdown.called
        # shutdown 은 wait=False 로 호출되어야 함 (요청 차단 방지)
        call_kwargs = mock_shutdown.call_args.kwargs
        assert call_kwargs.get("wait") is False
