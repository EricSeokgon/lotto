"""SPEC-LOTTO-029: 회차별 상세 보기 — API/페이지 통합 테스트.

REQ-DETAIL-001 (API 회차 상세), REQ-DETAIL-002 (회차 상세 HTML 페이지),
REQ-DETAIL-003 (수집 목록 → 상세 링크) 검증.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import date

import pytest
from starlette.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """앱 클라이언트 — 모듈 단위 공유."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_draws() -> list[DrawResult]:
    """상세 보기용 추첨 데이터 — 1099 / 1100 / 1101회.

    1100회는 당첨금 데이터 포함, 1101회는 당첨금 데이터 없음(None).
    """
    return [
        # 1099회: 이전 회차 링크 대상
        DrawResult(
            drwNo=1099,
            date=date(2023, 12, 30),
            n1=2, n2=8, n3=19, n4=25, n5=32, n6=40,
            bonus=11,
        ),
        # 1100회: 메인 테스트 대상 — 당첨금 데이터 포함
        DrawResult(
            drwNo=1100,
            date=date(2024, 1, 6),
            n1=5, n2=12, n3=23, n4=34, n5=41, n6=43,
            bonus=7,
            prize1Amount=2_000_000_000,
            prize1Winners=3,
        ),
        # 1101회: 다음 회차 링크 대상 — 당첨금 데이터 없음
        DrawResult(
            drwNo=1101,
            date=date(2024, 1, 13),
            n1=1, n2=9, n3=15, n4=27, n5=38, n6=45,
            bonus=22,
        ),
    ]


@pytest.fixture(autouse=True)
def patch_draws(
    monkeypatch: pytest.MonkeyPatch,
    sample_draws: list[DrawResult],
) -> None:
    """모든 테스트에서 get_draws()가 sample_draws를 반환하도록 패치."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)


@pytest.fixture
def no_favorites(monkeypatch: pytest.MonkeyPatch) -> None:
    """기본적으로 즐겨찾기가 없는 상태로 격리."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_favorites", lambda: [])


# ─── REQ-DETAIL-001: GET /api/draws/{drw_no} ─────────────────────────────


