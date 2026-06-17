"""SPEC-LOTTO-038: 로또 통계 대규모 대시보드 — dashboard_overview() 단위 테스트.

전체 추첨 이력에서 7개 통계 요소를 단일 O(N) 패스로 집계하는 함수를 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest

from lotto.models import DrawResult


def _mk(
    no: int,
    d: date,
    nums: list[int],
    bonus: int,
    prize1: int | None = None,
) -> DrawResult:
    """DrawResult 생성 헬퍼."""
    return DrawResult(
        drwNo=no,
        date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
        prize1Amount=prize1,
    )


@pytest.fixture
def sample_draws() -> list[DrawResult]:
    """4회차 샘플 — 2개 연도(2023, 2024) 분포.

    회차 1 (2023): 1,2,3,4,5,6   보너스 7  prize=1_000_000_000
    회차 2 (2023): 1,10,20,30,40,45  보너스 8  prize=3_000_000_000
    회차 3 (2024): 11,12,13,14,15,16  보너스 9  prize=2_000_000_000
    회차 4 (2024): 41,42,43,44,45,40  보너스 10 prize=None
    """
    return [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7, 1_000_000_000),
        _mk(2, date(2023, 6, 3), [1, 10, 20, 30, 40, 45], 8, 3_000_000_000),
        _mk(3, date(2024, 1, 6), [11, 12, 13, 14, 15, 16], 9, 2_000_000_000),
        _mk(4, date(2024, 12, 28), [40, 41, 42, 43, 44, 45], 10, None),
    ]


# ---------------------------------------------------------------------------
# AC-1: 총 회차 수 + 1등 당첨금 합계
# ---------------------------------------------------------------------------


def test_total_draws_and_prize_sum(sample_draws: list[DrawResult]) -> None:
    """total_draws와 total_prize1_sum이 올바르게 집계된다 (None 제외)."""
    from lotto.web.data import dashboard_overview

    result = dashboard_overview(sample_draws)
    assert result["total_draws"] == 4
    # 1_000_000_000 + 3_000_000_000 + 2_000_000_000 (회차4는 None → 제외)
    assert result["total_prize1_sum"] == 6_000_000_000


# ---------------------------------------------------------------------------
# AC-2: number_frequency (보너스 제외, 1~45 전체 키)
# ---------------------------------------------------------------------------


def test_number_frequency_all_keys_present(sample_draws: list[DrawResult]) -> None:
    """number_frequency는 1~45 전체를 번호 오름차순으로 포함한다."""
    from lotto.web.data import dashboard_overview

    result = dashboard_overview(sample_draws)
    freq = result["number_frequency"]
    assert len(freq) == 45
    assert [item["number"] for item in freq] == list(range(1, 46))


def test_number_frequency_counts_exclude_bonus(sample_draws: list[DrawResult]) -> None:
    """본번호만 집계하고 보너스 번호는 빈도에 포함하지 않는다."""
    from lotto.web.data import dashboard_overview

    result = dashboard_overview(sample_draws)
    freq_map = {item["number"]: item["count"] for item in result["number_frequency"]}
    # 번호 1: 회차1, 회차2 → 2회 (본번호)
    assert freq_map[1] == 2
    # 번호 45: 회차2, 회차4 → 2회
    assert freq_map[45] == 2
    # 번호 40: 회차2, 회차4 → 2회
    assert freq_map[40] == 2
    # 보너스 7은 본번호로는 회차1에만 (n4) → 1회. 보너스로 출현한 것은 미집계 확인:
    # 회차1 본번호 1,2,3,4,5,6 중 7 없음 → 보너스 7 미집계 → count 0
    assert freq_map[7] == 0
    # 번호 8(회차2 보너스)도 본번호로는 없음 → 0
    assert freq_map[8] == 0


# ---------------------------------------------------------------------------
# AC-3: 최고/최저 1등 당첨금 회차
# ---------------------------------------------------------------------------


def test_highest_lowest_prize_draw(sample_draws: list[DrawResult]) -> None:
    """highest/lowest prize1 회차가 올바르게 식별된다."""
    from lotto.web.data import dashboard_overview

    result = dashboard_overview(sample_draws)
    highest = result["highest_prize1_draw"]
    lowest = result["lowest_prize1_draw"]
    assert highest["drwNo"] == 2
    assert highest["prize1Amount"] == 3_000_000_000
    assert highest["date"] == "2023-06-03"
    assert lowest["drwNo"] == 1
    assert lowest["prize1Amount"] == 1_000_000_000
    assert lowest["date"] == "2023-01-07"


# ---------------------------------------------------------------------------
# AC-4: 모든 prize None
# ---------------------------------------------------------------------------


def test_all_prize_none() -> None:
    """모든 prize1Amount가 None이면 sum=0, highest=None, lowest=None."""
    from lotto.web.data import dashboard_overview

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7, None),
        _mk(2, date(2023, 6, 3), [7, 8, 9, 10, 11, 12], 13, None),
    ]
    result = dashboard_overview(draws)
    assert result["total_draws"] == 2
    assert result["total_prize1_sum"] == 0
    assert result["highest_prize1_draw"] is None
    assert result["lowest_prize1_draw"] is None


# ---------------------------------------------------------------------------
# AC-5: 홀짝 / 범위 분포 합계 무결성
# ---------------------------------------------------------------------------


def test_odd_even_sum_equals_total_numbers(sample_draws: list[DrawResult]) -> None:
    """odd + even 합은 total_draws * 6 이다."""
    from lotto.web.data import dashboard_overview

    result = dashboard_overview(sample_draws)
    odd_even = result["odd_even"]
    assert odd_even["odd"] + odd_even["even"] == 4 * 6


def test_range_distribution_sum_equals_total_numbers(
    sample_draws: list[DrawResult],
) -> None:
    """range_distribution 모든 구간 합은 total_draws * 6 이다."""
    from lotto.web.data import dashboard_overview

    result = dashboard_overview(sample_draws)
    rd = result["range_distribution"]
    assert set(rd.keys()) == {"1-9", "10-19", "20-29", "30-39", "40-45"}
    assert sum(rd.values()) == 4 * 6


def test_odd_even_concrete_counts(sample_draws: list[DrawResult]) -> None:
    """홀짝 카운트 구체값 검증."""
    from lotto.web.data import dashboard_overview

    result = dashboard_overview(sample_draws)
    # 회차1: 1,3,5 홀(3), 2,4,6 짝(3)
    # 회차2: 1,45 홀(2), 10,20,30,40 짝(4)
    # 회차3: 11,13,15 홀(3), 12,14,16 짝(3)
    # 회차4: 41,43,45 홀(3), 40,42,44 짝(3)
    # 홀 합 = 3+2+3+3 = 11, 짝 합 = 3+4+3+3 = 13
    assert result["odd_even"]["odd"] == 11
    assert result["odd_even"]["even"] == 13


# ---------------------------------------------------------------------------
# AC-6: 연도별 평균 당첨금
# ---------------------------------------------------------------------------


def test_yearly_avg_prize_ascending_and_values(
    sample_draws: list[DrawResult],
) -> None:
    """yearly_avg_prize는 연도 오름차순이며 연도별 평균/회차 수가 정확하다."""
    from lotto.web.data import dashboard_overview

    result = dashboard_overview(sample_draws)
    yearly = result["yearly_avg_prize"]
    assert [y["year"] for y in yearly] == ["2023", "2024"]

    y2023 = yearly[0]
    # 2023: 회차1(1B) + 회차2(3B) → 평균 2B, draws=2
    assert y2023["year"] == "2023"
    assert y2023["avg_prize1"] == 2_000_000_000
    assert y2023["draws"] == 2

    y2024 = yearly[1]
    # 2024: 회차3(2B), 회차4(None) → prize 있는 1건만 평균 → 2B, draws는 연도 총 회차 2
    assert y2024["year"] == "2024"
    assert y2024["avg_prize1"] == 2_000_000_000
    assert y2024["draws"] == 2


# ---------------------------------------------------------------------------
# AC-6b: 빈 리스트
# ---------------------------------------------------------------------------


def test_empty_list_returns_zero_structure() -> None:
    """빈 리스트는 예외 없이 일관된 0 구조를 반환한다."""
    from lotto.web.data import dashboard_overview

    result = dashboard_overview([])
    assert result["total_draws"] == 0
    assert result["total_prize1_sum"] == 0
    assert len(result["number_frequency"]) == 45
    assert all(item["count"] == 0 for item in result["number_frequency"])
    assert result["highest_prize1_draw"] is None
    assert result["lowest_prize1_draw"] is None
    assert result["odd_even"] == {"odd": 0, "even": 0}
    assert result["range_distribution"] == {
        "1-9": 0, "10-19": 0, "20-29": 0, "30-39": 0, "40-45": 0,
    }
    assert result["yearly_avg_prize"] == []


def test_none_returns_zero_structure() -> None:
    """draws가 None(명시적)이어도 빈 구조를 반환한다."""
    from lotto.web.data import dashboard_overview

    result = dashboard_overview(None)
    assert result["total_draws"] == 0
    assert result["yearly_avg_prize"] == []


# ---------------------------------------------------------------------------
# AC-6c: 인자 미전달 시 get_draws() 자동 호출
# ---------------------------------------------------------------------------


def test_no_args_calls_get_draws(monkeypatch: pytest.MonkeyPatch) -> None:
    """인자 생략 시 get_draws()를 자동 호출한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7, 1_000_000_000),
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    result = wd.dashboard_overview()
    assert result["total_draws"] == 1
    assert result["total_prize1_sum"] == 1_000_000_000


