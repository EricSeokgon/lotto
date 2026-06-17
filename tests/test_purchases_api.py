"""SPEC-LOTTO-014: 구매 이력 API 통합 테스트."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from lotto.web.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def isolate_purchases_path(tmp_path, monkeypatch):
    """각 테스트마다 임시 purchases.json 경로로 격리."""
    purchases_file = tmp_path / "purchases.json"
    monkeypatch.setattr("lotto.purchase._PURCHASES_PATH", purchases_file)


# ─── POST /api/purchases ──────────────────────────────────────────────────────

class TestCreatePurchase:
    def test_201_created(self, client):
        res = client.post(
            "/api/purchases",
            json={"drwNo": 100, "numbers": [1, 2, 3, 4, 5, 6]},
        )
        assert res.status_code == 201
        body = res.json()
        assert body["id"] == 1
        assert body["drwNo"] == 100
        assert body["numbers"] == [1, 2, 3, 4, 5, 6]
        assert "purchased_at" in body

    def test_422_wrong_count(self, client):
        res = client.post("/api/purchases", json={"drwNo": 1, "numbers": [1, 2, 3, 4, 5]})
        assert res.status_code == 422

    def test_422_out_of_range(self, client):
        res = client.post(
            "/api/purchases",
            json={"drwNo": 1, "numbers": [0, 1, 2, 3, 4, 5]},
        )
        assert res.status_code == 422

    def test_422_duplicate(self, client):
        res = client.post(
            "/api/purchases",
            json={"drwNo": 1, "numbers": [1, 1, 2, 3, 4, 5]},
        )
        assert res.status_code == 422

    def test_422_invalid_drw_no(self, client):
        res = client.post(
            "/api/purchases",
            json={"drwNo": 0, "numbers": [1, 2, 3, 4, 5, 6]},
        )
        assert res.status_code == 422


# ─── GET /api/purchases ───────────────────────────────────────────────────────

class TestListPurchases:
    def test_200_empty_list(self, client):
        res = client.get("/api/purchases")
        assert res.status_code == 200
        assert res.json() == []

    def test_200_with_records(self, client):
        client.post("/api/purchases", json={"drwNo": 100, "numbers": [1, 2, 3, 4, 5, 6]})
        res = client.get("/api/purchases")
        assert res.status_code == 200
        body = res.json()
        assert len(body) == 1
        assert body[0]["prize_rank"] in (
            "pending", "none", "1st", "2nd", "3rd", "4th", "5th",
        )
        assert "matched_count" in body[0]
        assert "matched_bonus" in body[0]

    def test_sorted_by_id_desc(self, client):
        client.post("/api/purchases", json={"drwNo": 1, "numbers": [1, 2, 3, 4, 5, 6]})
        client.post("/api/purchases", json={"drwNo": 2, "numbers": [7, 8, 9, 10, 11, 12]})
        res = client.get("/api/purchases")
        body = res.json()
        ids = [p["id"] for p in body]
        assert ids == sorted(ids, reverse=True)


# ─── DELETE /api/purchases/{id} ───────────────────────────────────────────────

class TestDeletePurchase:
    def test_204_no_content(self, client):
        create_res = client.post(
            "/api/purchases",
            json={"drwNo": 100, "numbers": [1, 2, 3, 4, 5, 6]},
        )
        purchase_id = create_res.json()["id"]
        res = client.delete(f"/api/purchases/{purchase_id}")
        assert res.status_code == 204
        assert res.content == b""

    def test_404_not_found(self, client):
        res = client.delete("/api/purchases/99999")
        assert res.status_code == 404
        body = res.json()
        assert "detail" in body

    def test_deleted_not_in_list(self, client):
        create_res = client.post(
            "/api/purchases",
            json={"drwNo": 100, "numbers": [1, 2, 3, 4, 5, 6]},
        )
        purchase_id = create_res.json()["id"]
        client.delete(f"/api/purchases/{purchase_id}")
        list_res = client.get("/api/purchases")
        ids = [p["id"] for p in list_res.json()]
        assert purchase_id not in ids
