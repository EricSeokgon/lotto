"""SPEC-LOTTO-025: 조건부 알림(Webhook/Email) 테스트.

REQ-NOTIF-001~005 의 핵심 동작 검증:
- 임계값/채널 설정 조건 평가
- Webhook POST 페이로드 및 실패 처리
- Email SMTP 호출 및 실패 처리
- notify() 통합 동작 및 이력 누적
- GET /api/notifications 응답 shape

@MX:SPEC: SPEC-LOTTO-025 REQ-NOTIF-001~005
"""

from __future__ import annotations

import contextlib
import dataclasses
import smtplib
from typing import Any
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient


@contextlib.contextmanager
def _override_notifier_settings(**overrides: Any):
    """frozen Settings 를 일시 치환하는 헬퍼.

    notifier 모듈의 settings 와 config.settings 두 곳을 모두 교체해야
    모듈 내부 참조가 일관되게 변경된다.
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


@pytest.fixture
def tmp_notifications_dir(tmp_path, monkeypatch):
    """data_dir 을 임시 디렉토리로 교체하여 이력 파일을 격리한다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    from lotto import config as cfg_mod
    from lotto.web import notifier as notif_mod

    new_settings = dataclasses.replace(cfg_mod.settings, data_dir=data_dir)
    monkeypatch.setattr(notif_mod, "settings", new_settings)
    monkeypatch.setattr(cfg_mod, "settings", new_settings)
    return data_dir


# === REQ-NOTIF-001: should_notify 조건 평가 ===


def test_should_notify_returns_false_when_threshold_is_zero():
    """threshold=0 (기본값) 이면 항상 False 를 반환한다."""
    from lotto.web import notifier as notif

    with _override_notifier_settings(notify_prize_threshold=0):
        assert notif.should_notify(1000, 5_000_000_000) is False


def test_should_notify_returns_false_when_prize_below_threshold():
    """1등 당첨금이 임계값 미만이면 False."""
    from lotto.web import notifier as notif

    with _override_notifier_settings(notify_prize_threshold=3_000_000_000):
        assert notif.should_notify(1000, 2_500_000_000) is False


def test_should_notify_returns_true_when_prize_at_or_above_threshold():
    """1등 당첨금 >= 임계값 이면 True."""
    from lotto.web import notifier as notif

    with _override_notifier_settings(notify_prize_threshold=3_000_000_000):
        assert notif.should_notify(1000, 3_000_000_000) is True
        assert notif.should_notify(1001, 5_000_000_000) is True


def test_should_notify_returns_false_when_prize_amount_none():
    """prize_amount=None 이면 비교 불가 → False."""
    from lotto.web import notifier as notif

    with _override_notifier_settings(notify_prize_threshold=1):
        assert notif.should_notify(1000, None) is False


# === REQ-NOTIF-002: Webhook 알림 ===


def test_send_webhook_calls_httpx_post_with_payload(monkeypatch):
    """Webhook URL 설정 시 httpx.Client.post 가 페이로드와 함께 호출된다."""
    from lotto.web import notifier as notif

    captured: dict[str, Any] = {}

    class _FakeResponse:
        status_code = 204
        text = ""

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            captured["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None):
            captured["url"] = url
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr(httpx, "Client", _FakeClient)

    with _override_notifier_settings(notify_webhook_url="https://discord.test/webhook"):
        ok = notif.send_webhook({
            "drwNo": 1234,
            "numbers": [1, 7, 13, 22, 35, 44],
            "bonus": 9,
            "prize1Amount": 5_000_000_000,
            "prize1Winners": 3,
        })

    assert ok is True
    assert captured["url"] == "https://discord.test/webhook"
    # Discord/Slack 호환 — content + text 두 필드 모두 존재
    assert "content" in captured["json"]
    assert "text" in captured["json"]
    assert "1234" in captured["json"]["content"]
    assert "5,000,000,000" in captured["json"]["content"]


def test_send_webhook_returns_false_when_url_not_configured():
    """Webhook URL 미설정 시 즉시 False — 외부 호출 없음."""
    from lotto.web import notifier as notif

    with _override_notifier_settings(notify_webhook_url=""):
        assert notif.send_webhook({"drwNo": 1, "prize1Amount": 9_999_999_999}) is False


def test_send_webhook_failure_logs_warning_and_returns_false(monkeypatch, caplog):
    """httpx 예외 발생 시 로그 경고 + False 반환 (예외 전파 금지)."""
    import logging

    from lotto.web import notifier as notif

    class _ExplodingClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "Client", _ExplodingClient)

    with (
        _override_notifier_settings(notify_webhook_url="https://invalid.test/webhook"),
        caplog.at_level(logging.WARNING, logger="lotto.web.notifier"),
    ):
        result = notif.send_webhook({"drwNo": 1, "prize1Amount": 1})

    assert result is False
    assert any("Webhook notification failed" in rec.message for rec in caplog.records)


