"""SPEC-LOTTO-027: 웹 설정 관리 페이지 테스트.

REQ-SET-001~005 의 핵심 동작 검증:
- GET /api/settings: 마스킹된 설정 상태 반환
- POST /api/settings/test-webhook: 설정/미설정/실패 분기
- POST /api/settings/test-email: 설정/미설정/실패 분기
- GET /settings: HTML 페이지 렌더링
- 마스킹 헬퍼(mask_webhook_url, mask_email) 단위 검증

@MX:SPEC: SPEC-LOTTO-027
"""

from __future__ import annotations

import contextlib
import dataclasses
from typing import Any

import pytest
from fastapi.testclient import TestClient


@contextlib.contextmanager
def _override_settings(**overrides: Any) -> Any:
    """frozen Settings 를 일시 치환하는 헬퍼.

    notifier 모듈의 settings 와 config.settings 두 곳을 모두 교체해야
    모듈 내부 참조(설정 조회/마스킹/발송)가 일관되게 변경된다.
    """
    from lotto import config as cfg_mod
    from lotto.web import notifier as notif_mod

    original_notif = notif_mod.settings
    original_cfg = cfg_mod.settings
    replaced = dataclasses.replace(original_notif, **overrides)
    notif_mod.settings = replaced
    cfg_mod.settings = replaced
    try:
        yield replaced
    finally:
        notif_mod.settings = original_notif
        cfg_mod.settings = original_cfg


# === 마스킹 헬퍼 단위 테스트 ===


def test_mask_webhook_url_long() -> None:
    """길이 10 이상 URL 은 앞 10자 + '****'."""
    from lotto.web import notifier as notif

    assert notif.mask_webhook_url("https://discord.com/api/webhooks/secret") == "https://di****"


def test_mask_webhook_url_short() -> None:
    """길이 10 미만 URL 은 전체 + '****'."""
    from lotto.web import notifier as notif

    assert notif.mask_webhook_url("http://x") == "http://x****"


def test_mask_webhook_url_empty() -> None:
    """미설정(빈 문자열)은 빈 문자열을 그대로 반환."""
    from lotto.web import notifier as notif

    assert notif.mask_webhook_url("") == ""


def test_mask_email_normal() -> None:
    """@ 앞 2자 노출 + '****' + @domain."""
    from lotto.web import notifier as notif

    assert notif.mask_email("abc@example.com") == "ab****@example.com"


def test_mask_email_single_char_local() -> None:
    """@ 앞 1자만 있을 때는 가용한 만큼만 노출."""
    from lotto.web import notifier as notif

    assert notif.mask_email("a@example.com") == "a****@example.com"


def test_mask_email_empty() -> None:
    """미설정(빈 문자열)은 빈 문자열을 그대로 반환."""
    from lotto.web import notifier as notif

    assert notif.mask_email("") == ""


def test_mask_email_no_at_sign() -> None:
    """'@' 가 없는 잘못된 값은 앞 2자 + '****' (도메인 없음)."""
    from lotto.web import notifier as notif

    assert notif.mask_email("plainvalue") == "pl****"


# === REQ-SET-002: GET /api/settings ===


def test_api_settings_webhook_enabled() -> None:
    """Webhook 설정 시 webhook_enabled=True 및 마스킹 URL 반환."""
    from lotto.web.app import app

    with _override_settings(
        notify_webhook_url="https://discord.com/api/webhooks/secret-token",
        notify_prize_threshold=1_000_000_000,
    ), TestClient(app) as client:
        resp = client.get("/api/settings")

    assert resp.status_code == 200
    body = resp.json()
    assert body["webhook_enabled"] is True
    assert body["webhook_url_masked"] == "https://di****"
    # 실제 토큰은 노출되지 않아야 함
    assert "secret-token" not in resp.text
    assert body["notify_threshold"] == 1_000_000_000


def test_api_settings_email_enabled() -> None:
    """이메일 설정(host+to+from) 시 email_enabled=True 및 마스킹 주소 반환."""
    from lotto.web.app import app

    with _override_settings(
        notify_smtp_host="smtp.gmail.com",
        notify_email_to="user@gmail.com",
        notify_email_from="alert@app.com",
    ), TestClient(app) as client:
        resp = client.get("/api/settings")

    body = resp.json()
    assert body["email_enabled"] is True
    assert body["email_to_masked"] == "us****@gmail.com"
    assert "user@gmail.com" not in resp.text


