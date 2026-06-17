"""SPEC-LOTTO-048: 시뮬레이션 결과 저장/비교 API 통합 테스트.

REQ: POST/GET/DELETE /api/simulation-history.

각 테스트마다 임시 sim_history.json 경로로 격리하여 실제 사용자 데이터를
오염시키지 않는다.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from lotto.web.app import app


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """앱 클라이언트 — 모듈 단위 공유."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def isolate_sim_history_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """각 테스트마다 임시 sim_history.json 경로로 격리한다."""
    sim_history_file = tmp_path / "sim_history.json"
    monkeypatch.setattr("lotto.web.data._SIM_HISTORY_PATH", sim_history_file)


def _payload(label: str = "내 전략 A") -> dict:
    return {
        "label": label,
        "strategy": "random",
        "numbers": [1, 7, 14, 21, 35, 42],
        "iterations": 1000,
        "rank_counts": {
            "1등": 0, "2등": 1, "3등": 5, "4등": 50, "5등": 200, "낙첨": 744,
        },
        "total_spent": 1000000,
        "total_won": 250000,
        "roi": -0.75,
    }


# ─── POST /api/simulation-history ────────────────────────────────────────────


def test_post_valid_returns_200_with_entry(client: TestClient) -> None:
    """유효한 본문 저장 → 200 + id/created_at 포함 엔트리."""
    res = client.post("/api/simulation-history", json=_payload())
    assert res.status_code == 200, res.text
    body = res.json()
    assert isinstance(body["id"], str) and len(body["id"]) == 8
    assert body["label"] == "내 전략 A"
    assert body["iterations"] == 1000
    assert "created_at" in body and "T" in body["created_at"]


def test_post_empty_label_returns_422(client: TestClient) -> None:
    """빈 라벨은 검증 실패로 422를 반환한다."""
    payload = _payload(label="")
    res = client.post("/api/simulation-history", json=payload)
    assert res.status_code == 422, res.text


# ─── GET /api/simulation-history ─────────────────────────────────────────────


def test_get_list_returns_200_array(client: TestClient) -> None:
    """저장 후 목록 조회 → 200 + 최신순 배열."""
    client.post("/api/simulation-history", json=_payload("첫번째"))
    client.post("/api/simulation-history", json=_payload("두번째"))
    res = client.get("/api/simulation-history")
    assert res.status_code == 200, res.text
    body = res.json()
    assert isinstance(body, list)
    assert len(body) == 2  # noqa: PLR2004
    assert body[0]["label"] == "두번째"  # 최신 우선


# ─── DELETE /api/simulation-history/{id} ─────────────────────────────────────


def test_delete_existing_returns_200(client: TestClient) -> None:
    """존재하는 결과 삭제 → 200 {deleted: true}."""
    saved = client.post("/api/simulation-history", json=_payload()).json()
    res = client.delete(f"/api/simulation-history/{saved['id']}")
    assert res.status_code == 200, res.text
    assert res.json()["deleted"] is True


def test_delete_missing_returns_404(client: TestClient) -> None:
    """존재하지 않는 결과 삭제 → 404."""
    res = client.delete("/api/simulation-history/nonexist")
    assert res.status_code == 404, res.text