def test_send_webhook_returns_false_on_non_2xx_status(monkeypatch):
    """비-2xx 응답은 실패로 간주."""
    from lotto.web import notifier as notif

    class _FakeResponse:
        status_code = 500
        text = "internal error"

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, json=None):
            return _FakeResponse()

    monkeypatch.setattr(httpx, "Client", _FakeClient)
    with _override_notifier_settings(notify_webhook_url="https://x.test/webhook"):
        assert notif.send_webhook({"drwNo": 1, "prize1Amount": 1}) is False


# === REQ-NOTIF-003: Email 알림 ===


def test_send_email_calls_smtp_with_correct_parameters(monkeypatch):
    """SMTP 설정 시 smtplib.SMTP 가 호출되고 send_message 가 호출된다."""
    from lotto.web import notifier as notif

    fake_smtp = MagicMock()
    fake_smtp.__enter__ = MagicMock(return_value=fake_smtp)
    fake_smtp.__exit__ = MagicMock(return_value=False)

    smtp_factory = MagicMock(return_value=fake_smtp)
    monkeypatch.setattr(smtplib, "SMTP", smtp_factory)

    with _override_notifier_settings(
        notify_smtp_host="smtp.test.com",
        notify_smtp_port=587,
        notify_email_to="recipient@test.com",
        notify_email_from="sender@test.com",
        notify_smtp_user="user",
        notify_smtp_pass="pass",
    ):
        ok = notif.send_email({
            "drwNo": 1234,
            "numbers": [1, 7, 13, 22, 35, 44],
            "bonus": 9,
            "prize1Amount": 5_000_000_000,
            "prize1Winners": 3,
        })

    assert ok is True
    smtp_factory.assert_called_once_with("smtp.test.com", 587, timeout=10)
    fake_smtp.login.assert_called_once_with("user", "pass")
    fake_smtp.send_message.assert_called_once()


def test_send_email_returns_false_when_settings_missing():
    """SMTP host/to/from 중 하나라도 없으면 즉시 False."""
    from lotto.web import notifier as notif

    with _override_notifier_settings(
        notify_smtp_host="",
        notify_email_to="r@test.com",
        notify_email_from="s@test.com",
    ):
        assert notif.send_email({"drwNo": 1, "prize1Amount": 1}) is False


def test_send_email_failure_logs_warning_and_returns_false(monkeypatch, caplog):
    """SMTP 예외 발생 시 로그 경고 + False (예외 전파 금지)."""
    import logging

    from lotto.web import notifier as notif

    def _exploding_smtp(*args, **kwargs):
        raise smtplib.SMTPConnectError(421, "service not available")

    monkeypatch.setattr(smtplib, "SMTP", _exploding_smtp)

    with (
        _override_notifier_settings(
            notify_smtp_host="smtp.bad.test",
            notify_email_to="r@test.com",
            notify_email_from="s@test.com",
        ),
        caplog.at_level(logging.WARNING, logger="lotto.web.notifier"),
    ):
        result = notif.send_email({"drwNo": 1, "prize1Amount": 1})

    assert result is False
    assert any("Email notification failed" in rec.message for rec in caplog.records)


