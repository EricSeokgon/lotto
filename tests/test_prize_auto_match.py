"""SPEC-LOTTO-015: 구매 이력 당첨 자동 대조 및 ROI 요약 — RED phase 테스트.

REQ-PRIZE-001 ~ REQ-PRIZE-006 검증.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ─── REQ-PRIZE-001: /api/history 응답 자동 대조 7개 필드 ────────────────────────

class TestApiHistoryPrizeFields:
    """REQ-PRIZE-001: GET /api/history 응답에 7개 필드(prize_rank, prize_amount,
    matched_count, matched_bonus, draw_numbers, draw_bonus, draw_date)가 포함된다."""

    def test_api_history_has_prize_fields_when_draw_exists(self, tmp_path, monkeypatch):
        """추첨 데이터가 존재하면 7개 필드 모두 포함되어야 한다."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        tickets = [{
            "id": "abc",
            "drwNo": 1100,
            "numbers": [1, 2, 3, 4, 5, 6],
            "bought_at": "2024-01-15",
        }]
        (tmp_path / "data" / "history.json").write_text(
            json.dumps(tickets), encoding="utf-8",
        )

        mock_draw = MagicMock()
        mock_draw.drwNo = 1100
        mock_draw.numbers.return_value = [1, 2, 3, 4, 5, 6]
        mock_draw.bonus = 7
        mock_draw.date = "2024-01-15"

        from lotto.web.app import app

        with patch("lotto.web.data.get_draws", return_value=[mock_draw]):
            client = TestClient(app)
            response = client.get("/api/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        record = data[0]

        # 신규 7개 필드 검증
        assert "prize_rank" in record
        assert "prize_amount" in record
        assert "matched_count" in record
        assert "matched_bonus" in record
        assert "draw_numbers" in record
        assert "draw_bonus" in record
        assert "draw_date" in record

        # 1등(6개 일치): prize_rank="1st", prize_amount=0 (변동)
        assert record["prize_rank"] == "1st"
        assert record["prize_amount"] == 0
        assert record["matched_count"] == 6
        assert record["matched_bonus"] is False
        assert record["draw_numbers"] == [1, 2, 3, 4, 5, 6]
        assert record["draw_bonus"] == 7

    def test_api_history_3rd_prize_amount(self, tmp_path, monkeypatch):
        """3등(5개 일치, 보너스 불일치): prize_amount=1_500_000."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        tickets = [{
            "id": "abc",
            "drwNo": 1100,
            "numbers": [1, 2, 3, 4, 5, 10],
            "bought_at": "2024-01-15",
        }]
        (tmp_path / "data" / "history.json").write_text(
            json.dumps(tickets), encoding="utf-8",
        )

        mock_draw = MagicMock()
        mock_draw.drwNo = 1100
        mock_draw.numbers.return_value = [1, 2, 3, 4, 5, 6]
        mock_draw.bonus = 7
        mock_draw.date = "2024-01-15"

        from lotto.web.app import app

        with patch("lotto.web.data.get_draws", return_value=[mock_draw]):
            client = TestClient(app)
            response = client.get("/api/history")

        record = response.json()[0]
        assert record["prize_rank"] == "3rd"
        assert record["prize_amount"] == 1_500_000
        assert record["matched_count"] == 5
        assert record["matched_bonus"] is False

    def test_api_history_5th_prize_amount(self, tmp_path, monkeypatch):
        """5등(3개 일치): prize_amount=5_000."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        tickets = [{
            "id": "abc",
            "drwNo": 1100,
            "numbers": [1, 2, 3, 40, 41, 42],
            "bought_at": "2024-01-15",
        }]
        (tmp_path / "data" / "history.json").write_text(
            json.dumps(tickets), encoding="utf-8",
        )

        mock_draw = MagicMock()
        mock_draw.drwNo = 1100
        mock_draw.numbers.return_value = [1, 2, 3, 4, 5, 6]
        mock_draw.bonus = 7
        mock_draw.date = "2024-01-15"

        from lotto.web.app import app

        with patch("lotto.web.data.get_draws", return_value=[mock_draw]):
            client = TestClient(app)
            response = client.get("/api/history")

        record = response.json()[0]
        assert record["prize_rank"] == "5th"
        assert record["prize_amount"] == 5_000


# ─── REQ-PRIZE-002: 추첨 데이터 미존재 시 pending ─────────────────────────────

