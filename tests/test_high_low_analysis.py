"""SPEC-LOTTO-061: 고저 비율 분석 테스트.

데이터 계층(get_high_low_stats), 캐시, 페이지/API 라우트를
RED-GREEN-REFACTOR로 검증한다.

분류(회차별 본번호 6개, 보너스 제외):
- 저(low): 1~22 (경계 22는 low)
- 고(high): 23~45 (경계 23은 high)
- high_count == 6 - low_count (불변식, 합 항상 6)
- balanced(균형) 회차: low_count == high_count == 3
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
    bonus는 본번호 외 값을 사용해 고저 집계에 영향을 주지 않음을 검증할 수 있게 한다.
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
# 데이터 계층: get_high_low_stats — 빈 데이터
# ---------------------------------------------------------------------------


def test_high_low_empty_zeros() -> None:
    """빈 데이터는 total_draws=0, 평균/카운트/비율 0을 반환한다."""
    from lotto.web import data as wd

    result = wd.get_high_low_stats([])

    assert result["total_draws"] == 0
    assert result["avg_low"] == 0.0
    assert result["avg_high"] == 0.0
    assert result["most_common_low_count"] == 0
    assert result["most_common_high_count"] == 0
    assert result["balanced_count"] == 0
    assert result["balanced_pct"] == 0.0


def test_high_low_none_zeros() -> None:
    """None 입력도 빈 데이터와 동일하게 처리한다."""
    from lotto.web import data as wd

    result = wd.get_high_low_stats(None)

    assert result["total_draws"] == 0


def test_high_low_empty_distributions_all_keys_zero() -> None:
    """빈 데이터의 분포는 0..6 모든 키가 0이다."""
    from lotto.web import data as wd

    result = wd.get_high_low_stats([])

    assert set(result["low_distribution"].keys()) == set(range(7))
    assert set(result["high_distribution"].keys()) == set(range(7))
    assert all(v == 0 for v in result["low_distribution"].values())
    assert all(v == 0 for v in result["high_distribution"].values())
    assert all(v == 0 for v in result["low_distribution_pct"].values())
    assert all(v == 0 for v in result["high_distribution_pct"].values())


# ---------------------------------------------------------------------------
# 데이터 계층: 단일 회차
# ---------------------------------------------------------------------------


def test_high_low_single_all_low() -> None:
    """[1,2,3,4,5,6] → 저 6, 고 0."""
    from lotto.web import data as wd

    result = wd.get_high_low_stats([_mk(1, [1, 2, 3, 4, 5, 6])])

    assert result["low_distribution"][6] == 1
    assert result["high_distribution"][0] == 1
    assert result["avg_low"] == 6.0
    assert result["avg_high"] == 0.0


def test_high_low_single_all_high() -> None:
    """[23,24,25,26,27,28] → 저 0, 고 6."""
    from lotto.web import data as wd

    result = wd.get_high_low_stats([_mk(1, [23, 24, 25, 26, 27, 28])])

    assert result["low_distribution"][0] == 1
    assert result["high_distribution"][6] == 1
    assert result["avg_low"] == 0.0
    assert result["avg_high"] == 6.0


def test_high_low_boundary_22_low_23_high() -> None:
    """경계: 22는 low, 23은 high.

    [22,23,1,45,11,33] → 저(1,11,22)=3, 고(23,33,45)=3 → 균형.
    """
    from lotto.web import data as wd

    result = wd.get_high_low_stats([_mk(1, [22, 23, 1, 45, 11, 33])])

    assert result["low_distribution"][3] == 1
    assert result["high_distribution"][3] == 1
    assert result["balanced_count"] == 1
    assert result["avg_low"] == 3.0
    assert result["avg_high"] == 3.0


def test_high_low_single_balanced() -> None:
    """[1,2,3,30,40,45] → 저 3, 고 3 (균형)."""
    from lotto.web import data as wd

    result = wd.get_high_low_stats([_mk(1, [1, 2, 3, 30, 40, 45])])

    assert result["low_distribution"][3] == 1
    assert result["high_distribution"][3] == 1
    assert result["balanced_count"] == 1
    assert result["balanced_pct"] == 100.0


def test_high_low_bonus_excluded() -> None:
    """보너스 번호는 고저 집계에 포함되지 않는다.

    본번호 [1,2,3,4,5,6](모두 low)에 고(high) 보너스 30을 주어도
    고 카운트는 0이어야 한다 (보너스 제외).
    """
    from lotto.web import data as wd

    result = wd.get_high_low_stats([_mk(1, [1, 2, 3, 4, 5, 6], bonus=30)])

    assert result["high_distribution"][0] == 1
    assert result["avg_high"] == 0.0


# ---------------------------------------------------------------------------
# 데이터 계층: 4회차 픽스처 (avg_low=3.25, balanced=1, balanced_pct=25.0)
# ---------------------------------------------------------------------------


def _four_draw_fixture() -> list[DrawResult]:
    """저 개수 [6,0,3,4]가 되도록 구성한 4회차 픽스처.

    회차 1: [1,2,3,4,5,6]      → 저 6
    회차 2: [23,24,25,26,27,28] → 저 0
    회차 3: [1,2,3,30,40,45]    → 저 3 (균형)
    회차 4: [1,2,3,4,23,24]     → 저 4
    합계 저 = 6+0+3+4 = 13 → avg_low = 13/4 = 3.25
    avg_high = (0+6+3+2)/4 = 11/4 = 2.75
    """
    return [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [23, 24, 25, 26, 27, 28]),
        _mk(3, [1, 2, 3, 30, 40, 45]),
        _mk(4, [1, 2, 3, 4, 23, 24]),
    ]


def test_high_low_four_draw_avg_low() -> None:
    """4회차 픽스처: avg_low == 3.25."""
    from lotto.web import data as wd

    result = wd.get_high_low_stats(_four_draw_fixture())

    assert result["total_draws"] == 4
    assert result["avg_low"] == 3.25


def test_high_low_four_draw_avg_high() -> None:
    """4회차 픽스처: avg_high == 2.75 (== 6 - avg_low)."""
    from lotto.web import data as wd

    result = wd.get_high_low_stats(_four_draw_fixture())

    assert result["avg_high"] == 2.75


def test_high_low_four_draw_balanced() -> None:
    """4회차 픽스처: balanced_count == 1, balanced_pct == 25.0."""
    from lotto.web import data as wd

    result = wd.get_high_low_stats(_four_draw_fixture())

    assert result["balanced_count"] == 1
    assert result["balanced_pct"] == 25.0


def test_high_low_four_draw_low_distribution() -> None:
    """4회차 픽스처: low_distribution은 저 개수 [6,0,3,4]를 반영한다."""
    from lotto.web import data as wd

    result = wd.get_high_low_stats(_four_draw_fixture())
    dist = result["low_distribution"]

    assert dist[6] == 1  # 회차 1
    assert dist[0] == 1  # 회차 2
    assert dist[3] == 1  # 회차 3
    assert dist[4] == 1  # 회차 4
    assert dist[1] == 0
    assert dist[2] == 0
    assert dist[5] == 0


# ---------------------------------------------------------------------------
# 데이터 계층: 불변식 / 분포 키
# ---------------------------------------------------------------------------


def test_high_low_all_distribution_keys_present() -> None:
    """low/high distribution은 0..6 키를 모두 포함한다 (zero 포함)."""
    from lotto.web import data as wd

    result = wd.get_high_low_stats([_mk(1, [1, 2, 3, 30, 40, 45])])

    assert set(result["low_distribution"].keys()) == set(range(7))
    assert set(result["high_distribution"].keys()) == set(range(7))
    assert set(result["low_distribution_pct"].keys()) == set(range(7))
    assert set(result["high_distribution_pct"].keys()) == set(range(7))


def test_high_low_sum_invariant() -> None:
    """불변식: low_count + high_count == 6 (분포 대칭성).

    low_distribution[k] == high_distribution[6-k] 이어야 한다.
    """
    from lotto.web import data as wd

    result = wd.get_high_low_stats(_four_draw_fixture())
    low = result["low_distribution"]
    high = result["high_distribution"]

    for k in range(7):
        assert low[k] == high[6 - k]


def test_high_low_distribution_sums_to_total_draws() -> None:
    """low/high distribution 값 합 == total_draws."""
    from lotto.web import data as wd

    result = wd.get_high_low_stats(_four_draw_fixture())

    assert sum(result["low_distribution"].values()) == 4
    assert sum(result["high_distribution"].values()) == 4


def test_high_low_pct_sums_to_100() -> None:
    """low/high distribution_pct 값 합 ≈ 100 (허용 오차 0.1)."""
    from lotto.web import data as wd

    result = wd.get_high_low_stats(_four_draw_fixture())

    assert abs(sum(result["low_distribution_pct"].values()) - 100.0) < 0.1
    assert abs(sum(result["high_distribution_pct"].values()) - 100.0) < 0.1


def test_high_low_pct_values() -> None:
    """distribution_pct = count / total_draws * 100 (2 decimals)."""
    from lotto.web import data as wd

    # 4회차: 저 6이 1회 → 25.0%
    result = wd.get_high_low_stats(_four_draw_fixture())

    assert result["low_distribution_pct"][6] == 25.0
    assert result["low_distribution_pct"][1] == 0.0


# ---------------------------------------------------------------------------
# 데이터 계층: most_common 동률 타이브레이크 (작은 값 우선)
# ---------------------------------------------------------------------------


def test_high_low_most_common_basic() -> None:
    """most_common_low_count는 가장 빈도 높은 저 개수를 택한다."""
    from lotto.web import data as wd

    # 저 3이 2회, 나머지 1회 → most_common_low_count == 3
    draws = [
        _mk(1, [1, 2, 3, 30, 40, 45]),    # 저 3
        _mk(2, [1, 10, 22, 23, 35, 44]),  # 저 3
        _mk(3, [1, 2, 3, 4, 5, 6]),       # 저 6
    ]
    result = wd.get_high_low_stats(draws)

    assert result["most_common_low_count"] == 3


def test_high_low_most_common_tie_smallest_wins() -> None:
    """most_common 동률 시 더 작은 값이 선택된다.

    저 2가 1회, 저 4가 1회로 동률 → 작은 값 2를 택한다.
    """
    from lotto.web import data as wd

    # 회차1: 저 2 (1,2 + 고 4개), 회차2: 저 4 (1,2,3,4 + 고 2개)
    draws = [
        _mk(1, [1, 2, 23, 24, 25, 26]),   # 저 2
        _mk(2, [1, 2, 3, 4, 23, 24]),     # 저 4
    ]
    result = wd.get_high_low_stats(draws)

    assert result["most_common_low_count"] == 2


def test_high_low_most_common_high_count() -> None:
    """most_common_high_count도 동률 시 더 작은 값을 택한다.

    고 2가 1회, 고 4가 1회 동률 → 작은 값 2.
    """
    from lotto.web import data as wd

    # 회차1: 저 4 → 고 2, 회차2: 저 2 → 고 4
    draws = [
        _mk(1, [1, 2, 3, 4, 23, 24]),     # 고 2
        _mk(2, [1, 2, 23, 24, 25, 26]),   # 고 4
    ]
    result = wd.get_high_low_stats(draws)

    assert result["most_common_high_count"] == 2


# ---------------------------------------------------------------------------
# 데이터 계층: 입력 불변성
# ---------------------------------------------------------------------------


def test_high_low_does_not_mutate_input() -> None:
    """입력 draws 리스트를 변형하지 않는다."""
    from lotto.web import data as wd

    draws = _four_draw_fixture()
    snapshot = list(draws)
    wd.get_high_low_stats(draws)

    assert draws == snapshot


# ---------------------------------------------------------------------------
# 캐시
# ---------------------------------------------------------------------------


def test_high_low_cache_populated_after_first_call() -> None:
    """첫 호출 후 캐시가 채워진다."""
    from lotto.web import data as wd

    wd.invalidate_cache()
    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    wd.get_high_low_stats(draws)

    assert str(len(draws)) in wd._high_low_cache


def test_high_low_cache_hit_returns_same_object() -> None:
    """두 번째 호출은 캐시된 동일 객체를 반환한다."""
    from lotto.web import data as wd

    wd.invalidate_cache()
    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    first = wd.get_high_low_stats(draws)
    second = wd.get_high_low_stats(draws)

    assert first is second


def test_high_low_invalidate_clears_cache() -> None:
    """invalidate_cache()는 고저 캐시를 비운다."""
    from lotto.web import data as wd

    wd.get_high_low_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    wd.invalidate_cache()

    assert wd._high_low_cache == {}


# ---------------------------------------------------------------------------
# 라우트: 페이지/API
# ---------------------------------------------------------------------------


def test_high_low_page_renders(api_client: TestClient) -> None:
    """GET /stats/high-low는 200으로 렌더된다."""
    with _patch_draws([_mk(1, [1, 2, 3, 30, 40, 45])]):
        resp = api_client.get("/stats/high-low")

    assert resp.status_code == 200
    assert "고저" in resp.text


def test_high_low_page_empty_state(api_client: TestClient) -> None:
    """데이터 부재 시에도 페이지는 200."""
    with _patch_draws([]):
        resp = api_client.get("/stats/high-low")

    assert resp.status_code == 200


def test_high_low_api_returns_json(api_client: TestClient) -> None:
    """GET /api/stats/high-low는 고저 분석 JSON을 반환한다."""
    with _patch_draws(_four_draw_fixture()):
        resp = api_client.get("/api/stats/high-low")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    assert body["avg_low"] == 3.25
    assert body["balanced_count"] == 1


def test_high_low_api_empty(api_client: TestClient) -> None:
    """데이터 부재 시에도 API는 200으로 정상 응답."""
    with _patch_draws([]):
        resp = api_client.get("/api/stats/high-low")

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
