"""SPEC-LOTTO-042: 번호 추이 트래커 — number_trend() 단위 테스트.

선택 번호(1~3개)의 최근 N회차 출현 타임라인과 간격 통계를
집계하는 함수를 검증한다.
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


@pytest.fixture
def sample_draws() -> list[DrawResult]:
    """5회차 샘플 (drwNo 오름차순).

    회차 1: 1,2,3,4,5,6     보너스 7  → 7은 본번호 아님(보너스만)
    회차 2: 7,8,9,10,11,12  보너스 1  → 7 출현
    회차 3: 1,2,3,4,5,6     보너스 8  → 7 미출현
    회차 4: 7,13,14,15,16,17 보너스 2 → 7 출현
    회차 5: 7,18,19,20,21,22 보너스 3 → 7 출현 (최신 회차)

    번호 7 출현 회차(본번호 기준): 2, 4, 5 → 윈도 위치 1,3,4
    """
    return [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7),
        _mk(2, date(2023, 1, 14), [7, 8, 9, 10, 11, 12], 1),
        _mk(3, date(2023, 1, 21), [1, 2, 3, 4, 5, 6], 8),
        _mk(4, date(2023, 1, 28), [7, 13, 14, 15, 16, 17], 2),
        _mk(5, date(2023, 2, 4), [7, 18, 19, 20, 21, 22], 3),
    ]


_TOP_KEYS = {"recent_n", "draws_analyzed", "numbers"}
_NUMBER_KEYS = {
    "number",
    "total_appearances",
    "avg_gap",
    "last_appeared_drwNo",
    "current_gap",
    "timeline",
}


# ---------------------------------------------------------------------------
# AC-1: 정상 구조 반환
# ---------------------------------------------------------------------------


def test_normal_structure(sample_draws: list[DrawResult]) -> None:
    """최상위 키와 번호 항목 키가 모두 존재한다."""
    from lotto.web.data import number_trend

    result = number_trend([7], recent_n=100, draws=sample_draws)
    assert set(result.keys()) == _TOP_KEYS
    assert result["recent_n"] == 100
    assert isinstance(result["numbers"], list)
    assert len(result["numbers"]) == 1

    entry = result["numbers"][0]
    assert set(entry.keys()) == _NUMBER_KEYS
    assert entry["number"] == 7


# ---------------------------------------------------------------------------
# AC-2: 타임라인 길이 == draws_analyzed
# ---------------------------------------------------------------------------


def test_timeline_length_matches_draws_analyzed(
    sample_draws: list[DrawResult],
) -> None:
    """각 번호 타임라인 길이는 draws_analyzed와 같다."""
    from lotto.web.data import number_trend

    result = number_trend([7, 1], recent_n=100, draws=sample_draws)
    analyzed = result["draws_analyzed"]
    assert analyzed == 5
    for entry in result["numbers"]:
        assert len(entry["timeline"]) == analyzed
    # 타임라인은 시간 오름차순 (오래된 → 최신)
    first_entry = result["numbers"][0]
    drw_nos = [t["drwNo"] for t in first_entry["timeline"]]
    assert drw_nos == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# AC-3: 출현 횟수 정확성
# ---------------------------------------------------------------------------


def test_total_appearances_accurate(sample_draws: list[DrawResult]) -> None:
    """total_appearances는 본번호 실제 출현 횟수와 일치한다 (보너스 제외)."""
    from lotto.web.data import number_trend

    result = number_trend([7], draws=sample_draws)
    entry = result["numbers"][0]
    # 번호 7: 회차 2,4,5 본번호로 출현 = 3회 (회차1은 보너스라 미집계)
    assert entry["total_appearances"] == 3

    # 타임라인의 appeared=True 개수도 일치해야 한다
    appeared_count = sum(1 for t in entry["timeline"] if t["appeared"])
    assert appeared_count == 3
    # 회차1은 보너스 7이지만 본번호 아님 → appeared False
    assert entry["timeline"][0]["appeared"] is False
    assert entry["timeline"][1]["appeared"] is True


# ---------------------------------------------------------------------------
# AC-4: avg_gap (None when < 2 appearances)
# ---------------------------------------------------------------------------


def test_avg_gap_with_multiple_appearances(
    sample_draws: list[DrawResult],
) -> None:
    """2회 이상 출현 시 avg_gap은 위치 간격 평균(소수 1자리)이다."""
    from lotto.web.data import number_trend

    result = number_trend([7], draws=sample_draws)
    entry = result["numbers"][0]
    # 출현 위치(0기반): 1, 3, 4 → gaps = [2, 1] → 평균 1.5
    assert entry["avg_gap"] == 1.5


def test_avg_gap_none_when_fewer_than_two(
    sample_draws: list[DrawResult],
) -> None:
    """출현 2회 미만이면 avg_gap은 None이다."""
    from lotto.web.data import number_trend

    # 번호 13: 회차4에만 1회 출현
    result = number_trend([13], draws=sample_draws)
    entry = result["numbers"][0]
    assert entry["total_appearances"] == 1
    assert entry["avg_gap"] is None


# ---------------------------------------------------------------------------
# AC-5: current_gap
# ---------------------------------------------------------------------------


def test_current_gap_zero_when_in_latest(
    sample_draws: list[DrawResult],
) -> None:
    """윈도 최신 회차에 출현하면 current_gap=0, last_appeared_drwNo는 최신 회차."""
    from lotto.web.data import number_trend

    # 번호 7은 회차5(최신)에 출현
    result = number_trend([7], draws=sample_draws)
    entry = result["numbers"][0]
    assert entry["current_gap"] == 0
    assert entry["last_appeared_drwNo"] == 5


def test_current_gap_positive_when_older(
    sample_draws: list[DrawResult],
) -> None:
    """마지막 출현이 과거면 current_gap은 경과 회차 수다."""
    from lotto.web.data import number_trend

    # 번호 13: 회차4에만 출현. 윈도 마지막은 회차5(위치4), 출현 위치3 → gap=1
    result = number_trend([13], draws=sample_draws)
    entry = result["numbers"][0]
    assert entry["last_appeared_drwNo"] == 4
    assert entry["current_gap"] == 1


def test_never_appeared(sample_draws: list[DrawResult]) -> None:
    """윈도 내 한 번도 출현하지 않으면 last_appeared=None, avg_gap=None."""
    from lotto.web.data import number_trend

    # 번호 30: 어느 회차에도 없음
    result = number_trend([30], draws=sample_draws)
    entry = result["numbers"][0]
    assert entry["total_appearances"] == 0
    assert entry["last_appeared_drwNo"] is None
    assert entry["avg_gap"] is None
    # 미출현 시 current_gap은 윈도 전체 크기
    assert entry["current_gap"] == result["draws_analyzed"]


# ---------------------------------------------------------------------------
# AC-6 / AC-7: 빈 / None draws
# ---------------------------------------------------------------------------


def test_empty_draws_returns_empty_structure() -> None:
    """draws=[] → 빈 구조, 예외 없음."""
    from lotto.web.data import number_trend

    result = number_trend([7], recent_n=100, draws=[])
    assert result == {"recent_n": 100, "draws_analyzed": 0, "numbers": []}


def test_none_draws_returns_empty_structure() -> None:
    """draws=None(명시) → 빈 구조, 예외 없음."""
    from lotto.web.data import number_trend

    result = number_trend([7, 14], recent_n=50, draws=None)
    assert result == {"recent_n": 50, "draws_analyzed": 0, "numbers": []}


# ---------------------------------------------------------------------------
# AC-8: recent_n 클램프
# ---------------------------------------------------------------------------


def test_recent_n_clamped_to_total_draws(
    sample_draws: list[DrawResult],
) -> None:
    """recent_n이 전체 회차보다 크면 draws_analyzed는 전체 회차 수다."""
    from lotto.web.data import number_trend

    result = number_trend([7], recent_n=500, draws=sample_draws)
    # 요청 recent_n은 그대로 노출, 분석 회차는 가용 전체(5)
    assert result["recent_n"] == 500
    assert result["draws_analyzed"] == 5


def test_recent_n_window_uses_most_recent(
    sample_draws: list[DrawResult],
) -> None:
    """recent_n이 작으면 최신 회차 윈도만 사용한다."""
    from lotto.web.data import number_trend

    # 최근 2회차(4,5)만 분석
    result = number_trend([7], recent_n=2, draws=sample_draws)
    assert result["draws_analyzed"] == 2
    entry = result["numbers"][0]
    drw_nos = [t["drwNo"] for t in entry["timeline"]]
    assert drw_nos == [4, 5]
    # 회차4,5 모두 7 출현 → 2회
    assert entry["total_appearances"] == 2


def test_no_args_calls_get_draws(monkeypatch: pytest.MonkeyPatch) -> None:
    """draws 인자 생략 시 get_draws()를 자동 호출한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [7, 8, 9, 10, 11, 12], 1),
        _mk(2, date(2023, 1, 14), [1, 2, 3, 4, 5, 6], 7),
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    result = wd.number_trend([7])
    assert result["draws_analyzed"] == 2
    assert result["numbers"][0]["total_appearances"] == 1