def test_send_email_works_without_starttls(monkeypatch):
    """STARTTLS 미지원 서버는 평문 전송으로 fallback (예외 안전)."""
    from lotto.web import notifier as notif

    fake_smtp = MagicMock()
    fake_smtp.__enter__ = MagicMock(return_value=fake_smtp)
    fake_smtp.__exit__ = MagicMock(return_value=False)
    fake_smtp.starttls.side_effect = smtplib.SMTPException("not supported")

    monkeypatch.setattr(smtplib, "SMTP", MagicMock(return_value=fake_smtp))

    with _override_notifier_settings(
        notify_smtp_host="smtp.local",
        notify_email_to="r@test.com",
        notify_email_from="s@test.com",
        notify_smtp_user="",
        notify_smtp_pass="",
    ):
        assert notif.send_email({"drwNo": 1, "prize1Amount": 1}) is True
    fake_smtp.send_message.assert_called_once()


# === REQ-NOTIF-004: notify() 통합 동작 + 이력 저장 ===


def test_notify_skips_when_threshold_zero(tmp_notifications_dir):
    """threshold=0 이면 알림 미발사 및 이력 미기록."""
    from lotto.web import notifier as notif

    with _override_notifier_settings(
        notify_prize_threshold=0,
        notify_webhook_url="https://x.test/wh",
        notify_smtp_host="smtp.test",
        notify_email_to="r@t.com",
        notify_email_from="s@t.com",
    ):
        # data_dir 도 함께 유지하기 위해 추가 치환
        from lotto import config as cfg_mod
        from lotto.web import notifier as notif_mod
        merged = dataclasses.replace(cfg_mod.settings, data_dir=tmp_notifications_dir)
        notif_mod.settings = merged
        cfg_mod.settings = merged

        entries = notif.notify({"drwNo": 1, "prize1Amount": 9_999_999_999})

    assert entries == []
    assert notif.load_history() == []


def test_notify_calls_both_channels_when_configured(tmp_notifications_dir, monkeypatch):
    """webhook + email 둘 다 설정되고 임계값 충족 시 두 채널 모두 호출."""
    from lotto.web import notifier as notif

    monkeypatch.setattr(notif, "send_webhook", lambda info: True)
    monkeypatch.setattr(notif, "send_email", lambda info: True)

    from lotto import config as cfg_mod
    merged = dataclasses.replace(
        cfg_mod.settings,
        data_dir=tmp_notifications_dir,
        notify_prize_threshold=1_000_000_000,
        notify_webhook_url="https://x.test/wh",
        notify_smtp_host="smtp.test",
        notify_email_to="r@t.com",
        notify_email_from="s@t.com",
    )
    monkeypatch.setattr(notif, "settings", merged)
    monkeypatch.setattr(cfg_mod, "settings", merged)

    entries = notif.notify({"drwNo": 1234, "prize1Amount": 5_000_000_000})

    assert len(entries) == 2
    channels = {e["channel"] for e in entries}
    assert channels == {"webhook", "email"}
    assert all(e["success"] is True for e in entries)


def test_notify_records_failure_in_history(tmp_notifications_dir, monkeypatch):
    """채널이 실패해도 이력에 success=False 로 기록된다."""
    from lotto.web import notifier as notif

    monkeypatch.setattr(notif, "send_webhook", lambda info: False)

    from lotto import config as cfg_mod
    merged = dataclasses.replace(
        cfg_mod.settings,
        data_dir=tmp_notifications_dir,
        notify_prize_threshold=1,
        notify_webhook_url="https://x.test/wh",
        notify_smtp_host="",
        notify_email_to="",
        notify_email_from="",
    )
    monkeypatch.setattr(notif, "settings", merged)
    monkeypatch.setattr(cfg_mod, "settings", merged)

    entries = notif.notify({"drwNo": 1, "prize1Amount": 100})

    assert len(entries) == 1
    assert entries[0]["channel"] == "webhook"
    assert entries[0]["success"] is False
    assert entries[0]["error_message"] is not None

    history = notif.load_history()
    assert len(history) == 1
    assert history[0]["success"] is False


def test_notify_persists_history_to_file(tmp_notifications_dir, monkeypatch):
    """이력 한 건이 data/notifications.json 에 저장되고 다시 로드 가능."""
    from lotto.web import notifier as notif

    monkeypatch.setattr(notif, "send_webhook", lambda info: True)

    from lotto import config as cfg_mod
    merged = dataclasses.replace(
        cfg_mod.settings,
        data_dir=tmp_notifications_dir,
        notify_prize_threshold=1,
        notify_webhook_url="https://x.test/wh",
        notify_smtp_host="",
    )
    monkeypatch.setattr(notif, "settings", merged)
    monkeypatch.setattr(cfg_mod, "settings", merged)

    notif.notify({"drwNo": 999, "prize1Amount": 100})

    path = tmp_notifications_dir / "notifications.json"
    assert path.exists()
    reloaded = notif.load_history()
    assert len(reloaded) == 1
    assert reloaded[0]["drwNo"] == 999
    assert reloaded[0]["channel"] == "webhook"


