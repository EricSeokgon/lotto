"""SPEC-LOTTO-113: user_settings 모듈 + /api/settings, /api/settings/values 엔드포인트 테스트."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

# ──────────────────────────────────────────────
# user_settings 모듈 단위 테스트
# ──────────────────────────────────────────────


def _patch_path(tmp_path: Path):
    """lotto.user_settings._path를 tmp_path 기반으로 교체하는 컨텍스트 매니저."""
    target = tmp_path / "user_settings.json"
    return patch("lotto.user_settings._path", return_value=target)


def test_save_and_load(tmp_path: Path) -> None:
    """save() 후 load()가 동일 데이터를 반환해야 한다."""
    from lotto import user_settings as _us

    data: dict[str, Any] = {
        "notify_webhook_url": "https://example.com/hook",
        "notify_prize_threshold": 500000000,
    }
    with _patch_path(tmp_path):
        _us.save(data)
        result = _us.load()

    assert result["notify_webhook_url"] == "https://example.com/hook"
    assert result["notify_prize_threshold"] == 500000000


def test_load_missing_file(tmp_path: Path) -> None:
    """파일이 없으면 load()는 빈 딕셔너리를 반환해야 한다."""
    from lotto import user_settings as _us

    with _patch_path(tmp_path):
        result = _us.load()

    assert result == {}


def test_load_corrupted_file(tmp_path: Path) -> None:
    """손상된 JSON 파일이면 load()는 빈 딕셔너리를 반환해야 한다."""
    from lotto import user_settings as _us

    target = tmp_path / "user_settings.json"
    target.write_text("NOT_VALID_JSON", encoding="utf-8")

    with _patch_path(tmp_path):
        result = _us.load()

    assert result == {}


def test_save_atomic(tmp_path: Path) -> None:
    """save() 후 .json.tmp 임시 파일은 남아있지 않아야 한다."""
    from lotto import user_settings as _us

    with _patch_path(tmp_path):
        _us.save({"notify_webhook_url": "https://hook.example.com"})

    tmp_file = tmp_path / "user_settings.json.tmp"
    assert not tmp_file.exists(), ".json.tmp 임시 파일이 남아있으면 안 됨"
    assert (tmp_path / "user_settings.json").exists()


def test_save_overwrites(tmp_path: Path) -> None:
    """두 번 save() 하면 마지막 값으로 덮어써야 한다."""
    from lotto import user_settings as _us

    with _patch_path(tmp_path):
        _us.save({"notify_webhook_url": "https://first.example.com"})
        _us.save({"notify_webhook_url": "https://second.example.com"})
        result = _us.load()

    assert result["notify_webhook_url"] == "https://second.example.com"


# ──────────────────────────────────────────────
# API 엔드포인트 통합 테스트
# ──────────────────────────────────────────────


def test_api_get_settings_values(tmp_path: Path) -> None:
    """GET /api/settings/values 는 저장된 값을 반환해야 한다."""
    from fastapi.testclient import TestClient

    from lotto.web.app import app

    saved: dict[str, Any] = {
        "notify_webhook_url": "https://hook.test",
        "notify_prize_threshold": 100000000,
    }
    target = tmp_path / "user_settings.json"
    target.write_text(json.dumps(saved), encoding="utf-8")

    with patch("lotto.user_settings._path", return_value=target):
        client = TestClient(app)
        response = client.get("/api/settings/values")

    assert response.status_code == 200
    body = response.json()
    assert body["notify_webhook_url"] == "https://hook.test"
    assert body["notify_prize_threshold"] == 100000000


def test_api_update_settings(tmp_path: Path) -> None:
    """POST /api/settings 는 설정을 저장하고 {ok: True}를 반환해야 한다."""
    from fastapi.testclient import TestClient

    import lotto.config as _config
    from lotto.web.app import app

    original_settings = _config.settings
    target = tmp_path / "user_settings.json"

    payload = {
        "notify_webhook_url": "https://new-hook.example.com",
        "notify_email_to": "test@example.com",
        "notify_email_from": "from@example.com",
        "notify_smtp_host": "smtp.example.com",
        "notify_smtp_port": 465,
        "notify_smtp_user": "user",
        "notify_smtp_pass": "pass",
        "notify_prize_threshold": 200000000,
    }

    try:
        with patch("lotto.user_settings._path", return_value=target):
            client = TestClient(app)
            response = client.post("/api/settings", json=payload)
    finally:
        # 전역 settings 복원 — 다른 테스트 오염 방지
        _config.settings = original_settings

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True

    # 파일에 저장됐는지 확인
    assert target.exists()
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["notify_webhook_url"] == "https://new-hook.example.com"
    assert saved["notify_smtp_port"] == 465


def test_config_loads_file_override(tmp_path: Path) -> None:
    """user_settings.json이 있고 환경 변수 미설정 시 config가 파일 값을 반영해야 한다."""
    import importlib
    import os

    saved: dict[str, Any] = {
        "notify_webhook_url": "https://from-file.example.com",
        "notify_prize_threshold": 300000000,
    }
    settings_file = tmp_path / "user_settings.json"
    settings_file.write_text(json.dumps(saved), encoding="utf-8")

    env_patch = {
        "LOTTO_DATA_DIR": str(tmp_path),
    }
    # 환경 변수에 WEBHOOK_URL이 없는 상태에서 config 재로드
    with patch.dict(os.environ, env_patch, clear=False):
        # LOTTO_NOTIFY_WEBHOOK_URL이 없을 때
        os.environ.pop("LOTTO_NOTIFY_WEBHOOK_URL", None)
        os.environ.pop("LOTTO_NOTIFY_PRIZE_THRESHOLD", None)

        import lotto.config as _config

        importlib.reload(_config)
        new_settings = _config.settings

    assert new_settings.notify_webhook_url == "https://from-file.example.com"
    assert new_settings.notify_prize_threshold == 300000000