class TestApiHistoryPending:
    """REQ-PRIZE-002: 추첨 데이터가 없는 회차는 prize_rank='pending'."""

    def test_api_history_pending_when_no_draw(self, tmp_path, monkeypatch):
        """추첨 데이터 없음 → prize_rank='pending', 'none' 아님."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        tickets = [{
            "id": "abc",
            "drwNo": 9999,  # 존재하지 않는 회차
            "numbers": [1, 2, 3, 4, 5, 6],
            "bought_at": "2024-01-15",
        }]
        (tmp_path / "data" / "history.json").write_text(
            json.dumps(tickets), encoding="utf-8",
        )

        from lotto.web.app import app

        with patch("lotto.web.data.get_draws", return_value=None):
            client = TestClient(app)
            response = client.get("/api/history")

        assert response.status_code == 200
        record = response.json()[0]
        assert record["prize_rank"] == "pending"
        assert record["prize_rank"] != "none"
        assert record["prize_amount"] == 0
        assert record["matched_count"] == 0
        assert record["matched_bonus"] is False
        assert record["draw_numbers"] == []
        assert record["draw_bonus"] == 0
        assert record["draw_date"] == ""


# ─── REQ-PRIZE-003 / REQ-PRIZE-004: ROI 계산 helper ────────────────────────────

class TestCalcRoi:
    """REQ-PRIZE-003/004: calc_roi 헬퍼는 미추첨 제외하고 ROI를 계산한다."""

    def test_calc_roi_empty_list_returns_zero(self):
        """빈 리스트 → 총 매수/투자/당첨금/ROI 모두 0."""
        from lotto.purchase import calc_roi

        summary = calc_roi([])
        assert summary["total_tickets"] == 0
        assert summary["total_invested"] == 0
        assert summary["total_won"] == 0
        assert summary["roi_pct"] == 0.0

    def test_calc_roi_basic_calculation(self):
        """5매 구매, 3매 추첨 완료(3등 1매, 낙첨 2매), 2매 미추첨.

        총 매수=5, 총 투자=5000, 추첨 완료 투자=3000, 총 당첨금=1_500_000.
        ROI = (1_500_000 - 3000) / 3000 * 100 = 49900.0
        """
        from lotto.purchase import calc_roi

        responses = [
            {"prize_rank": "3rd", "prize_amount": 1_500_000},
            {"prize_rank": "none", "prize_amount": 0},
            {"prize_rank": "none", "prize_amount": 0},
            {"prize_rank": "pending", "prize_amount": 0},
            {"prize_rank": "pending", "prize_amount": 0},
        ]
        summary = calc_roi(responses)
        assert summary["total_tickets"] == 5
        assert summary["total_invested"] == 5 * 1000
        assert summary["total_won"] == 1_500_000
        # ROI는 추첨 완료분 기준
        expected_roi = (1_500_000 - 3 * 1000) / (3 * 1000) * 100
        assert abs(summary["roi_pct"] - expected_roi) < 0.01

    def test_calc_roi_excludes_pending_from_numerator(self):
        """REQ-PRIZE-004: pending 티켓은 분자(당첨금)에서도 제외 (당첨금 자체 0이지만)."""
        from lotto.purchase import calc_roi

        responses = [
            {"prize_rank": "5th", "prize_amount": 5_000},
            {"prize_rank": "pending", "prize_amount": 0},
        ]
        summary = calc_roi(responses)
        # 추첨 완료 1매, 투자 1000원, 당첨 5000원 → ROI = (5000-1000)/1000*100 = 400
        assert summary["total_tickets"] == 2
        assert summary["total_invested"] == 2_000
        assert summary["total_won"] == 5_000
        assert abs(summary["roi_pct"] - 400.0) < 0.01

    def test_calc_roi_zero_when_all_pending(self):
        """REQ-PRIZE-004: 모두 pending → ROI 0.0% (ZeroDivisionError 없음)."""
        from lotto.purchase import calc_roi

        responses = [
            {"prize_rank": "pending", "prize_amount": 0},
            {"prize_rank": "pending", "prize_amount": 0},
        ]
        summary = calc_roi(responses)
        assert summary["total_tickets"] == 2
        assert summary["total_invested"] == 2_000
        assert summary["total_won"] == 0
        assert summary["roi_pct"] == 0.0

    def test_calc_roi_zero_when_empty_does_not_raise(self):
        """빈 리스트에서도 ZeroDivisionError 없음."""
        from lotto.purchase import calc_roi

        # 직접 호출에서 raise되지 않음을 확인
        summary = calc_roi([])
        assert summary["roi_pct"] == 0.0

    def test_calc_roi_ticket_price_constant(self):
        """TICKET_PRICE_KRW = 1000 상수가 존재한다."""
        from lotto.purchase import TICKET_PRICE_KRW

        assert TICKET_PRICE_KRW == 1000

    def test_calc_roi_accepts_pydantic_response_objects(self):
        """PurchaseResponse 객체도 동일하게 처리 (속성 접근)."""
        from lotto.purchase import PurchaseResponse, calc_roi

        responses = [
            PurchaseResponse(
                id=1, drwNo=1, numbers=[1, 2, 3, 4, 5, 6],
                purchased_at="2024-01-01T00:00:00",
                prize_rank="3rd", prize_amount=1_500_000,
                matched_count=5, matched_bonus=False,
            ),
            PurchaseResponse(
                id=2, drwNo=2, numbers=[1, 2, 3, 4, 5, 7],
                purchased_at="2024-01-01T00:00:00",
                prize_rank="none", prize_amount=0,
                matched_count=2, matched_bonus=False,
            ),
        ]
        summary = calc_roi(responses)
        assert summary["total_tickets"] == 2
        assert summary["total_invested"] == 2_000
        assert summary["total_won"] == 1_500_000


# ─── REQ-PRIZE-003: ROI 요약 카드 HTML 렌더링 ─────────────────────────────────

class TestRoiSummaryHtmlRendering:
    """REQ-PRIZE-003: /purchases와 /history 페이지에 ROI 요약 카드가 표시된다."""

    def test_purchases_page_shows_roi_summary(self, tmp_path, monkeypatch):
        """GET /purchases 응답 HTML에 ROI 요약 카드 4종이 포함된다."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        from lotto.web.app import app

        client = TestClient(app)
        response = client.get("/purchases")

        assert response.status_code == 200
        html = response.text
        # 4개 카드 라벨 확인
        assert "총 매수" in html or "총매수" in html
        assert "총 투자" in html or "총투자" in html
        assert "총 당첨금" in html or "총당첨금" in html
        assert "ROI" in html

    def test_history_page_shows_roi_summary(self, tmp_path, monkeypatch):
        """GET /history 응답 HTML에 ROI 요약 카드 4종이 포함된다."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        from lotto.web.app import app

        with patch("lotto.web.routes.pages.compute_ticket_results", return_value=[]):
            client = TestClient(app)
            response = client.get("/history")

        assert response.status_code == 200
        html = response.text
        assert "총 매수" in html or "총매수" in html
        assert "총 투자" in html or "총투자" in html
        assert "총 당첨금" in html or "총당첨금" in html
        assert "ROI" in html


# ─── REQ-PRIZE-006: 영문 코드 비노출 ──────────────────────────────────────────

class TestNoEnglishCodesInHtml:
    """REQ-PRIZE-006: HTML에 raw English codes('1st','none','pending')가 등장하지 않는다."""

    def test_purchases_page_no_english_codes(self, tmp_path, monkeypatch):
        """purchases.html: 영문 prize_rank 코드가 사용자 화면에 노출되지 않는다."""
        from lotto import purchase as _pm

        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()
        # SPEC-014 형식 purchases.json — 1등/낙첨/미추첨 각 1건
        purchases_path = tmp_path / "data" / "purchases.json"
        monkeypatch.setattr(_pm, "_PURCHASES_PATH", purchases_path)

        # 3개 레코드: 회차 1(추첨 있음), 회차 9999(추첨 없음)
        records = [
            {"id": 1, "drwNo": 1, "numbers": [1, 10, 20, 30, 40, 45],
             "purchased_at": "2024-01-01T00:00:00"},
            {"id": 2, "drwNo": 1, "numbers": [2, 3, 4, 6, 7, 8],
             "purchased_at": "2024-01-02T00:00:00"},
            {"id": 3, "drwNo": 9999, "numbers": [1, 2, 3, 4, 5, 6],
             "purchased_at": "2024-01-03T00:00:00"},
        ]
        purchases_path.write_text(json.dumps(records), encoding="utf-8")

        mock_draw = MagicMock()
        mock_draw.drwNo = 1
        mock_draw.numbers.return_value = [1, 10, 20, 30, 40, 45]
        mock_draw.bonus = 5

        from lotto.web.app import app

        with patch("lotto.web.routes.pages.get_draws", return_value=[mock_draw]):
            client = TestClient(app)
            response = client.get("/purchases")

        assert response.status_code == 200
        html = response.text

        # 한국어 라벨은 노출되어야 함
        assert "1등" in html
        # 영문 코드는 사용자 화면(렌더링된 td 셀)에 노출되어서는 안 됨
        # NOTE: HTML 속성/주석에 코드가 들어갈 수 있지만, 셀 콘텐츠 텍스트로 노출되면 안 됨.
        # data-* 속성과 클래스명 등은 허용하되, 표시되는 단어로 사용되면 안 됨.
        # 가장 엄격한 검증: 셀 텍스트에 정확히 "1st", "none", "pending"이 단어로 나타나지 않음
        import re

        # <td>...</td> 또는 <span>...</span> 내부에 정확히 영문 코드만 있는지 검사
        td_pattern = re.compile(r">\s*(1st|2nd|3rd|4th|5th|none|pending)\s*<", re.IGNORECASE)
        matches = td_pattern.findall(html)
        assert not matches, f"영문 코드가 HTML 셀에 노출됨: {matches}"

    def test_history_page_no_english_codes(self, tmp_path, monkeypatch):
        """history.html: 영문 prize_rank 코드가 사용자 화면에 노출되지 않는다."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        # 미추첨 + 추첨 완료 시나리오
        fake_results = [
            {
                "ticket": {"id": "a", "drwNo": 1100, "numbers": [1, 2, 3, 4, 5, 6],
                           "bought_at": "2024-01-15"},
                "draw_numbers": [1, 2, 3, 4, 5, 6],
                "draw_bonus": 7,
                "draw_date": "2024-01-15",
                "matched": 6, "bonus_match": False,
                "prize": "1등",
                "prize_rank": "1st", "prize_amount": 0,
                "matched_count": 6, "matched_bonus": False,
            },
            {
                "ticket": {"id": "b", "drwNo": 9999, "numbers": [10, 20, 30, 40, 41, 42],
                           "bought_at": "2024-01-22"},
                "draw_numbers": [], "draw_bonus": 0, "draw_date": "",
                "matched": 0, "bonus_match": False,
                "prize": "미추첨",
                "prize_rank": "pending", "prize_amount": 0,
                "matched_count": 0, "matched_bonus": False,
            },
        ]
        from lotto.web.app import app

        with patch("lotto.web.routes.pages.compute_ticket_results", return_value=fake_results):
            client = TestClient(app)
            response = client.get("/history")

        assert response.status_code == 200
        html = response.text

        import re

        td_pattern = re.compile(r">\s*(1st|2nd|3rd|4th|5th|none|pending)\s*<", re.IGNORECASE)
        matches = td_pattern.findall(html)
        assert not matches, f"영문 코드가 HTML 셀에 노출됨: {matches}"

        # 한국어 라벨은 표시되어야 함
        assert "1등" in html
        assert "미추첨" in html


