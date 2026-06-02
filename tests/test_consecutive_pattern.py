"""SPEC-LOTTO-043: 연속 번호 패턴 분석 — consecutive_pattern() 단위 테스트.

역대 당첨번호의 정렬된 본번호 6개에서 연속 런(2개 이상 인접)을 탐지하여
런 길이 분포·연속 비율·최장 런·연속 쌍 빈도를 집계하는 함수를 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest

from lotto.models import DrawResult


def _mk(no: int, d: date, nums: list[int], bonus: int) -> DrawResult:
    """DrawResult 생성 헬퍼."""
    return DrawResult(
        drwNo=no,
        date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


_TOP_KEYS = {
    "total_draws",
    "draws_with_consecutive",
    "consecutive_ratio",
    "run_length_distribution",
    "max_run_length",
    "most_common_pairs",
    "draws_without_consecutive",
}
_RUN_LEN_KEYS = {"2", "3", "4", "5", "6"}


# ---------------------------------------------------------------------------
# AC-1: 길이 3 런 집계 (3-4-5 → run["3"]=1, 쌍 3-4 / 4-5)
# ---------------------------------------------------------------------------


def test_run_length_3_and_pairs() -> None:
    """본번호 [3,4,5,18,33,40] → 길이 3 런 1개, 쌍 3-4/4-5 각 1회."""
    from lotto.web.data import consecutive_pattern

    draws = [_mk(1, date(2023, 1, 7), [3, 4, 5, 18, 33, 40], 12)]
    result = consecutive_pattern(draws)

    assert set(result.keys()) == _TOP_KEYS
    assert set(result["run_length_distribution"].keys()) == _RUN_LEN_KEYS
    assert result["run_length_distribution"]["3"] == 1
    assert result["max_run_length"] == 3

    pairs = {p["pair"]: p["count"] for p in result["most_common_pairs"]}
    assert pairs.get("3-4") == 1
    assert pairs.get("4-5") == 1


# ---------------------------------------------------------------------------
# AC-2: 길이 2 런 2개 (7-8, 19-20)
# ---------------------------------------------------------------------------


def test_two_separate_length_2_runs() -> None:
    """본번호 [7,8,19,20,41,45] → 길이 2 런 2개, 쌍 7-8/19-20."""
    from lotto.web.data import consecutive_pattern

    draws = [_mk(1, date(2023, 1, 7), [7, 8, 19, 20, 41, 45], 3)]
    result = consecutive_pattern(draws)

    assert result["run_length_distribution"]["2"] == 2
    assert result["run_length_distribution"]["3"] == 0
    assert result["max_run_length"] == 2

    pairs = {p["pair"]: p["count"] for p in result["most_common_pairs"]}
    assert pairs.get("7-8") == 1
    assert pairs.get("19-20") == 1


# ---------------------------------------------------------------------------
# AC-3: 연속 미포함 회차 → draws_without_consecutive
# ---------------------------------------------------------------------------


def test_draw_without_consecutive() -> None:
    """본번호 [2,5,9,14,30,44] (인접 차이 모두 ≥2) → 연속 없음."""
    from lotto.web.data import consecutive_pattern

    draws = [_mk(1, date(2023, 1, 7), [2, 5, 9, 14, 30, 44], 1)]
    result = consecutive_pattern(draws)

    assert result["draws_without_consecutive"] == 1
    assert result["draws_with_consecutive"] == 0
    assert result["max_run_length"] == 0
    assert result["most_common_pairs"] == []
    # 모든 런 분포 0
    assert all(v == 0 for v in result["run_length_distribution"].values())


# ---------------------------------------------------------------------------
# AC-4: consecutive_ratio 계산 (3/4 = 0.75)
# ---------------------------------------------------------------------------


def test_consecutive_ratio() -> None:
    """4회차 중 3회차 연속 포함 → ratio 0.75."""
    from lotto.web.data import consecutive_pattern

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 10, 20, 30, 40], 5),   # 연속(1-2)
        _mk(2, date(2023, 1, 14), [3, 4, 11, 22, 33, 44], 6),  # 연속(3-4)
        _mk(3, date(2023, 1, 21), [5, 6, 12, 24, 36, 45], 7),  # 연속(5-6)
        _mk(4, date(2023, 1, 28), [2, 5, 9, 14, 30, 44], 8),   # 연속 없음
    ]
    result = consecutive_pattern(draws)

    assert result["total_draws"] == 4
    assert result["draws_with_consecutive"] == 3
    assert result["draws_without_consecutive"] == 1
    assert result["consecutive_ratio"] == 0.75


# ---------------------------------------------------------------------------
# AC-5: 최장 런 6 (1-2-3-4-5-6)
# ---------------------------------------------------------------------------


def test_max_run_length_six() -> None:
    """본번호 [1,2,3,4,5,6] → 길이 6 런 1개, max_run_length=6."""
    from lotto.web.data import consecutive_pattern

    draws = [_mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7)]
    result = consecutive_pattern(draws)

    assert result["max_run_length"] == 6
    assert result["run_length_distribution"]["6"] == 1
    # 길이 6 런은 5개의 인접 쌍 포함
    pairs = {p["pair"]: p["count"] for p in result["most_common_pairs"]}
    assert pairs == {"1-2": 1, "2-3": 1, "3-4": 1, "4-5": 1, "5-6": 1}


# ---------------------------------------------------------------------------
# AC-6: most_common_pairs 정렬 (count desc, pair asc, top 10)
# ---------------------------------------------------------------------------


def test_most_common_pairs_sorting_and_limit() -> None:
    """쌍 빈도 내림차순, 동률은 라벨 오름차순, 최대 10개."""
    from lotto.web.data import consecutive_pattern

    # 1-2 쌍을 3회, 3-4 쌍을 2회, 그 외 다양한 쌍 1회씩 등장하게 구성
    draws = [
        _mk(1, date(2023, 1, 1), [1, 2, 10, 20, 30, 40], 5),   # 1-2
        _mk(2, date(2023, 1, 8), [1, 2, 11, 21, 31, 41], 5),   # 1-2
        _mk(3, date(2023, 1, 15), [1, 2, 12, 22, 32, 42], 5),  # 1-2
        _mk(4, date(2023, 1, 22), [3, 4, 13, 23, 33, 43], 5),  # 3-4
        _mk(5, date(2023, 1, 29), [3, 4, 14, 24, 34, 44], 5),  # 3-4
        _mk(6, date(2023, 2, 5), [5, 6, 7, 8, 9, 10], 1),      # 5-6,6-7,7-8,8-9,9-10
    ]
    result = consecutive_pattern(draws)

    pairs = result["most_common_pairs"]
    # 최대 10개
    assert len(pairs) <= 10
    # 첫 두 개: 1-2(3회), 3-4(2회)
    assert pairs[0] == {"pair": "1-2", "count": 3}
    assert pairs[1] == {"pair": "3-4", "count": 2}
    # count 내림차순 정렬 보장
    counts = [p["count"] for p in pairs]
    assert counts == sorted(counts, reverse=True)
    # 동률 구간(count 1)은 라벨 오름차순
    ones = [p["pair"] for p in pairs if p["count"] == 1]
    assert ones == sorted(ones)


# ---------------------------------------------------------------------------
# AC-7: 빈 리스트 → 빈 구조
# ---------------------------------------------------------------------------


def test_empty_draws_returns_empty_structure() -> None:
    """draws=[] → 일관된 빈 구조, 예외 없음."""
    from lotto.web.data import consecutive_pattern

    result = consecutive_pattern([])
    assert result["total_draws"] == 0
    assert result["draws_with_consecutive"] == 0
    assert result["draws_without_consecutive"] == 0
    assert result["consecutive_ratio"] == 0.0
    assert result["max_run_length"] == 0
    assert result["most_common_pairs"] == []
    assert set(result["run_length_distribution"].keys()) == _RUN_LEN_KEYS
    assert all(v == 0 for v in result["run_length_distribution"].values())


# ---------------------------------------------------------------------------
# AC-8: None draws → 빈 구조
# ---------------------------------------------------------------------------


def test_none_draws_returns_empty_structure() -> None:
    """draws=None(명시) → 빈 구조, 예외 없음."""
    from lotto.web.data import consecutive_pattern

    result = consecutive_pattern(None)
    assert set(result.keys()) == _TOP_KEYS
    assert result["total_draws"] == 0
    assert result["consecutive_ratio"] == 0.0
    assert result["most_common_pairs"] == []


# ---------------------------------------------------------------------------
# AC-9: recent_n 클램프 (recent_n > total → 전체 사용)
# ---------------------------------------------------------------------------


def test_recent_n_clamped_to_total() -> None:
    """recent_n이 전체 회차보다 크면 total_draws는 가용 전체."""
    from lotto.web.data import consecutive_pattern

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 10, 20, 30, 40], 5),
        _mk(2, date(2023, 1, 14), [3, 4, 11, 22, 33, 44], 6),
    ]
    result = consecutive_pattern(draws, recent_n=500)
    assert result["total_draws"] == 2


def test_recent_n_window_uses_most_recent() -> None:
    """recent_n이 작으면 최신 회차 윈도만 분석한다."""
    from lotto.web.data import consecutive_pattern

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 10, 20, 30, 40], 5),   # 연속(오래된)
        _mk(2, date(2023, 1, 14), [2, 5, 9, 14, 30, 44], 6),   # 연속 없음
        _mk(3, date(2023, 1, 21), [8, 11, 17, 25, 36, 41], 7),  # 연속 없음(최신)
    ]
    # 최근 1회차(회차3)만 → 연속 없음
    result = consecutive_pattern(draws, recent_n=1)
    assert result["total_draws"] == 1
    assert result["draws_with_consecutive"] == 0


def test_no_args_calls_get_draws(monkeypatch: pytest.MonkeyPatch) -> None:
    """draws 인자 생략 시 get_draws()를 자동 호출한다."""
    from lotto.web import data as wd

    draws = [_mk(1, date(2023, 1, 7), [1, 2, 3, 10, 20, 30], 5)]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    result = wd.consecutive_pattern()
    assert result["total_draws"] == 1
    assert result["max_run_length"] == 3
