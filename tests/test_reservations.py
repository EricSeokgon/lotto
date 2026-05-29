"""SPEC-LOTTO-035: 번호 예약 API 통합 테스트.

REQ: POST/GET/DELETE /api/reservations, DELETE /api/reservations (전체),
     /recommend 페이지 예약 섹션.
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
def isolate_reservations_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """각 테스트마다 임시 reservations.json 경로로 격리한다."""
    reservations_file = tmp_path / "reservations.json"
    monkeypatch.setattr("lotto.web.data._RESERVATIONS_PATH", reservations_file)


# ─── POST /api/reservations ──────────────────────────────────────────────────


class TestCreateReservation:
    def test_201_created_with_fields(self, client: TestClient) -> None:
        res = client.post(
            "/api/reservations",
            json={"numbers": [5, 12, 23, 34, 41, 43], "note": "이번 주 메인"},
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert isinstance(body["id"], str) and len(body["id"]) == 8
        assert body["numbers"] == [5, 12, 23, 34, 41, 43]
        assert body["note"] == "이번 주 메인"
        assert "created_at" in body and "T" in body["created_at"]

    def test_201_numbers_sorted(self, client: TestClient) -> None:
        res = client.post(
            "/api/reservations",
            json={"numbers": [43, 5, 41, 12, 34, 23]},
        )
        assert res.status_code == 201, res.text
        assert res.json()["numbers"] == [5, 12, 23, 34, 41, 43]

    def test_201_note_defaults_to_empty_string(self, client: TestClient) -> None:
        res = client.post(
            "/api/reservations",
            json={"numbers": [1, 2, 3, 4, 5, 6]},
        )
        assert res.status_code == 201, res.text
        assert res.json()["note"] == ""

    def test_422_not_six_numbers(self, client: TestClient) -> None:
        res = client.post(
            "/api/reservations",
            json={"numbers": [1, 2, 3, 4, 5]},
        )
        assert res.status_code == 422, res.text

    def test_422_duplicate_numbers(self, client: TestClient) -> None:
        res = client.post(
            "/api/reservations",
            json={"numbers": [1, 1, 2, 3, 4, 5]},
        )
        assert res.status_code == 422, res.text

    def test_422_out_of_range(self, client: TestClient) -> None:
        res = client.post(
            "/api/reservations",
            json={"numbers": [1, 2, 3, 4, 5, 46]},
        )
        assert res.status_code == 422, res.text

    def test_400_when_exceeding_max_10(self, client: TestClient) -> None:
        """예약은 최대 10개까지만 허용된다 (11번째 → 400)."""
        for i in range(10):
            # 서로 다른 10개 조합 (각 번호 1~45, 중복 없음 보장)
            base = [1 + i, 11 + i, 21 + i, 31 + i, 41 + (i % 5), 40 - (i % 4)]
            assert len(set(base)) == 6, base
            res = client.post("/api/reservations", json={"numbers": base})
            assert res.status_code == 201, res.text
        # 11번째
        res = client.post(
            "/api/reservations",
            json={"numbers": [2, 8, 14, 23, 36, 45]},
        )
        assert res.status_code == 400, res.text
        assert res.json()["detail"] == "최대 10개까지 예약 가능합니다"


# ─── GET /api/reservations ───────────────────────────────────────────────────


class TestListReservations:
    def test_empty_list_initially(self, client: TestClient) -> None:
        res = client.get("/api/reservations")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_list_reverse_creation_order(self, client: TestClient) -> None:
        """목록은 생성 역순(최신 먼저)으로 반환된다."""
        client.post("/api/reservations", json={"numbers": [1, 2, 3, 4, 5, 6], "note": "A"})
        client.post("/api/reservations", json={"numbers": [7, 8, 9, 10, 11, 12], "note": "B"})
        client.post("/api/reservations", json={"numbers": [13, 14, 15, 16, 17, 18], "note": "C"})

        res = client.get("/api/reservations")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["total"] == 3
        notes = [item["note"] for item in body["items"]]
        assert notes == ["C", "B", "A"]


# ─── DELETE /api/reservations/{id} ──────────────────────────────────────────


class TestDeleteReservation:
    def test_delete_single_ok(self, client: TestClient) -> None:
        created = client.post(
            "/api/reservations",
            json={"numbers": [1, 2, 3, 4, 5, 6]},
        ).json()
        res = client.delete(f"/api/reservations/{created['id']}")
        assert res.status_code == 200, res.text

        # 삭제 확인
        listing = client.get("/api/reservations").json()
        assert listing["total"] == 0

    def test_delete_missing_404(self, client: TestClient) -> None:
        res = client.delete("/api/reservations/nonexist")
        assert res.status_code == 404, res.text


# ─── DELETE /api/reservations (전체) ─────────────────────────────────────────


class TestDeleteAllReservations:
    def test_delete_all_returns_count(self, client: TestClient) -> None:
        client.post("/api/reservations", json={"numbers": [1, 2, 3, 4, 5, 6]})
        client.post("/api/reservations", json={"numbers": [7, 8, 9, 10, 11, 12]})

        res = client.delete("/api/reservations")
        assert res.status_code == 200, res.text
        assert res.json()["deleted"] == 2

        # 전체 비워짐
        assert client.get("/api/reservations").json()["total"] == 0

    def test_delete_all_empty_returns_zero(self, client: TestClient) -> None:
        res = client.delete("/api/reservations")
        assert res.status_code == 200, res.text
        assert res.json()["deleted"] == 0


# ─── data 레이어 직접 검증 ───────────────────────────────────────────────────


class TestReservationDataLayer:
    def test_get_reservations_empty_when_no_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from lotto.web import data as wd

        monkeypatch.setattr(wd, "_RESERVATIONS_PATH", tmp_path / "none.json")
        assert wd.get_reservations() == []

    def test_save_and_get_roundtrip(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        from lotto.web import data as wd

        path = tmp_path / "reservations.json"
        monkeypatch.setattr(wd, "_RESERVATIONS_PATH", path)
        items = [{"id": "abc12345", "numbers": [1, 2, 3, 4, 5, 6], "note": "x"}]
        wd.save_reservations(items)
        assert wd.get_reservations() == items


# ─── /recommend 페이지 예약 섹션 ─────────────────────────────────────────────


def test_recommend_page_has_reservation_section(client: TestClient) -> None:
    """/recommend 페이지에 번호 예약 섹션 마커가 존재한다."""
    res = client.get("/recommend")
    assert res.status_code == 200
    html = res.text
    assert "reservation" in html.lower()
    assert "번호 예약" in html
