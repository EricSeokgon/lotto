"""SPEC-LOTTO-041: 회차 구간 통계 — range_stats() 단위 테스트.

사용자 지정 구간(start_drw ~ end_drw)에 속한 회차만 대상으로
번호 빈도/홀짝/번호대/1등 당첨금 통계를 집계하는 함수를 검증한다.
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
    """4회차 샘플.

    회차 1: 1,2,3,4,5,6      보너스 7   prize=1_000_000_000
    회차 2: 1,10,20,30,40,45 보너스 8   prize=3_000_000_000
    회차 3: 11,12,13,14,15,16 보너스 9  prize=2_000_000_000
    회차 4: 40,41,42,43,44,45 보너스 10 prize=None
    """
    return [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7, 1_000_000_000),
        _mk(2, date(2023, 6, 3), [1, 10, 20, 30, 40, 45], 8, 3_000_000_000),
        _mk(3, date(2024, 1, 6), [11, 12, 13, 14, 15, 16], 9, 2_000_000_000),
        _mk(4, date(2024, 12, 28), [40, 41, 42, 43, 44, 45], 10, None),
    ]


_RANGE_KEYS = {
    "start_drw",
    "end_drw",
    "total_draws",
    "number_frequency",
    "odd_even",
    "range_distribution",
    "avg_prize1",
    "highest_prize1_draw",
    "lowest_prize1_draw",
}


# ---------------------------------------------------------------------------
# AC-1: 정상 구간 집계
# ---------------------------------------------------------------------------


def test_normal_range_total_and_frequency(sample_draws: list[DrawResult]) -> None:
    """구간 1~2: total_draws=2, number_frequency는 1~45 전체 키."""
    from lotto.web.data import range_stats

    result = range_stats(1, 2, sample_draws)
    assert set(result.keys()) == _RANGE_KEYS
    assert result["start_drw"] == 1
    assert result["end_drw"] == 2
    assert result["total_draws"] == 2

    freq = result["number_frequency"]
    assert len(freq) == 45
    assert [item["number"] for item in freq] == list(range(1, 46))

    freq_map = {item["number"]: item["count"] for item in freq}
    # 번호 1: 회차1, 회차2 → 2회
    assert freq_map[1] == 2
    # 번호 45: 회차2만 (회차4는 구간 밖) → 1회
    assert freq_map[45] == 1
    # 번호 11: 회차3은 구간 밖 → 0회
    assert freq_map[11] == 0
    # 보너스 7은 본번호 미집계 → 0회
    assert freq_map[7] == 0


def test_range_filters_out_of_range_draws(sample_draws: list[DrawResult]) -> None:
    """구간 3~4: 회차 1,2는 제외되고 3,4만 집계된다."""
    from lotto.web.data import range_stats

    result = range_stats(3, 4, sample_draws)
    assert result["total_draws"] == 2
    freq_map = {item["number"]: item["count"] for item in result["number_frequency"]}
    # 번호 1은 회차1,2에만 → 구간 3~4에서는 0
    assert freq_map[1] == 0
    # 번호 45는 회차4 → 1
    assert freq_map[45] == 1


def test_odd_even_and_range_distribution_integrity(
    sample_draws: list[DrawResult],
) -> None:
    """홀짝/번호대 분포 합은 total_draws * 6 이다."""
    from lotto.web.data import range_stats

    result = range_stats(1, 3, sample_draws)
    odd_even = result["odd_even"]
    assert odd_even["odd"] + odd_even["even"] == 3 * 6

    rd = result["range_distribution"]
    assert set(rd.keys()) == {"1-9", "10-19", "20-29", "30-39", "40-45"}
    assert sum(rd.values()) == 3 * 6


# ---------------------------------------------------------------------------
# AC-2: 당첨금 통계
# ---------------------------------------------------------------------------


def test_prize_stats_in_range(sample_draws: list[DrawResult]) -> None:
    """구간 1~3: avg/highest/lowest 1등 당첨금이 정확히 산출된다."""
    from lotto.web.data import range_stats

    result = range_stats(1, 3, sample_draws)
    # (1B + 3B + 2B) // 3 = 2B
    assert result["avg_prize1"] == 2_000_000_000
    assert result["highest_prize1_draw"]["drwNo"] == 2
    assert result["highest_prize1_draw"]["prize1Amount"] == 3_000_000_000
    assert result["highest_prize1_draw"]["date"] == "2023-06-03"
    assert result["lowest_prize1_draw"]["drwNo"] == 1
    assert result["lowest_prize1_draw"]["prize1Amount"] == 1_000_000_000


def test_prize_none_excluded_from_avg(sample_draws: list[DrawResult]) -> None:
    """구간 2~4: 회차4(None)는 평균/최고/최저에서 제외된다."""
    from lotto.web.data import range_stats

    result = range_stats(2, 4, sample_draws)
    assert result["total_draws"] == 3
    # 회차2(3B), 회차3(2B) → (3B+2B)//2 = 2.5B
    assert result["avg_prize1"] == 2_500_000_000
    # 회차4(None)는 highest/lowest 후보에서 제외
    assert result["highest_prize1_draw"]["drwNo"] == 2
    assert result["lowest_prize1_draw"]["drwNo"] == 3


# ---------------------------------------------------------------------------
# AC-3: 구간 내 당첨금 데이터 없음
# ---------------------------------------------------------------------------


def test_no_prize_data_in_range() -> None:
    """구간 내 모든 prize1Amount가 None이면 avg/highest/lowest 모두 None."""
    from lotto.web.data import range_stats

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7, None),
        _mk(2, date(2023, 6, 3), [7, 8, 9, 10, 11, 12], 13, None),
    ]
    result = range_stats(1, 2, draws)
    assert result["total_draws"] == 2
    assert result["avg_prize1"] is None
    assert result["highest_prize1_draw"] is None
    assert result["lowest_prize1_draw"] is None


# ---------------------------------------------------------------------------
# AC-4: 역전 구간 (start > end)
# ---------------------------------------------------------------------------


def test_inverted_range_returns_empty_structure(
    sample_draws: list[DrawResult],
) -> None:
    """start > end이면 예외 없이 일관된 빈 구조를 반환한다."""
    from lotto.web.data import range_stats

    result = range_stats(100, 1, sample_draws)
    assert set(result.keys()) == _RANGE_KEYS
    assert result["start_drw"] == 100
    assert result["end_drw"] == 1
    assert result["total_draws"] == 0
    assert all(item["count"] == 0 for item in result["number_frequency"])
    assert result["avg_prize1"] is None
    assert result["highest_prize1_draw"] is None
    assert result["lowest_prize1_draw"] is None
    assert result["odd_even"] == {"odd": 0, "even": 0}


# ---------------------------------------------------------------------------
# AC-5: 매칭 회차 없음
# ---------------------------------------------------------------------------


def test_no_matching_draws_returns_empty_structure(
    sample_draws: list[DrawResult],
) -> None:
    """구간에 해당하는 회차가 없으면 일관된 빈 구조를 반환한다."""
    from lotto.web.data import range_stats

    result = range_stats(50, 100, sample_draws)
    assert result["total_draws"] == 0
    assert len(result["number_frequency"]) == 45
    assert all(item["count"] == 0 for item in result["number_frequency"])
    assert result["avg_prize1"] is None
    assert result["range_distribution"] == {
        "1-9": 0, "10-19": 0, "20-29": 0, "30-39": 0, "40-45": 0,
    }


# ---------------------------------------------------------------------------
# AC-6: 단일 회차 구간
# ---------------------------------------------------------------------------


def test_single_draw_range(sample_draws: list[DrawResult]) -> None:
    """구간 2~2: total_draws=1, 해당 회차 통계가 정확하다."""
    from lotto.web.data import range_stats

    result = range_stats(2, 2, sample_draws)
    assert result["total_draws"] == 1
    freq_map = {item["number"]: item["count"] for item in result["number_frequency"]}
    # 회차2 본번호 1,10,20,30,40,45 각 1회
    for n in (1, 10, 20, 30, 40, 45):
        assert freq_map[n] == 1
    # highest == lowest == 회차2
    assert result["highest_prize1_draw"]["drwNo"] == 2
    assert result["lowest_prize1_draw"]["drwNo"] == 2
    assert result["avg_prize1"] == 3_000_000_000


# ---------------------------------------------------------------------------
# AC-7: None 입력
# ---------------------------------------------------------------------------


def test_none_draws_returns_empty_structure() -> None:
    """draws=None(명시) 전달 시 빈 구조를 반환한다(예외 없음)."""
    from lotto.web.data import range_stats

    result = range_stats(1, 100, None)
    assert set(result.keys()) == _RANGE_KEYS
    assert result["total_draws"] == 0
    assert result["start_drw"] == 1
    assert result["end_drw"] == 100
    assert len(result["number_frequency"]) == 45


def test_no_args_calls_get_draws(monkeypatch: pytest.MonkeyPatch) -> None:
    """draws 인자 생략 시 get_draws()를 자동 호출한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7, 1_000_000_000),
        _mk(2, date(2023, 6, 3), [7, 8, 9, 10, 11, 12], 13, 5_000_000_000),
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    result = wd.range_stats(1, 1)
    assert result["total_draws"] == 1
    assert result["avg_prize1"] == 1_000_000_000


# ---------------------------------------------------------------------------
# AC-8: 결정성
# ---------------------------------------------------------------------------


def test_deterministic(sample_draws: list[DrawResult]) -> None:
    """동일 입력에 대해 반복 호출 시 동일 결과를 반환한다."""
    from lotto.web.data import range_stats

    r1 = range_stats(1, 4, sample_draws)
    r2 = range_stats(1, 4, sample_draws)
    assert r1 == r2
