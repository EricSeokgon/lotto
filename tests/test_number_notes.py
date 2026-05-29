"""SPEC-LOTTO-036: 번호 메모 기능 API 통합 테스트.

특정 번호(1~45)에 개인 메모를 달아 관리하는 기능을 검증한다.
- POST   /api/numbers/{number}/note  : 메모 저장 (빈 문자열이면 삭제)
- GET    /api/numbers/{number}/note  : 단일 번호 메모 조회
- GET    /api/numbers/notes          : 메모 있는 번호 전체 조회
- /numbers/{number} 페이지의 메모 인라인 편집 섹션 존재
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from lotto.web.app import app


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """앱 클라이언트 — 모듈 단위로 재사용."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def isolate_notes_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """각 테스트마다 임시 number_notes.json 경로로 격리한다.

    실제 운영 데이터(`data/number_notes.json`)에 영향이 가지 않도록 한다.
    """
    notes_file = tmp_path / "number_notes.json"
    monkeypatch.setattr("lotto.web.data._NUMBER_NOTES_PATH", notes_file)


# ─── POST /api/numbers/{number}/note (저장) ─────────────────────────────────


class TestSaveNote:
    def test_save_returns_number_note_and_updated_at(self, client: TestClient) -> None:
        res = client.post("/api/numbers/7/note", json={"note": "최근 핫한 번호"})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["number"] == 7
        assert body["note"] == "최근 핫한 번호"
        # updated_at은 ISO-8601 문자열 (None 아님)
        assert isinstance(body["updated_at"], str)
        assert "T" in body["updated_at"]

    def test_save_persists_and_can_be_read(self, client: TestClient) -> None:
        client.post("/api/numbers/13/note", json={"note": "행운의 번호"})
        res = client.get("/api/numbers/13/note")
        assert res.status_code == 200
        body = res.json()
        assert body["number"] == 13
        assert body["note"] == "행운의 번호"
        assert body["updated_at"] is not None

    def test_save_overwrites_existing_note(self, client: TestClient) -> None:
        client.post("/api/numbers/21/note", json={"note": "이전 메모"})
        res = client.post("/api/numbers/21/note", json={"note": "새 메모"})
        assert res.status_code == 200
        assert res.json()["note"] == "새 메모"
        # 조회 시에도 갱신된 값
        got = client.get("/api/numbers/21/note").json()
        assert got["note"] == "새 메모"

    def test_save_number_boundaries_1_and_45(self, client: TestClient) -> None:
        for number in (1, 45):
            res = client.post(f"/api/numbers/{number}/note", json={"note": f"경계 {number}"})
            assert res.status_code == 200, res.text
            assert res.json()["number"] == number

    def test_save_number_out_of_range_returns_422(self, client: TestClient) -> None:
        for number in (0, 46, 100):
            res = client.post(f"/api/numbers/{number}/note", json={"note": "x"})
            assert res.status_code == 422, f"number={number}: {res.text}"


# ─── 빈 문자열 → 삭제 처리 ───────────────────────────────────────────────────


class TestEmptyNoteDeletes:
    def test_empty_note_removes_existing(self, client: TestClient) -> None:
        # 먼저 저장
        client.post("/api/numbers/30/note", json={"note": "지울 메모"})
        # 빈 문자열로 삭제
        res = client.post("/api/numbers/30/note", json={"note": ""})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["number"] == 30
        assert body["note"] == ""
        # 삭제되었으므로 조회 시 빈 메모 + updated_at None
        got = client.get("/api/numbers/30/note").json()
        assert got["note"] == ""
        assert got["updated_at"] is None

    def test_empty_note_on_absent_number_is_noop(self, client: TestClient) -> None:
        res = client.post("/api/numbers/40/note", json={"note": ""})
        assert res.status_code == 200
        body = res.json()
        assert body["number"] == 40
        assert body["note"] == ""

    def test_empty_note_not_listed(self, client: TestClient) -> None:
        client.post("/api/numbers/5/note", json={"note": "임시"})
        client.post("/api/numbers/5/note", json={"note": ""})
        listing = client.get("/api/numbers/notes").json()
        numbers = [item["number"] for item in listing["items"]]
        assert 5 not in numbers


# ─── GET /api/numbers/{number}/note (단일 조회) ─────────────────────────────


class TestGetNote:
    def test_get_absent_note_returns_empty(self, client: TestClient) -> None:
        res = client.get("/api/numbers/7/note")
        assert res.status_code == 200
        body = res.json()
        assert body["number"] == 7
        assert body["note"] == ""
        assert body["updated_at"] is None

    def test_get_number_out_of_range_returns_422(self, client: TestClient) -> None:
        res = client.get("/api/numbers/99/note")
        assert res.status_code == 422


# ─── GET /api/numbers/notes (전체 조회) ─────────────────────────────────────


class TestListNotes:
    def test_list_empty_when_no_notes(self, client: TestClient) -> None:
        res = client.get("/api/numbers/notes")
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_list_returns_all_notes_sorted_by_number(self, client: TestClient) -> None:
        client.post("/api/numbers/33/note", json={"note": "c"})
        client.post("/api/numbers/7/note", json={"note": "a"})
        client.post("/api/numbers/20/note", json={"note": "b"})
        res = client.get("/api/numbers/notes")
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 3
        numbers = [item["number"] for item in body["items"]]
        # 번호 오름차순 정렬
        assert numbers == [7, 20, 33]
        # 각 항목은 number/note/updated_at 키를 갖는다
        for item in body["items"]:
            assert set(item.keys()) >= {"number", "note", "updated_at"}
            assert item["updated_at"] is not None

    def test_list_item_note_content_matches(self, client: TestClient) -> None:
        client.post("/api/numbers/11/note", json={"note": "내용확인"})
        body = client.get("/api/numbers/notes").json()
        item = next(i for i in body["items"] if i["number"] == 11)
        assert item["note"] == "내용확인"


# ─── /numbers/{number} 페이지 메모 섹션 (REQ-NOTE-004) ───────────────────────


class TestNoteSectionOnPage:
    def test_number_detail_page_contains_note_section(self, client: TestClient) -> None:
        res = client.get("/numbers/7")
        assert res.status_code == 200
        text = res.text
        # 메모 편집 섹션을 식별할 수 있는 마커 + API 호출 경로 존재
        assert "메모" in text
        assert "/api/numbers/7/note" in text

    def test_number_detail_page_has_save_and_delete_controls(self, client: TestClient) -> None:
        res = client.get("/numbers/14")
        text = res.text
        # 저장/삭제 버튼 텍스트
        assert "저장" in text
        assert "삭제" in text