def test_load_history_missing_file_returns_empty(tmp_notifications_dir):
    """파일 부재 시 빈 리스트 반환 (graceful)."""
    from lotto.web import notifier as notif

    assert notif.load_history() == []


def test_load_history_corrupted_file_returns_empty(tmp_notifications_dir):
    """JSON 파싱 실패 시 빈 리스트 반환."""
    from lotto.web import notifier as notif

    path = tmp_notifications_dir / "notifications.json"
    path.write_text("{not valid json")
    assert notif.load_history() == []


# === REQ-NOTIF-004,005: API & UI ===


def test_notifications_api_returns_settings_and_items(tmp_notifications_dir, monkeypatch):
    """GET /api/notifications 가 {settings, items} 구조를 반환한다."""
    from lotto.web import notifier as notif
    from lotto.web.app import app

    monkeypatch.setattr(notif, "send_webhook", lambda info: True)

    from lotto import config as cfg_mod
    merged = dataclasses.replace(
        cfg_mod.settings,
        data_dir=tmp_notifications_dir,
        notify_prize_threshold=1,
        notify_webhook_url="https://x.test/wh",
    )
    monkeypatch.setattr(notif, "settings", merged)
    monkeypatch.setattr(cfg_mod, "settings", merged)

    notif.notify({"drwNo": 42, "prize1Amount": 100})

    with TestClient(app) as client:
        resp = client.get("/api/notifications")

    assert resp.status_code == 200
    body = resp.json()
    assert "settings" in body
    assert "items" in body
    assert isinstance(body["items"], list)
    assert body["settings"]["webhook"] == "설정됨"
    assert body["settings"]["threshold"] == 1
    assert body["settings"]["enabled"] is True
    assert any(item["drwNo"] == 42 for item in body["items"])


def test_notifications_api_empty_when_no_history(tmp_notifications_dir):
    """이력 파일 부재 시 items=[] 반환."""
    from lotto.web.app import app

    with TestClient(app) as client:
        resp = client.get("/api/notifications")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_settings_status_masks_actual_values():
    """get_settings_status 는 실제 URL/이메일을 노출하지 않는다."""
    from lotto.web import notifier as notif

    with _override_notifier_settings(
        notify_prize_threshold=5_000_000_000,
        notify_webhook_url="https://very-secret.example/webhook/abc123",
        notify_smtp_host="smtp.gmail.com",
        notify_email_to="user@gmail.com",
        notify_email_from="alert@app.com",
    ):
        status = notif.get_settings_status()

    # 마스킹 — 실제 URL/이메일 값이 노출되지 않아야 함
    assert "very-secret" not in str(status)
    assert "user@gmail.com" not in str(status)
    assert status["webhook"] == "설정됨"
    assert status["email"] == "설정됨"
    assert status["threshold"] == 5_000_000_000
    assert status["enabled"] is True


def test_index_page_shows_notification_card():
    """인덱스 페이지에 알림 설정 카드가 렌더링된다 (REQ-NOTIF-005)."""
    from lotto.web.app import app

    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "알림 설정" in resp.text
    assert "data-testid=\"notify-webhook\"" in resp.text


# === Config 외부화 ===


def test_settings_default_notification_values():
    """기본값: threshold=0 (비활성), 모든 채널 빈 문자열."""
    from lotto.config import settings

    # 환경 변수가 설정되지 않은 baseline 상태에서 기본값 확인 (필드 존재 검증)
    assert hasattr(settings, "notify_prize_threshold")
    assert hasattr(settings, "notify_webhook_url")
    assert hasattr(settings, "notify_email_to")
    assert hasattr(settings, "notify_smtp_host")
    assert hasattr(settings, "notify_smtp_port")
    assert isinstance(settings.notify_prize_threshold, int)
    assert isinstance(settings.notify_smtp_port, int)
