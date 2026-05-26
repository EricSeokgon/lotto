"""SPEC-LOTTO-014: 구매 이력 페이지 라우트 테스트."""

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


class TestPurchasesPage:
    def test_200_ok(self, client):
        res = client.get("/purchases")
        assert res.status_code == 200

    def test_html_content_type(self, client):
        res = client.get("/purchases")
        assert "text/html" in res.headers["content-type"]

    def test_active_tab_purchases(self, client):
        res = client.get("/purchases")
        assert "구매 이력" in res.text

    def test_empty_state_message(self, client):
        res = client.get("/purchases")
        assert "등록된 구매 이력이 없습니다" in res.text

    def test_purchase_appears_in_page(self, client):
        client.post("/api/purchases", json={"drwNo": 100, "numbers": [1, 2, 3, 4, 5, 6]})
        res = client.get("/purchases")
        assert "100회" in res.text

    def test_nav_item_in_desktop(self, client):
        res = client.get("/purchases")
        assert 'href="/purchases"' in res.text

    def test_nav_item_in_mobile(self, client):
        res = client.get("/purchases")
        assert "구매 이력" in res.text
