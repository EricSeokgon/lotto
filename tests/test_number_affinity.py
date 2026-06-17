"""SPEC-LOTTO-044: 번호 궁합 추천기 — number_affinity() 단위 테스트.

특정 번호가 포함된 회차에서 함께 나온 다른 번호의 동반 출현(co-occurrence)을
집계하여 궁합 파트너와 추천 조합을 산출하는 함수를 검증한다.
"""

from __future__ import annotations

from datetime import date

import pytest

from lotto.models import DrawResult

_TOP_KEYS = {
    "target",
    "total_draws",
    "target_appearances",
    "partners",
    "recommended_combination",
}


def _mk(no: int, d: date, nums: list[int], bonus: int) -> DrawResult:
    """DrawResult 생성 헬퍼."""
    return DrawResult(
        drwNo=no, date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# ---------------------------------------------------------------------------
# AC-1: 동반 횟수 정확성 (알려진 픽스처)
# ---------------------------------------------------------------------------


def test_partner_counts_are_correct() -> None:
    """대상 7과 함께 나온 번호의 동반 횟수가 정확하다."""
    from lotto.web.data import number_affinity

    # 대상 7이 회차 1,2,3에 등장. 27은 회차 1,2(2회), 13은 회차 1(1회).
    draws = [
        _mk(1, date(2023, 1, 7), [7, 13, 27, 30, 40, 45], 1),
        _mk(2, date(2023, 1, 14), [7, 18, 27, 33, 41, 44], 2),
        _mk(3, date(2023, 1, 21), [7, 11, 22, 31, 39, 42], 3),
        _mk(4, date(2023, 1, 28), [2, 5, 9, 14, 30, 44], 4),  # 7 없음
    ]
    result = number_affinity(7, draws)

    assert set(result.keys()) == _TOP_KEYS
    assert result["target"] == 7
    assert result["total_draws"] == 4
    assert result["target_appearances"] == 3

    counts = {p["number"]: p["count"] for p in result["partners"]}
    assert counts[27] == 2
    assert counts[13] == 1
    assert counts[18] == 1


# ---------------------------------------------------------------------------
# AC-2: partners 정렬 (count desc, number asc) + top_k 절단
# ---------------------------------------------------------------------------


def test_partners_sorted_and_top_k_limited() -> None:
    """partners는 count desc, number asc 정렬, 길이 <= top_k."""
    from lotto.web.data import number_affinity

    draws = [
        _mk(1, date(2023, 1, 7), [7, 10, 20, 30, 40, 44], 1),
        _mk(2, date(2023, 1, 14), [7, 10, 20, 31, 41, 45], 2),
        _mk(3, date(2023, 1, 21), [7, 10, 21, 32, 42, 43], 3),
    ]
    # 10: 3회, 20: 2회, 나머지 1회
    result = number_affinity(7, draws, top_k=3)

    partners = result["partners"]
    assert len(partners) <= 3
    # count 내림차순 정렬
    counts = [p["count"] for p in partners]
    assert counts == sorted(counts, reverse=True)
    assert partners[0]["number"] == 10
    assert partners[0]["count"] == 3
    assert partners[1]["number"] == 20
    assert partners[1]["count"] == 2


def test_partners_tie_break_by_number_ascending() -> None:
    """동률 count는 번호 오름차순으로 정렬한다."""
    from lotto.web.data import number_affinity

    # 7과 함께 11,12가 각각 1회씩 (동률) → 11이 먼저
    draws = [_mk(1, date(2023, 1, 7), [7, 11, 12, 30, 40, 45], 1)]
    result = number_affinity(7, draws, top_k=10)

    ones = [p["number"] for p in result["partners"] if p["count"] == 1]
    assert ones == sorted(ones)
    assert result["partners"][0]["number"] == 11


# ---------------------------------------------------------------------------
# AC-3: 대상은 자신의 partners 목록에서 제외
# ---------------------------------------------------------------------------


def test_target_excluded_from_partners() -> None:
    """대상 번호는 partners에 포함되지 않는다."""
    from lotto.web.data import number_affinity

    draws = [
        _mk(1, date(2023, 1, 7), [7, 13, 27, 30, 40, 45], 1),
        _mk(2, date(2023, 1, 14), [7, 13, 27, 31, 41, 44], 2),
    ]
    result = number_affinity(7, draws)
    partner_numbers = {p["number"] for p in result["partners"]}
    assert 7 not in partner_numbers


# ---------------------------------------------------------------------------
# AC-4: rate = count / target_appearances (소수 4자리)
# ---------------------------------------------------------------------------


def test_rate_is_count_over_appearances() -> None:
    """rate = count / target_appearances, 소수 4자리."""
    from lotto.web.data import number_affinity

    # 7이 4회 등장, 27은 그중 1회 → rate = 1/4 = 0.25
    draws = [
        _mk(1, date(2023, 1, 7), [7, 27, 30, 33, 40, 45], 1),
        _mk(2, date(2023, 1, 14), [7, 11, 22, 31, 41, 44], 2),
        _mk(3, date(2023, 1, 21), [7, 12, 23, 32, 39, 42], 3),
        _mk(4, date(2023, 1, 28), [7, 13, 24, 34, 38, 43], 4),
    ]
    result = number_affinity(7, draws)
    rate_by_num = {p["number"]: p["rate"] for p in result["partners"]}
    assert result["target_appearances"] == 4
    assert rate_by_num[27] == 0.25


# ---------------------------------------------------------------------------
# AC-5: recommended_combination = sorted([target] + 상위 5 파트너), 6개
# ---------------------------------------------------------------------------


def test_recommended_combination_six_numbers() -> None:
    """파트너가 충분하면 추천 조합은 대상 + 상위 5 = 6개, 오름차순."""
    from lotto.web.data import number_affinity

    # 7과 함께 10,20,30,40,44,45 가 모두 1회 이상
    draws = [
        _mk(1, date(2023, 1, 7), [7, 10, 20, 30, 40, 44], 1),
        _mk(2, date(2023, 1, 14), [7, 10, 20, 30, 40, 45], 2),
        _mk(3, date(2023, 1, 21), [7, 10, 20, 30, 41, 45], 3),
    ]
    result = number_affinity(7, draws)
    combo = result["recommended_combination"]
    assert len(combo) == 6
    assert combo == sorted(combo)
    assert 7 in combo
    # 가장 강한 파트너(10,20,30)는 반드시 포함
    assert 10 in combo
    assert 20 in combo
    assert 30 in combo


def test_recommended_combination_fewer_than_five_partners() -> None:
    """파트너가 5개 미만이면 가용 파트너만 포함 (6개 미만 가능)."""
    from lotto.web.data import number_affinity

    # 7과 함께 11,12 두 개만 등장 → 추천 조합 = [7,11,12]
    draws = [_mk(1, date(2023, 1, 7), [7, 11, 12, 30, 40, 45], 1)]
    result = number_affinity(7, draws, top_k=10)
    combo = result["recommended_combination"]
    # 7 + 상위 5 파트너이지만 파트너는 5개(11,12,30,40,45) → 6개
    assert combo == sorted(combo)
    assert 7 in combo
    assert combo[0] == 7  # 7이 가장 작음


# ---------------------------------------------------------------------------
# AC-6: 대상 미출현 → 빈 구조 + recommended_combination=[target]
# ---------------------------------------------------------------------------


def test_target_never_appears() -> None:
    """대상이 한 번도 등장하지 않으면 빈 구조, 추천 조합은 [target]."""
    from lotto.web.data import number_affinity

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 10, 20, 30], 5),
        _mk(2, date(2023, 1, 14), [4, 5, 6, 11, 21, 31], 6),
    ]
    result = number_affinity(7, draws)
    assert result["target"] == 7
    assert result["total_draws"] == 2
    assert result["target_appearances"] == 0
    assert result["partners"] == []
    assert result["recommended_combination"] == [7]


