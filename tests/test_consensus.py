"""SPEC-LOTTO-051: 교차 전략 합의(consensus) 오버레이 테스트.

읽기 전용 합의 오버레이를 검증한다. 추천 표시 시 각 번호가 11개 전략 중
몇 개에서 추천되는지(consensus N/11)를 주석으로 표시하고, 합의 4 이상이면
주의 배지를 부여한다.

핵심 불변식:
- get_cross_strategy_consensus는 recommend_by_strategy만 호출 (private 접근 금지)
- STRATEGY_LABELS마다 정확히 1회씩, 총 11회 호출
- 반환 매핑은 target_numbers의 모든 번호를 키로 갖고 값은 0..11
- Recommendation dataclass / recommender.py 코어는 변경하지 않음
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult, Statistics
from lotto.recommender import STRATEGY_LABELS, LottoRecommender


@pytest.fixture
def sample_stats(mini_draws: list[DrawResult]) -> Statistics:
    """mini-dataset 기반 Statistics 픽스처."""
    from lotto.analyzer import LottoAnalyzer

    return LottoAnalyzer().analyze(mini_draws)


@pytest.fixture
def api_client() -> TestClient:
    """매 테스트 새 TestClient — 라우터는 모듈 공유."""
    from lotto.web.app import app

    return TestClient(app)


def _mk(no: int, d: date, nums: list[int], bonus: int) -> DrawResult:
    return DrawResult(
        drwNo=no, date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


class _CountingRecommender:
    """recommend_by_strategy 호출을 기록하는 스파이 래퍼.

    실제 추천 로직은 위임하되, 호출된 라벨 목록을 calls에 누적한다.
    이를 통해 '11회만 호출' / 'private 미접근' 불변식을 검증한다.
    """

    def __init__(self, inner: LottoRecommender) -> None:
        self._inner = inner
        self.calls: list[str] = []

    def recommend_by_strategy(self, label: str):  # noqa: ANN201
        self.calls.append(label)
        return self._inner.recommend_by_strategy(label)


# ---------------------------------------------------------------------------
# AC-07: recommend_by_strategy 정확히 11회 호출 (전략 라벨당 1회)
# ---------------------------------------------------------------------------


def test_consensus_calls_recommend_by_strategy_exactly_11_times(
    sample_stats: Statistics,
) -> None:
    """get_cross_strategy_consensus는 11개 전략 각각 1회씩 호출한다 (AC-04/AC-07)."""
    from lotto.web.data import get_cross_strategy_consensus

    spy = _CountingRecommender(LottoRecommender(sample_stats))
    get_cross_strategy_consensus(spy, [1, 2, 3])

    assert len(spy.calls) == 11
    assert sorted(spy.calls) == sorted(STRATEGY_LABELS)


# ---------------------------------------------------------------------------
# AC-06: 반환 매핑은 target_numbers 전부를 키로, 값은 0..11
# ---------------------------------------------------------------------------


def test_consensus_returns_all_target_keys_with_valid_counts(
    sample_stats: Statistics,
) -> None:
    """반환 매핑은 모든 target_numbers를 키로 갖고 값은 0~11 범위다 (AC-06)."""
    from lotto.web.data import get_cross_strategy_consensus

    rec = LottoRecommender(sample_stats)
    targets = [1, 7, 15, 23, 44]
    result = get_cross_strategy_consensus(rec, targets)

    assert set(result.keys()) == set(targets)
    for count in result.values():
        assert 0 <= count <= len(STRATEGY_LABELS)


# ---------------------------------------------------------------------------
# AC-09: target_numbers에 없는 번호는 반환 매핑에 없다
# ---------------------------------------------------------------------------


def test_consensus_excludes_non_target_numbers(sample_stats: Statistics) -> None:
    """target_numbers에 없는 번호는 결과 매핑에 포함되지 않는다 (AC-09)."""
    from lotto.web.data import get_cross_strategy_consensus

    rec = LottoRecommender(sample_stats)
    targets = [5, 10]
    result = get_cross_strategy_consensus(rec, targets)

    assert set(result.keys()) == {5, 10}
    # target에 없는 번호는 키가 아니다
    assert 3 not in result
    assert 40 not in result


# ---------------------------------------------------------------------------
# AC-11: 빈 target_numbers → 빈 매핑
# ---------------------------------------------------------------------------


def test_consensus_empty_targets_returns_empty_mapping(
    sample_stats: Statistics,
) -> None:
    """빈 target_numbers는 빈 매핑을 반환한다 (AC-11)."""
    from lotto.web.data import get_cross_strategy_consensus

    rec = LottoRecommender(sample_stats)
    result = get_cross_strategy_consensus(rec, [])

    assert result == {}


# ---------------------------------------------------------------------------
# AC-08: 여러 전략에 등장하는 번호의 합의 카운트 정확성
# ---------------------------------------------------------------------------


def test_consensus_counts_match_actual_strategy_recommendations(
    sample_stats: Statistics,
) -> None:
    """합의 카운트는 실제 전략 추천 결과와 일치한다 (AC-08).

    동일 recommender로 11개 전략을 직접 호출해 산출한 기대 카운트와
    get_cross_strategy_consensus 결과가 일치하는지 검증한다.
    (난수 사용 전략이 있으므로 시드 고정 후 양쪽을 동일하게 비교)
    """
    import random

    from lotto.web.data import get_cross_strategy_consensus

    targets = list(range(1, 46))

    # 기대값: 시드 고정 후 11개 전략을 직접 호출하여 카운트
    random.seed(20260609)
    rec_expected = LottoRecommender(sample_stats)
    expected: dict[int, int] = dict.fromkeys(targets, 0)
    for label in STRATEGY_LABELS:
        picked = set(rec_expected.recommend_by_strategy(label).numbers)
        for n in targets:
            if n in picked:
                expected[n] += 1

    # 실제값: 동일 시드 재고정 후 합의 함수 호출
    random.seed(20260609)
    rec_actual = LottoRecommender(sample_stats)
    actual = get_cross_strategy_consensus(rec_actual, targets)

    assert actual == expected


# ---------------------------------------------------------------------------
# AC-01: GET /recommend?count=5 → HTTP 200, 번호에 N/11 합의 표시
# ---------------------------------------------------------------------------


def test_recommend_page_shows_consensus(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /recommend는 200을 반환하고 각 번호에 N/11 합의를 표시한다 (AC-01)."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [1, 10, 20, 30, 40, 45], 5),
        _mk(2, date(2023, 1, 14), [1, 10, 15, 25, 35, 44], 3),
        _mk(3, date(2023, 1, 21), [1, 2, 3, 10, 11, 12], 7),
    ]
    from lotto.analyzer import LottoAnalyzer

    stats = LottoAnalyzer().analyze(draws)
    monkeypatch.setattr(wd, "get_stats", lambda: stats)
    monkeypatch.setattr(wd, "STATS_PATH", _ExistingPath())

    response = api_client.get("/recommend?count=5")
    assert response.status_code == 200, response.text
    # N/11 형식의 합의 표시가 렌더링되어야 한다
    assert "/11" in response.text


# ---------------------------------------------------------------------------
# AC-10: recommendations None → 합의 스킵, 200, 패널 미표시
# ---------------------------------------------------------------------------


def test_recommend_page_no_stats_skips_consensus(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """통계 부재 시 합의를 스킵하고 200을 반환하며 패널을 표시하지 않는다 (AC-10)."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_recommendations", lambda count=5: None)

    response = api_client.get("/recommend?count=5")
    assert response.status_code == 200, response.text
    # 합의 패널 마커가 없어야 한다
    assert "consensus-panel" not in response.text


