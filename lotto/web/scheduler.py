"""SPEC-LOTTO-023: APScheduler 기반 주간 자동 수집 스케줄러.

# @MX:ANCHOR: [AUTO] 주간 자동 수집 스케줄러 진입점 — app/lifespan, API, 테스트에서 참조
# @MX:REASON: app.py(시작/종료), api.py(상태/수동트리거), 테스트(검증)
#   3곳 이상에서 참조 (fan_in >= 3)
# @MX:SPEC: SPEC-LOTTO-023 REQ-SCHED-001~004

스케줄러는 BackgroundScheduler 로 동작하며, lotto.config.settings 에서 정의한
크론 표현식과 타임존에 따라 증분 수집(_collect_worker) 과 당첨금 업데이트
(_update_prizes_worker) 를 순차 실행한 뒤 캐시를 무효화한다.

테스트 가능성을 위해 모든 부수 효과는 모듈 수준 함수로 분리되어 있다.
"""

from __future__ import annotations

import datetime
import logging
import threading
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# SPEC-LOTTO-045: 명시적 재노출(PEP 484 redundant-alias). 테스트가 모듈 네임스페이스
# (lotto.web.scheduler.settings)로 패치/참조하므로 명시적 재노출로 처리한다 (런타임 동작 무관).
from lotto.config import settings as settings

logger = logging.getLogger(__name__)

# 단일 BackgroundScheduler 인스턴스 (모듈 임포트 시 생성, start_scheduler 에서 시작)
_scheduler: BackgroundScheduler | None = None
_scheduler_lock = threading.Lock()

# 마지막 실행 상태 — 외부에 노출 (REQ-SCHED-003)
_last_run_state: dict[str, Any] = {
    "last_run_at": None,      # ISO-8601 문자열
    "last_run_result": None,  # "success" | "failed" | None
    "last_run_error": None,   # 실패 시 메시지
}
_state_lock = threading.Lock()

# 스케줄 등록 시 사용하는 job id
_JOB_ID = "lotto_weekly_collect"


def _parse_cron(expression: str) -> CronTrigger:
    """크론 표현식 5필드("분 시 일 월 요일")를 CronTrigger 로 변환한다.

    APScheduler CronTrigger.from_crontab 는 5필드 표준을 지원하지만,
    타임존을 명시적으로 적용하기 위해 별도 헬퍼로 감싼다.
    """
    return CronTrigger.from_crontab(expression, timezone=settings.schedule_tz)


def _scheduled_collect_job() -> None:
    """스케줄러가 호출하는 핵심 작업 — 증분 수집 → 당첨금 업데이트 → 캐시 무효화.

    실패는 마지막 실행 상태에 기록하고 로그에 흔적을 남긴다. 어떤 예외도
    스케줄러 스레드를 종료시키지 않도록 광범위하게 처리한다.
    """
    # 순환 임포트 회피 — 함수 내부에서 임포트
    from lotto.web import data as wd
    from lotto.web.routes import api as api_routes

    started_at = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()  # noqa: UP017

    try:
        # 1. 증분 수집 (start_from = 마지막+1, 추정 최신 회차까지)
        from lotto.collector import LottoCollector

        existing = LottoCollector().load_existing()
        start_from = (max(d.drwNo for d in existing) + 1) if existing else 1
        max_drw_no = api_routes._estimate_latest_drw_no()
        if start_from <= max_drw_no:
            api_routes._collect_worker(False, start_from, max_drw_no)  # noqa: FBT003

        # 2. 1등 당첨금 소급 업데이트 (누락 행만)
        api_routes._update_prizes_worker()

        # 3. 캐시 무효화 (REQ-SCHED-001)
        wd.invalidate_cache()

        # 4. SPEC-LOTTO-025 REQ-NOTIF-002~004: 조건부 알림 발사
        # 최신 회차 정보를 알림 모듈로 위임. 실패는 흡수 (로그만 남김).
        try:
            from lotto.web import notifier as _notifier

            refreshed = LottoCollector().load_existing()
            if refreshed:
                latest = max(refreshed, key=lambda d: d.drwNo)
                draw_info = {
                    "drwNo": latest.drwNo,
                    "numbers": latest.numbers(),
                    "bonus": latest.bonus,
                    "prize1Amount": latest.prize1Amount,
                    "prize1Winners": latest.prize1Winners,
                }
                _notifier.notify(draw_info)
            # SPEC-LOTTO-115: 추천 번호 알림
            _notifier.notify_recommendations(refreshed)
        except Exception as exc:  # noqa: BLE001 — 알림 실패가 스케줄 결과를 뒤집지 않음
            logger.warning("Post-collect notification failed: %s", exc, exc_info=True)

        with _state_lock:
            _last_run_state.update({
                "last_run_at": started_at,
                "last_run_result": "success",
                "last_run_error": None,
            })
        logger.info("Scheduled weekly collect job completed successfully")
    except Exception as exc:  # noqa: BLE001 — 스케줄러 스레드 보호 목적
        with _state_lock:
            _last_run_state.update({
                "last_run_at": started_at,
                "last_run_result": "failed",
                "last_run_error": str(exc),
            })
        logger.warning("Scheduled weekly collect job failed: %s", exc, exc_info=True)


