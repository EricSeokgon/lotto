"""SPEC-LOTTO-011 REQ-COV-001: LottoRecommender _pick_set 폴백 경로 테스트.

random.sample을 mock하여 항상 excluded와 충돌하는 값을 반환하도록 만들어
전략별 100회 시도 실패 후 candidates 폴백 경로와 최종 RuntimeError 경로를 검증한다.

@MX:SPEC: SPEC-LOTTO-011 REQ-COV-001
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from lotto.recommender import STRATEGY_LABELS, LottoRecommender


def _make_recommender_with_dummy_stats() -> LottoRecommender:
    """_pick_set 단독 테스트용 더미 stats를 가진 recommender를 만든다."""
    # _pick_set은 stats 객체에 직접 접근하지 않으므로 None으로 충분하다.
    # 단, 인스턴스 메서드이기 때문에 self만 있으면 호출 가능하다.
    return LottoRecommender.__new__(LottoRecommender)


def _strategy_idx_for(label: str) -> int:
    """label에 해당하는 strategy_idx를 반환한다."""
    return STRATEGY_LABELS.index(label)


def _build_excluded(label: str, collision_sets: list) -> set:
    """label 전략으로 분기하도록 excluded set을 구성한다.

    _pick_set은 `len(excluded) % len(STRATEGY_LABELS)`로 strategy_idx를 결정한다.
    최종 len(excluded) == strategy_idx 가 되도록 음수 더미를 채운 후
    collision_sets(실제 1~45 충돌 frozenset들)를 추가한다.

    Note: collision_sets는 실제 번호 frozenset이며, dummy와 절대 충돌하지 않는다.
    Note: dummy 개수가 target_idx보다 많을 수 없으므로 collision_sets는
          dummy slots를 일부 대체하는 형태가 아니라, dummy + collision == target_idx
          가 되도록 dummy 수를 조정해야 한다.
    """
    target_idx = _strategy_idx_for(label)
    n_collisions = len(collision_sets)
    n_dummies = max(0, target_idx - n_collisions)
    excluded: set = {frozenset({-i}) for i in range(1, n_dummies + 1)}
    for cs in collision_sets:
        excluded.add(cs)
    return excluded


def _scores_all_ones() -> dict[int, float]:
    """1~45 모든 번호에 동일한 점수를 부여한 dict."""
    return dict.fromkeys(range(1, 46), 1.0)


# === REQ-COV-001 (a): 홀짝균형 100회 시도 실패 → candidates 폴백 ===


def test_odd_even_balance_falls_back_after_100_failures() -> None:
    """label='홀짝균형'에서 random.sample 결과가 항상 excluded에 포함되면
    100회 후 candidates = range(1, 46) 폴백 경로로 진입한다.
    """
    recommender = _make_recommender_with_dummy_stats()
    scores = _scores_all_ones()

    # random.sample이 항상 [1,3,5]/[2,4,6]을 반환하도록 강제
    # → 조합 [1,2,3,4,5,6]을 excluded에 추가하여 100회 실패 유도
    collision = frozenset([1, 2, 3, 4, 5, 6])
    excluded = _build_excluded("홀짝균형", [collision])

    def fake_sample(pool: list[int], k: int) -> list[int]:
        # 홀수 풀이면 [1,3,5], 짝수 풀이면 [2,4,6]
        if 1 in pool and 2 not in pool:
            return [1, 3, 5]
        if 2 in pool and 1 not in pool:
            return [2, 4, 6]
        # 폴백 후 호출되는 일반 sample은 1~45에서 다른 조합 반환
        return [7, 8, 9, 11, 13, 15]

    with patch("lotto.recommender.random.sample", side_effect=fake_sample):
        numbers, label = recommender._pick_set(scores, excluded)

    assert label == "홀짝균형"
    assert len(numbers) == 6
    assert all(1 <= n <= 45 for n in numbers)
    # 폴백 결과가 excluded에 없어야 한다
    assert frozenset(numbers) not in excluded


# === REQ-COV-001 (b): 번호대균형 100회 시도 실패 → candidates 폴백 ===


def test_zone_balance_falls_back_after_100_failures() -> None:
    """label='번호대균형'에서 zone-pick이 항상 excluded와 충돌하면
    100회 후 candidates = range(1, 46) 폴백 경로로 진입한다.
    """
    recommender = _make_recommender_with_dummy_stats()
    scores = _scores_all_ones()

    # 번호대균형은 zone 기반 무작위 + remaining_pool sample.
    # random 함수 전체를 모킹하여 항상 동일한 [1,2,3,4,5,6]을 생성하도록 한다.
    collision = frozenset([1, 2, 3, 4, 5, 6])
    excluded = _build_excluded("번호대균형", [collision])

    sample_calls = [0]

    def fake_randint(low: int, high: int) -> int:
        # zone-pick 단계 동안 [1,2,3,4]를 순환적으로 반환
        return [1, 2, 3, 4][(low + high) % 4]

    def fake_sample(pool: list[Any], k: int) -> list[Any]:
        sample_calls[0] += 1
        # 처음 100회 동안 remaining_pool에서 [5,6]을 반환 → [1,2,3,4,5,6] 충돌
        if k == 2 and sample_calls[0] <= 100:  # noqa: PLR2004
            return [5, 6]
        # 100회 후 폴백 일반 sample (k=6, pool=1..45)에서는
        # excluded와 충돌하지 않는 다른 6개 조합 반환
        if k == 6:  # noqa: PLR2004
            return [10, 20, 30, 40, 41, 42]
        # 그 외 (remaining_pool sample이 추가로 호출되면) — 비충돌 값
        return [7, 8, 9, 11, 13, 15][:k]

    def fake_shuffle(seq: list[Any]) -> None:
        # in-place shuffle은 그대로 두기
        pass

    with (
        patch("lotto.recommender.random.randint", side_effect=fake_randint),
        patch("lotto.recommender.random.sample", side_effect=fake_sample),
        patch("lotto.recommender.random.shuffle", side_effect=fake_shuffle),
    ):
        numbers, label = recommender._pick_set(scores, excluded)

    assert label == "번호대균형"
    assert len(numbers) == 6
    assert all(1 <= n <= 45 for n in numbers)


# === REQ-COV-001 (c): 핫콜드혼합 100회 시도 실패 → candidates 폴백 ===


def test_hot_cold_mix_falls_back_after_100_failures() -> None:
    """label='핫콜드혼합'에서 hot/cold sample 결과가 항상 excluded와 충돌하면
    100회 후 candidates = range(1, 46) 폴백 경로로 진입한다.
    """
    recommender = _make_recommender_with_dummy_stats()
    scores = _scores_all_ones()

    # 동일한 결과(1,2,3,4,5,6)를 만들기 위해 sample을 고정
    collision = frozenset([1, 2, 3, 4, 5, 6])
    excluded = _build_excluded("핫콜드혼합", [collision])

    call_count = [0]

    def fake_sample(pool: list[Any], k: int) -> list[Any]:
        call_count[0] += 1
        # hot pool은 sorted_by_freq[:15], cold는 [-15:].
        # 점수가 모두 1.0이므로 정렬 순서 의존적. 첫 호출은 hot, 두 번째는 cold.
        # 항상 [1,2,3]/[4,5,6] 반환하여 같은 조합 유도
        # 단, 폴백 후 일반 sample은 다른 조합 반환해야 함
        if k == 3 and call_count[0] <= 200:  # noqa: PLR2004
            return [1, 2, 3] if call_count[0] % 2 == 1 else [4, 5, 6]
        # 폴백 candidates sample
        return [7, 8, 9, 10, 11, 12]

    with patch("lotto.recommender.random.sample", side_effect=fake_sample):
        numbers, label = recommender._pick_set(scores, excluded)

    assert label == "핫콜드혼합"
    assert len(numbers) == 6
    assert all(1 <= n <= 45 for n in numbers)


# === REQ-COV-001 (d): 후보 부족 경고 (line 230) ===


def test_candidates_under_six_emits_warning() -> None:
    """candidates 길이가 6 미만이면 경고가 발생하고 전체 범위로 폴백한다.

    sorted_nums[-20:] 같은 정상 경로에서는 항상 >= 20이 보장되지만,
    sorted_nums의 길이 자체가 6 미만인 경우(인위적 점수)를 만들 수 있다.
    """
    recommender = _make_recommender_with_dummy_stats()

    # 점수에 5개 번호만 부여 → sorted_nums 길이가 5
    scores = {n: float(n) for n in range(1, 6)}

    # 균형 전략(label='균형')은 candidates = list(range(1, 46))이므로 적합하지 않음.
    # 고빈도 전략(label='고빈도')은 sorted_nums[:20]이므로 점수가 5개면 후보가 5개가 된다.
    # 고빈도는 strategy_idx=0 → excluded 크기 0
    excluded: set = set()

    with pytest.warns(UserWarning, match="후보 번호 부족"):
        numbers, label = recommender._pick_set(scores, excluded)

    assert label == "고빈도"
    assert len(numbers) == 6
    # 폴백 후에는 1~45 전체 범위에서 선택되어야 한다
    assert all(1 <= n <= 45 for n in numbers)


# === REQ-COV-001 (e): 최종 폴백 RuntimeError (lines 237-244) ===


def test_all_attempts_fail_raises_runtime_error() -> None:
    """100+1000 모든 시도가 실패하면 RuntimeError를 발생시킨다.

    random.sample을 mock하여 항상 [1,2,3,4,5,6]을 반환하도록 만들고,
    excluded에 해당 frozenset을 미리 넣어둔다.
    """
    recommender = _make_recommender_with_dummy_stats()
    scores = _scores_all_ones()

    # 강제된 sample 결과를 excluded에 추가하여 모든 시도가 실패하도록 함
    # '균형' 전략: candidates = list(range(1, 46))이므로 폴백 분기 없이
    # 곧장 100회 + 1000회 시도 → RuntimeError 경로로 진입한다.
    collision = frozenset([1, 2, 3, 4, 5, 6])
    excluded = _build_excluded("균형", [collision])

    with (
        patch("lotto.recommender.random.sample", return_value=[1, 2, 3, 4, 5, 6]),
        pytest.warns(UserWarning, match="중복 없는 세트 생성 실패"),
        pytest.raises(RuntimeError, match="추천 세트를 생성할 수 없습니다"),
    ):
        recommender._pick_set(scores, excluded)