# ---------------------------------------------------------------------------
# AC-02: GET /api/recommendations?count=5 → 각 추천에 consensus 필드
# ---------------------------------------------------------------------------


def test_api_recommendations_includes_consensus_field(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """API 추천 응답의 각 객체는 번호→카운트 매핑인 consensus 필드를 포함한다 (AC-02)."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [1, 10, 20, 30, 40, 45], 5),
        _mk(2, date(2023, 1, 14), [1, 10, 15, 25, 35, 44], 3),
        _mk(3, date(2023, 1, 21), [1, 2, 3, 10, 11, 12], 7),
    ]
    from lotto.analyzer import LottoAnalyzer

    stats = LottoAnalyzer().analyze(draws)
    monkeypatch.setattr(wd, "get_stats", lambda: stats)
    monkeypatch.setattr(wd, "STATS_PATH", _ExistingPath())

    response = api_client.get("/api/recommendations?count=5")
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 5
    for item in body:
        assert "consensus" in item
        consensus = item["consensus"]
        assert isinstance(consensus, dict)
        # 추천된 모든 번호가 consensus 키에 포함된다 (JSON은 키가 문자열)
        for num in item["numbers"]:
            assert str(num) in consensus
            assert 0 <= consensus[str(num)] <= 11


class _ExistingPath:
    """STATS_PATH.exists()가 True를 반환하도록 하는 테스트 더블."""

    def exists(self) -> bool:
        return True
