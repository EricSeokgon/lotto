"""SPEC-LOTTO-047: 번호별 당첨 주기 분석 — cycle_analysis() 단위 테스트.

전체 회차에 대해 번호 1~45의 평균 출현 주기(avg_cycle)와 현재 간격(current_gap)을
산출하고, overdue/frequent/normal/never 상태로 분류하는 함수를 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest

from lotto.models import DrawResult

_TOP_KEYS = {"total_draws", "numbers", "most_overdue", "summary"}
_NUM_KEYS = {
    "number",
    "appearances",
    "avg_cycle",
    "last_appeared_drwNo",
    "current_gap",
    "status",
}
_SUMMARY_KEYS = {"overdue", "frequent", "normal", "never"}


def _mk(no: int, d: date, nums: list[int], bonus: int) -> DrawResult:
    """DrawResult 생성 헬퍼."""
    return DrawResult(
        drwNo=no, date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


def _fixture_draws() -> list[DrawResult]:
    """5회차 픽스처 (시간순).

    회차 1: 1, 2, 3, 4, 5, 6
    회차 2: 1, 2, 3, 4, 5, 7
    회차 3: 1, 2, 3, 4, 8, 9
    회차 4: 1, 2, 3, 10, 11, 12
    회차 5: 1, 2, 13, 14, 15, 16

    번호 1: 5회 출현(전 회차), 마지막 회차 5 → current_gap 0
    번호 6: 1회 출현(회차 1), 마지막 회차 1 → current_gap 4
    번호 13: 1회 출현(회차 5) → current_gap 0
    번호 45: 미출현 → never
    """
    return [
        _mk(1, date(2020, 1, 1), [1, 2, 3, 4, 5, 6], 45),
        _mk(2, date(2020, 1, 8), [1, 2, 3, 4, 5, 7], 44),
        _mk(3, date(2020, 1, 15), [1, 2, 3, 4, 8, 9], 43),
        _mk(4, date(2020, 1, 22), [1, 2, 3, 10, 11, 12], 42),
        _mk(5, date(2020, 1, 29), [1, 2, 13, 14, 15, 16], 41),
    ]


# ---------------------------------------------------------------------------
# AC-1: numbers는 정확히 45개, 번호 오름차순 1~45
# ---------------------------------------------------------------------------


def test_numbers_has_45_entries_ascending() -> None:
    """numbers는 정확히 45개이며 번호 1~45 오름차순이다."""
    from lotto.web.data import cycle_analysis

    result = cycle_analysis(_fixture_draws())
    assert set(result.keys()) == _TOP_KEYS
    numbers = result["numbers"]
    assert len(numbers) == 45
    assert [n["number"] for n in numbers] == list(range(1, 46))
    for n in numbers:
        assert set(n.keys()) == _NUM_KEYS


# ---------------------------------------------------------------------------
# AC-2: appearances / avg_cycle 정확성
# ---------------------------------------------------------------------------


def test_appearances_and_avg_cycle() -> None:
    """appearances와 avg_cycle(total_draws/appearances)이 정확하다."""
    from lotto.web.data import cycle_analysis

    result = cycle_analysis(_fixture_draws())
    by_num = {n["number"]: n for n in result["numbers"]}

    assert result["total_draws"] == 5
    # 번호 1: 5회 출현 → avg_cycle 5/5 = 1.0
    assert by_num[1]["appearances"] == 5
    assert by_num[1]["avg_cycle"] == 1.0
    # 번호 6: 1회 출현 → avg_cycle 5/1 = 5.0
    assert by_num[6]["appearances"] == 1
    assert by_num[6]["avg_cycle"] == 5.0
    # 번호 4: 3회 출현(회차 1,2,3) → avg_cycle 5/3 = 1.67
    assert by_num[4]["appearances"] == 3
    assert by_num[4]["avg_cycle"] == 1.67


# ---------------------------------------------------------------------------
# AC-3: current_gap 정확성 (최신 회차 출현 시 0)
# ---------------------------------------------------------------------------


def test_current_gap() -> None:
    """current_gap이 마지막 출현 이후 경과 회차 수와 일치한다."""
    from lotto.web.data import cycle_analysis

    result = cycle_analysis(_fixture_draws())
    by_num = {n["number"]: n for n in result["numbers"]}

    # 번호 1: 최신 회차(5)에 출현 → current_gap 0
    assert by_num[1]["current_gap"] == 0
    assert by_num[1]["last_appeared_drwNo"] == 5
    # 번호 13: 최신 회차(5)에 처음 출현 → current_gap 0
    assert by_num[13]["current_gap"] == 0
    # 번호 6: 회차 1에만 출현, 이후 4회차 동안 미출현 → current_gap 4
    assert by_num[6]["current_gap"] == 4
    assert by_num[6]["last_appeared_drwNo"] == 1
    # 번호 4: 회차 3에 마지막 출현 → current_gap 2
    assert by_num[4]["current_gap"] == 2


# ---------------------------------------------------------------------------
# AC-4: status 분류 — overdue / frequent / normal
# ---------------------------------------------------------------------------


def test_status_classification() -> None:
    """status가 current_gap vs avg_cycle 비교로 정확히 분류된다."""
    from lotto.web.data import cycle_analysis

    result = cycle_analysis(_fixture_draws())
    by_num = {n["number"]: n for n in result["numbers"]}

    # 번호 1: gap 0 < cycle 1.0 → frequent
    assert by_num[1]["status"] == "frequent"
    # 번호 6: gap 4 < cycle 5.0 → frequent
    assert by_num[6]["status"] == "frequent"
    # 번호 3: 회차 1~4 출현(4회), 마지막 회차 4(idx 3) → avg_cycle 5/4=1.25,
    #   current_gap = 4-3 = 1 → |1 - 1.25| = 0.25 <= 0.5 → normal
    assert by_num[3]["avg_cycle"] == 1.25
    assert by_num[3]["current_gap"] == 1
    assert by_num[3]["status"] == "normal"


def test_status_normal_within_half() -> None:
    """status가 normal인 번호는 |current_gap - avg_cycle| <= 0.5를 만족한다."""
    from lotto.web.data import cycle_analysis

    result = cycle_analysis(_fixture_draws())
    # normal 판정 불변식: 차가 0.5 이내이며 출현 이력이 존재
    normal_found = False
    for n in result["numbers"]:
        if n["status"] == "normal":
            normal_found = True
            assert abs(n["current_gap"] - n["avg_cycle"]) <= 0.5
            assert n["appearances"] > 0
    assert normal_found  # 픽스처에 normal 번호가 최소 1개 존재


def test_status_normal_exact_match() -> None:
    """current_gap == avg_cycle인 번호는 normal로 분류된다."""
    from lotto.web.data import cycle_analysis

    # 번호 6: 회차 1, 2 출현(2회). total=4 → avg_cycle 4/2=2.0.
    #   마지막 출현 회차 2(idx 1) → current_gap = (4-1)-1 = 2 → 2 == 2.0 → normal
    draws = [
        _mk(1, date(2020, 1, 1), [1, 2, 3, 4, 5, 6], 45),
        _mk(2, date(2020, 1, 8), [6, 7, 8, 9, 10, 11], 44),
        _mk(3, date(2020, 1, 15), [20, 21, 22, 23, 24, 25], 43),
        _mk(4, date(2020, 1, 22), [30, 31, 32, 33, 34, 35], 42),
    ]
    # 번호 6: 회차 1, 2 출현. total=4 → avg_cycle 4/2=2.0
    #   마지막 출현 회차 2 (index 1) → current_gap = (4-1) - 1 = 2 → 2 == 2.0 → normal
    result = cycle_analysis(draws)
    by_num = {n["number"]: n for n in result["numbers"]}
    assert by_num[6]["avg_cycle"] == 2.0
    assert by_num[6]["current_gap"] == 2
    assert by_num[6]["status"] == "normal"


# ---------------------------------------------------------------------------
# AC-5: 미출현 번호 → status "never", appearances 0
# ---------------------------------------------------------------------------


def test_never_appeared_number() -> None:
    """한 번도 출현하지 않은 번호는 never, appearances 0, last None이다."""
    from lotto.web.data import cycle_analysis

    result = cycle_analysis(_fixture_draws())
    by_num = {n["number"]: n for n in result["numbers"]}

    # 번호 45: 본번호로 미출현 (보너스로만 등장 — 보너스 제외)
    assert by_num[45]["status"] == "never"
    assert by_num[45]["appearances"] == 0
    assert by_num[45]["avg_cycle"] == 0.0
    assert by_num[45]["last_appeared_drwNo"] is None
    assert by_num[45]["current_gap"] == 5  # = total_draws


# ---------------------------------------------------------------------------
# AC-6: most_overdue — (gap - cycle) 내림차순 상위 5, overdue만
# ---------------------------------------------------------------------------


def _overdue_draws() -> list[DrawResult]:
    """overdue 번호가 명확히 존재하는 8회차 픽스처.

    번호 30: 회차 1, 2에만 출현(2회). total=8 → avg_cycle 8/2=4.0,
             마지막 출현 회차 2(idx 1) → current_gap = 7-1 = 6 → 6 > 4.0 → overdue
    번호 31: 회차 1에만 출현(1회). avg_cycle 8.0, gap = 7-0 = 7 → 7 < 8.0 → frequent
    """
    return [
        _mk(1, date(2020, 1, 1), [30, 31, 1, 2, 3, 4], 45),
        _mk(2, date(2020, 1, 8), [30, 5, 6, 7, 8, 9], 44),
        _mk(3, date(2020, 1, 15), [10, 11, 12, 13, 14, 15], 43),
        _mk(4, date(2020, 1, 22), [16, 17, 18, 19, 20, 21], 42),
        _mk(5, date(2020, 1, 29), [22, 23, 24, 25, 26, 27], 41),
        _mk(6, date(2020, 2, 5), [1, 2, 3, 4, 5, 6], 40),
        _mk(7, date(2020, 2, 12), [7, 8, 9, 10, 11, 12], 39),
        _mk(8, date(2020, 2, 19), [13, 14, 15, 16, 17, 18], 38),
    ]


def test_most_overdue_top5() -> None:
    """most_overdue는 (current_gap - avg_cycle) 내림차순 상위 5개이며 overdue만 포함한다."""
    from lotto.web.data import cycle_analysis

    result = cycle_analysis(_overdue_draws())
    most_overdue = result["most_overdue"]

    assert len(most_overdue) <= 5
    assert len(most_overdue) >= 1  # overdue 번호가 최소 1개 존재
    for item in most_overdue:
        assert set(item.keys()) == {"number", "current_gap", "avg_cycle"}

    # 모든 most_overdue 항목은 overdue (gap > cycle)
    by_num = {n["number"]: n for n in result["numbers"]}
    for item in most_overdue:
        assert by_num[item["number"]]["status"] == "overdue"

    # 번호 30이 overdue로 포함됨
    overdue_numbers = {item["number"] for item in most_overdue}
    assert 30 in overdue_numbers
    assert by_num[30]["avg_cycle"] == 4.0
    assert by_num[30]["current_gap"] == 6

    # (gap - cycle) 내림차순 정렬 확인
    diffs = [item["current_gap"] - item["avg_cycle"] for item in most_overdue]
    assert diffs == sorted(diffs, reverse=True)


# ---------------------------------------------------------------------------
# AC-7: summary 카운트 합계 == 45
# ---------------------------------------------------------------------------


def test_summary_counts_sum_to_45() -> None:
    """summary의 4개 상태 카운트 합계가 45이다."""
    from lotto.web.data import cycle_analysis

    result = cycle_analysis(_fixture_draws())
    summary = result["summary"]
    assert set(summary.keys()) == _SUMMARY_KEYS
    assert sum(summary.values()) == 45

    # summary 카운트가 numbers의 status 분포와 일치
    by_status: dict[str, int] = {"overdue": 0, "frequent": 0, "normal": 0, "never": 0}
    for n in result["numbers"]:
        by_status[n["status"]] += 1
    assert summary == by_status


# ---------------------------------------------------------------------------
# AC-8: 빈 리스트 → 전부 never, 예외 없음
# ---------------------------------------------------------------------------


def test_empty_draws_all_never() -> None:
    """draws=[] → total_draws 0, 45개 모두 never, most_overdue 빈 리스트."""
    from lotto.web.data import cycle_analysis

    result = cycle_analysis([])
    assert set(result.keys()) == _TOP_KEYS
    assert result["total_draws"] == 0
    assert len(result["numbers"]) == 45
    for n in result["numbers"]:
        assert n["appearances"] == 0
        assert n["avg_cycle"] == 0.0
        assert n["last_appeared_drwNo"] is None
        assert n["current_gap"] == 0
        assert n["status"] == "never"
    assert result["most_overdue"] == []
    assert result["summary"] == {"overdue": 0, "frequent": 0, "normal": 0, "never": 45}


# ---------------------------------------------------------------------------
# AC-9: None draws → 빈 구조
# ---------------------------------------------------------------------------


def test_none_draws_empty_structure() -> None:
    """draws=None(명시) → 빈 구조, 예외 없음."""
    from lotto.web.data import cycle_analysis

    result = cycle_analysis(None)
    assert result["total_draws"] == 0
    assert len(result["numbers"]) == 45
    assert all(n["status"] == "never" for n in result["numbers"])
    assert result["most_overdue"] == []


# ---------------------------------------------------------------------------
# AC-10: 결정론 — 동일 입력 2회 → 동일 출력
# ---------------------------------------------------------------------------


def test_deterministic_output() -> None:
    """동일 입력으로 2회 호출 시 결과가 동일하다."""
    from lotto.web.data import cycle_analysis

    draws = _fixture_draws()
    assert cycle_analysis(draws) == cycle_analysis(draws)


def test_no_args_calls_get_draws(monkeypatch: pytest.MonkeyPatch) -> None:
    """draws 인자 생략 시 get_draws()를 자동 호출한다."""
    from lotto.web import data as wd

    draws = _fixture_draws()
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    result = wd.cycle_analysis()
    assert result["total_draws"] == 5
