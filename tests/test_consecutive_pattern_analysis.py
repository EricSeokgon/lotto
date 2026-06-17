"""SPEC-LOTTO-062: 연속 번호 패턴 분석 테스트.

데이터 계층(get_consecutive_pattern_stats), 캐시, 페이지/API 라우트를
RED-GREEN-REFACTOR로 검증한다.

분석(회차별 본번호 6개, 보너스 제외):
- 연속 쌍(consecutive pair): 정렬된 인접 두 번호 차이가 정확히 1인 쌍.
  예) [5,6,7] → (5,6),(6,7) 2쌍.
- has_triple: 정렬된 번호 중 3개 이상이 연속(차이 1)으로 이어지는 런이 있으면 True.
- pair_count: 회차당 연속 쌍 개수(0~5).
- SPEC-043의 consecutive_pattern 함수와는 독립적으로 구현된다.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult

if TYPE_CHECKING:
    from collections.abc import Iterator
    from contextlib import AbstractContextManager


def _mk(no: int, nums: list[int], bonus: int = 13) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    bonus는 본번호 외 값을 사용해 연속 집계에 영향을 주지 않음을 검증할 수 있게 한다.
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


@pytest.fixture
def api_client() -> TestClient:
    """매 테스트 새 TestClient — 라우터는 모듈 공유."""
    from lotto.web.app import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# 데이터 계층: get_consecutive_pattern_stats — 빈 데이터
# ---------------------------------------------------------------------------


def test_consecutive_empty_zeros() -> None:
    """빈 데이터는 total_draws=0, 평균/카운트/비율 0을 반환한다."""
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats([])

    assert result["total_draws"] == 0
    assert result["avg_consecutive_pairs"] == 0.0
    assert result["most_common_pair_count"] == 0
    assert result["no_consecutive_count"] == 0
    assert result["no_consecutive_pct"] == 0.0
    assert result["has_triple_count"] == 0
    assert result["has_triple_pct"] == 0.0
    assert result["max_consecutive_count"] == 0


def test_consecutive_none_zeros() -> None:
    """None 입력도 빈 데이터와 동일하게 처리한다."""
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats(None)

    assert result["total_draws"] == 0


def test_consecutive_empty_distribution_all_keys_present() -> None:
    """빈 데이터의 pair_distribution은 0..5 모든 키가 0이다."""
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats([])

    assert set(result["pair_distribution"].keys()) == set(range(6))
    assert all(v == 0 for v in result["pair_distribution"].values())
    assert set(result["pair_distribution_pct"].keys()) == set(range(6))
    assert all(v == 0 for v in result["pair_distribution_pct"].values())


# ---------------------------------------------------------------------------
# 데이터 계층: 단일 회차 — 핵심 케이스
# ---------------------------------------------------------------------------


def test_consecutive_six_in_a_row() -> None:
    """[1,2,3,4,5,6] → 연속 쌍 5개, has_triple=True."""
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats([_mk(1, [1, 2, 3, 4, 5, 6])])

    assert result["pair_distribution"][5] == 1
    assert result["avg_consecutive_pairs"] == 5.0
    assert result["has_triple_count"] == 1
    assert result["max_consecutive_count"] == 5


def test_consecutive_none_consecutive() -> None:
    """[1,3,5,7,9,11] → 연속 쌍 0개, has_triple=False."""
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats([_mk(1, [1, 3, 5, 7, 9, 11])])

    assert result["pair_distribution"][0] == 1
    assert result["avg_consecutive_pairs"] == 0.0
    assert result["has_triple_count"] == 0
    assert result["no_consecutive_count"] == 1
    assert result["no_consecutive_pct"] == 100.0


def test_consecutive_pairs_but_no_triple() -> None:
    """[1,2,4,5,7,8] → 연속 쌍 3개, has_triple=False (3연속 없음)."""
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats([_mk(1, [1, 2, 4, 5, 7, 8])])

    assert result["pair_distribution"][3] == 1
    assert result["avg_consecutive_pairs"] == 3.0
    assert result["has_triple_count"] == 0
    assert result["max_consecutive_count"] == 3


def test_consecutive_triple_in_middle() -> None:
    """[5,6,7,20,21,30] → 연속 쌍 4개((5,6),(6,7),(20,21)... 실은 3), has_triple=True.

    정렬: [5,6,7,20,21,30]
    인접 차이 1인 쌍: (5,6),(6,7),(20,21) → 4개? 검증:
    - 5→6: 1 (쌍)
    - 6→7: 1 (쌍)
    - 7→20: 13
    - 20→21: 1 (쌍)
    - 21→30: 9
    연속 쌍 = 3. SPEC 요약 표기는 "4 pairs"이나 실제 인접 차이 1 쌍은 3개다.
    has_triple은 5,6,7 런으로 True.
    """
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats([_mk(1, [5, 6, 7, 20, 21, 30])])

    # 5,6,7 (2쌍) + 20,21 (1쌍) = 3쌍
    assert result["pair_distribution"][3] == 1
    assert result["has_triple_count"] == 1
    assert result["max_consecutive_count"] == 3


def test_consecutive_bonus_excluded() -> None:
    """보너스 번호는 연속 집계에 포함되지 않는다.

    본번호 [1,3,5,7,9,11](연속 없음)에 본번호와 연속이 될 보너스 2를 줘도
    연속 쌍은 0이어야 한다 (보너스 제외).
    """
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats([_mk(1, [1, 3, 5, 7, 9, 11], bonus=2)])

    assert result["pair_distribution"][0] == 1
    assert result["avg_consecutive_pairs"] == 0.0
    assert result["has_triple_count"] == 0


# ---------------------------------------------------------------------------
# 데이터 계층: 4회차 픽스처 — pair_counts [0,2,3,3]
# ---------------------------------------------------------------------------


def _four_draw_fixture() -> list[DrawResult]:
    """연속 쌍 개수 [0,2,3,3]이 되도록 구성한 4회차 픽스처.

    회차 1: [1,3,5,7,9,11]   → 연속 쌍 0, has_triple=False
    회차 2: [1,2,3,10,20,30] → 연속 쌍 2 (1,2,3 → 2쌍), has_triple=True
    회차 3: [1,2,3,4,20,30]  → 연속 쌍 3 (1,2,3,4 → 3쌍), has_triple=True
    회차 4: [1,2,4,5,7,8]    → 연속 쌍 3 (1,2 / 4,5 / 7,8), has_triple=False
    합계 = 0+2+3+3 = 8 → avg = 8/4 = 2.0
    has_triple_count = 2 (회차 2,3)
    max_consecutive_count = 3 (최대 연속 쌍)
    """
    return [
        _mk(1, [1, 3, 5, 7, 9, 11]),
        _mk(2, [1, 2, 3, 10, 20, 30]),
        _mk(3, [1, 2, 3, 4, 20, 30]),
        _mk(4, [1, 2, 4, 5, 7, 8]),
    ]


def test_consecutive_four_draw_avg() -> None:
    """4회차 픽스처: avg_consecutive_pairs == 2.0."""
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats(_four_draw_fixture())

    assert result["total_draws"] == 4
    assert result["avg_consecutive_pairs"] == 2.0


def test_consecutive_four_draw_has_triple_count() -> None:
    """4회차 픽스처: has_triple_count == 2 (회차 2,3)."""
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats(_four_draw_fixture())

    assert result["has_triple_count"] == 2
    assert result["has_triple_pct"] == 50.0


def test_consecutive_four_draw_max() -> None:
    """4회차 픽스처: max_consecutive_count == 3."""
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats(_four_draw_fixture())

    assert result["max_consecutive_count"] == 3


def test_consecutive_four_draw_distribution() -> None:
    """4회차 픽스처: pair_distribution은 쌍 개수 [0,2,3,3]을 반영한다."""
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats(_four_draw_fixture())
    dist = result["pair_distribution"]

    assert dist[0] == 1  # 회차 1
    assert dist[2] == 1  # 회차 2
    assert dist[3] == 2  # 회차 3,4
    assert dist[1] == 0
    assert dist[4] == 0
    assert dist[5] == 0


def test_consecutive_four_draw_no_consecutive() -> None:
    """4회차 픽스처: no_consecutive_count == 1 (회차 1), pct == 25.0."""
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats(_four_draw_fixture())

    assert result["no_consecutive_count"] == 1
    assert result["no_consecutive_pct"] == 25.0


# ---------------------------------------------------------------------------
# 데이터 계층: 분포 키 / 비율 합
# ---------------------------------------------------------------------------


def test_consecutive_all_distribution_keys_present() -> None:
    """pair_distribution은 0..5 키를 모두 포함한다 (zero 포함)."""
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats([_mk(1, [1, 2, 3, 4, 5, 6])])

    assert set(result["pair_distribution"].keys()) == set(range(6))
    assert set(result["pair_distribution_pct"].keys()) == set(range(6))


def test_consecutive_distribution_sums_to_total_draws() -> None:
    """pair_distribution 값 합 == total_draws."""
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats(_four_draw_fixture())

    assert sum(result["pair_distribution"].values()) == 4


def test_consecutive_pct_sums_to_100() -> None:
    """pair_distribution_pct 값 합 ≈ 100 (허용 오차 0.1)."""
    from lotto.web import data as wd

    result = wd.get_consecutive_pattern_stats(_four_draw_fixture())

    assert abs(sum(result["pair_distribution_pct"].values()) - 100.0) < 0.1


def test_consecutive_pct_values() -> None:
    """pair_distribution_pct = count / total_draws * 100 (2 decimals)."""
    from lotto.web import data as wd

    # 4회차: 쌍 3개가 2회 → 50.0%
    result = wd.get_consecutive_pattern_stats(_four_draw_fixture())

    assert result["pair_distribution_pct"][3] == 50.0
    assert result["pair_distribution_pct"][0] == 25.0
    assert result["pair_distribution_pct"][1] == 0.0


# ---------------------------------------------------------------------------
# 데이터 계층: most_common 동률 타이브레이크 (작은 값 우선)
# ---------------------------------------------------------------------------


def test_consecutive_most_common_basic() -> None:
    """most_common_pair_count는 가장 빈도 높은 쌍 개수를 택한다."""
    from lotto.web import data as wd

    # 쌍 2가 2회, 나머지 1회 → most_common_pair_count == 2
    draws = [
        _mk(1, [1, 2, 3, 10, 20, 30]),  # 쌍 2
        _mk(2, [5, 6, 7, 11, 22, 33]),  # 쌍 2
        _mk(3, [1, 3, 5, 7, 9, 11]),    # 쌍 0
    ]
    result = wd.get_consecutive_pattern_stats(draws)

    assert result["most_common_pair_count"] == 2


def test_consecutive_most_common_tie_smallest_wins() -> None:
    """most_common 동률 시 더 작은 값이 선택된다.

    쌍 0이 1회, 쌍 2가 1회로 동률 → 작은 값 0을 택한다.
    """
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 3, 5, 7, 9, 11]),    # 쌍 0
        _mk(2, [1, 2, 3, 10, 20, 30]),  # 쌍 2
    ]
    result = wd.get_consecutive_pattern_stats(draws)

    assert result["most_common_pair_count"] == 0


# ---------------------------------------------------------------------------
# 데이터 계층: 입력 불변성
# ---------------------------------------------------------------------------


def test_consecutive_does_not_mutate_input() -> None:
    """입력 draws 리스트를 변형하지 않는다."""
    from lotto.web import data as wd

    draws = _four_draw_fixture()
    snapshot = list(draws)
    wd.get_consecutive_pattern_stats(draws)

    assert draws == snapshot


# ---------------------------------------------------------------------------
# 캐시
# ---------------------------------------------------------------------------


def test_consecutive_cache_populated_after_first_call() -> None:
    """첫 호출 후 캐시가 채워진다."""
    from lotto.web import data as wd

    wd.invalidate_cache()
    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    wd.get_consecutive_pattern_stats(draws)

    assert str(len(draws)) in wd._consecutive_cache


def test_consecutive_cache_hit_returns_same_object() -> None:
    """두 번째 호출은 캐시된 동일 객체를 반환한다."""
    from lotto.web import data as wd

    wd.invalidate_cache()
    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    first = wd.get_consecutive_pattern_stats(draws)
    second = wd.get_consecutive_pattern_stats(draws)

    assert first is second


def test_consecutive_invalidate_clears_cache() -> None:
    """invalidate_cache()는 연속 패턴 캐시를 비운다."""
    from lotto.web import data as wd

    wd.get_consecutive_pattern_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    wd.invalidate_cache()

    assert wd._consecutive_cache == {}


# ---------------------------------------------------------------------------
# 라우트: 페이지/API
# ---------------------------------------------------------------------------


def test_consecutive_page_renders(api_client: TestClient) -> None:
    """GET /stats/consecutive-pattern은 200으로 렌더된다."""
    with _patch_draws([_mk(1, [1, 2, 3, 4, 5, 6])]):
        resp = api_client.get("/stats/consecutive-pattern")

    assert resp.status_code == 200
    assert "연속" in resp.text


def test_consecutive_page_empty_state(api_client: TestClient) -> None:
    """데이터 부재 시에도 페이지는 200."""
    with _patch_draws([]):
        resp = api_client.get("/stats/consecutive-pattern")

    assert resp.status_code == 200


def test_consecutive_api_returns_json(api_client: TestClient) -> None:
    """GET /api/stats/consecutive-pattern은 연속 패턴 JSON을 반환한다."""
    with _patch_draws(_four_draw_fixture()):
        resp = api_client.get("/api/stats/consecutive-pattern")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    assert body["avg_consecutive_pairs"] == 2.0
    assert body["has_triple_count"] == 2


def test_consecutive_api_empty(api_client: TestClient) -> None:
    """데이터 부재 시에도 API는 200으로 정상 응답."""
    with _patch_draws([]):
        resp = api_client.get("/api/stats/consecutive-pattern")

    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _patch_draws(draws: list[DrawResult]) -> AbstractContextManager[None]:
    """get_draws를 주어진 draws로 패치하고 캐시를 무효화하는 컨텍스트."""
    from lotto.web import data as wd

    @contextmanager
    def _ctx() -> Iterator[None]:
        wd.invalidate_cache()
        with patch.object(wd, "get_draws", return_value=draws):
            yield
        wd.invalidate_cache()

    return _ctx()
