"""SPEC-LOTTO-033: 번호 생성 히스토리 (Generation History) — API + 데이터 레이어 테스트.

GET /api/recommendations 호출 시 결과를 gen_history.json 에 자동 append 하고,
GET /api/gen-history 로 조회, DELETE /api/gen-history 로 전체 삭제한다.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from starlette.testclient import TestClient

from lotto.models import Recommendation
from lotto.web.app import app


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """앱 클라이언트 — 모듈 단위 공유."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def isolate_gen_history(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    """gen_history.json 경로를 임시 디렉터리로 격리한다."""
    from pathlib import Path

    from lotto.web import data as wd

    tmp_file = Path(str(tmp_path)) / "gen_history.json"
    monkeypatch.setattr(wd, "_GEN_HISTORY_PATH", tmp_file)


@pytest.fixture
def sample_recs() -> list[Recommendation]:
    """추천 결과 샘플 2건."""
    return [
        Recommendation(
            numbers=[1, 7, 13, 22, 35, 44],
            strategy_label="균형",
            strategy_desc="",
            scores={},
        ),
        Recommendation(
            numbers=[3, 9, 18, 27, 36, 45],
            strategy_label="고빈도",
            strategy_desc="",
            scores={},
        ),
    ]


@pytest.fixture
def patch_recs(monkeypatch: pytest.MonkeyPatch, sample_recs: list[Recommendation]) -> None:
    """get_recommendations()가 샘플을 반환하도록 패치.

    /api/recommendations 는 api 모듈로 import 한 get_recommendations 심볼을 사용하므로
    해당 심볼을 패치한다 (기존 test_api_strategy_filter 와 동일 규약).
    """
    from lotto.web.routes import api as api_mod

    monkeypatch.setattr(api_mod, "get_recommendations", lambda count=5: list(sample_recs))


# ─── 데이터 레이어: gen_history CRUD ───────────────────────────────────────


class TestGenHistoryData:
    """data 레이어 get/append/clear 검증."""

    def test_empty_when_no_file(self) -> None:
        from lotto.web.data import get_gen_history

        assert get_gen_history() == []

    def test_append_persists(self) -> None:
        from lotto.web.data import append_gen_history, get_gen_history

        append_gen_history(strategy="균형", numbers=[1, 2, 3, 4, 5, 6])
        items = get_gen_history()
        assert len(items) == 1
        assert items[0]["numbers"] == [1, 2, 3, 4, 5, 6]
        assert items[0]["strategy"] == "균형"

    def test_appended_entry_has_id_and_timestamp(self) -> None:
        from lotto.web.data import append_gen_history, get_gen_history

        append_gen_history(strategy="고빈도", numbers=[1, 2, 3, 4, 5, 6])
        entry = get_gen_history()[0]
        assert "id" in entry and len(entry["id"]) == 8
        assert "generated_at" in entry and entry["generated_at"]
        assert entry["source"] == "api"

    def test_keeps_only_latest_200(self) -> None:
        from lotto.web.data import append_gen_history, get_gen_history

        for i in range(210):
            append_gen_history(strategy="균형", numbers=[1, 2, 3, 4, 5, (i % 40) + 6])
        items = get_gen_history()
        assert len(items) == 200

    def test_clear_returns_count_and_empties(self) -> None:
        from lotto.web.data import append_gen_history, clear_gen_history, get_gen_history

        append_gen_history(strategy="균형", numbers=[1, 2, 3, 4, 5, 6])
        append_gen_history(strategy="고빈도", numbers=[7, 8, 9, 10, 11, 12])
        deleted = clear_gen_history()
        assert deleted == 2
        assert get_gen_history() == []

    def test_append_failure_is_silent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from pathlib import Path

        from lotto.web import data as wd

        # 쓰기 불가능한 경로로 강제 — 예외가 전파되지 않아야 한다
        monkeypatch.setattr(wd, "_GEN_HISTORY_PATH", Path("/nonexistent_dir/x/gen.json"))
        # 예외 없이 반환되어야 함
        wd.append_gen_history(strategy="균형", numbers=[1, 2, 3, 4, 5, 6])


# ─── API: GET /api/recommendations 자동 저장 ───────────────────────────────


class TestRecommendationsAutoSave:
    """추천 API 호출 시 자동 이력 저장."""

    def test_recommendations_appends_history(
        self, client: TestClient, patch_recs: None
    ) -> None:
        from lotto.web.data import get_gen_history

        before = len(get_gen_history())
        res = client.get("/api/recommendations?count=2")
        assert res.status_code == 200
        after = len(get_gen_history())
        assert after == before + 2

    def test_recommendations_still_returns_data(
        self, client: TestClient, patch_recs: None
    ) -> None:
        res = client.get("/api/recommendations?count=2")
        assert res.status_code == 200
        body = res.json()
        assert len(body) == 2

    def test_save_failure_does_not_break_response(
        self, client: TestClient, patch_recs: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from lotto.web import data as wd

        def _boom(*args: object, **kwargs: object) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(wd, "append_gen_history", _boom)
        res = client.get("/api/recommendations?count=2")
        assert res.status_code == 200


# ─── API: GET /api/gen-history ─────────────────────────────────────────────


class TestGenHistoryGet:
    """생성 이력 조회 엔드포인트."""

    def test_empty_history(self, client: TestClient) -> None:
        res = client.get("/api/gen-history")
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_returns_total_and_items(self, client: TestClient) -> None:
        from lotto.web.data import append_gen_history

        append_gen_history(strategy="균형", numbers=[1, 2, 3, 4, 5, 6])
        append_gen_history(strategy="고빈도", numbers=[7, 8, 9, 10, 11, 12])
        res = client.get("/api/gen-history")
        body = res.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    def test_returns_latest_first(self, client: TestClient) -> None:
        from lotto.web.data import append_gen_history

        append_gen_history(strategy="first", numbers=[1, 2, 3, 4, 5, 6])
        append_gen_history(strategy="second", numbers=[7, 8, 9, 10, 11, 12])
        res = client.get("/api/gen-history")
        items = res.json()["items"]
        # 최신순 — 마지막에 추가한 second 가 먼저
        assert items[0]["strategy"] == "second"

    def test_caps_at_50_items(self, client: TestClient) -> None:
        from lotto.web.data import append_gen_history

        for i in range(60):
            append_gen_history(strategy="균형", numbers=[1, 2, 3, 4, 5, (i % 40) + 6])
        res = client.get("/api/gen-history")
        body = res.json()
        assert body["total"] == 60
        assert len(body["items"]) == 50


# ─── API: DELETE /api/gen-history ──────────────────────────────────────────


class TestGenHistoryDelete:
    """생성 이력 전체 삭제 엔드포인트."""

    def test_delete_returns_count(self, client: TestClient) -> None:
        from lotto.web.data import append_gen_history

        append_gen_history(strategy="균형", numbers=[1, 2, 3, 4, 5, 6])
        append_gen_history(strategy="고빈도", numbers=[7, 8, 9, 10, 11, 12])
        res = client.delete("/api/gen-history")
        assert res.status_code == 200
        assert res.json()["deleted"] == 2

    def test_delete_empties_history(self, client: TestClient) -> None:
        from lotto.web.data import append_gen_history, get_gen_history

        append_gen_history(strategy="균형", numbers=[1, 2, 3, 4, 5, 6])
        client.delete("/api/gen-history")
        assert get_gen_history() == []

    def test_delete_when_empty_returns_zero(self, client: TestClient) -> None:
        res = client.delete("/api/gen-history")
        assert res.status_code == 200
        assert res.json()["deleted"] == 0