# ─── REQ-PRIZE-005: 단일 calc_prize 호출 (회귀 방지) ──────────────────────────

class TestComputeTicketResultsUsesCalcPrize:
    """REQ-PRIZE-005: compute_ticket_results는 calc_prize를 단일 소스로 사용한다."""

    def test_compute_ticket_results_returns_new_fields(self, tmp_path, monkeypatch):
        """compute_ticket_results 결과에 신규 7개 필드가 포함된다."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        tickets = [{"id": "abc", "drwNo": 1100, "numbers": [1, 2, 3, 4, 5, 10],
                    "bought_at": "2024-01-15"}]
        (tmp_path / "data" / "history.json").write_text(
            json.dumps(tickets), encoding="utf-8",
        )

        mock_draw = MagicMock()
        mock_draw.drwNo = 1100
        mock_draw.numbers.return_value = [1, 2, 3, 4, 5, 6]
        mock_draw.bonus = 7
        mock_draw.date = "2024-01-15"

        from lotto.web.data import compute_ticket_results

        with patch("lotto.web.data.get_draws", return_value=[mock_draw]):
            result = compute_ticket_results()

        assert len(result) == 1
        record = result[0]
        # 신규 필드 검증
        assert record["prize_rank"] == "3rd"
        assert record["prize_amount"] == 1_500_000
        assert record["matched_count"] == 5
        assert record["matched_bonus"] is False
        # 기존 필드 회귀 방지
        assert record["prize"] == "3등"
        assert record["matched"] == 5
        assert record["bonus_match"] is False

    def test_compute_ticket_results_pending_when_no_draw(self, tmp_path, monkeypatch):
        """미추첨 케이스: prize_rank='pending', prize='미추첨' 양쪽 모두 일관."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()

        tickets = [{"id": "abc", "drwNo": 9999, "numbers": [1, 2, 3, 4, 5, 6],
                    "bought_at": "2024-01-01"}]
        (tmp_path / "data" / "history.json").write_text(
            json.dumps(tickets), encoding="utf-8",
        )

        from lotto.web.data import compute_ticket_results

        with patch("lotto.web.data.get_draws", return_value=None):
            result = compute_ticket_results()

        record = result[0]
        assert record["prize_rank"] == "pending"
        assert record["prize_amount"] == 0
        assert record["prize"] == "미추첨"  # 기존 한국어 라벨 회귀 방지
        assert record["draw_numbers"] == []
        assert record["draw_date"] == ""


