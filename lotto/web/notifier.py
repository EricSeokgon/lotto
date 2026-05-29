"""SPEC-LOTTO-025: 조건부 알림 모듈 (Webhook/Email).

# @MX:ANCHOR: [AUTO] 알림 진입점 — scheduler/api 등 다수 모듈에서 참조
# @MX:REASON: 외부 통합(Discord/Slack/SMTP) 경계 — 실패가 본 작업을 중단시키지 않아야 함
# @MX:SPEC: SPEC-LOTTO-025 REQ-NOTIF-001~005

REQ-NOTIF-001~005 의 동작 보장:
- 임계값(0=비활성) 비교 및 채널별 설정 확인
- httpx 로 Webhook POST, smtplib 로 SMTP 전송
- 실패는 로그 경고로 흡수하고 수집 프로세스를 중단하지 않음
- 알림 이력을 data/notifications.json 에 누적 저장 (최대 50건 유지)
"""

from __future__ import annotations

import datetime
import json
import logging
import smtplib
import threading
import uuid
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from lotto.config import settings

logger = logging.getLogger(__name__)

# 이력 파일 동시 쓰기 방지 (스레드 안전)
_history_lock = threading.Lock()

# REQ-NOTIF-004: 이력 최대 보관 건수 (UI/API 반환 50건과 일치하도록 단순화)
_HISTORY_MAX_ENTRIES = 50


def _history_path() -> Path:
    """알림 이력 파일 경로 — settings.data_dir 기준."""
    return Path(settings.data_dir) / "notifications.json"


def should_notify(drwNo: int, prize_amount: int | None) -> bool:  # noqa: N803
    """REQ-NOTIF-001: 알림 조건 평가.

    - threshold=0 이면 비활성 → 항상 False
    - prize_amount 가 None 이면 비교 불가 → False
    - prize_amount >= threshold 일 때만 True
    """
    threshold = settings.notify_prize_threshold
    if threshold <= 0:
        return False
    if prize_amount is None:
        return False
    return prize_amount >= threshold


def _format_payload(draw_info: dict[str, Any]) -> dict[str, Any]:
    """Webhook/Email 본문에 공통 사용할 표준화된 페이로드."""
    drw_no = draw_info.get("drwNo")
    numbers = draw_info.get("numbers") or []
    bonus = draw_info.get("bonus")
    prize = draw_info.get("prize1Amount") or 0
    winners = draw_info.get("prize1Winners")

    numbers_str = ", ".join(str(n) for n in numbers)
    prize_str = f"{prize:,}원" if isinstance(prize, int) else str(prize)
    winners_str = f"{winners}명" if winners else "-"

    title = f"제 {drw_no}회 로또 1등 당첨 안내"
    text = (
        f"제 {drw_no}회 당첨 번호: {numbers_str} + {bonus}\n"
        f"1등 당첨금: {prize_str}\n"
        f"1등 당첨자 수: {winners_str}"
    )
    return {
        "title": title,
        "text": text,
        "drwNo": drw_no,
        "numbers": numbers,
        "bonus": bonus,
        "prize1Amount": prize,
        "prize1Winners": winners,
    }


def send_webhook(draw_info: dict[str, Any]) -> bool:
    """REQ-NOTIF-002: Discord/Slack Webhook 으로 알림 전송.

    실패는 경고 로그 후 False 반환 — 예외를 호출자에게 전파하지 않음.
    """
    url = settings.notify_webhook_url.strip()
    if not url:
        return False

    payload = _format_payload(draw_info)
    # Discord/Slack 공통 호환 — 두 서비스 모두 {"content"|"text"} 필드를 인식
    body = {
        "content": f"{payload['title']}\n{payload['text']}",  # Discord
        "text": f"{payload['title']}\n{payload['text']}",      # Slack
    }

    try:
        import httpx

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=body)
        # 2xx 만 성공으로 간주
        if 200 <= resp.status_code < 300:
            return True
        logger.warning(
            "Webhook notification returned non-2xx status=%d body=%r",
            resp.status_code, resp.text[:200],
        )
    except Exception as exc:  # noqa: BLE001 — 알림 실패는 본 작업을 중단시키지 않음
        logger.warning("Webhook notification failed: %s", exc, exc_info=True)
    return False