def start_scheduler() -> bool:
    """스케줄러를 시작하고 주간 수집 작업을 등록한다.

    settings.schedule_enabled 가 False 이면 아무 일도 하지 않고 False 반환.
    이미 시작된 경우 중복 등록 없이 True 반환.

    Returns:
        True 시작 성공 (혹은 이미 동작 중), False 비활성화 상태.
    """
    global _scheduler  # noqa: PLW0603

    if not settings.schedule_enabled:
        logger.info("Scheduler disabled by configuration (LOTTO_SCHEDULE_ENABLED)")
        return False

    with _scheduler_lock:
        if _scheduler is not None and _scheduler.running:
            return True

        _scheduler = BackgroundScheduler(timezone=settings.schedule_tz)
        try:
            trigger = _parse_cron(settings.schedule_cron)
        except (ValueError, KeyError) as exc:
            logger.error(
                "Invalid LOTTO_SCHEDULE_CRON=%r — scheduler not started: %s",
                settings.schedule_cron, exc,
            )
            _scheduler = None
            return False

        _scheduler.add_job(
            _scheduled_collect_job,
            trigger=trigger,
            id=_JOB_ID,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        _scheduler.start()
        logger.info(
            "Scheduler started — cron=%r tz=%s next_run=%s",
            settings.schedule_cron, settings.schedule_tz, _next_run_iso(),
        )
        return True


def shutdown_scheduler(wait: bool = False) -> None:
    """스케줄러를 안전하게 종료한다.

    Args:
        wait: True 면 현재 실행 중인 job 완료를 대기.
    """
    global _scheduler  # noqa: PLW0603
    with _scheduler_lock:
        if _scheduler is not None and _scheduler.running:
            try:
                _scheduler.shutdown(wait=wait)
                logger.info("Scheduler shut down (wait=%s)", wait)
            except Exception as exc:  # noqa: BLE001 — 종료 경로 방어
                logger.warning("Scheduler shutdown failed: %s", exc, exc_info=True)
        _scheduler = None


def _next_run_iso() -> str | None:
    """등록된 job 의 다음 실행 시각을 ISO-8601 문자열로 반환한다 (없으면 None)."""
    if _scheduler is None or not _scheduler.running:
        return None
    job = _scheduler.get_job(_JOB_ID)
    if job is None or job.next_run_time is None:
        return None
    # SPEC-LOTTO-045: apscheduler에 py.typed 마커가 없어 next_run_time이 Any로 추론된다.
    # isoformat()은 datetime 메서드이므로 str 반환을 명시한다 (동작 변경 없음).
    next_run: str = job.next_run_time.isoformat()
    return next_run


def get_status() -> dict[str, Any]:
    """REQ-SCHED-003: 스케줄러 상태를 dict 로 반환한다.

    Returns:
        enabled: settings.schedule_enabled
        running: 실제로 BackgroundScheduler 가 동작 중인지
        next_run: 다음 실행 ISO-8601 (비활성/미동작 시 None)
        last_run_at, last_run_result, last_run_error: 마지막 실행 정보
        cron, tz: 현재 설정값 (디버깅 보조)
    """
    with _state_lock:
        state_snapshot = dict(_last_run_state)
    return {
        "enabled": settings.schedule_enabled,
        "running": _scheduler is not None and _scheduler.running,
        "next_run": _next_run_iso(),
        "last_run_at": state_snapshot["last_run_at"],
        "last_run_result": state_snapshot["last_run_result"],
        "last_run_error": state_snapshot["last_run_error"],
        "cron": settings.schedule_cron,
        "tz": settings.schedule_tz,
    }


def trigger_now() -> dict[str, Any]:
    """REQ-SCHED-003: 수집 작업을 즉시 백그라운드 스레드로 실행한다.

    스케줄러가 비활성이거나 미동작 상태여도 호출 가능 (수동 트리거 경로).
    실행은 데몬 스레드로 분리되어 API 응답을 차단하지 않는다.
    """
    thread = threading.Thread(
        target=_scheduled_collect_job,
        name="lotto-scheduler-manual-trigger",
        daemon=True,
    )
    thread.start()
    return {
        "status": "started",
        "message": "주간 수집 작업을 즉시 트리거했습니다.",
    }