def test_api_settings_all_disabled() -> None:
    """모든 채널 미설정 시 enabled=False, 마스킹 값은 빈 문자열, threshold=0."""
    from lotto.web.app import app

    with _override_settings(
        notify_webhook_url="",
        notify_smtp_host="",
        notify_email_to="",
        notify_email_from="",
        notify_prize_threshold=0,
        schedule_enabled=False,
        schedule_cron="",
    ), TestClient(app) as client:
        resp = client.get("/api/settings")

    body = resp.json()
    assert body["webhook_enabled"] is False
    assert body["webhook_url_masked"] == ""
    assert body["email_enabled"] is False
    assert body["email_to_masked"] == ""
    assert body["scheduler_enabled"] is False
    assert body["collect_cron"] == ""
    assert body["notify_threshold"] == 0


def test_api_settings_scheduler_status() -> None:
    """스케줄러 설정값(enabled/cron)이 그대로 노출된다."""
    from lotto.web.app import app

    with _override_settings(
        schedule_enabled=True,
        schedule_cron="10 21 * * 6",
    ), TestClient(app) as client:
        resp = client.get("/api/settings")

    body = resp.json()
    assert body["scheduler_enabled"] is True
    assert body["collect_cron"] == "10 21 * * 6"


# === REQ-SET-003: POST /api/settings/test-webhook ===


def test_test_webhook_configured_sends(monkeypatch: pytest.MonkeyPatch) -> None:
    """Webhook 설정 시 발송 후 {'sent': True} 반환."""
    from lotto.web import notifier as notif
    from lotto.web.app import app

    monkeypatch.setattr(notif, "send_webhook", lambda info: True)

    with _override_settings(notify_webhook_url="https://x.test/webhook"), TestClient(app) as client:
        resp = client.post("/api/settings/test-webhook")

    assert resp.status_code == 200
    assert resp.json() == {"sent": True}


def test_test_webhook_not_configured() -> None:
    """Webhook 미설정 시 HTTP 400 + {'sent': False, 'reason': 'not_configured'}."""
    from lotto.web.app import app

    with _override_settings(notify_webhook_url=""), TestClient(app) as client:
        resp = client.post("/api/settings/test-webhook")

    assert resp.status_code == 400
    body = resp.json()
    assert body["sent"] is False
    assert body["reason"] == "not_configured"


def test_test_webhook_send_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """발송 실패(예외) 시 {'sent': False, 'reason': <error>} 반환."""
    from lotto.web import notifier as notif
    from lotto.web.app import app

    def _boom(info: object) -> bool:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(notif, "send_webhook", _boom)

    with _override_settings(notify_webhook_url="https://x.test/webhook"), TestClient(app) as client:
        resp = client.post("/api/settings/test-webhook")

    assert resp.status_code == 200
    body = resp.json()
    assert body["sent"] is False
    assert "connection refused" in body["reason"]


def test_test_webhook_send_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """send_webhook 가 False 반환 시 {'sent': False, 'reason': ...} 반환."""
    from lotto.web import notifier as notif
    from lotto.web.app import app

    monkeypatch.setattr(notif, "send_webhook", lambda info: False)

    with _override_settings(notify_webhook_url="https://x.test/webhook"), TestClient(app) as client:
        resp = client.post("/api/settings/test-webhook")

    assert resp.status_code == 200
    body = resp.json()
    assert body["sent"] is False
    assert body["reason"]  # 비어있지 않은 사유 문자열


# === REQ-SET-004: POST /api/settings/test-email ===


def test_test_email_configured_sends(monkeypatch: pytest.MonkeyPatch) -> None:
    """이메일 설정 시 발송 후 {'sent': True} 반환."""
    from lotto.web import notifier as notif
    from lotto.web.app import app

    monkeypatch.setattr(notif, "send_email", lambda info: True)

    with _override_settings(
        notify_smtp_host="smtp.test",
        notify_email_to="to@test.com",
        notify_email_from="from@test.com",
    ), TestClient(app) as client:
        resp = client.post("/api/settings/test-email")

    assert resp.status_code == 200
    assert resp.json() == {"sent": True}