def send_email(draw_info: dict[str, Any]) -> bool:
    """REQ-NOTIF-003: SMTP 로 HTML 이메일 전송.

    필수 설정(SMTP host, recipient, sender) 누락 시 False.
    실패는 경고 로그 후 False 반환.
    """
    smtp_host = settings.notify_smtp_host.strip()
    email_to = settings.notify_email_to.strip()
    email_from = settings.notify_email_from.strip()
    if not (smtp_host and email_to and email_from):
        return False

    payload = _format_payload(draw_info)
    drw_no = payload["drwNo"]
    numbers = payload["numbers"]
    bonus = payload["bonus"]
    prize = payload["prize1Amount"]
    winners = payload["prize1Winners"]

    prize_str = f"{prize:,}원" if isinstance(prize, int) else str(prize)
    winners_str = f"{winners}명" if winners else "-"
    numbers_html = " ".join(f"<b>{n}</b>" for n in numbers)

    msg = EmailMessage()
    msg["Subject"] = payload["title"]
    msg["From"] = email_from
    msg["To"] = email_to
    msg.set_content(payload["text"])
    msg.add_alternative(
        f"""<html><body>
        <h2>{payload['title']}</h2>
        <p><b>당첨 번호:</b> {numbers_html} + 보너스 <b>{bonus}</b></p>
        <p><b>1등 당첨금:</b> {prize_str}</p>
        <p><b>1등 당첨자 수:</b> {winners_str}</p>
        <hr/>
        <p style="color:#888;font-size:12px;">제 {drw_no}회 자동 알림 — Lotto Dashboard</p>
        </body></html>""",
        subtype="html",
    )

    try:
        with smtplib.SMTP(smtp_host, settings.notify_smtp_port, timeout=10) as smtp:
            smtp.ehlo()
            try:
                smtp.starttls()
                smtp.ehlo()
            except smtplib.SMTPException:
                # STARTTLS 미지원 서버는 평문 전송 (테스트/내부 SMTP)
                logger.debug("STARTTLS not supported, sending without TLS")
            if settings.notify_smtp_user and settings.notify_smtp_pass:
                smtp.login(settings.notify_smtp_user, settings.notify_smtp_pass)
            smtp.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001 — 알림 실패는 본 작업을 중단시키지 않음
        logger.warning("Email notification failed: %s", exc, exc_info=True)
        return False


def load_history() -> list[dict[str, Any]]:
    """REQ-NOTIF-004: 알림 이력 로드 — 파일 없거나 손상 시 빈 리스트."""
    path = _history_path()
    if not path.exists():
        return []
    try:
        with _history_lock:
            data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        logger.warning("notifications.json is not a list — returning empty")
    except (OSError, ValueError) as exc:
        logger.warning("Failed to load notifications.json: %s", exc)
    return []


