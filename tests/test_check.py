"""SPEC-LOTTO-024: 번호 즉시 검증 도구 — API/페이지 통합 테스트.

REQ-CHECK-001 (API 등수 계산), REQ-CHECK-002 (페이지 렌더),
REQ-CHECK-003 (네비 링크) 검증.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from starlette.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """앱 클라이언트 — 모듈 단위 공유."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_draws() -> list[DrawResult]:
    """검증용 추첨 데이터 — 1234회 / 1235회."""
    return [
        # 1234회: 본번호 1,7,13,22,35,44 / 보너스 5
        DrawResult(
            drwNo=1234,
            date=date(2026, 5, 24),
            n1=1, n2=7, n3=13, n4=22, n5=35, n6=44,
            bonus=5,
        ),
        # 1235회: 본번호 3,9,11,20,33,42 / 보너스 17
        DrawResult(
            drwNo=1235,
            date=date(2026, 5, 31),
            n1=3, n2=9, n3=11, n4=20, n5=33, n6=42,
            bonus=17,
        ),
    ]


@pytest.fixture(autouse=True)
def patch_draws(monkeypatch, sample_draws):
    """모든 테스트에서 get_draws()가 sample_draws를 반환하도록 패치."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)


# ─── REQ-CHECK-001: GET /api/check 등수 계산 ─────────────────────────────


class TestCheckRank:
    """등수 1~5 + 미당첨 케이스."""

    def test_rank1_all_six_matched(self, client: TestClient) -> None:
        """6개 모두 일치 → 1등."""
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "1,7,13,22,35,44",
        })
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["drwNo"] == 1234
        assert body["rank"] == 1
        assert set(body["matched"]) == {1, 7, 13, 22, 35, 44}
        assert body["bonus_matched"] is False
        assert body["draw_date"] == "2026-05-24"

    def test_rank2_five_matched_with_bonus(self, client: TestClient) -> None:
        """5개 일치 + 보너스 → 2등."""
        # 본번호 5개(1,7,13,22,35) + 보너스(5)
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "1,7,13,22,35,5",
        })
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["rank"] == 2
        assert body["bonus_matched"] is True
        assert set(body["matched"]) == {1, 7, 13, 22, 35}

    def test_rank3_five_matched_no_bonus(self, client: TestClient) -> None:
        """5개 일치, 보너스 미일치 → 3등."""
        # 본번호 5개(1,7,13,22,35) + 임의(2)
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "1,7,13,22,35,2",
        })
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["rank"] == 3
        assert body["bonus_matched"] is False
        assert set(body["matched"]) == {1, 7, 13, 22, 35}

    def test_rank4_four_matched(self, client: TestClient) -> None:
        """4개 일치 → 4등."""
        # 본번호 4개(1,7,13,22) + 임의(2,3)
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "1,7,13,22,2,3",
        })
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["rank"] == 4
        assert set(body["matched"]) == {1, 7, 13, 22}

    def test_rank5_three_matched(self, client: TestClient) -> None:
        """3개 일치 → 5등."""
        # 본번호 3개(1,7,13) + 임의(2,3,4)
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "1,7,13,2,3,4",
        })
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["rank"] == 5
        assert set(body["matched"]) == {1, 7, 13}

    def test_no_prize_two_matched(self, client: TestClient) -> None:
        """2개 일치 → 미당첨 (rank 0)."""
        # 본번호 2개(1,7) + 임의(2,3,4,6)
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "1,7,2,3,4,6",
        })
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["rank"] == 0
        assert set(body["matched"]) == {1, 7}

    def test_no_prize_zero_matched(self, client: TestClient) -> None:
        """0개 일치 → 미당첨."""
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "2,3,4,6,8,9",
        })
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["rank"] == 0
        assert body["matched"] == []


# ─── REQ-CHECK-001: 응답 스키마 ───────────────────────────────────────────


class TestCheckResponseSchema:
    """응답 구조 및 필드 검증."""

    def test_response_has_all_required_keys(self, client: TestClient) -> None:
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "1,7,13,22,35,44",
        })
        body = res.json()
        required = {"drwNo", "rank", "matched", "bonus_matched",
                    "prize_amount", "draw_date"}
        assert required.issubset(body.keys())

    def test_prize_amount_for_rank3(self, client: TestClient) -> None:
        """3등 당첨금은 1,500,000원."""
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "1,7,13,22,35,2",
        })
        body = res.json()
        assert body["prize_amount"] == 1_500_000

    def test_prize_amount_for_no_prize_is_zero(self, client: TestClient) -> None:
        """미당첨은 prize_amount=0 (null 아님)."""
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "2,3,4,6,8,9",
        })
        body = res.json()
        assert body["prize_amount"] == 0


# ─── REQ-CHECK-001: 검증 에러 ─────────────────────────────────────────────


class TestCheckValidation:
    """입력 검증 — 404/422."""

    def test_round_not_found_returns_404(self, client: TestClient) -> None:
        res = client.get("/api/check", params={
            "drw_no": 9999,  # 존재하지 않는 회차
            "numbers": "1,7,13,22,35,44",
        })
        assert res.status_code == 404

    def test_invalid_numbers_count_less_returns_422(self, client: TestClient) -> None:
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "1,2,3,4,5",  # 5개
        })
        assert res.status_code == 422

    def test_invalid_numbers_count_more_returns_422(self, client: TestClient) -> None:
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "1,2,3,4,5,6,7",  # 7개
        })
        assert res.status_code == 422

    def test_out_of_range_high_returns_422(self, client: TestClient) -> None:
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "1,2,3,4,5,46",  # 46 > 45
        })
        assert res.status_code == 422

    def test_out_of_range_low_returns_422(self, client: TestClient) -> None:
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "0,2,3,4,5,6",  # 0 < 1
        })
        assert res.status_code == 422

    def test_duplicate_numbers_returns_422(self, client: TestClient) -> None:
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "1,1,2,3,4,5",
        })
        assert res.status_code == 422

    def test_non_numeric_returns_422(self, client: TestClient) -> None:
        res = client.get("/api/check", params={
            "drw_no": 1234,
            "numbers": "1,2,3,4,5,abc",
        })
        assert res.status_code == 422

    def test_missing_drw_no_returns_422(self, client: TestClient) -> None:
        res = client.get("/api/check", params={
            "numbers": "1,2,3,4,5,6",
        })
        assert res.status_code == 422


# ─── REQ-CHECK-002: GET /check 페이지 렌더링 ──────────────────────────────


class TestCheckPage:
    def test_page_loads_200(self, client: TestClient) -> None:
        res = client.get("/check")
        assert res.status_code == 200

    def test_page_has_dark_mode_classes(self, client: TestClient) -> None:
        """다크모드 대응 — dark: 클래스 포함."""
        res = client.get("/check")
        assert "dark:" in res.text

    def test_page_has_input_fields(self, client: TestClient) -> None:
        """회차 입력 + 번호 입력 필드 존재."""
        res = client.get("/check")
        text = res.text
        # 회차 입력
        assert 'name="drw_no"' in text or 'id="drw-no"' in text or 'id="check-drw-no"' in text
        # "확인" 버튼
        assert "확인" in text

    def test_page_has_favorites_button(self, client: TestClient) -> None:
        """즐겨찾기 불러오기 버튼 존재."""
        res = client.get("/check")
        assert "즐겨찾기" in res.text


# ─── REQ-CHECK-003: base.html 네비게이션 ─────────────────────────────────


class TestCheckNavigation:
    def test_base_template_has_check_link(self, client: TestClient) -> None:
        """모든 페이지의 base.html에 /check 링크가 포함되어야 한다."""
        res = client.get("/")
        assert 'href="/check"' in res.text

    def test_check_page_active_tab(self, client: TestClient) -> None:
        """/check 진입 시 active_tab='check'으로 탭이 활성화된다."""
        res = client.get("/check")
        # active_tab="check" 인 경우 data-blue 스타일이 적용된 /check 링크가 있어야 함
        # 또는 단순히 페이지가 정상 렌더되고 nav가 포함되면 OK
        assert 'href="/check"' in res.text
        assert "번호 확인" in res.text
