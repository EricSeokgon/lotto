"""SPEC-LOTTO-009: 인덱스 페이지 last_date 컨텍스트 및 get_last_sync_date 테스트.

REQ-LAST-001/002 검증.
"""
from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

# ──────────────────────────────────────────────
# REQ-LAST-002: get_last_sync_date 소스 우선순위
# ──────────────────────────────────────────────


def test_get_last_sync_date_from_last_sync_json(tmp_path, monkeypatch):
    """AC-LAST-002-3: last_sync.json의 synced_at 앞 10자(YYYY-MM-DD)를 반환한다."""
    from lotto.web import data as wd

    last_sync_path = tmp_path / "last_sync.json"
    last_sync_path.write_text(json.dumps({
        "last_round": 1100,
        "synced_at": "2026-05-15T14:30:00.123456",
        "total_rounds": 1100,
    }))

    monkeypatch.setattr(wd, "LAST_SYNC_PATH", tmp_path / "last_sync.json")

    result = wd.get_last_sync_date()
    assert result == "2026-05-15"


def test_get_last_sync_date_fallback_to_draws(tmp_path, monkeypatch):
    """AC-LAST-002-1: last_sync.json이 없으면 최신 회차 date를 반환한다."""
    from lotto.web import data as wd

    # last_sync.json 없음
    monkeypatch.setattr(wd, "LAST_SYNC_PATH", tmp_path / "last_sync.json")

    fake_draws = [
        MagicMock(drwNo=10, date=date(2024, 1, 1)),
        MagicMock(drwNo=20, date=date(2024, 6, 15)),
        MagicMock(drwNo=15, date=date(2024, 3, 10)),
    ]
    with patch("lotto.web.data.get_draws", return_value=fake_draws):
        result = wd.get_last_sync_date()

    # 가장 큰 drwNo의 date 문자열
    assert result == "2024-06-15"


def test_get_last_sync_date_no_data_returns_none(tmp_path, monkeypatch):
    """AC-LAST-002-2: 두 소스 모두 없으면 None을 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "LAST_SYNC_PATH", tmp_path / "last_sync.json")

    with patch("lotto.web.data.get_draws", return_value=None):
        result = wd.get_last_sync_date()

    assert result is None


def test_get_last_sync_date_last_sync_takes_priority(tmp_path, monkeypatch):
    """AC-LAST-002-3: last_sync.json이 있으면 draws.csv보다 우선한다."""
    from lotto.web import data as wd

    last_sync_path = tmp_path / "last_sync.json"
    last_sync_path.write_text(json.dumps({
        "last_round": 1100,
        "synced_at": "2026-05-15T14:30:00",
        "total_rounds": 1100,
    }))

    monkeypatch.setattr(wd, "LAST_SYNC_PATH", tmp_path / "last_sync.json")

    fake_draws = [MagicMock(drwNo=1, date=date(2002, 12, 7))]
    with patch("lotto.web.data.get_draws", return_value=fake_draws):
        result = wd.get_last_sync_date()

    # last_sync.json의 값이 우선
    assert result == "2026-05-15"


def test_get_last_sync_date_malformed_json_falls_back(tmp_path, monkeypatch):
    """last_sync.json이 손상된 경우 안전하게 draws 폴백."""
    from lotto.web import data as wd

    last_sync_path = tmp_path / "last_sync.json"
    last_sync_path.write_text("{not valid json")
    monkeypatch.setattr(wd, "LAST_SYNC_PATH", tmp_path / "last_sync.json")

    fake_draws = [MagicMock(drwNo=5, date=date(2024, 12, 1))]
    with patch("lotto.web.data.get_draws", return_value=fake_draws):
        result = wd.get_last_sync_date()

    assert result == "2024-12-01"


def test_get_last_sync_date_missing_synced_at_field(tmp_path, monkeypatch):
    """last_sync.json에 synced_at 키가 없으면 draws 폴백을 사용한다."""
    from lotto.web import data as wd

    last_sync_path = tmp_path / "last_sync.json"
    last_sync_path.write_text(json.dumps({"last_round": 100, "total_rounds": 100}))
    monkeypatch.setattr(wd, "LAST_SYNC_PATH", tmp_path / "last_sync.json")

    fake_draws = [MagicMock(drwNo=3, date=date(2024, 7, 7))]
    with patch("lotto.web.data.get_draws", return_value=fake_draws):
        result = wd.get_last_sync_date()

    assert result == "2024-07-07"


# ──────────────────────────────────────────────
# REQ-LAST-001: 인덱스 라우트가 last_date를 템플릿에 전달
# ──────────────────────────────────────────────


def test_index_has_last_date_from_last_sync(tmp_path, monkeypatch):
    """AC-LAST-001-1: GET / 응답에 last_sync.json 기반 날짜가 포함된다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    last_sync_path = tmp_path / "last_sync.json"
    last_sync_path.write_text(json.dumps({
        "last_round": 1100,
        "synced_at": "2026-04-20T10:00:00",
        "total_rounds": 1100,
    }))
    monkeypatch.setattr(wd, "LAST_SYNC_PATH", tmp_path / "last_sync.json")

    c = TestClient(app)
    response = c.get("/")
    assert response.status_code == 200
    assert "2026-04-20" in response.text


def test_index_has_last_date_from_draws_fallback(tmp_path, monkeypatch):
    """AC-LAST-001-2: last_sync.json이 없을 때 draws의 최신 date가 헤더에 노출된다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    monkeypatch.setattr(wd, "LAST_SYNC_PATH", tmp_path / "last_sync.json")

    fake_draws = [MagicMock(drwNo=1100, date=date(2026, 3, 7))]
    with patch("lotto.web.data.get_draws", return_value=fake_draws):
        c = TestClient(app)
        response = c.get("/")

    assert response.status_code == 200
    assert "2026-03-07" in response.text


def test_index_no_data_returns_200(tmp_path, monkeypatch):
    """AC-LAST-002-2: 데이터가 전혀 없어도 인덱스 페이지가 200을 반환한다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    monkeypatch.setattr(wd, "LAST_SYNC_PATH", tmp_path / "last_sync.json")

    with patch("lotto.web.data.get_draws", return_value=None):
        c = TestClient(app)
        response = c.get("/")

    assert response.status_code == 200
    # last_date가 None이면 헤더 영역이 숨겨지므로 "최근 수집:"이 없어야 한다
    assert "최근 수집" not in response.text


def test_index_shows_recent_label_when_date_available(tmp_path, monkeypatch):
    """AC-LAST-001-2: 헤더에 '최근 수집:' 라벨이 함께 표시된다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    last_sync_path = tmp_path / "last_sync.json"
    last_sync_path.write_text(json.dumps({"synced_at": "2026-01-15T08:00:00"}))
    monkeypatch.setattr(wd, "LAST_SYNC_PATH", tmp_path / "last_sync.json")

    c = TestClient(app)
    response = c.get("/")

    assert response.status_code == 200
    assert "최근 수집" in response.text
    assert "2026-01-15" in response.text