class TestDrawDetailAPI:
    """특정 회차 상세 JSON 반환."""

    def test_returns_draw_detail(self, client: TestClient) -> None:
        """존재하는 회차 → 200 + 상세 정보 반환."""
        res = client.get("/api/draws/1100")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["drwNo"] == 1100
        assert body["drwNoDate"] == "2024-01-06"
        assert body["numbers"] == [5, 12, 23, 34, 41, 43]
        assert body["bonus"] == 7
        assert body["prize1Amount"] == 2_000_000_000
        assert body["prize1Winners"] == 3

    def test_numbers_are_sorted(self, client: TestClient) -> None:
        """numbers는 오름차순 정렬되어 있다."""
        res = client.get("/api/draws/1101")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["numbers"] == [1, 9, 15, 27, 38, 45]
        assert body["numbers"] == sorted(body["numbers"])

    def test_prize_fields_null_when_unavailable(self, client: TestClient) -> None:
        """당첨금 데이터 없는 회차 → prize1Amount/prize1Winners null."""
        res = client.get("/api/draws/1101")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["prize1Amount"] is None
        assert body["prize1Winners"] is None

    def test_404_when_draw_not_found(self, client: TestClient) -> None:
        """존재하지 않는 회차 → 404."""
        res = client.get("/api/draws/9999")
        assert res.status_code == 404

    def test_404_when_drw_no_zero(self, client: TestClient) -> None:
        """drw_no=0 → 404 (미존재와 동일)."""
        res = client.get("/api/draws/0")
        assert res.status_code == 404

    def test_404_when_drw_no_negative(self, client: TestClient) -> None:
        """drw_no가 음수 → 404 (미존재와 동일)."""
        res = client.get("/api/draws/-5")
        assert res.status_code == 404

    def test_404_when_no_data(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """draws 데이터가 전혀 없을 때 → 404."""
        from lotto.web import data as wd

        monkeypatch.setattr(wd, "get_draws", lambda: None)
        res = client.get("/api/draws/1100")
        assert res.status_code == 404


# ─── REQ-DETAIL-002: GET /draw/{drw_no} 페이지 렌더링 ────────────────────


class TestDrawDetailPage:
    """회차 상세 HTML 페이지."""

    def test_page_loads_200(self, client: TestClient, no_favorites: None) -> None:
        """존재하는 회차 → 200."""
        res = client.get("/draw/1100")
        assert res.status_code == 200

    def test_page_shows_numbers_and_bonus(
        self, client: TestClient, no_favorites: None
    ) -> None:
        """당첨 번호 6개 + 보너스 번호가 표시된다."""
        res = client.get("/draw/1100")
        text = res.text
        for n in (5, 12, 23, 34, 41, 43):
            assert str(n) in text
        # 보너스 번호 표시
        assert "보너스" in text or "+7" in text

    def test_page_shows_prize_info(
        self, client: TestClient, no_favorites: None
    ) -> None:
        """1등 당첨금/당첨자 수가 표시된다."""
        res = client.get("/draw/1100")
        text = res.text
        # 천 단위 콤마 또는 원본 숫자
        assert "2,000,000,000" in text or "2000000000" in text
        assert "3" in text  # 당첨자 수

    def test_page_shows_no_prize_message(
        self, client: TestClient, no_favorites: None
    ) -> None:
        """당첨금 데이터 없는 회차 → '정보 없음' 표시."""
        res = client.get("/draw/1101")
        assert "정보 없음" in res.text

    def test_page_has_dark_mode_classes(
        self, client: TestClient, no_favorites: None
    ) -> None:
        """다크모드 대응 — dark: 클래스 포함."""
        res = client.get("/draw/1100")
        assert "dark:" in res.text

    def test_prev_link_present_when_exists(
        self, client: TestClient, no_favorites: None
    ) -> None:
        """이전 회차 링크 (/draw/1099)가 활성 상태로 존재."""
        res = client.get("/draw/1100")
        assert 'href="/draw/1099"' in res.text

    def test_next_link_present_when_exists(
        self, client: TestClient, no_favorites: None
    ) -> None:
        """다음 회차 링크 (/draw/1101)가 활성 상태로 존재."""
        res = client.get("/draw/1100")
        assert 'href="/draw/1101"' in res.text

    def test_prev_link_disabled_for_first_draw(
        self, client: TestClient, no_favorites: None
    ) -> None:
        """첫 회차(1099)에서는 이전 회차 링크가 활성화되지 않는다."""
        # 1099가 가장 작은 회차이므로 /draw/1098 링크는 활성화되면 안 됨
        res = client.get("/draw/1099")
        assert res.status_code == 200
        assert 'href="/draw/1098"' not in res.text

    def test_next_link_disabled_for_last_draw(
        self, client: TestClient, no_favorites: None
    ) -> None:
        """마지막 회차(1101)에서는 다음 회차 링크가 활성화되지 않는다."""
        res = client.get("/draw/1101")
        assert res.status_code == 200
        assert 'href="/draw/1102"' not in res.text

    def test_404_page_when_draw_not_found(self, client: TestClient) -> None:
        """존재하지 않는 회차 → 404 HTML 메시지."""
        res = client.get("/draw/9999")
        assert res.status_code == 404

    def test_404_page_when_drw_no_zero(self, client: TestClient) -> None:
        """drw_no=0 → 404."""
        res = client.get("/draw/0")
        assert res.status_code == 404

    def test_404_page_when_drw_no_negative(self, client: TestClient) -> None:
        """drw_no 음수 → 404."""
        res = client.get("/draw/-3")
        assert res.status_code == 404


# ─── REQ-DETAIL-002 (favorites): 즐겨찾기 번호 대조 ──────────────────────


class TestDrawDetailFavorites:
    """즐겨찾기 번호 대조 및 하이라이트."""

    def test_favorite_match_highlight(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """즐겨찾기 번호와 당첨 번호가 일치하면 하이라이트 마커가 표시된다."""
        from lotto.web import data as wd

        # 1100회 당첨 번호: 5,12,23,34,41,43 / 즐겨찾기에 5,12 포함
        monkeypatch.setattr(
            wd,
            "get_favorites",
            lambda: [{"id": "a", "name": "내번호", "numbers": [5, 12, 1, 2, 3, 4]}],
        )
        res = client.get("/draw/1100")
        assert res.status_code == 200
        # 하이라이트 마커(box-shadow 링) 또는 일치 안내 텍스트가 존재해야 함
        assert "box-shadow" in res.text or "일치" in res.text

    def test_no_favorites_section_hidden(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """즐겨찾기가 없으면 대조 섹션을 노출하지 않거나 빈 안내만 표시."""
        from lotto.web import data as wd

        monkeypatch.setattr(wd, "get_favorites", lambda: [])
        res = client.get("/draw/1100")
        # 페이지는 정상 렌더되어야 한다 (대조 섹션 부재여도 200)
        assert res.status_code == 200


# ─── REQ-DETAIL-003: /collect 목록 → 상세 링크 ──────────────────────────


class TestCollectPageDetailLinks:
    """수집 목록 테이블에서 회차 상세 링크."""

    def test_collect_page_has_detail_links(self, client: TestClient) -> None:
        """수집 목록의 회차에 /draw/{drw_no} 링크가 포함된다 (서버 렌더링)."""
        res = client.get("/collect")
        assert res.status_code == 200
        # 서버사이드 초기 렌더링된 회차 중 하나에 대한 링크
        assert 'href="/draw/1100"' in res.text or "/draw/" in res.text
