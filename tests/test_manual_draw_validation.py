"""SPEC-LOTTO-002 REQ-VAL-001: POST /draws/manual 입력 검증 추가 보장.

기존 test_web_api.py 가 422 응답 자체는 커버하지만, "잘못된 입력이 CSV에 기록되지 않는다"는
SPEC 요구는 명시적으로 검증해야 한다.

@MX:SPEC: SPEC-LOTTO-002 REQ-VAL-001
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def isolated_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """data 디렉토리를 임시 경로로 격리합니다."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    return data_dir


def test_manual_draw_422_does_not_persist_invalid_data(
    isolated_data_dir: Path,
) -> None:
    """REQ-VAL-001: 422 응답 시 draws.csv 에 데이터가 기록되어서는 안 된다."""
    from lotto.web.app import app

    csv_path = isolated_data_dir / "draws.csv"
    assert not csv_path.exists(), "테스트 시작 시 draws.csv 가 없어야 함"

    c = TestClient(app)
    # 보너스가 당첨 번호와 중복 — 422 응답이어야 함
    response = c.post("/api/draws/manual", json={
        "drwNo": 12345,
        "date": "20240115",
        "numbers": [1, 2, 3, 4, 5, 6],
        "bonus": 3,  # numbers와 중복
    })

    assert response.status_code == 422, \
        f"검증 실패는 422여야 함. 실제: {response.status_code} - {response.text}"
    assert not csv_path.exists() or csv_path.stat().st_size < 10, \
        "422 응답 시 CSV에 데이터가 기록되어서는 안 됨"


def test_manual_draw_422_returns_detail_field() -> None:
    """REQ-VAL-001: 응답 본문에 'detail' 필드가 있어야 한다 (FastAPI 기본 포맷)."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/draws/manual", json={
        "drwNo": 99999,
        "date": "20240115",
        "numbers": [1, 2, 3, 4, 5, 99],  # 99 is out of range
        "bonus": 7,
    })

    assert response.status_code == 422
    body = response.json()
    assert "detail" in body, f"422 응답에 'detail' 필드가 있어야 함. 받은 응답: {body}"


def test_manual_draw_accepts_valid_input(isolated_data_dir: Path) -> None:
    """REQ-VAL-001 정상 경로: YYYYMMDD 형식 날짜와 유효한 번호는 201을 반환."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/draws/manual", json={
        "drwNo": 99998,
        "date": "20240601",
        "numbers": [3, 7, 14, 21, 28, 35],
        "bonus": 42,
    })

    assert response.status_code == 201, \
        f"유효한 입력은 201을 반환해야 함. 실제: {response.status_code} - {response.text}"


def test_manual_draw_422_invalid_date_format() -> None:
    """REQ-VAL-001: YYYY-MM-DD 같은 비표준 형식은 422를 반환해야 한다."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/draws/manual", json={
        "drwNo": 99997,
        "date": "2024-06-01",  # YYYYMMDD 형식이 아님
        "numbers": [3, 7, 14, 21, 28, 35],
        "bonus": 42,
    })

    assert response.status_code == 422, \
        f"YYYY-MM-DD 형식은 422여야 함. 실제: {response.status_code} - {response.text}"