# ---------------------------------------------------------------------------
# Edge: 단일 회차 (min == max, highest == lowest)
# ---------------------------------------------------------------------------


def test_single_draw_min_equals_max() -> None:
    """단일 회차에서 highest와 lowest가 동일 회차를 가리킨다."""
    from lotto.web.data import dashboard_overview

    draws = [_mk(5, date(2024, 3, 2), [1, 2, 3, 4, 5, 6], 7, 5_000_000_000)]
    result = dashboard_overview(draws)
    assert result["highest_prize1_draw"]["drwNo"] == 5
    assert result["lowest_prize1_draw"]["drwNo"] == 5
    assert result["highest_prize1_draw"]["prize1Amount"] == 5_000_000_000
    assert result["lowest_prize1_draw"]["prize1Amount"] == 5_000_000_000


# ---------------------------------------------------------------------------
# Edge: 동률 타이브레이크 — 낮은 drwNo 우선
# ---------------------------------------------------------------------------


def test_tie_break_lower_drw_no_wins() -> None:
    """prize 동률 시 highest/lowest 모두 낮은 drwNo가 선택된다."""
    from lotto.web.data import dashboard_overview

    draws = [
        _mk(3, date(2024, 1, 6), [1, 2, 3, 4, 5, 6], 7, 2_000_000_000),
        _mk(1, date(2024, 1, 20), [7, 8, 9, 10, 11, 12], 13, 2_000_000_000),
        _mk(2, date(2024, 2, 3), [14, 15, 16, 17, 18, 19], 20, 2_000_000_000),
    ]
    result = dashboard_overview(draws)
    # 모두 동일 prize → 낮은 drwNo(1)가 highest와 lowest 양쪽에 선택됨
    assert result["highest_prize1_draw"]["drwNo"] == 1
    assert result["lowest_prize1_draw"]["drwNo"] == 1


# ---------------------------------------------------------------------------
# Edge: prize None 섞임 — None은 highest/lowest/합계에서 제외, 빈도/홀짝엔 포함
# ---------------------------------------------------------------------------


def test_mixed_none_prize(sample_draws: list[DrawResult]) -> None:
    """일부 회차 prize None — 합계/highest/lowest에서 제외되지만 빈도 집계는 유지."""
    from lotto.web.data import dashboard_overview

    result = dashboard_overview(sample_draws)
    # 회차4 (prize None) 의 번호도 빈도에는 포함된다
    freq_map = {item["number"]: item["count"] for item in result["number_frequency"]}
    # 번호 41,42,43,44 는 회차4에만 출현 → 각 1회
    assert freq_map[41] == 1
    assert freq_map[42] == 1
    assert freq_map[43] == 1
    assert freq_map[44] == 1
    # highest/lowest는 None인 회차4를 제외
    assert result["highest_prize1_draw"]["drwNo"] != 4
    assert result["lowest_prize1_draw"]["drwNo"] != 4
