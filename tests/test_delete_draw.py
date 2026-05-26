"""추첨 결과 회차 삭제 API 테스트.

DELETE /api/draws/{drw_no} 엔드포인트 검증.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    return data_dir


@pytest.fixture
def client_with_draws(isolated_data_dir: Path) -> TestClient:
    """2개 회차가 저장된 상태의 테스트 클라이언트를 반환합니다."""
    from lotto.web.app import app

    c = TestClient(app)
    for drw_no, date, nums, bonus in [
        (1145, "20250101", [1, 2, 3, 4, 5, 6], 7),
        (1146, "20250108", [10, 11, 12, 13, 14, 15], 16),
    ]:
        res = c.post(
            "/api/draws/manual",
            json={"drwNo": drw_no, "date": date, "numbers": nums, "bonus": bonus},
        )
        assert res.status_code == 201
    return c


def test_delete_draw_success(client_with_draws: TestClient) -> None:
    """존재하는 회차를 삭제하면 200과 성공 메시지를 반환합니다."""
    res = client_with_draws.delete("/api/draws/1145")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "1145" in body["message"]
    assert body["total"] == 1


def test_delete_draw_removes_from_csv(client_with_draws: TestClient, isolated_data_dir: Path) -> None:
    """삭제 후 CSV에서 해당 회차가 사라집니다."""
    from lotto.collector import LottoCollector

    client_with_draws.delete("/api/draws/1145")
    draws = LottoCollector().load_existing()
    assert all(d.drwNo != 1145 for d in draws)
    assert any(d.drwNo == 1146 for d in draws)


def test_delete_draw_not_found(client_with_draws: TestClient) -> None:
    """존재하지 않는 회차를 삭제하면 404를 반환합니다."""
    res = client_with_draws.delete("/api/draws/9999")
    assert res.status_code == 404
    assert "9999" in res.json()["detail"]


def test_delete_draw_twice_returns_404(client_with_draws: TestClient) -> None:
    """한 번 삭제한 회차를 다시 삭제하면 404를 반환합니다."""
    client_with_draws.delete("/api/draws/1145")
    res = client_with_draws.delete("/api/draws/1145")
    assert res.status_code == 404


def test_delete_all_draws(client_with_draws: TestClient) -> None:
    """모든 회차를 삭제하면 total이 0이 됩니다."""
    client_with_draws.delete("/api/draws/1145")
    res = client_with_draws.delete("/api/draws/1146")
    assert res.status_code == 200
    assert res.json()["total"] == 0