# ---------------------------------------------------------------------------
# AC-7: 빈 리스트 → 빈 구조
# ---------------------------------------------------------------------------


def test_empty_draws_returns_empty_structure() -> None:
    """draws=[] → 일관된 빈 구조, 예외 없음."""
    from lotto.web.data import number_affinity

    result = number_affinity(7, [])
    assert set(result.keys()) == _TOP_KEYS
    assert result["target"] == 7
    assert result["total_draws"] == 0
    assert result["target_appearances"] == 0
    assert result["partners"] == []
    assert result["recommended_combination"] == [7]


# ---------------------------------------------------------------------------
# AC-8: None draws → 빈 구조
# ---------------------------------------------------------------------------


def test_none_draws_returns_empty_structure() -> None:
    """draws=None(명시) → 빈 구조, 예외 없음."""
    from lotto.web.data import number_affinity

    result = number_affinity(7, None)
    assert set(result.keys()) == _TOP_KEYS
    assert result["target_appearances"] == 0
    assert result["partners"] == []
    assert result["recommended_combination"] == [7]


# ---------------------------------------------------------------------------
# AC-9: 결정론 — 동일 입력 2회 → 동일 출력
# ---------------------------------------------------------------------------


def test_deterministic_output() -> None:
    """동일 입력으로 2회 호출 시 결과가 동일하다."""
    from lotto.web.data import number_affinity

    draws = [
        _mk(1, date(2023, 1, 7), [7, 10, 20, 30, 40, 44], 1),
        _mk(2, date(2023, 1, 14), [7, 10, 21, 31, 41, 45], 2),
    ]
    r1 = number_affinity(7, draws)
    r2 = number_affinity(7, draws)
    assert r1 == r2


def test_no_args_calls_get_draws(monkeypatch: pytest.MonkeyPatch) -> None:
    """draws 인자 생략 시 get_draws()를 자동 호출한다."""
    from lotto.web import data as wd

    draws = [_mk(1, date(2023, 1, 7), [7, 13, 27, 30, 40, 45], 1)]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    result = wd.number_affinity(7)
    assert result["total_draws"] == 1
    assert result["target_appearances"] == 1
