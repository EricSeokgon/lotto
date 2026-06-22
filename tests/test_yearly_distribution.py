"""SPEC-LOTTO-110: 번호 연도별 출현 분포 분석 테스트.

`draw.date.year`(속성, int)로 회차를 달력 연도(2002~현재)별로 그룹화하여 각 연도에서
번호(1~45)의 출현 횟수·비율을 집계한다. 회차 인덱스 기준(period_trend)이나 달력 월
(monthly)이 아니라 실제 달력 연도(가변 개수)를 축으로 장기 추세를 본다. 모든 기댓값은
acceptance.md의 4회차 손계산 픽스처에서 직접 산출·검증되었다.

Fixture (4 draws):
| 회차 | 추첨일             | 연도 | 본번호(sorted)        |
|------|--------------------|------|-----------------------|
| D1   | date(2020, 3, 7)   | 2020 | 1, 2, 3, 4, 5, 6      |
| D2   | date(2020, 3, 14)  | 2020 | 1, 7, 8, 9, 10, 11    |
| D3   | date(2021, 5, 1)   | 2021 | 2, 12, 13, 14, 15, 16 |
| D4   | date(2023, 1, 7)   | 2023 | 3, 17, 18, 19, 20, 21 |
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.data import get_yearly_distribution


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
        make_draw(1, date(2020, 3, 7), 1, 2, 3, 4, 5, 6),
        make_draw(2, date(2020, 3, 14), 1, 7, 8, 9, 10, 11),
        make_draw(3, date(2021, 5, 1), 2, 12, 13, 14, 15, 16),
        make_draw(4, date(2023, 1, 7), 3, 17, 18, 19, 20, 21),
    ]


# ---------------------------------------------------------------------------
# 핵심 계산 (data layer)
# ---------------------------------------------------------------------------


def test_total_draws() -> None:
    """AC-YD-001: total_draws == 4."""
    assert get_yearly_distribution(fixture_4())["total_draws"] == 4


def test_top_level_keys() -> None:
    """AC-YD-002: 반환 dict가 모든 핵심 키를 포함한다."""
    result = get_yearly_distribution(fixture_4())
    assert set(result.keys()) >= {
        "total_draws",
        "total_years",
        "top_n",
        "yearly_summary",
        "top_numbers_by_year",
        "top_years_by_number",
        "disclaimer",
    }


def test_total_years() -> None:
    """AC-YD-003: total_years == 3 (2020, 2021, 2023)."""
    assert get_yearly_distribution(fixture_4())["total_years"] == 3


def test_yearly_summary_order() -> None:
    """AC-YD-004: yearly_summary 길이 3, 연도 오름차순."""
    summary = get_yearly_distribution(fixture_4())["yearly_summary"]
    assert len(summary) == 3
    assert [s["year"] for s in summary] == [2020, 2021, 2023]


def test_yearly_summary_draw_counts() -> None:
    """AC-YD-005: 2020:2, 2021:1, 2023:1 회차 수."""
    summary = get_yearly_distribution(fixture_4())["yearly_summary"]
    counts = {s["year"]: s["draw_count"] for s in summary}
    assert counts == {2020: 2, 2021: 1, 2023: 1}


def test_top_numbers_by_year_keys() -> None:
    """AC-YD-006: top_numbers_by_year 키는 데이터 있는 연도 문자열만."""
    result = get_yearly_distribution(fixture_4())
    assert set(result["top_numbers_by_year"].keys()) == {"2020", "2021", "2023"}


def test_top_numbers_by_year_2020_first() -> None:
    """AC-YD-007: 2020 첫 항목은 {number:1, count:2, pct:100.0}."""
    result = get_yearly_distribution(fixture_4(), top_n=3)
    top = result["top_numbers_by_year"]["2020"]
    assert top[0] == {"number": 1, "count": 2, "pct": 100.0}


def test_top_numbers_by_year_2020_tie_order() -> None:
    """AC-YD-008: 2020 동률(count=1)은 번호 오름차순 → 2, 3."""
    result = get_yearly_distribution(fixture_4(), top_n=3)
    top = result["top_numbers_by_year"]["2020"]
    assert top[1]["number"] == 2
    assert top[2]["number"] == 3
    assert top[1]["count"] == 1
    assert top[1]["pct"] == 50.0


def test_top_n_limits_list_length() -> None:
    """AC-YD-009: top_n이 각 연도 리스트 길이를 제한한다."""
    result = get_yearly_distribution(fixture_4(), top_n=3)
    assert len(result["top_numbers_by_year"]["2020"]) == 3
    result10 = get_yearly_distribution(fixture_4(), top_n=10)
    # 2020에는 11개 번호 출현 → top_n=10이면 10개로 제한
    assert len(result10["top_numbers_by_year"]["2020"]) == 10


def test_top_numbers_by_year_2021_all_full_pct() -> None:
    """AC-YD-010: 2021(회차 1)은 모든 항목 pct=100.0."""
    result = get_yearly_distribution(fixture_4(), top_n=3)
    top = result["top_numbers_by_year"]["2021"]
    assert all(item["pct"] == 100.0 for item in top)
    assert top[0]["number"] == 2  # 동률 → 번호 오름차순


def test_top_years_by_number_length() -> None:
    """AC-YD-011: top_years_by_number 길이 45, index0 = 번호 1."""
    result = get_yearly_distribution(fixture_4())
    tybn = result["top_years_by_number"]
    assert len(tybn) == 45
    assert tybn[0]["number"] == 1
    assert tybn[44]["number"] == 45


def test_top_years_by_number_n1() -> None:
    """AC-YD-012: 번호 1 = best_year:2020, count:2, pct:100.0."""
    tybn = get_yearly_distribution(fixture_4())["top_years_by_number"]
    assert tybn[0] == {
        "number": 1,
        "best_year": 2020,
        "best_year_count": 2,
        "best_year_pct": 100.0,
    }


def test_top_years_by_number_n2_tie_earliest() -> None:
    """AC-YD-013: 번호 2 동률(2020,2021) → 이른 연도 2020."""
    tybn = get_yearly_distribution(fixture_4())["top_years_by_number"]
    assert tybn[1]["best_year"] == 2020
    assert tybn[1]["best_year_count"] == 1
    assert tybn[1]["best_year_pct"] == 50.0


def test_top_years_by_number_n3_tie_earliest() -> None:
    """AC-YD-014: 번호 3 동률(2020,2023) → 이른 연도 2020."""
    tybn = get_yearly_distribution(fixture_4())["top_years_by_number"]
    assert tybn[2]["best_year"] == 2020


def test_top_years_by_number_n45_absent() -> None:
    """AC-YD-015: 번호 45 미출현 → best_year=None, 0, 0.0."""
    tybn = get_yearly_distribution(fixture_4())["top_years_by_number"]
    assert tybn[44] == {
        "number": 45,
        "best_year": None,
        "best_year_count": 0,
        "best_year_pct": 0.0,
    }


# ---------------------------------------------------------------------------
# 빈/None 데이터 가드
# ---------------------------------------------------------------------------


def test_empty_structure_none() -> None:
    """AC-YD-016: None 입력 → 0 채움 구조."""
    result = get_yearly_distribution(None)
    assert result["total_draws"] == 0
    assert result["total_years"] == 0
    assert result["yearly_summary"] == []
    assert result["top_numbers_by_year"] == {}
    assert len(result["top_years_by_number"]) == 45
    assert all(item["best_year"] is None for item in result["top_years_by_number"])


def test_empty_structure_empty_list() -> None:
    """AC-YD-016: 빈 리스트 입력 → 0 채움 구조."""
    result = get_yearly_distribution([])
    assert result["total_draws"] == 0
    assert result["total_years"] == 0
    assert result["yearly_summary"] == []
    assert result["top_numbers_by_year"] == {}
    assert result["top_years_by_number"][0] == {
        "number": 1,
        "best_year": None,
        "best_year_count": 0,
        "best_year_pct": 0.0,
    }


# ---------------------------------------------------------------------------
# API / 페이지 라우트
# ---------------------------------------------------------------------------


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_returns_result() -> None:
    """AC-YD-017: GET /api/stats/yearly는 200과 분석 결과를 반환한다."""
    with patch("lotto.web.data.get_draws", return_value=fixture_4()):
        resp = _client().get("/api/stats/yearly?top_n=3")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    assert body["total_years"] == 3
    assert body["top_numbers_by_year"]["2020"][0]["number"] == 1


def test_api_top_n_out_of_range() -> None:
    """AC-YD-017: top_n=0/46은 422."""
    client = _client()
    assert client.get("/api/stats/yearly?top_n=0").status_code == 422
    assert client.get("/api/stats/yearly?top_n=46").status_code == 422


def test_page_renders() -> None:
    """AC-YD-018: GET /stats/yearly는 200·HTML, disclaimer 포함."""
    with patch("lotto.web.data.get_draws", return_value=fixture_4()):
        resp = _client().get("/stats/yearly")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "연도별" in resp.text


def test_page_empty_data() -> None:
    """AC-YD-018: 빈 데이터에서도 200."""
    with patch("lotto.web.data.get_draws", return_value=[]):
        resp = _client().get("/stats/yearly")
    assert resp.status_code == 200
