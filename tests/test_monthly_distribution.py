"""SPEC-LOTTO-108: 번호 월별 출현 분포 분석 테스트.

`draw.date.month`(1=1월 … 12=12월)로 회차를 그룹화하여 각 월에서 번호(1~45)의
출현 횟수·비율을 집계한다. 회차 인덱스 기준(rolling/period_trend)이 아니라
달력 기반(1~12월) 주기성을 분석한다. 모든 기댓값은 acceptance.md의 4회차
손계산 픽스처에서 직접 산출·검증되었다.

Fixture (4 draws):
| 회차 | 추첨일       | 월      | 본번호(sorted)        |
|------|--------------|---------|-----------------------|
| D1   | 2024-01-06   | 1 (Jan) | 1, 2, 3, 4, 5, 6      |
| D2   | 2024-01-13   | 1 (Jan) | 1, 7, 8, 9, 10, 11    |
| D3   | 2024-03-02   | 3 (Mar) | 2, 12, 13, 14, 15, 16 |
| D4   | 2024-06-01   | 6 (Jun) | 3, 17, 18, 19, 20, 21 |
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.data import get_monthly_distribution


def make_draw(
    draw_no: int,
    draw_date: date,
    n1: int,
    n2: int,
    n3: int,
    n4: int,
    n5: int,
    n6: int,
    bonus: int = 13,
) -> DrawResult:
    """테스트용 DrawResult 생성 헬퍼."""
    return DrawResult(
        drwNo=draw_no,
        date=draw_date,
        n1=n1,
        n2=n2,
        n3=n3,
        n4=n4,
        n5=n5,
        n6=n6,
        bonus=bonus,
    )


def fixture_4() -> list[DrawResult]:
    """acceptance.md 4회차 손계산 픽스처."""
    return [
        make_draw(1, date(2024, 1, 6), 1, 2, 3, 4, 5, 6),
        make_draw(2, date(2024, 1, 13), 1, 7, 8, 9, 10, 11),
        make_draw(3, date(2024, 3, 2), 2, 12, 13, 14, 15, 16),
        make_draw(4, date(2024, 6, 1), 3, 17, 18, 19, 20, 21),
    ]


# ---------------------------------------------------------------------------
# 핵심 계산 (data layer)
# ---------------------------------------------------------------------------


def test_total_draws() -> None:
    """AC-MD-001: total_draws == 4."""
    assert get_monthly_distribution(fixture_4())["total_draws"] == 4


def test_top_level_keys() -> None:
    """AC-MD-002: 반환 dict가 모든 핵심 키를 포함한다."""
    result = get_monthly_distribution(fixture_4())
    assert set(result.keys()) >= {
        "total_draws",
        "top_n",
        "monthly_summary",
        "top_numbers_by_month",
        "top_months_by_number",
        "disclaimer",
    }


def test_monthly_summary_length_and_bounds() -> None:
    """AC-MD-003: monthly_summary 길이 12, index0=1월(Jan), index11=12월(Dec)."""
    summary = get_monthly_distribution(fixture_4())["monthly_summary"]
    assert len(summary) == 12
    assert summary[0]["month"] == 1
    assert summary[0]["month_name"] == "Jan"
    assert summary[11]["month"] == 12
    assert summary[11]["month_name"] == "Dec"


def test_monthly_summary_draw_counts() -> None:
    """AC-MD-004: Jan=2, Mar=1, Jun=1 회차 수."""
    summary = get_monthly_distribution(fixture_4())["monthly_summary"]
    assert summary[0]["draw_count"] == 2  # Jan
    assert summary[2]["draw_count"] == 1  # Mar
    assert summary[5]["draw_count"] == 1  # Jun


def test_monthly_summary_empty_month() -> None:
    """AC-MD-005: Feb(회차 없음) draw_count == 0."""
    summary = get_monthly_distribution(fixture_4())["monthly_summary"]
    assert summary[1]["draw_count"] == 0


def test_monthly_summary_month_names() -> None:
    """AC-MD-006: 모든 month_name이 정확한 약어 순서를 따른다."""
    summary = get_monthly_distribution(fixture_4())["monthly_summary"]
    expected = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    assert [s["month_name"] for s in summary] == expected


# ---------------------------------------------------------------------------
# top_numbers_by_month
# ---------------------------------------------------------------------------


def test_top_numbers_january() -> None:
    """AC-MD-007: 1월 top_n=3 — 1(count2,100%), 2/3(count1,50%)."""
    result = get_monthly_distribution(fixture_4(), top_n=3)
    assert result["top_numbers_by_month"]["1"] == [
        {"number": 1, "count": 2, "pct": 100.0},
        {"number": 2, "count": 1, "pct": 50.0},
        {"number": 3, "count": 1, "pct": 50.0},
    ]


def test_top_numbers_march() -> None:
    """AC-MD-008: 3월 top_n=3 — 2/12/13 각 count1, 100%."""
    result = get_monthly_distribution(fixture_4(), top_n=3)
    assert result["top_numbers_by_month"]["3"] == [
        {"number": 2, "count": 1, "pct": 100.0},
        {"number": 12, "count": 1, "pct": 100.0},
        {"number": 13, "count": 1, "pct": 100.0},
    ]


def test_top_numbers_february_empty() -> None:
    """AC-MD-009: 2월(회차 없음) top_numbers == []."""
    result = get_monthly_distribution(fixture_4(), top_n=3)
    assert result["top_numbers_by_month"]["2"] == []


def test_top_numbers_all_12_keys() -> None:
    """AC-MD-010: top_numbers_by_month 키 "1"~"12" 12개 모두 존재."""
    result = get_monthly_distribution(fixture_4())
    keys = set(result["top_numbers_by_month"].keys())
    assert keys == {str(m) for m in range(1, 13)}


def test_top_numbers_june_first() -> None:
    """AC-MD-011: 6월 top_n=3 첫 항목 {number:3,count:1,pct:100.0}."""
    result = get_monthly_distribution(fixture_4(), top_n=3)
    assert result["top_numbers_by_month"]["6"][0] == {
        "number": 3,
        "count": 1,
        "pct": 100.0,
    }


# ---------------------------------------------------------------------------
# top_months_by_number
# ---------------------------------------------------------------------------


def test_top_months_length_and_bounds() -> None:
    """AC-MD-012: top_months_by_number 길이 45, index0=번호1, index44=번호45."""
    tmbn = get_monthly_distribution(fixture_4())["top_months_by_number"]
    assert len(tmbn) == 45
    assert tmbn[0]["number"] == 1
    assert tmbn[44]["number"] == 45


def test_top_months_number_1() -> None:
    """AC-MD-013: 번호 1 — best_month=1, count=2, pct=100.0."""
    tmbn = get_monthly_distribution(fixture_4())["top_months_by_number"]
    item = tmbn[0]
    assert item["best_month"] == 1
    assert item["best_month_count"] == 2
    assert item["best_month_pct"] == 100.0


def test_top_months_number_2_tie_smallest() -> None:
    """AC-MD-014: 번호 2 — Jan·Mar 동률 → 가장 작은 월 best_month=1."""
    tmbn = get_monthly_distribution(fixture_4())["top_months_by_number"]
    assert tmbn[1]["best_month"] == 1
    assert tmbn[1]["best_month_count"] == 1


def test_top_months_number_3_tie_smallest() -> None:
    """AC-MD-015: 번호 3 — Jan·Jun 동률 → best_month=1."""
    tmbn = get_monthly_distribution(fixture_4())["top_months_by_number"]
    assert tmbn[2]["best_month"] == 1
    assert tmbn[2]["best_month_count"] == 1


def test_top_months_unseen_number() -> None:
    """AC-MD-016: 번호 22(미출현) — best_month=0, count=0, pct=0.0."""
    tmbn = get_monthly_distribution(fixture_4())["top_months_by_number"]
    item = tmbn[21]
    assert item["number"] == 22
    assert item["best_month"] == 0
    assert item["best_month_count"] == 0
    assert item["best_month_pct"] == 0.0


# ---------------------------------------------------------------------------
# 엣지 케이스 (Edge Cases)
# ---------------------------------------------------------------------------


def test_none_input_zero_structure() -> None:
    """AC-MD-017: None 입력 → 0 채움 구조."""
    result = get_monthly_distribution(None)
    assert result["total_draws"] == 0
    assert len(result["monthly_summary"]) == 12
    for s in result["monthly_summary"]:
        assert s["draw_count"] == 0
    for m in range(1, 13):
        assert result["top_numbers_by_month"][str(m)] == []
    assert len(result["top_months_by_number"]) == 45
    for item in result["top_months_by_number"]:
        assert item["best_month"] == 0
        assert item["best_month_count"] == 0
        assert item["best_month_pct"] == 0.0


def test_empty_input_zero_structure() -> None:
    """AC-MD-018: [] 입력 → None과 동일한 0 채움 구조."""
    result = get_monthly_distribution([])
    assert result["total_draws"] == 0
    assert all(s["draw_count"] == 0 for s in result["monthly_summary"])
    assert result["top_numbers_by_month"]["1"] == []


def test_top_n_cache_key_separation() -> None:
    """AC-MD-019: top_n=3과 top_n=5는 서로 다른 길이를 반환한다(캐시 키 분리)."""
    r3 = get_monthly_distribution(fixture_4(), top_n=3)
    r5 = get_monthly_distribution(fixture_4(), top_n=5)
    # 1월에는 출현 번호가 11개 → top_n에 따라 길이가 달라진다.
    assert len(r3["top_numbers_by_month"]["1"]) == 3
    assert len(r5["top_numbers_by_month"]["1"]) == 5
    assert r3["top_n"] == 3
    assert r5["top_n"] == 5


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


class TestMonthlyApi:
    """GET /api/stats/monthly 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app

        return TestClient(app)

    def test_api_200_and_keys(self) -> None:
        """AC-MD-020: 200, 핵심 키 포함, top_n 기본 5."""
        with patch("lotto.web.data.get_draws", return_value=fixture_4()):
            resp = self._client().get("/api/stats/monthly")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) >= {
            "total_draws",
            "top_n",
            "monthly_summary",
            "top_numbers_by_month",
            "top_months_by_number",
            "disclaimer",
        }
        assert body["top_n"] == 5

    def test_api_top_n_validation(self) -> None:
        """AC-MD-021: 0/46 → 422, 1/45 → 200."""
        client = self._client()
        assert client.get("/api/stats/monthly?top_n=0").status_code == 422
        assert client.get("/api/stats/monthly?top_n=46").status_code == 422
        with patch("lotto.web.data.get_draws", return_value=fixture_4()):
            assert client.get("/api/stats/monthly?top_n=1").status_code == 200
            assert client.get("/api/stats/monthly?top_n=45").status_code == 200


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


class TestMonthlyPage:
    """GET /stats/monthly 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app

        return TestClient(app)

    def test_page_200_and_label(self) -> None:
        """AC-MD-022: 200, '월별' 문자열 포함."""
        with patch("lotto.web.data.get_draws", return_value=fixture_4()):
            resp = self._client().get("/stats/monthly")
        assert resp.status_code == 200
        assert "월별" in resp.text

    def test_page_empty_data_200(self) -> None:
        """AC-MD-023: 데이터 부재 시에도 200."""
        with patch("lotto.web.data.get_draws", return_value=None):
            resp = self._client().get("/stats/monthly")
        assert resp.status_code == 200
