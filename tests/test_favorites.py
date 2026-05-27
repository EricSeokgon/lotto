"""SPEC-LOTTO-016: 번호 즐겨찾기 API 통합 테스트.

REQ-FAV-001~003 + REQ-FAV-004(웹 UI 섹션 존재) 검증.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from lotto.web.app import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """앱 클라이언트 — 모듈 단위로 재사용."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def isolate_favorites_path(tmp_path, monkeypatch):
    """각 테스트마다 임시 favorites.json 경로로 격리한다.

    `lotto.web.data._FAVORITES_PATH`를 임시 디렉터리의 빈 경로로 교체하여
    실제 운영 데이터(`data/favorites.json`)에 영향이 가지 않도록 한다.
    """
    favorites_file = tmp_path / "favorites.json"
    monkeypatch.setattr("lotto.web.data._FAVORITES_PATH", favorites_file)


# ─── POST /api/favorites (REQ-FAV-001) ──────────────────────────────────────


class TestCreateFavorite:
    def test_201_created_with_id_and_numbers_sorted(self, client: TestClient) -> None:
        res = client.post(
            "/api/favorites",
            json={"numbers": [10, 5, 23, 7, 33, 1], "name": "내 행운번호"},
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert "id" in body and isinstance(body["id"], str) and len(body["id"]) >= 8
        assert body["name"] == "내 행운번호"
        # 정렬 보장
        assert body["numbers"] == sorted(body["numbers"])
        # 입력 번호 집합과 동일
        assert set(body["numbers"]) == {1, 5, 7, 10, 23, 33}

    def test_201_auto_name_when_missing(self, client: TestClient) -> None:
        """이름을 생략하면 '번호조합 N' 형식으로 자동 부여된다."""
        res = client.post(
            "/api/favorites",
            json={"numbers": [1, 2, 3, 4, 5, 6]},
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["name"].startswith("번호조합 ")
        # 첫 항목이므로 "번호조합 1"
        assert body["name"] == "번호조합 1"

    def test_409_duplicate_numbers_order_independent(self, client: TestClient) -> None:
        """동일한 번호 집합이 이미 존재하면 409를 반환한다 (순서 무관)."""
        client.post(
            "/api/favorites",
            json={"numbers": [11, 22, 33, 44, 4, 5], "name": "A"},
        )
        res = client.post(
            "/api/favorites",
            # 같은 집합이지만 순서가 다름
            json={"numbers": [5, 4, 44, 33, 22, 11], "name": "B"},
        )
        assert res.status_code == 409, res.text
        body = res.json()
        assert "detail" in body

    def test_422_wrong_count_less(self, client: TestClient) -> None:
        res = client.post(
            "/api/favorites",
            json={"numbers": [1, 2, 3, 4, 5], "name": "N"},
        )
        assert res.status_code == 422

    def test_422_wrong_count_more(self, client: TestClient) -> None:
        res = client.post(
            "/api/favorites",
            json={"numbers": [1, 2, 3, 4, 5, 6, 7], "name": "N"},
        )
        assert res.status_code == 422

    def test_422_out_of_range_low(self, client: TestClient) -> None:
        res = client.post(
            "/api/favorites",
            json={"numbers": [0, 2, 3, 4, 5, 6], "name": "N"},
        )
        assert res.status_code == 422

    def test_422_out_of_range_high(self, client: TestClient) -> None:
        res = client.post(
            "/api/favorites",
            json={"numbers": [1, 2, 3, 4, 5, 46], "name": "N"},
        )
        assert res.status_code == 422

    def test_422_duplicate_numbers(self, client: TestClient) -> None:
        res = client.post(
            "/api/favorites",
            json={"numbers": [1, 1, 2, 3, 4, 5], "name": "N"},
        )
        assert res.status_code == 422

    def test_422_name_too_long(self, client: TestClient) -> None:
        """이름이 20자를 초과하면 422를 반환한다."""
        long_name = "가" * 21
        res = client.post(
            "/api/favorites",
            json={"numbers": [1, 2, 3, 4, 5, 6], "name": long_name},
        )
        assert res.status_code == 422

    def test_201_name_at_max_length(self, client: TestClient) -> None:
        """이름이 정확히 20자이면 허용된다 (경계값)."""
        max_name = "가" * 20
        res = client.post(
            "/api/favorites",
            json={"numbers": [7, 14, 21, 28, 35, 42], "name": max_name},
        )
        assert res.status_code == 201, res.text


# ─── GET /api/favorites (REQ-FAV-002) ───────────────────────────────────────


class TestListFavorites:
    def test_200_empty_list_initial(self, client: TestClient) -> None:
        res = client.get("/api/favorites")
        assert res.status_code == 200
        assert res.json() == []

    def test_200_returns_in_save_order(self, client: TestClient) -> None:
        """저장 순서대로 반환되어야 한다."""
        a = client.post(
            "/api/favorites",
            json={"numbers": [1, 2, 3, 4, 5, 6], "name": "첫째"},
        ).json()
        b = client.post(
            "/api/favorites",
            json={"numbers": [7, 8, 9, 10, 11, 12], "name": "둘째"},
        ).json()
        c = client.post(
            "/api/favorites",
            json={"numbers": [13, 14, 15, 16, 17, 18], "name": "셋째"},
        ).json()

        res = client.get("/api/favorites")
        assert res.status_code == 200
        body = res.json()
        assert len(body) == 3
        assert [item["id"] for item in body] == [a["id"], b["id"], c["id"]]
        assert [item["name"] for item in body] == ["첫째", "둘째", "셋째"]


# ─── DELETE /api/favorites/{fav_id} (REQ-FAV-003) ────────────────────────────


class TestDeleteFavorite:
    def test_200_deleted_and_not_in_list(self, client: TestClient) -> None:
        created = client.post(
            "/api/favorites",
            json={"numbers": [2, 4, 6, 8, 10, 12], "name": "삭제대상"},
        ).json()
        fav_id = created["id"]

        res = client.delete(f"/api/favorites/{fav_id}")
        assert res.status_code == 200, res.text

        list_res = client.get("/api/favorites")
        ids = [item["id"] for item in list_res.json()]
        assert fav_id not in ids

    def test_404_unknown_id(self, client: TestClient) -> None:
        res = client.delete("/api/favorites/00000000-0000-0000-0000-000000000000")
        assert res.status_code == 404
        body = res.json()
        assert "detail" in body


# ─── 자동 네이밍 카운터 (REQ-FAV-001 인수 기준) ─────────────────────────────


class TestAutoNamingCounter:
    def test_auto_name_uses_sequential_counter(self, client: TestClient) -> None:
        """이름 없이 추가하면 '번호조합 1', '번호조합 2' 순으로 부여된다."""
        a = client.post(
            "/api/favorites",
            json={"numbers": [1, 2, 3, 4, 5, 6]},
        ).json()
        b = client.post(
            "/api/favorites",
            json={"numbers": [7, 8, 9, 10, 11, 12]},
        ).json()
        assert a["name"] == "번호조합 1"
        assert b["name"] == "번호조합 2"

    def test_auto_name_skips_existing_user_names(self, client: TestClient) -> None:
        """사용자 지정 이름이 섞여 있어도 '번호조합 N'은 단조 증가한다."""
        client.post(
            "/api/favorites",
            json={"numbers": [1, 2, 3, 4, 5, 6], "name": "사용자이름"},
        )
        auto1 = client.post(
            "/api/favorites",
            json={"numbers": [7, 8, 9, 10, 11, 12]},
        ).json()
        client.post(
            "/api/favorites",
            json={"numbers": [13, 14, 15, 16, 17, 18], "name": "또다른"},
        )
        auto2 = client.post(
            "/api/favorites",
            json={"numbers": [19, 20, 21, 22, 23, 24]},
        ).json()
        # 사용자 이름은 제외하고 자동 이름만 카운팅 → 1, 2
        assert auto1["name"] == "번호조합 1"
        assert auto2["name"] == "번호조합 2"


# ─── REQ-FAV-004: 추천 페이지 즐겨찾기 섹션 존재 확인 ────────────────────────


class TestRecommendPageFavoritesSection:
    def test_recommend_page_contains_favorites_section(self, client: TestClient) -> None:
        """/recommend 페이지에 즐겨찾기 섹션 마커가 포함된다."""
        res = client.get("/recommend")
        assert res.status_code == 200
        html = res.text
        # 섹션 식별자: 한국어 헤더 + JS 호출 대상 id
        assert "즐겨찾기" in html
        assert "favorites-section" in html or 'id="favorites-' in html