def test_test_email_not_configured() -> None:
    """이메일 미설정 시 HTTP 400 + {'sent': False, 'reason': 'not_configured'}."""
    from lotto.web.app import app

    with _override_settings(
        notify_smtp_host="",
        notify_email_to="",
        notify_email_from="",
    ), TestClient(app) as client:
        resp = client.post("/api/settings/test-email")

    assert resp.status_code == 400
    body = resp.json()
    assert body["sent"] is False
    assert body["reason"] == "not_configured"


def test_test_email_send_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """발송 실패(예외) 시 {'sent': False, 'reason': <error>} 반환."""
    from lotto.web import notifier as notif
    from lotto.web.app import app

    def _boom(info: object) -> bool:
        raise RuntimeError("smtp auth failed")

    monkeypatch.setattr(notif, "send_email", _boom)

    with _override_settings(
        notify_smtp_host="smtp.test",
        notify_email_to="to@test.com",
        notify_email_from="from@test.com",
    ), TestClient(app) as client:
        resp = client.post("/api/settings/test-email")

    assert resp.status_code == 200
    body = resp.json()
    assert body["sent"] is False
    assert "smtp auth failed" in body["reason"]


# === REQ-SET-001: GET /settings 페이지 ===


def test_settings_page_renders_html() -> None:
    """GET /settings 가 200 HTML 을 반환한다."""
    from lotto.web.app import app

    with TestClient(app) as client:
        resp = client.get("/settings")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "설정" in resp.text


def test_settings_page_shows_masked_values() -> None:
    """설정 페이지에 폼 필드가 있으며 원본 비밀값은 HTML에 노출되지 않는다.

    SPEC-LOTTO-113: 설정이 편집 가능한 폼으로 변경됨.
    값은 JS(/api/settings/values)로 로드하므로 마스킹 텍스트가 HTML에 없음.
    원본 secret-token 등은 HTML에 포함되어서는 안 됨.
    """
    from lotto.web.app import app

    with _override_settings(
        notify_webhook_url="https://discord.com/api/webhooks/secret-token",
        notify_smtp_host="smtp.gmail.com",
        notify_email_to="user@gmail.com",
        notify_email_from="alert@app.com",
        notify_prize_threshold=1,
    ), TestClient(app) as client:
        resp = client.get("/settings")

    assert resp.status_code == 200
    # 폼 필드 존재 확인
    assert 'id="notify_webhook_url"' in resp.text
    assert 'id="notify_email_to"' in resp.text
    # 원본 비밀값은 HTML에 노출되지 않음 (JS 로드 방식)
    assert "secret-token" not in resp.text
    # 테스트 발송 버튼 존재
    assert 'data-testid="test-webhook-btn"' in resp.text
    assert 'data-testid="test-email-btn"' in resp.text


def test_settings_page_empty_state() -> None:
    """모든 항목 미설정 시에도 설정 폼이 정상 렌더링된다.

    SPEC-LOTTO-113: 설정 페이지가 폼 기반으로 변경됨.
    빈 상태에서도 폼 요소가 표시되어야 함.
    """
    from lotto.web.app import app

    with _override_settings(
        notify_webhook_url="",
        notify_smtp_host="",
        notify_email_to="",
        notify_email_from="",
        notify_prize_threshold=0,
        schedule_enabled=False,
    ), TestClient(app) as client:
        resp = client.get("/settings")

    assert resp.status_code == 200
    # 폼 요소가 있어야 함
    assert 'id="notify_webhook_url"' in resp.text
    assert 'id="notify_prize_threshold"' in resp.text


def test_settings_nav_link_present() -> None:
    """네비게이션에 설정 페이지 링크(/settings)가 존재한다."""
    from lotto.web.app import app

    with TestClient(app) as client:
        resp = client.get("/")

    assert resp.status_code == 200
    assert 'href="/settings"' in resp.text
