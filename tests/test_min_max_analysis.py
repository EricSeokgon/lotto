"""SPEC-LOTTO-064: 최솟값·최댓값 분포 분석 테스트.

데이터 계층(get_min_max_stats), 캐시, 페이지/API 라우트를
RED-GREEN-REFACTOR로 검증한다.

분석(회차별 본번호 6개, 보너스 제외):
- min_num:   본번호 6개의 최솟값.
- max_num:   본번호 6개의 최댓값.
- range_val: max_num - min_num.
- 카테고리:  small(range_val < 30), large(range_val >= 30).
- min/max/range_distribution: 실제로 관측된 값만 키로 포함한다(미관측 값은 0으로 채우지 않음).
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

    from contextlib import AbstractContextManager  # noqa: F401


def _mk(no: int, nums: list[int], bonus: int = 13) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    bonus는 본번호 외 값을 사용해 최솟값/최댓값 집계에 영향을 주지 않음을 검증할 수 있게 한다.
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


@pytest.fixture
def four_draws() -> list[DrawResult]:
    """SPEC 고정 4회차 픽스처.

    - D1=[3,11,18,25,33,40] → min=3,  max=40, range=37 (large)
    - D2=[1,5,10,15,20,20]  → min=1,  max=20, range=19 (small)
    - D3=[9,19,29,39,40,44] → min=9,  max=44, range=35 (large)
    - D4=[7,8,17,18,27,28]  → min=7,  max=28, range=21 (small)
    avg_min=5.0, avg_max=33.0, avg_range=28.0, small=2(50%), large=2(50%).
    """
    return [
        _mk(1, [3, 11, 18, 25, 33, 40]),
        _mk(2, [1, 5, 10, 15, 20, 20]),
        _mk(3, [9, 19, 29, 39, 40, 44]),
        _mk(4, [7, 8, 17, 18, 27, 28]),
    ]


@pytest.fixture
def api_client() -> TestClient:
    """매 테스트 새 TestClient — 라우터는 모듈 공유."""
    from lotto.web.app import app

    return TestClient(app)


# ── 빈 데이터 / None ───────────────────────────────────────────────────────


def test_empty_returns_zeros() -> None:
    """빈 리스트 → total_draws=0, 모든 수치 0, 분포는 빈 dict."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    stats = get_min_max_stats([])
    assert stats["total_draws"] == 0
    assert stats["avg_min"] == 0.0
    assert stats["avg_max"] == 0.0
    assert stats["avg_range"] == 0.0
    assert stats["most_common_min"] == 0
    assert stats["most_common_max"] == 0
    assert stats["most_common_range"] == 0
    assert stats["small_range_count"] == 0
    assert stats["large_range_count"] == 0
    assert stats["small_range_pct"] == 0.0
    assert stats["large_range_pct"] == 0.0


def test_none_returns_zeros() -> None:
    """None → 빈 리스트와 동일한 빈 구조."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    stats = get_min_max_stats(None)
    assert stats["total_draws"] == 0
    assert stats["min_distribution"] == {}
    assert stats["max_distribution"] == {}
    assert stats["range_distribution"] == {}


def test_empty_distributions_are_empty_dicts() -> None:
    """빈 데이터의 세 분포는 모두 빈 dict (0 채움 없음)."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    stats = get_min_max_stats([])
    assert stats["min_distribution"] == {}
    assert stats["max_distribution"] == {}
    assert stats["range_distribution"] == {}


# ── 단일 회차 ──────────────────────────────────────────────────────────────


def test_single_draw_large_range() -> None:
    """[3,11,18,25,33,40] → min=3, max=40, range=37 (large)."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    stats = get_min_max_stats([_mk(1, [3, 11, 18, 25, 33, 40])])
    assert stats["total_draws"] == 1
    assert stats["avg_min"] == 3.0
    assert stats["avg_max"] == 40.0
    assert stats["avg_range"] == 37.0
    assert stats["most_common_min"] == 3
    assert stats["most_common_max"] == 40
    assert stats["most_common_range"] == 37
    assert stats["large_range_count"] == 1
    assert stats["small_range_count"] == 0
    assert stats["large_range_pct"] == 100.0
    assert stats["small_range_pct"] == 0.0


def test_single_draw_small_range() -> None:
    """[5,6,7,8,9,10] → min=5, max=10, range=5 (small)."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    stats = get_min_max_stats([_mk(1, [5, 6, 7, 8, 9, 10])])
    assert stats["avg_min"] == 5.0
    assert stats["avg_max"] == 10.0
    assert stats["avg_range"] == 5.0
    assert stats["small_range_count"] == 1
    assert stats["large_range_count"] == 0
    assert stats["small_range_pct"] == 100.0


