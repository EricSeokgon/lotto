"""SPEC-LOTTO-109: 번호 출현 간격 상세 분포 분석 테스트.

각 번호(1~45)의 역대 연속 출현 간격(drwNo 차이)을 수집하여 min/max/avg/median/
std와 6버킷 히스토그램, 전체 요약(역대 최대·최소 간격)을 산출한다. 모든 기댓값은
acceptance.md의 5회차 손계산 픽스처에서 직접 산출·검증되었다.

Fixture (5 draws, drwNo 오름차순):
| drwNo | 본번호(sorted)         |
|-------|------------------------|
| 1     | 1, 2, 3, 4, 5, 6       |
| 5     | 1, 7, 8, 9, 10, 11     |
| 10    | 2, 12, 13, 14, 15, 16  |
| 12    | 1, 17, 18, 19, 20, 21  |
| 20    | 2, 22, 23, 24, 25, 26  |

손계산:
- 번호 1 출현 drwNo=[1,5,12] → gaps=[4,7] → min4 max7 avg5.5 med5.5 std2.12
- 번호 2 출현 drwNo=[1,10,20] → gaps=[9,10] → min9 max10 avg9.5 med9.5 std0.71
- 번호 7 출현 drwNo=[5] (1회) → count=0, 통계 None
- 번호 45 미출현 → count=0, appearance_count=0
- overall: all_gaps=[4,7,9,10] → avg_gap_all=7.5, max=10(번호2), min=4(번호1)
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.data import get_gap_distribution

_EMPTY_HISTOGRAM = {
    "1-10": 0,
    "11-20": 0,
    "21-30": 0,
    "31-40": 0,
    "41-50": 0,
    "51+": 0,
}


def make_draw(
    draw_no: int,
    n1: int,
    n2: int,
    n3: int,
    n4: int,
    n5: int,
    n6: int,
    bonus: int = 30,
) -> DrawResult:
    """테스트용 DrawResult 생성 헬퍼."""
    return DrawResult(
        drwNo=draw_no,
        date=date(2024, 1, 1),
        n1=n1,
        n2=n2,
        n3=n3,
        n4=n4,
        n5=n5,
        n6=n6,
        bonus=bonus,
    )


def fixture_5() -> list[DrawResult]:
    """acceptance.md 5회차 손계산 픽스처."""
    return [
        make_draw(1, 1, 2, 3, 4, 5, 6),
        make_draw(5, 1, 7, 8, 9, 10, 11),
        make_draw(10, 2, 12, 13, 14, 15, 16),
        make_draw(12, 1, 17, 18, 19, 20, 21),
        make_draw(20, 2, 22, 23, 24, 25, 26),
    ]


def _num(result: dict, number: int) -> dict:
    """결과 numbers 리스트에서 특정 번호 항목을 반환."""
    return result["numbers"][number - 1]


# ---------------------------------------------------------------------------
# 핵심 계산 (data layer)
# ---------------------------------------------------------------------------


def test_number1_gaps() -> None:
    """AC-01: 번호 1의 gaps == [4, 7] (drwNo 차이 기반)."""
    item = _num(get_gap_distribution(fixture_5()), 1)
    assert item["gaps"] == [4, 7]


def test_number1_basic_stats() -> None:
    """AC-02: 번호 1 count/min/max/avg/median."""
    item = _num(get_gap_distribution(fixture_5()), 1)
    assert item["count"] == 2
    assert item["min_gap"] == 4
    assert item["max_gap"] == 7
    assert item["avg_gap"] == 5.5
    assert item["median_gap"] == 5.5


def test_number1_std() -> None:
    """AC-03: 번호 1 std_gap == 2.12."""
    assert _num(get_gap_distribution(fixture_5()), 1)["std_gap"] == 2.12


def test_number1_appearance_count() -> None:
    """AC-04: 번호 1 appearance_count == 3."""
    assert _num(get_gap_distribution(fixture_5()), 1)["appearance_count"] == 3


def test_number2_stats() -> None:
    """AC-05: 번호 2 gaps=[9,10], stats."""
    item = _num(get_gap_distribution(fixture_5()), 2)
    assert item["gaps"] == [9, 10]
    assert item["min_gap"] == 9
    assert item["max_gap"] == 10
    assert item["avg_gap"] == 9.5
    assert item["median_gap"] == 9.5
    assert item["std_gap"] == 0.71


def test_number1_histogram() -> None:
    """AC-06: 번호 1 히스토그램 {"1-10":2, 나머지 0}."""
    item = _num(get_gap_distribution(fixture_5()), 1)
    assert item["gap_histogram"] == {**_EMPTY_HISTOGRAM, "1-10": 2}


def test_number2_histogram() -> None:
    """AC-07: 번호 2 히스토그램도 {"1-10":2, 나머지 0} (9,10 모두 1~10)."""
    item = _num(get_gap_distribution(fixture_5()), 2)
    assert item["gap_histogram"] == {**_EMPTY_HISTOGRAM, "1-10": 2}


def test_single_appearance_number() -> None:
    """AC-08: 번호 7(1회 출현) count=0, 통계 None, appearance_count=1."""
    item = _num(get_gap_distribution(fixture_5()), 7)
    assert item["count"] == 0
    assert item["avg_gap"] is None
    assert item["median_gap"] is None
    assert item["min_gap"] is None
    assert item["max_gap"] is None
    assert item["std_gap"] is None
    assert item["appearance_count"] == 1


def test_single_appearance_histogram_zero() -> None:
    """AC-09: 번호 7 히스토그램 모든 버킷 0."""
    assert _num(get_gap_distribution(fixture_5()), 7)["gap_histogram"] == _EMPTY_HISTOGRAM


def test_never_appeared_number() -> None:
    """AC-10: 번호 45(미출현) count=0, appearance_count=0, 통계 None."""
    item = _num(get_gap_distribution(fixture_5()), 45)
    assert item["count"] == 0
    assert item["appearance_count"] == 0
    assert item["avg_gap"] is None
    assert item["std_gap"] is None
    assert item["gap_histogram"] == _EMPTY_HISTOGRAM


def test_overall_avg_gap_all() -> None:
    """AC-11: overall_summary.avg_gap_all == 7.5."""
    assert get_gap_distribution(fixture_5())["overall_summary"]["avg_gap_all"] == 7.5


def test_overall_max_gap() -> None:
    """AC-12: max_gap_ever=10, max_gap_number=2."""
    summary = get_gap_distribution(fixture_5())["overall_summary"]
    assert summary["max_gap_ever"] == 10
    assert summary["max_gap_number"] == 2


def test_overall_min_gap() -> None:
    """AC-13: min_gap_ever=4, min_gap_number=1."""
    summary = get_gap_distribution(fixture_5())["overall_summary"]
    assert summary["min_gap_ever"] == 4
    assert summary["min_gap_number"] == 1


def test_numbers_length_and_bounds() -> None:
    """AC-14: numbers 길이 45, index0=번호1, index44=번호45."""
    result = get_gap_distribution(fixture_5())
    assert len(result["numbers"]) == 45
    assert result["numbers"][0]["number"] == 1
    assert result["numbers"][44]["number"] == 45


def test_none_data_zero_structure() -> None:
    """AC-15: draws=None → 0 채움 구조."""
    result = get_gap_distribution(None)
    assert result["total_draws"] == 0
    summary = result["overall_summary"]
    assert summary["avg_gap_all"] is None
    assert summary["max_gap_ever"] is None
    assert summary["max_gap_number"] is None
    assert summary["min_gap_ever"] is None
    assert summary["min_gap_number"] is None
    assert len(result["numbers"]) == 45
    for item in result["numbers"]:
        assert item["count"] == 0
        assert item["avg_gap"] is None
        assert item["gap_histogram"] == _EMPTY_HISTOGRAM


def test_empty_list_zero_structure() -> None:
    """AC-16: draws=[] → AC-15와 동일한 0 채움 구조."""
    result = get_gap_distribution([])
    assert result["total_draws"] == 0
    assert result["overall_summary"]["avg_gap_all"] is None
    assert len(result["numbers"]) == 45
    assert result["numbers"][0]["count"] == 0


def test_histogram_bucket_boundaries() -> None:
    """AC-17: 버킷 경계 — gap 50 → "41-50", 51 → "51+", 큰 간격 검증.

    번호 1: drwNo [1, 51, 102] → gaps [50, 51]
      50은 "41-50", 51은 "51+".
    """
    draws = [
        make_draw(1, 1, 2, 3, 4, 5, 6),
        make_draw(51, 1, 7, 8, 9, 10, 11),
        make_draw(102, 1, 12, 13, 14, 15, 16),
    ]
    item = _num(get_gap_distribution(draws), 1)
    assert item["gaps"] == [50, 51]
    assert item["gap_histogram"]["41-50"] == 1
    assert item["gap_histogram"]["51+"] == 1
    assert item["gap_histogram"]["1-10"] == 0


def test_disclaimer_present() -> None:
    """AC-18: disclaimer가 비어 있지 않은 str."""
    disclaimer = get_gap_distribution(fixture_5())["disclaimer"]
    assert isinstance(disclaimer, str)
    assert len(disclaimer) > 0
    assert "예측" in disclaimer


def test_unsorted_input_is_sorted() -> None:
    """draws가 drwNo 역순으로 들어와도 동일 결과(내부 정렬)."""
    ordered = get_gap_distribution(fixture_5())
    reversed_in = get_gap_distribution(list(reversed(fixture_5())))
    assert _num(reversed_in, 1)["gaps"] == _num(ordered, 1)["gaps"]


# ---------------------------------------------------------------------------
# API 통합
# ---------------------------------------------------------------------------


class TestGapDistributionApi:
    """GET /api/stats/gap-distribution."""

    def _client(self) -> TestClient:
        from lotto.web.app import app

        return TestClient(app)

    def test_api_200_and_keys(self) -> None:
        """AC-API-01: 200 + 핵심 키 + numbers 45개."""
        with patch("lotto.web.data.get_draws", return_value=fixture_5()):
            resp = self._client().get("/api/stats/gap-distribution")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) >= {
            "total_draws",
            "overall_summary",
            "numbers",
            "disclaimer",
        }
        assert len(body["numbers"]) == 45

    def test_api_empty_data_200(self) -> None:
        """데이터 부재 시에도 200 (0 채움)."""
        with patch("lotto.web.data.get_draws", return_value=None):
            resp = self._client().get("/api/stats/gap-distribution")
        assert resp.status_code == 200
        assert resp.json()["total_draws"] == 0


# ---------------------------------------------------------------------------
# 페이지 통합
# ---------------------------------------------------------------------------


class TestGapDistributionPage:
    """GET /stats/gap-distribution."""

    def _client(self) -> TestClient:
        from lotto.web.app import app

        return TestClient(app)

    def test_page_200_and_label(self) -> None:
        """AC-PAGE-01: 200 + 제목 렌더링."""
        with patch("lotto.web.data.get_draws", return_value=fixture_5()):
            resp = self._client().get("/stats/gap-distribution")
        assert resp.status_code == 200
        assert "간격" in resp.text

    def test_page_empty_data_200(self) -> None:
        """데이터 부재 시에도 200."""
        with patch("lotto.web.data.get_draws", return_value=None):
            resp = self._client().get("/stats/gap-distribution")
        assert resp.status_code == 200
