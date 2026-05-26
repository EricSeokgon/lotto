"""SPEC-LOTTO-012: GET /api/health 운영 상태 확인 엔드포인트 테스트.

REQ-HLT-001: status 필드는 "ok" 또는 "degraded" 중 하나여야 한다.
REQ-HLT-002: csv_exists + stats_exists 모두 True면 "ok", 아니면 "degraded".
REQ-HLT-003: data.csv_rows 는 CSV 데이터 행 수(헤더 제외)여야 한다.
REQ-HLT-004: uptime_seconds 는 양수여야 한다.
REQ-HLT-005: version 필드는 항상 존재해야 한다 (패키지 미설치 시 "unknown").

@MX:SPEC: SPEC-LOTTO-012
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_returns_200() -> None:
    """REQ-HLT-001: /api/health 는 200 OK 를 반환해야 한다."""
    from lotto.web.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_status_ok_when_files_exist(tmp_path: Path, monkeypatch) -> None:
    """REQ-HLT-002: csv + stats 모두 존재 시 status=ok."""
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # CSV 파일 생성 (헤더 + 2 행)
    (data_dir / "draws.csv").write_text(
        "drwNo,date,n1,n2,n3,n4,n5,n6,bonus\n"
        "1,2002-12-07,10,23,29,33,37,40,16\n"
        "2,2002-12-14,9,13,21,25,32,42,2\n"
    )
    (data_dir / "stats.json").write_text('{"total_rounds": 2}')

    from lotto.web.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["data"]["csv_exists"] is True
    assert body["data"]["stats_exists"] is True
    assert body["data"]["csv_rows"] == 2  # noqa: PLR2004


@pytest.mark.asyncio
async def test_health_status_degraded_when_files_missing(
    tmp_path: Path, monkeypatch
) -> None:
    """REQ-HLT-002: 데이터 파일 없을 때 status=degraded."""
    monkeypatch.chdir(tmp_path)
    # data 디렉토리 자체를 만들지 않아 파일 부재 상태 보장

    from lotto.web.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["data"]["csv_exists"] is False
    assert body["data"]["stats_exists"] is False


@pytest.mark.asyncio
async def test_health_uptime_is_positive() -> None:
    """REQ-HLT-004: uptime_seconds 는 0 이상의 실수여야 한다."""
    from lotto.web.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    body = response.json()
    assert isinstance(body["uptime_seconds"], (int, float))
    assert body["uptime_seconds"] >= 0


@pytest.mark.asyncio
async def test_health_version_present() -> None:
    """REQ-HLT-005: version 필드는 항상 존재해야 한다."""
    from lotto.web.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    body = response.json()
    assert "version" in body
    assert isinstance(body["version"], str)
    assert len(body["version"]) > 0


@pytest.mark.asyncio
async def test_health_response_schema_complete(tmp_path: Path, monkeypatch) -> None:
    """응답이 HealthResponse 스키마(status, uptime_seconds, data, version)를 모두 포함."""
    monkeypatch.chdir(tmp_path)

    from lotto.web.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    body = response.json()
    # 최상위 필드
    for key in ("status", "uptime_seconds", "data", "version"):
        assert key in body, f"top-level field missing: {key}"
    # data 하위 필드
    for key in ("csv_exists", "csv_rows", "stats_exists", "last_sync"):
        assert key in body["data"], f"data.{key} missing"


@pytest.mark.asyncio
async def test_health_last_sync_from_file(tmp_path: Path, monkeypatch) -> None:
    """data/last_sync.json 이 있을 때 last_sync 값이 반영되어야 한다."""
    import json

    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "last_sync.json").write_text(
        json.dumps({"last_sync_date": "2026-05-21"})
    )

    from lotto.web.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    body = response.json()
    assert body["data"]["last_sync"] == "2026-05-21"


@pytest.mark.asyncio
async def test_health_last_sync_none_when_missing(tmp_path: Path, monkeypatch) -> None:
    """last_sync.json 없을 때 last_sync 는 None 이어야 한다."""
    monkeypatch.chdir(tmp_path)

    from lotto.web.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    body = response.json()
    assert body["data"]["last_sync"] is None


@pytest.mark.asyncio
async def test_health_handles_corrupt_last_sync(tmp_path: Path, monkeypatch) -> None:
    """last_sync.json 이 손상된 경우에도 200 + last_sync=None 반환."""
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "last_sync.json").write_text("not valid json {")

    from lotto.web.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["data"]["last_sync"] is None


@pytest.mark.asyncio
async def test_health_csv_rows_zero_on_oserror(tmp_path: Path, monkeypatch) -> None:
    """CSV 파일 읽기 중 OSError 발생 시 csv_rows=0으로 처리되어야 한다."""
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    csv_path = data_dir / "draws.csv"
    csv_path.write_text("header\n")

    from pathlib import Path as _Path

    from lotto.web.app import app

    _orig_open = _Path.open

    def _raise_for_draws(self, *args, **kwargs):
        if self.name == "draws.csv":
            raise OSError("disk error")
        return _orig_open(self, *args, **kwargs)

    with patch.object(_Path, "open", _raise_for_draws):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["data"]["csv_rows"] == 0


@pytest.mark.asyncio
async def test_health_version_unknown_when_package_not_installed() -> None:
    """패키지 메타데이터 미발견 시 version 은 'unknown'."""
    from importlib.metadata import PackageNotFoundError

    from lotto.web.app import app

    with patch(
        "lotto.web.routes.api._pkg_version_lookup",
        side_effect=PackageNotFoundError("lotto"),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/health")

    assert response.json()["version"] == "unknown"