# ─── ROI 카드 정확한 값 렌더링 (AC-PRIZE-003) ─────────────────────────────────

class TestRoiCardValues:
    """AC-PRIZE-003: ROI 카드에 정확한 값이 렌더링된다."""

    def test_purchases_roi_card_values(self, tmp_path, monkeypatch):
        """5매(1등 1매 가정 불가능 - 3등 1매, 낙첨 2매, 미추첨 2매)."""
        from lotto import purchase as _pm

        monkeypatch.chdir(tmp_path)
        (tmp_path / "data").mkdir()
        purchases_path = tmp_path / "data" / "purchases.json"
        monkeypatch.setattr(_pm, "_PURCHASES_PATH", purchases_path)

        # 5개 레코드
        records = [
            # 회차 1: 3등 (5개 일치, 보너스 불일치)
            {"id": 1, "drwNo": 1, "numbers": [1, 2, 10, 20, 30, 40],
             "purchased_at": "2024-01-01T00:00:00"},
            # 회차 1: 낙첨
            {"id": 2, "drwNo": 1, "numbers": [2, 3, 4, 6, 7, 8],
             "purchased_at": "2024-01-02T00:00:00"},
            # 회차 1: 낙첨
            {"id": 3, "drwNo": 1, "numbers": [11, 12, 13, 14, 15, 16],
             "purchased_at": "2024-01-03T00:00:00"},
            # 회차 9999: 미추첨
            {"id": 4, "drwNo": 9999, "numbers": [1, 2, 3, 4, 5, 6],
             "purchased_at": "2024-01-04T00:00:00"},
            {"id": 5, "drwNo": 9999, "numbers": [7, 8, 9, 10, 11, 12],
             "purchased_at": "2024-01-05T00:00:00"},
        ]
        purchases_path.write_text(json.dumps(records), encoding="utf-8")

        # 회차 1: 1,10,20,30,40,45 / 보너스 5
        mock_draw = MagicMock()
        mock_draw.drwNo = 1
        mock_draw.numbers.return_value = [1, 10, 20, 30, 40, 45]
        mock_draw.bonus = 5

        from lotto.web.app import app

        with patch("lotto.web.routes.pages.get_draws", return_value=[mock_draw]):
            client = TestClient(app)
            response = client.get("/purchases")

        assert response.status_code == 200
        html = response.text

        # 총 매수: 5
        # 총 투자: 5,000원
        # 총 당첨금: 1,500,000원
        # ROI: (1_500_000 - 3*1000) / (3*1000) * 100 = 49900.0
        assert "5,000" in html  # 총 투자
        assert "1,500,000" in html  # 총 당첨금
        # ROI 값 표기 (소수점 첫째 자리)
        assert "49900.0" in html or "49,900.0" in html or "49900" in html


@pytest.mark.parametrize("rank,amount", [
    ("1st", 0),
    ("2nd", 0),
    ("3rd", 1_500_000),
    ("4th", 50_000),
    ("5th", 5_000),
    ("none", 0),
    ("pending", 0),
])
def test_prize_amount_mapping_matches_spec(rank, amount):
    """REQ-PRIZE-001: prize_amount는 등수별 고정값이다."""
    from lotto.purchase import _PRIZE_AMOUNTS

    assert _PRIZE_AMOUNTS[rank] == amount
