"""SPEC-LOTTO-039: 당첨번호 예측 리포트 — prediction_report() 단위 테스트.

최근 N회차에 대한 4차원 복합 스코어링(빈도/간격/홀짝/범위)으로 상위 후보와
추천 조합을 산출하는 함수를 검증한다.
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
    """8회차 샘플 — 번호별 빈도/간격에 변별력을 주는 분포."""
    return [
        _mk(1, date(2024, 1, 6), [1, 2, 3, 4, 5, 6], 7),
        _mk(2, date(2024, 1, 13), [1, 2, 3, 10, 20, 30], 8),
        _mk(3, date(2024, 1, 20), [1, 2, 11, 21, 31, 41], 9),
        _mk(4, date(2024, 1, 27), [1, 12, 22, 32, 42, 43], 10),
        _mk(5, date(2024, 2, 3), [5, 13, 23, 33, 43, 44], 11),
        _mk(6, date(2024, 2, 10), [6, 14, 24, 34, 44, 45], 12),
        _mk(7, date(2024, 2, 17), [7, 15, 25, 35, 40, 45], 13),
        _mk(8, date(2024, 2, 24), [8, 16, 26, 36, 41, 42], 14),
    ]


# ---------------------------------------------------------------------------
# 1: 정상 — top_candidates 10개, composite_score 내림차순
# ---------------------------------------------------------------------------


def test_top_candidates_count_and_order(sample_draws: list[DrawResult]) -> None:
    """top_candidates는 10개이며 composite_score 내림차순으로 정렬된다."""
    from lotto.web.data import prediction_report

    result = prediction_report(sample_draws, recent_n=8)
    candidates = result["top_candidates"]
    assert len(candidates) == 10
    scores = [c["composite_score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# 2: 구조 — 각 후보의 키 셋
# ---------------------------------------------------------------------------


def test_candidate_structure(sample_draws: list[DrawResult]) -> None:
    """각 후보는 number, composite_score, breakdown(4키)을 갖는다."""
    from lotto.web.data import prediction_report

    result = prediction_report(sample_draws, recent_n=8)
    for c in result["top_candidates"]:
        assert set(c.keys()) == {"number", "composite_score", "breakdown"}
        assert set(c["breakdown"].keys()) == {
            "frequency",
            "interval",
            "odd_even",
            "range",
        }
        assert isinstance(c["number"], int)
        assert 1 <= c["number"] <= 45


# ---------------------------------------------------------------------------
# 3: 조합 — 3세트, 각 6개 오름차순
# ---------------------------------------------------------------------------


def test_combinations_three_sets_sorted(sample_draws: list[DrawResult]) -> None:
    """recommended_combinations는 3세트이며 각 조합은 6개 번호 오름차순이다."""
    from lotto.web.data import prediction_report

    result = prediction_report(sample_draws, recent_n=8)
    combos = result["recommended_combinations"]
    assert len(combos) == 3
    for combo in combos:
        nums = combo["numbers"]
        assert len(nums) == 6
        assert nums == sorted(nums)
        assert len(set(nums)) == 6  # 중복 없음
        assert all(1 <= n <= 45 for n in nums)
        assert "label" in combo


# ---------------------------------------------------------------------------
# 4: 조합이 서로 구별됨
# ---------------------------------------------------------------------------


def test_combinations_distinct(sample_draws: list[DrawResult]) -> None:
    """충분한 후보가 있을 때 3개 조합 중 최소 한 쌍은 다르다."""
    from lotto.web.data import prediction_report

    result = prediction_report(sample_draws, recent_n=8)
    combos = [tuple(c["numbers"]) for c in result["recommended_combinations"]]
    assert len(set(combos)) >= 2


# ---------------------------------------------------------------------------
# 5: 빈 리스트
# ---------------------------------------------------------------------------


def test_empty_list_returns_empty_structure() -> None:
    """빈 리스트는 예외 없이 빈 구조를 반환한다."""
    from lotto.web.data import prediction_report

    result = prediction_report([], recent_n=50)
    assert result["draws_analyzed"] == 0
    assert result["top_candidates"] == []
    assert result["recommended_combinations"] == []
    assert result["recent_n"] == 50
    assert "weights" in result


# ---------------------------------------------------------------------------
# 6: None
# ---------------------------------------------------------------------------


def test_none_returns_empty_structure() -> None:
    """draws가 None(명시적)이어도 빈 구조를 반환한다."""
    from lotto.web.data import prediction_report

    result = prediction_report(None, recent_n=30)
    assert result["draws_analyzed"] == 0
    assert result["top_candidates"] == []
    assert result["recommended_combinations"] == []
    assert result["recent_n"] == 30


# ---------------------------------------------------------------------------
# 7: recent_n 클램프
# ---------------------------------------------------------------------------


def test_recent_n_clamp(sample_draws: list[DrawResult]) -> None:
    """recent_n이 가용 회차보다 크면 draws_analyzed는 가용 회차 수다."""
    from lotto.web.data import prediction_report

    result = prediction_report(sample_draws, recent_n=100)
    assert result["recent_n"] == 100
    assert result["draws_analyzed"] == len(sample_draws)


def test_recent_n_smaller_than_total(sample_draws: list[DrawResult]) -> None:
    """recent_n이 가용 회차보다 작으면 draws_analyzed는 recent_n이다."""
    from lotto.web.data import prediction_report

    result = prediction_report(sample_draws, recent_n=3)
    assert result["draws_analyzed"] == 3


# ---------------------------------------------------------------------------
# 8: 점수 범위 [0.0, 1.0]
# ---------------------------------------------------------------------------


def test_all_scores_in_range(sample_draws: list[DrawResult]) -> None:
    """모든 composite_score와 partial score는 [0.0, 1.0] 범위다."""
    from lotto.web.data import prediction_report

    result = prediction_report(sample_draws, recent_n=8)
    for c in result["top_candidates"]:
        assert 0.0 <= c["composite_score"] <= 1.0
        for v in c["breakdown"].values():
            assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# 9: 결정성 — 동일 입력 → 동일 출력
# ---------------------------------------------------------------------------


def test_deterministic(sample_draws: list[DrawResult]) -> None:
    """동일 입력을 두 번 호출하면 동일 결과를 반환한다."""
    from lotto.web.data import prediction_report

    r1 = prediction_report(sample_draws, recent_n=8)
    r2 = prediction_report(sample_draws, recent_n=8)
    assert r1 == r2


# ---------------------------------------------------------------------------
# 10: 가중치 합 == 1.0
# ---------------------------------------------------------------------------


def test_weight_sum_is_one() -> None:
    """4개 가중치 상수의 합은 1.0이다."""
    from lotto.web.data import (
        _W_FREQUENCY,
        _W_INTERVAL,
        _W_ODD_EVEN,
        _W_RANGE,
    )

    assert _W_FREQUENCY + _W_INTERVAL + _W_ODD_EVEN + _W_RANGE == 1.0


def test_weights_in_result(sample_draws: list[DrawResult]) -> None:
    """반환 구조의 weights는 4개 키와 명세된 값을 갖는다."""
    from lotto.web.data import prediction_report

    result = prediction_report(sample_draws, recent_n=8)
    assert result["weights"] == {
        "frequency": 0.40,
        "interval": 0.30,
        "odd_even": 0.15,
        "range": 0.15,
    }


# ---------------------------------------------------------------------------
# 11: 타이브레이크 — composite 동률 시 낮은 번호 우선
# ---------------------------------------------------------------------------


def test_tie_break_lower_number_first() -> None:
    """composite_score 동률일 때 top_candidates에서 낮은 번호가 앞선다.

    단일 회차 [1,2,3,4,5,6] (모두 홀짝 3:3 불가 — 홀 3 짝 3)에서는
    출현 6개 번호의 빈도/간격이 모두 동일하므로 홀짝/범위만 변별력을 가진다.
    동률 후보 사이에서는 낮은 번호가 먼저 와야 한다.
    """
    from lotto.web.data import prediction_report

    draws = [_mk(1, date(2024, 1, 6), [1, 2, 3, 4, 5, 6], 7)]
    result = prediction_report(draws, recent_n=1)
    candidates = result["top_candidates"]
    # 인접한 동일 점수 후보 쌍에서 번호가 오름차순인지 확인
    for a, b in zip(candidates, candidates[1:]):  # noqa: B905 — Python 3.9 호환
        if a["composite_score"] == b["composite_score"]:
            assert a["number"] < b["number"]


# ---------------------------------------------------------------------------
# Edge: 인자 미전달 시 get_draws() 자동 호출
# ---------------------------------------------------------------------------


def test_no_args_calls_get_draws(
    monkeypatch: pytest.MonkeyPatch, sample_draws: list[DrawResult]
) -> None:
    """draws 인자 생략 시 get_draws()를 자동 호출한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)

    result = wd.prediction_report(recent_n=8)
    assert result["draws_analyzed"] == len(sample_draws)
    assert len(result["top_candidates"]) == 10
