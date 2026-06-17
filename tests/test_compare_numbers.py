"""SPEC-LOTTO-040: 번호 비교 분석기 — compare_numbers() 단위 테스트.

입력 6개 번호를 전체 회차와 비교하여 일치 수준별 통계/번호 빈도/등급을
산출하는 함수를 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest

from lotto.models import DrawResult


def _mk(no: int, d: date, nums: list[int], bonus: int) -> DrawResult:
    """DrawResult 생성 헬퍼."""
    return DrawResult(
        drwNo=no, date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


@pytest.fixture
def sample_draws() -> list[DrawResult]:
    """3회차 샘플.

    회차 1: 1,10,20,30,40,45  보너스 5
    회차 2: 1,10,15,25,35,44  보너스 3
    회차 3: 1,2,3,10,11,12    보너스 7
    → 번호 1: 3회, 번호 10: 3회, 번호 20/30/40/45: 1회, 번호 7: 0회(본번호)
    """
    return [
        _mk(1, date(2023, 1, 7), [1, 10, 20, 30, 40, 45], 5),
        _mk(2, date(2023, 1, 14), [1, 10, 15, 25, 35, 44], 3),
        _mk(3, date(2023, 1, 21), [1, 2, 3, 10, 11, 12], 7),
    ]


_SUMMARY_LEVELS = {"6", "5", "4", "3"}


# ---------------------------------------------------------------------------
# AC-1: 정상 구조 — 모든 키 존재
# ---------------------------------------------------------------------------


def test_returns_full_structure(sample_draws: list[DrawResult]) -> None:
    """응답에 모든 최상위 키가 존재하고 numbers는 정렬되어 반환된다."""
    from lotto.web.data import compare_numbers

    result = compare_numbers([45, 1, 30, 10, 40, 20], sample_draws)
    assert result["numbers"] == [1, 10, 20, 30, 40, 45]
    assert result["total_draws_checked"] == 3
    assert set(result["match_summary"].keys()) == _SUMMARY_LEVELS
    assert "number_frequency" in result
    assert "grade" in result


# ---------------------------------------------------------------------------
# AC-2: 6개 일치
# ---------------------------------------------------------------------------


def test_six_match(sample_draws: list[DrawResult]) -> None:
    """입력이 어떤 회차와 완전히 일치하면 6-match count >= 1, 회차 포함."""
    from lotto.web.data import compare_numbers

    result = compare_numbers([1, 10, 20, 30, 40, 45], sample_draws)
    six = result["match_summary"]["6"]
    assert six["count"] >= 1
    assert any(d["drwNo"] == 1 for d in six["draws"])
    assert all(set(d.keys()) == {"drwNo", "date"} for d in six["draws"])


# ---------------------------------------------------------------------------
# AC-3: 3/4 일치 정확도
# ---------------------------------------------------------------------------


def test_match_level_counts_accurate(sample_draws: list[DrawResult]) -> None:
    """알려진 입력에 대한 일치 수준 카운트가 정확하다."""
    from lotto.web.data import compare_numbers

    # 입력 [1,10,15,20,25,30]:
    #  회차1 {1,10,20,30}=4, 회차2 {1,10,15,25}=4, 회차3 {1,10}=2
    result = compare_numbers([1, 10, 15, 20, 25, 30], sample_draws)
    summary = result["match_summary"]
    assert summary["6"]["count"] == 0
    assert summary["5"]["count"] == 0
    assert summary["4"]["count"] == 2
    assert summary["3"]["count"] == 0
    # 4-match 회차 목록은 회차1,2
    drw_nos = sorted(d["drwNo"] for d in summary["4"]["draws"])
    assert drw_nos == [1, 2]


# ---------------------------------------------------------------------------
# AC-4: 번호 빈도 (본번호 기준, 6개 모두 존재)
# ---------------------------------------------------------------------------


def test_number_frequency(sample_draws: list[DrawResult]) -> None:
    """입력 6개 번호가 모두 존재하고 count가 본번호 출현 횟수와 같다."""
    from lotto.web.data import compare_numbers

    result = compare_numbers([1, 10, 20, 30, 40, 45], sample_draws)
    freq = result["number_frequency"]
    # 6개 번호 모두 존재, 번호 오름차순
    assert [item["number"] for item in freq] == [1, 10, 20, 30, 40, 45]
    freq_map = {item["number"]: item["count"] for item in freq}
    assert freq_map[1] == 3
    assert freq_map[10] == 3
    assert freq_map[20] == 1
    assert freq_map[45] == 1
    # rank 필드 존재 — 최다 출현(1,10)이 rank 1
    rank_map = {item["number"]: item["rank"] for item in freq}
    assert rank_map[1] == 1
    assert rank_map[10] == 1


# ---------------------------------------------------------------------------
# AC-5: 빈/None 데이터
# ---------------------------------------------------------------------------


def test_empty_draws_consistent_structure() -> None:
    """빈 리스트는 예외 없이 일관된 0 구조를 반환한다."""
    from lotto.web.data import compare_numbers

    result = compare_numbers([1, 2, 3, 4, 5, 6], [])
    assert result["total_draws_checked"] == 0
    for level in _SUMMARY_LEVELS:
        assert result["match_summary"][level]["count"] == 0
        assert result["match_summary"][level]["draws"] == []
    assert all(item["count"] == 0 for item in result["number_frequency"])
    assert isinstance(result["grade"], str)
    assert result["grade"] != ""


def test_none_draws_consistent_structure() -> None:
    """draws가 명시적 None이어도 빈 구조를 반환한다."""
    from lotto.web.data import compare_numbers

    result = compare_numbers([1, 2, 3, 4, 5, 6], None)
    assert result["total_draws_checked"] == 0
    assert all(item["count"] == 0 for item in result["number_frequency"])


# ---------------------------------------------------------------------------
# AC-6: 모든 번호가 모든 회차에 출현 → 6-match == total
# ---------------------------------------------------------------------------


def test_all_draws_full_match() -> None:
    """입력 6개가 모든 회차의 본번호와 동일하면 6-match count == total_draws."""
    from lotto.web.data import compare_numbers

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7),
        _mk(2, date(2023, 1, 14), [6, 5, 4, 3, 2, 1], 8),
        _mk(3, date(2023, 1, 21), [1, 2, 3, 4, 5, 6], 9),
    ]
    result = compare_numbers([1, 2, 3, 4, 5, 6], draws)
    assert result["total_draws_checked"] == 3
    assert result["match_summary"]["6"]["count"] == 3


# ---------------------------------------------------------------------------
# AC-7: 결정론
# ---------------------------------------------------------------------------


def test_deterministic(sample_draws: list[DrawResult]) -> None:
    """동일 입력은 두 번 호출해도 동일 결과를 반환한다."""
    from lotto.web.data import compare_numbers

    r1 = compare_numbers([1, 10, 20, 30, 40, 45], sample_draws)
    r2 = compare_numbers([1, 10, 20, 30, 40, 45], sample_draws)
    assert r1 == r2


# ---------------------------------------------------------------------------
# AC-7b: 인자 미전달 시 get_draws() 자동 호출
# ---------------------------------------------------------------------------


def test_no_args_calls_get_draws(monkeypatch: pytest.MonkeyPatch) -> None:
    """draws 인자 생략 시 get_draws()를 자동 호출한다."""
    from lotto.web import data as wd

    draws = [_mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7)]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    result = wd.compare_numbers([1, 2, 3, 4, 5, 6])
    assert result["total_draws_checked"] == 1
    assert result["match_summary"]["6"]["count"] == 1