def test_single_draw_bonus_excluded() -> None:
    """보너스 번호는 min/max 집계에 영향을 주지 않는다."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    # 본번호 [5,6,7,8,9,10], 보너스 45 → 보너스가 max에 영향 없어야 함
    stats = get_min_max_stats([_mk(1, [5, 6, 7, 8, 9, 10], bonus=45)])
    assert stats["avg_max"] == 10.0
    # 본번호 최솟값보다 작은 보너스도 min에 영향 없어야 함
    invalidate_cache()
    stats2 = get_min_max_stats([_mk(2, [5, 6, 7, 8, 9, 10], bonus=1)])
    assert stats2["avg_min"] == 5.0


# ── 4회차 고정 픽스처 ──────────────────────────────────────────────────────


def test_four_draws_total(four_draws: list[DrawResult]) -> None:
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    assert get_min_max_stats(four_draws)["total_draws"] == 4


def test_four_draws_avg_min(four_draws: list[DrawResult]) -> None:
    """avg_min = (3+1+9+7)/4 = 5.0."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    assert get_min_max_stats(four_draws)["avg_min"] == 5.0


def test_four_draws_avg_max(four_draws: list[DrawResult]) -> None:
    """avg_max = (40+20+44+28)/4 = 33.0."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    assert get_min_max_stats(four_draws)["avg_max"] == 33.0


def test_four_draws_avg_range(four_draws: list[DrawResult]) -> None:
    """avg_range = (37+19+35+21)/4 = 28.0."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    assert get_min_max_stats(four_draws)["avg_range"] == 28.0


def test_four_draws_categories(four_draws: list[DrawResult]) -> None:
    """small=2(50%), large=2(50%)."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    stats = get_min_max_stats(four_draws)
    assert stats["small_range_count"] == 2
    assert stats["large_range_count"] == 2
    assert stats["small_range_pct"] == 50.0
    assert stats["large_range_pct"] == 50.0


def test_four_draws_distributions_only_seen(four_draws: list[DrawResult]) -> None:
    """분포는 실제 관측된 값만 키로 포함한다."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    stats = get_min_max_stats(four_draws)
    # min: 3,1,9,7 / max: 40,20,44,28 / range: 37,19,35,21
    assert stats["min_distribution"] == {3: 1, 1: 1, 9: 1, 7: 1}
    assert stats["max_distribution"] == {40: 1, 20: 1, 44: 1, 28: 1}
    assert stats["range_distribution"] == {37: 1, 19: 1, 35: 1, 21: 1}
    # 미관측 값(예: 2)은 분포에 없어야 함
    assert 2 not in stats["min_distribution"]


# ── 경계값 (range=29 small, range=30 large) ───────────────────────────────


def test_boundary_range_29_is_small() -> None:
    """range_val=29 → small (< 30)."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    # min=1, max=30 → range=29
    stats = get_min_max_stats([_mk(1, [1, 2, 3, 4, 5, 30])])
    assert stats["avg_range"] == 29.0
    assert stats["small_range_count"] == 1
    assert stats["large_range_count"] == 0


def test_boundary_range_30_is_large() -> None:
    """range_val=30 → large (>= 30)."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    # min=1, max=31 → range=30
    stats = get_min_max_stats([_mk(1, [1, 2, 3, 4, 5, 31])])
    assert stats["avg_range"] == 30.0
    assert stats["large_range_count"] == 1
    assert stats["small_range_count"] == 0


# ── most_common 동률 → 최솟값 ─────────────────────────────────────────────