def _save_history(entries: list[dict[str, Any]]) -> None:
    """이력 파일에 원자적으로 기록한다. 최대 _HISTORY_MAX_ENTRIES 건만 유지."""
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # 최신 _HISTORY_MAX_ENTRIES 건만 유지 (오래된 것 절단)
    trimmed = entries[-_HISTORY_MAX_ENTRIES:]
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with _history_lock:
            tmp.write_text(json.dumps(trimmed, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
    except OSError as exc:
        logger.warning("Failed to save notifications.json: %s", exc)


def _append_history(
    drw_no: int,
    channel: str,
    success: bool,
    error_message: str | None = None,
) -> dict[str, Any]:
    """이력 한 건을 누적 저장 후 추가된 엔트리 반환."""
    entry: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "drwNo": drw_no,
        "channel": channel,
        "sent_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),  # noqa: UP017
        "success": success,
        "error_message": error_message,
    }
    history = load_history()
    history.append(entry)
    _save_history(history)
    return entry


# @MX:ANCHOR: [AUTO] 알림 디스패치 진입점 — scheduler 가 수집 성공 후 호출
# @MX:REASON: webhook/email 두 채널을 조건부로 발사하고 이력에 기록하는 단일 출구
def notify(draw_info: dict[str, Any]) -> list[dict[str, Any]]:
    """REQ-NOTIF-002~004: 조건 충족 시 두 채널로 알림 발사 및 이력 기록.

    - should_notify 가 False 면 즉시 빈 리스트 반환 (이력 미기록)
    - 각 채널은 설정되어 있을 때만 호출되며 결과(성공/실패)를 이력에 기록
    - 어떤 예외도 호출자(scheduler)로 전파하지 않음

    Returns:
        기록된 알림 엔트리 리스트 (전송 시도 채널별).
    """
    drw_no = draw_info.get("drwNo")
    prize = draw_info.get("prize1Amount")

    if not should_notify(drw_no or 0, prize):
        return []

    entries: list[dict[str, Any]] = []

    # Webhook 채널 — URL 설정된 경우만 발사
    if settings.notify_webhook_url.strip():
        success = False
        err: str | None = None
        try:
            success = send_webhook(draw_info)
            if not success:
                err = "Webhook 전송 실패 (상세는 로그 참조)"
        except Exception as exc:  # noqa: BLE001 — 본 작업 보호
            err = str(exc)
        entries.append(_append_history(drw_no or 0, "webhook", success, err))

    # Email 채널 — 필수 설정 충족 시만 발사
    if (
        settings.notify_smtp_host.strip()
        and settings.notify_email_to.strip()
        and settings.notify_email_from.strip()
    ):
        success = False
        err = None
        try:
            success = send_email(draw_info)
            if not success:
                err = "Email 전송 실패 (상세는 로그 참조)"
        except Exception as exc:  # noqa: BLE001 — 본 작업 보호
            err = str(exc)
        entries.append(_append_history(drw_no or 0, "email", success, err))

    return entries


def get_settings_status() -> dict[str, Any]:
    """REQ-NOTIF-005: 알림 설정 상태 (마스킹 처리) — UI 노출용.

    실제 URL/이메일은 노출하지 않고 "설정됨"/"미설정"만 반환.
    """
    return {
        "threshold": settings.notify_prize_threshold,
        "enabled": settings.notify_prize_threshold > 0,
        "webhook": "설정됨" if settings.notify_webhook_url.strip() else "미설정",
        "email": (
            "설정됨"
            if (
                settings.notify_smtp_host.strip()
                and settings.notify_email_to.strip()
                and settings.notify_email_from.strip()
            )
            else "미설정"
        ),
    }


# SPEC-LOTTO-027 REQ-SET-002: 마스킹 길이 상수 (앞 노출 글자 수)
_WEBHOOK_MASK_PREFIX = 10
_EMAIL_LOCAL_MASK_PREFIX = 2


def mask_webhook_url(url: str) -> str:
    """SPEC-LOTTO-027: Webhook URL 을 마스킹한다.

    - 미설정(빈 문자열) → 빈 문자열 그대로
    - 길이 10 이상 → 앞 10자 + "****"
    - 길이 10 미만 → 전체 + "****"
    """
    if not url:
        return ""
    return url[:_WEBHOOK_MASK_PREFIX] + "****"


def mask_email(email: str) -> str:
    """SPEC-LOTTO-027: 이메일 주소를 마스킹한다.

    - 미설정(빈 문자열) → 빈 문자열 그대로
    - "ab****@domain" 형식: @ 앞 로컬파트 2자 노출 + "****" + "@domain"
    - 로컬파트가 2자 미만이면 가용한 만큼만 노출
    - "@" 가 없으면 앞 2자 + "****" (도메인 없음)
    """
    if not email:
        return ""
    if "@" not in email:
        return email[:_EMAIL_LOCAL_MASK_PREFIX] + "****"
    local, _, domain = email.partition("@")
    return f"{local[:_EMAIL_LOCAL_MASK_PREFIX]}****@{domain}"


def is_webhook_configured() -> bool:
    """SPEC-LOTTO-027: Webhook 채널이 설정되어 있는지 여부."""
    return bool(settings.notify_webhook_url.strip())


def is_email_configured() -> bool:
    """SPEC-LOTTO-027: 이메일 채널(host+to+from)이 모두 설정되어 있는지 여부."""
    return bool(
        settings.notify_smtp_host.strip()
        and settings.notify_email_to.strip()
        and settings.notify_email_from.strip()
    )


def get_full_settings_status() -> dict[str, Any]:
    """SPEC-LOTTO-027 REQ-SET-002: 전체 설정 현황 (마스킹 처리) — 설정 페이지/API 용.

    Webhook/Email/스케줄러/임계값 상태를 한 번에 반환한다.
    실제 URL/이메일 값은 마스킹되어 노출되지 않는다.
    """
    webhook_url = settings.notify_webhook_url.strip()
    email_to = settings.notify_email_to.strip()
    email_enabled = bool(
        settings.notify_smtp_host.strip()
        and email_to
        and settings.notify_email_from.strip()
    )
    return {
        "webhook_enabled": bool(webhook_url),
        "webhook_url_masked": mask_webhook_url(webhook_url),
        "email_enabled": email_enabled,
        "email_to_masked": mask_email(email_to),
        "scheduler_enabled": settings.schedule_enabled,
        "collect_cron": settings.schedule_cron or "",
        "notify_threshold": settings.notify_prize_threshold or 0,
    }
