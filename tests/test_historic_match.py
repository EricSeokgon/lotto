"""SPEC-LOTTO-114: 역대 당첨 일치 이력 조회 테스트.

입력한 6개 번호가 역대 회차에서 얼마나 일치했는지 분석한다.
- 주번호 6개 일치 → 1등
- 주번호 5개 + 보너스 → 2등
- 주번호 5개 → 3등
- 주번호 4개 → 4등
- 주번호 3개 → 5등
- 주번호 2개 이상 → results 리스트에 포함
- 주번호 1개 이하 → results 리스트에 미포함

Fixture:
| drwNo | 본번호                  | 보너스 |
|-------|-------------------------|--------|
| 1     | 1, 2, 3, 4, 5, 6        | 7      |
| 2     | 1, 2, 3, 4, 5, 10       | 6      |  # 5+보너스(6)
| 3     | 1, 2, 3, 4, 10, 11      | 5      |  # 4일치
| 4     | 1, 2, 3, 10, 11, 12     | 30     |  # 3일치
| 5     | 1, 2, 10, 11, 12, 13    | 30     |  # 2일치
| 6     | 1, 10, 11, 12, 13, 14   | 30     |  # 1일치
| 7     | 10, 11, 12, 13, 14, 15  | 30     |  # 0일치

입력 번호: [1, 2, 3, 4, 5, 6]
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.data import get_historic_match

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

INPUT_NUMS = [1, 2, 3, 4, 5, 6]


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


def fixture_draws() -> list[DrawResult]:
    """SPEC-LOTTO-114 픽스처 — 7회차."""
    return [
        make_draw(1, 1, 2, 3, 4, 5, 6, bonus=7),    # 1등 (6개 일치)
        make_draw(2, 1, 2, 3, 4, 5, 10, bonus=6),   # 2등 (5+보너스 6)
        make_draw(3, 1, 2, 3, 4, 10, 11, bonus=5),  # 3등 (5개, 보너스 5 미일치 — 5가 본번호에 없음)
        make_draw(4, 1, 2, 3, 10, 11, 12, bonus=30),  # 4등 (4개)
        make_draw(5, 1, 2, 10, 11, 12, 13, bonus=30),  # 5등 (3개)
        make_draw(6, 1, 10, 11, 12, 13, 14, bonus=30),  # 해당없음 (2개 → results 포함)
        make_draw(7, 10, 11, 12, 13, 14, 15, bonus=30),  # 해당없음 (0개 → results 미포함)
    ]


# ---------------------------------------------------------------------------
# 단위 테스트 (data layer)
# ---------------------------------------------------------------------------


def test_get_historic_match_none_draws() -> None:
    """AC-01: draws=None → None 반환."""
    result = get_historic_match(INPUT_NUMS, None)
    assert result is None


def test_get_historic_match_empty_draws() -> None:
    """AC-02: draws=[] → None 반환."""
    result = get_historic_match(INPUT_NUMS, [])
    assert result is None


def test_get_historic_match_wrong_count() -> None:
    """AC-03: 번호가 6개가 아니면 None 반환."""
    draws = fixture_draws()
    assert get_historic_match([1, 2, 3, 4, 5], draws) is None
    assert get_historic_match([1, 2, 3, 4, 5, 6, 7], draws) is None
    assert get_historic_match([], draws) is None


def test_get_historic_match_rank_1() -> None:
    """AC-04: 주번호 6개 일치 → rank=1."""
    draws = [make_draw(1, 1, 2, 3, 4, 5, 6, bonus=7)]
    result = get_historic_match(INPUT_NUMS, draws)
    assert result is not None
    assert result["rank_counts"][1] == 1
    assert len(result["results"]) == 1
    assert result["results"][0]["rank"] == 1


def test_get_historic_match_rank_2() -> None:
    """AC-05: 주번호 5개 + 보너스 일치 → rank=2."""
    draws = [make_draw(1, 1, 2, 3, 4, 5, 10, bonus=6)]
    result = get_historic_match(INPUT_NUMS, draws)
    assert result is not None
    assert result["rank_counts"][2] == 1
    assert result["results"][0]["rank"] == 2
    assert result["results"][0]["bonus_match"] is True


def test_get_historic_match_rank_3() -> None:
    """AC-06: 주번호 5개, 보너스 불일치 → rank=3."""
    # 입력번호=[1,2,3,4,5,6], 본번호=[1,2,3,4,5,10], 보너스=7 (not in 입력)
    draws = [make_draw(1, 1, 2, 3, 4, 5, 10, bonus=7)]
    result = get_historic_match(INPUT_NUMS, draws)
    assert result is not None
    assert result["rank_counts"][3] == 1
    assert result["results"][0]["rank"] == 3
    assert result["results"][0]["bonus_match"] is False


def test_get_historic_match_rank_4() -> None:
    """AC-07: 주번호 4개 일치 → rank=4."""
    draws = [make_draw(1, 1, 2, 3, 4, 10, 11, bonus=30)]
    result = get_historic_match(INPUT_NUMS, draws)
    assert result is not None
    assert result["rank_counts"][4] == 1
    assert result["results"][0]["rank"] == 4


def test_get_historic_match_rank_5() -> None:
    """AC-08: 주번호 3개 일치 → rank=5, results에 포함."""
    draws = [make_draw(1, 1, 2, 3, 10, 11, 12, bonus=30)]
    result = get_historic_match(INPUT_NUMS, draws)
    assert result is not None
    assert result["rank_counts"][5] == 1
    assert len(result["results"]) == 1
    assert result["results"][0]["main_match"] == 3


def test_get_historic_match_2_main_no_prize() -> None:
    """AC-09: 주번호 2개 일치 → rank=0, results에 포함."""
    draws = [make_draw(1, 1, 2, 10, 11, 12, 13, bonus=30)]
    result = get_historic_match(INPUT_NUMS, draws)
    assert result is not None
    assert result["rank_counts"][0] == 1
    assert len(result["results"]) == 1
    assert result["results"][0]["main_match"] == 2
    assert result["results"][0]["rank"] == 0


def test_get_historic_match_1_match_excluded() -> None:
    """AC-10: 주번호 1개 일치 → results에 미포함."""
    draws = [make_draw(1, 1, 10, 11, 12, 13, 14, bonus=30)]
    result = get_historic_match(INPUT_NUMS, draws)
    assert result is not None
    assert len(result["results"]) == 0
    assert result["rank_counts"][0] == 1
    assert result["main_match_dist"][1] == 1


def test_get_historic_match_0_match_excluded() -> None:
    """AC-11: 주번호 0개 일치 → results에 미포함."""
    draws = [make_draw(1, 10, 11, 12, 13, 14, 15, bonus=30)]
    result = get_historic_match(INPUT_NUMS, draws)
    assert result is not None
    assert len(result["results"]) == 0
    assert result["main_match_dist"][0] == 1


def test_get_historic_match_summary_fields() -> None:
    """AC-12: 결과 딕셔너리에 필수 필드가 모두 포함된다."""
    result = get_historic_match(INPUT_NUMS, fixture_draws())
    assert result is not None
    required_keys = {
        "input_numbers", "total_draws", "rank_counts",
        "main_match_dist", "results", "results_total",
    }
    assert required_keys.issubset(result.keys())
    assert result["input_numbers"] == sorted(INPUT_NUMS)
    assert result["total_draws"] == 7
    # rank_counts 키: 0~5
    for rank in range(6):
        assert rank in result["rank_counts"]
    # main_match_dist 키: 0~6
    for m in range(7):
        assert m in result["main_match_dist"]


def test_get_historic_match_sorted_order() -> None:
    """AC-13: results는 main_match 내림차순, 동률은 drwNo 내림차순 정렬."""
    draws = fixture_draws()
    result = get_historic_match(INPUT_NUMS, draws)
    assert result is not None
    items = result["results"]
    # main_match 내림차순
    for i in range(len(items) - 1):
        assert items[i]["main_match"] >= items[i + 1]["main_match"]
    # 동일 main_match 내에서 drwNo 내림차순
    prev = None
    for item in items:
        if prev is not None and item["main_match"] == prev["main_match"]:
            assert item["drwNo"] <= prev["drwNo"]
        prev = item


# ---------------------------------------------------------------------------
# API 테스트
# ---------------------------------------------------------------------------


class TestApiHistoricMatchValid:
    """AC-14: /api/stats/historic-match?numbers=1,2,3,4,5,6 → 200."""

    def _client(self) -> TestClient:
        from lotto.web.app import app
        return TestClient(app)

    def test_valid_6_numbers(self) -> None:
        """유효한 6개 번호로 요청 시 200 반환."""
        draws = fixture_draws()
        with patch("lotto.web.data.get_draws", return_value=draws):
            resp = self._client().get("/api/stats/historic-match?numbers=1,2,3,4,5,6")
        assert resp.status_code == 200
        data = resp.json()
        assert "input_numbers" in data
        assert "total_draws" in data
        assert "rank_counts" in data
        assert "results" in data


class TestApiHistoricMatchWrongCount:
    """AC-15: 번호가 6개 미만/초과 시 422."""

    def _client(self) -> TestClient:
        from lotto.web.app import app
        return TestClient(app)

    def test_5_numbers(self) -> None:
        """5개 번호 → 422."""
        resp = self._client().get("/api/stats/historic-match?numbers=1,2,3,4,5")
        assert resp.status_code == 422

    def test_7_numbers(self) -> None:
        """7개 번호 → 422."""
        resp = self._client().get("/api/stats/historic-match?numbers=1,2,3,4,5,6,7")
        assert resp.status_code == 422


class TestApiHistoricMatchOutOfRange:
    """AC-16: 범위를 벗어난 번호(0 또는 46) 시 422."""

    def _client(self) -> TestClient:
        from lotto.web.app import app
        return TestClient(app)

    def test_number_0(self) -> None:
        """번호 0 포함 → 422."""
        resp = self._client().get("/api/stats/historic-match?numbers=0,2,3,4,5,6")
        assert resp.status_code == 422

    def test_number_46(self) -> None:
        """번호 46 포함 → 422."""
        resp = self._client().get("/api/stats/historic-match?numbers=1,2,3,4,5,46")
        assert resp.status_code == 422


class TestApiHistoricMatchDuplicate:
    """AC-17: 중복 번호 시 422."""

    def _client(self) -> TestClient:
        from lotto.web.app import app
        return TestClient(app)

    def test_duplicate_numbers(self) -> None:
        """중복 번호(1,1,...) → 422."""
        resp = self._client().get("/api/stats/historic-match?numbers=1,1,3,4,5,6")
        assert resp.status_code == 422
