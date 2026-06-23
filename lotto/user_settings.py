"""웹 UI에서 저장된 알림 설정 (data/user_settings.json).

환경 변수가 설정된 경우 환경 변수가 우선합니다.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()


def _path() -> Path:
    from lotto.config import settings

    return Path(settings.data_dir) / "user_settings.json"


# @MX:ANCHOR: [AUTO] 웹 UI 설정 로드 — config.py와 api.py에서 호출
# @MX:REASON: fan_in >= 3 (config.py, api.py/get_settings_values, api.py/update_settings)
def load() -> dict[str, Any]:
    """user_settings.json 로드. 파일 없거나 손상 시 빈 딕셔너리 반환."""
    p = _path()
    if not p.exists():
        return {}
    try:
        with _lock:
            data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


# @MX:ANCHOR: [AUTO] 웹 UI 설정 저장 — api.py/update_settings에서 호출
# @MX:REASON: 원자적 파일 쓰기 (tmp → rename), 스레드 안전
def save(data: dict[str, Any]) -> None:
    """user_settings.json 원자적 저장."""
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    with _lock:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
