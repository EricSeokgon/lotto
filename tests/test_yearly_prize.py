"""SPEC-LOTTO-046: 당첨금 연도별 비교 — yearly_prize_comparison() 단위 테스트.

연도별로 1등 당첨금 통계(평균/최대/최소/당첨자 합계)를 집계하고,
최고/최저 평균 연도를 산출하는 함수를 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest

from lotto.models import DrawResult

_TOP_KEYS = {
    "total_years",
    "overall_avg_prize1",
    "highest_avg_year",
    "lowest_avg_year",
    "years",
}
_YEAR_KEYS = {
    "year",
    "total_draws",
    "prize_draws",
    "avg_prize1",
    "max_prize1",
    "min_prize1",
    "total_winners",
}


def _mk(
    no: int,
    d: date,
    nums: list[int],
    bonus: int,
    prize: int | None = None,
    winners: int | None = None,
) -> DrawResult:
    """DrawResult 생성 헬퍼 (당첨금/당첨자 수는 선택)."""
    return DrawResult(
        drwNo=no, date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
        prize1Amount=prize, prize1Winners=winners,
    )


def _multi_year_draws() -> list[DrawResult]:
    """2개 연도, 연도별 2회차 픽스처.

    2022: 1000, 3000  → avg 2000, max 3000, min 1000, winners 1+3=4
    2023: 5000, 9000  → avg 7000, max 9000, min 5000, winners 2+2=4
    """
    nums = [1, 10, 20, 30, 40, 45]
    return [
        _mk(1, date(2022, 1, 1), nums, 5, prize=1000, winners=1),
        _mk(2, date(2022, 6, 1), nums, 5, prize=3000, winners=3),
        _mk(3, date(2023, 1, 1), nums, 5, prize=5000, winners=2),
        _mk(4, date(2023, 6, 1), nums, 5, prize=9000, winners=2),
    ]


# ---------------------------------------------------------------------------
# AC-1: 연도별 avg/max/min 정확성 + 연도 오름차순
# ---------------------------------------------------------------------------


def test_per_year_stats_and_ascending_order() -> None:
    """연도별 avg/max/min이 정확하고, years는 연도 오름차순이다."""
    from lotto.web.data import yearly_prize_comparison

    result = yearly_prize_comparison(_multi_year_draws())

    assert set(result.keys()) == _TOP_KEYS
    assert result["total_years"] == 2
    years = result["years"]
    assert [y["year"] for y in years] == ["2022", "2023"]
    for y in years:
        assert set(y.keys()) == _YEAR_KEYS

    by_year = {y["year"]: y for y in years}
    assert by_year["2022"]["avg_prize1"] == 2000
    assert by_year["2022"]["max_prize1"] == 3000
    assert by_year["2022"]["min_prize1"] == 1000
    assert by_year["2023"]["avg_prize1"] == 7000
    assert by_year["2023"]["max_prize1"] == 9000
    assert by_year["2023"]["min_prize1"] == 5000


# ---------------------------------------------------------------------------
# AC-2: overall_avg_prize1 — 전체 prize 보유 회차 평균
# ---------------------------------------------------------------------------


def test_overall_avg_prize1() -> None:
    """overall_avg_prize1은 prize 보유 전체 회차 평균(floor)이다."""
    from lotto.web.data import yearly_prize_comparison

    result = yearly_prize_comparison(_multi_year_draws())
    # (1000+3000+5000+9000)/4 = 4500
    assert result["overall_avg_prize1"] == 4500


# ---------------------------------------------------------------------------
# AC-3: highest_avg_year / lowest_avg_year
# ---------------------------------------------------------------------------


def test_highest_and_lowest_avg_year() -> None:
    """highest/lowest_avg_year가 평균이 가장 높은/낮은 연도를 가리킨다."""
    from lotto.web.data import yearly_prize_comparison

    result = yearly_prize_comparison(_multi_year_draws())
    assert result["highest_avg_year"] == "2023"
    assert result["lowest_avg_year"] == "2022"


# ---------------------------------------------------------------------------
# AC-4: prize 데이터 없는 연도 → avg/max/min = 0, prize_draws = 0
# ---------------------------------------------------------------------------


def test_year_without_prize_data() -> None:
    """prize 데이터가 없는 연도는 avg/max/min=0, prize_draws=0이다."""
    from lotto.web.data import yearly_prize_comparison

    nums = [1, 10, 20, 30, 40, 45]
    draws = [
        # 2021: prize 없음 (2회)
        _mk(1, date(2021, 1, 1), nums, 5),
        _mk(2, date(2021, 6, 1), nums, 5),
        # 2022: prize 있음
        _mk(3, date(2022, 1, 1), nums, 5, prize=2000, winners=1),
    ]
    result = yearly_prize_comparison(draws)
    by_year = {y["year"]: y for y in result["years"]}

    assert by_year["2021"]["avg_prize1"] == 0
    assert by_year["2021"]["max_prize1"] == 0
    assert by_year["2021"]["min_prize1"] == 0
    assert by_year["2021"]["prize_draws"] == 0
    # highest/lowest는 prize 보유 연도만 대상 → 둘 다 2022
    assert result["highest_avg_year"] == "2022"
    assert result["lowest_avg_year"] == "2022"


# ---------------------------------------------------------------------------
# AC-5: total_draws는 연도 내 모든 회차 (prize 유무 무관)
# ---------------------------------------------------------------------------


def test_total_draws_counts_all_in_year() -> None:
    """total_draws는 연도 내 prize 유무와 무관한 전체 회차 수이다."""
    from lotto.web.data import yearly_prize_comparison

    nums = [1, 10, 20, 30, 40, 45]
    draws = [
        _mk(1, date(2022, 1, 1), nums, 5, prize=1000, winners=1),
        _mk(2, date(2022, 3, 1), nums, 5),  # prize 없음
        _mk(3, date(2022, 6, 1), nums, 5, prize=3000, winners=2),
    ]
    result = yearly_prize_comparison(draws)
    y2022 = result["years"][0]
    assert y2022["total_draws"] == 3
    assert y2022["prize_draws"] == 2
    # avg는 prize 보유 2회만 → (1000+3000)/2 = 2000
    assert y2022["avg_prize1"] == 2000


# ---------------------------------------------------------------------------
# AC-6: total_winners — prize1Winners 합계 (없으면 0)
# ---------------------------------------------------------------------------


def test_total_winners_sums_prize1_winners() -> None:
    """total_winners는 연도 내 prize1Winners 합계이며, None은 0으로 친다."""
    from lotto.web.data import yearly_prize_comparison

    nums = [1, 10, 20, 30, 40, 45]
    draws = [
        _mk(1, date(2022, 1, 1), nums, 5, prize=1000, winners=3),
        _mk(2, date(2022, 6, 1), nums, 5, prize=2000, winners=None),  # winners 누락
    ]
    result = yearly_prize_comparison(draws)
    y2022 = result["years"][0]
    assert y2022["total_winners"] == 3


# ---------------------------------------------------------------------------
# AC-7: 빈 리스트 → 빈 구조
# ---------------------------------------------------------------------------


def test_empty_draws_returns_empty_structure() -> None:
    """draws=[] → 일관된 빈 구조, 예외 없음."""
    from lotto.web.data import yearly_prize_comparison

    result = yearly_prize_comparison([])
    assert set(result.keys()) == _TOP_KEYS
    assert result["total_years"] == 0
    assert result["overall_avg_prize1"] == 0
    assert result["highest_avg_year"] is None
    assert result["lowest_avg_year"] is None
    assert result["years"] == []


# ---------------------------------------------------------------------------
# AC-8: None draws → 빈 구조
# ---------------------------------------------------------------------------


def test_none_draws_returns_empty_structure() -> None:
    """draws=None(명시) → 빈 구조, 예외 없음."""
    from lotto.web.data import yearly_prize_comparison

    result = yearly_prize_comparison(None)
    assert set(result.keys()) == _TOP_KEYS
    assert result["total_years"] == 0
    assert result["overall_avg_prize1"] == 0
    assert result["highest_avg_year"] is None
    assert result["lowest_avg_year"] is None
    assert result["years"] == []


# ---------------------------------------------------------------------------
# AC-9: 결정론 — 동일 입력 2회 → 동일 출력
# ---------------------------------------------------------------------------


def test_deterministic_output() -> None:
    """동일 입력으로 2회 호출 시 결과가 동일하다."""
    from lotto.web.data import yearly_prize_comparison

    draws = _multi_year_draws()
    assert yearly_prize_comparison(draws) == yearly_prize_comparison(draws)


def test_no_args_calls_get_draws(monkeypatch: pytest.MonkeyPatch) -> None:
    """draws 인자 생략 시 get_draws()를 자동 호출한다."""
    from lotto.web import data as wd

    draws = _multi_year_draws()
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    result = wd.yearly_prize_comparison()
    assert result["total_years"] == 2
    assert result["overall_avg_prize1"] == 4500