def test_most_common_min_tie_smallest() -> None:
    """min 최빈값 동률 시 더 작은 값을 선택한다."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    # min: 5 (1회), 3 (1회) → 동률, 더 작은 3을 선택
    draws = [
        _mk(1, [5, 6, 7, 8, 9, 10]),
        _mk(2, [3, 11, 12, 13, 14, 15]),
    ]
    assert get_min_max_stats(draws)["most_common_min"] == 3


def test_most_common_max_tie_smallest() -> None:
    """max 최빈값 동률 시 더 작은 값을 선택한다."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    # max: 20 (1회), 30 (1회) → 동률, 더 작은 20을 선택
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 20]),
        _mk(2, [1, 2, 3, 4, 5, 30]),
    ]
    assert get_min_max_stats(draws)["most_common_max"] == 20


def test_most_common_range_tie_smallest() -> None:
    """range 최빈값 동률 시 더 작은 값을 선택한다."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    # range: 9 (1회), 19 (1회) → 동률, 더 작은 9를 선택
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 10]),   # range=9
        _mk(2, [1, 2, 3, 4, 5, 20]),   # range=19
    ]
    assert get_min_max_stats(draws)["most_common_range"] == 9


def test_most_common_picks_higher_count() -> None:
    """min 최빈값은 최다 빈도를 선택한다(동률 아님)."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    draws = [
        _mk(1, [5, 6, 7, 8, 9, 10]),    # min=5
        _mk(2, [5, 11, 12, 13, 14, 15]),  # min=5
        _mk(3, [3, 20, 21, 22, 23, 24]),  # min=3
    ]
    # min=5가 2회로 최다
    assert get_min_max_stats(draws)["most_common_min"] == 5


# ── 캐시 ───────────────────────────────────────────────────────────────────


def test_cache_populated_and_hit(four_draws: list[DrawResult]) -> None:
    """동일 입력 재호출 시 동일 객체를 반환(캐시 적중)."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    first = get_min_max_stats(four_draws)
    second = get_min_max_stats(four_draws)
    assert first is second


def test_cache_invalidated(four_draws: list[DrawResult]) -> None:
    """invalidate_cache 후에는 새 결과 객체를 생성한다."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    first = get_min_max_stats(four_draws)
    invalidate_cache()
    second = get_min_max_stats(four_draws)
    assert first is not second
    assert first == second


def test_cache_empty_key_separate() -> None:
    """빈 입력 캐시 키는 데이터 입력 캐시 키와 분리된다."""
    from lotto.web.data import get_min_max_stats, invalidate_cache

    invalidate_cache()
    empty = get_min_max_stats([])
    data = get_min_max_stats([_mk(1, [3, 11, 18, 25, 33, 40])])
    assert empty["total_draws"] == 0
    assert data["total_draws"] == 1


# ── 페이지 / API 라우트 ────────────────────────────────────────────────────


@contextmanager
def _patch_draws(draws: list[DrawResult]) -> Iterator[None]:
    """get_draws를 주어진 회차로 패치한다."""
    from lotto.web.data import invalidate_cache

    invalidate_cache()
    with patch("lotto.web.data.get_draws", return_value=draws):
        yield
    invalidate_cache()


def test_page_returns_200_with_data(
    api_client: TestClient, four_draws: list[DrawResult]
) -> None:
    """데이터가 있을 때 페이지는 200 + 본문에 제목 포함."""
    with _patch_draws(four_draws):
        resp = api_client.get("/stats/min-max")
    assert resp.status_code == 200
    assert "최대최소" in resp.text or "최솟값" in resp.text


def test_page_returns_200_empty(api_client: TestClient) -> None:
    """데이터가 없을 때도 페이지는 200."""
    with _patch_draws([]):
        resp = api_client.get("/stats/min-max")
    assert resp.status_code == 200


def test_api_returns_stats(
    api_client: TestClient, four_draws: list[DrawResult]
) -> None:
    """API는 집계 통계를 JSON으로 반환한다."""
    with _patch_draws(four_draws):
        resp = api_client.get("/api/stats/min-max")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    assert body["avg_min"] == 5.0
    assert body["avg_max"] == 33.0
    assert body["avg_range"] == 28.0


def test_api_empty(api_client: TestClient) -> None:
    """데이터 부재 시 API는 200 + 빈 구조."""
    with _patch_draws([]):
        resp = api_client.get("/api/stats/min-max")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 0
    assert body["min_distribution"] == {}
