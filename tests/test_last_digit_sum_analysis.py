"""SPEC-LOTTO-063: 끝자리 합계 분석 테스트.

데이터 계층(get_last_digit_sum_stats), 캐시, 페이지/API 라우트를
RED-GREEN-REFACTOR로 검증한다.

분석(회차별 본번호 6개, 보너스 제외):
- last_digit_sum: 각 번호의 끝자리(n % 10)를 모두 더한 값. 이론상 범위 0~54.
- 카테고리: low(<15), mid(15~29), high(>=30).
- sum_distribution: 실제로 관측된 합계 값만 키로 포함한다(미관측 값은 0으로 채우지 않음).
- SPEC-055의 끝자리 분포(get_last_digit_stats)와는 완전히 독립적인 별도 기능이다.
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
    bonus는 본번호 외 값을 사용해 끝자리 합계 집계에 영향을 주지 않음을 검증할 수 있게 한다.
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

    - D1=[3,11,18,25,33,40] → 끝자리 [3,1,8,5,3,0] 합=20 (mid)
    - D2=[1,2,5,6,10,20]    → 끝자리 [1,2,5,6,0,0] 합=14 (low)
    - D3=[9,19,29,39,40,44] → 끝자리 [9,9,9,9,0,4] 합=40 (high)
    - D4=[7,8,17,18,27,28]  → 끝자리 [7,8,7,8,7,8] 합=45 (high)
    avg=29.75, min=14, max=45, low=1, mid=1, high=2, most_common=14(동률→최소).
    """
    return [
        _mk(1, [3, 11, 18, 25, 33, 40]),
        _mk(2, [1, 2, 5, 6, 10, 20]),
        _mk(3, [9, 19, 29, 39, 40, 44]),
        _mk(4, [7, 8, 17, 18, 27, 28]),
    ]


@pytest.fixture
def api_client() -> TestClient:
    """매 테스트 새 TestClient — 라우터는 모듈 공유."""
    from lotto.web.app import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# 데이터 계층: get_last_digit_sum_stats — 빈 데이터
# ---------------------------------------------------------------------------


def test_empty_returns_zeros() -> None:
    """빈 리스트는 total_draws=0과 모든 수치 0, sum_distribution={} 를 반환한다."""
    from lotto.web import data as wd

    result = wd.get_last_digit_sum_stats([])

    assert result["total_draws"] == 0
    assert result["avg_sum"] == 0.0
    assert result["min_sum"] == 0
    assert result["max_sum"] == 0
    assert result["most_common_sum"] == 0
    assert result["sum_distribution"] == {}
    assert result["low_sum_count"] == 0
    assert result["mid_sum_count"] == 0
    assert result["high_sum_count"] == 0
    assert result["low_sum_pct"] == 0.0
    assert result["mid_sum_pct"] == 0.0
    assert result["high_sum_pct"] == 0.0


def test_none_returns_zeros() -> None:
    """None 입력도 빈 데이터와 동일한 빈 구조를 반환한다."""
    from lotto.web import data as wd

    result = wd.get_last_digit_sum_stats(None)

    assert result["total_draws"] == 0
    assert result["avg_sum"] == 0.0
    assert result["sum_distribution"] == {}


def test_empty_distribution_is_empty_dict_not_zero_fill() -> None:
    """빈 데이터의 sum_distribution은 0..54 키를 채우지 않고 빈 dict 이다."""
    from lotto.web import data as wd

    result = wd.get_last_digit_sum_stats([])

    assert result["sum_distribution"] == {}
    assert len(result["sum_distribution"]) == 0


# ---------------------------------------------------------------------------
# 데이터 계층: 단일 회차
# ---------------------------------------------------------------------------


def test_single_draw_low_sum() -> None:
    """[10,20,30,40,1,2] → 끝자리 [0,0,0,0,1,2] 합=3 (low)."""
    from lotto.web import data as wd

    result = wd.get_last_digit_sum_stats([_mk(1, [10, 20, 30, 40, 1, 2])])

    assert result["total_draws"] == 1
    assert result["avg_sum"] == 3.0
    assert result["min_sum"] == 3
    assert result["max_sum"] == 3
    assert result["most_common_sum"] == 3
    assert result["sum_distribution"] == {3: 1}
    assert result["low_sum_count"] == 1
    assert result["mid_sum_count"] == 0
    assert result["high_sum_count"] == 0
    assert result["low_sum_pct"] == 100.0


def test_single_draw_high_sum() -> None:
    """[9,19,29,39,7,8] → 끝자리 [9,9,9,9,7,8] 합=51 (high)."""
    from lotto.web import data as wd

    result = wd.get_last_digit_sum_stats([_mk(1, [9, 19, 29, 39, 7, 8])])

    assert result["total_draws"] == 1
    assert result["avg_sum"] == 51.0
    assert result["min_sum"] == 51
    assert result["max_sum"] == 51
    assert result["most_common_sum"] == 51
    assert result["sum_distribution"] == {51: 1}
    assert result["high_sum_count"] == 1
    assert result["high_sum_pct"] == 100.0


def test_single_draw_bonus_excluded() -> None:
    """보너스 번호는 끝자리 합계에 포함되지 않는다."""
    from lotto.web import data as wd

    # 본번호 합=3, 보너스=45(끝자리 5) — 보너스 무시되어 합은 3 유지.
    result = wd.get_last_digit_sum_stats([_mk(1, [10, 20, 30, 40, 1, 2], bonus=45)])

    assert result["sum_distribution"] == {3: 1}
    assert result["min_sum"] == 3


# ---------------------------------------------------------------------------
# 데이터 계층: 4회차 고정 픽스처
# ---------------------------------------------------------------------------


def test_four_draws_total(four_draws: list[DrawResult]) -> None:
    """4회차 픽스처의 total_draws=4."""
    from lotto.web import data as wd

    assert wd.get_last_digit_sum_stats(four_draws)["total_draws"] == 4


def test_four_draws_avg_sum(four_draws: list[DrawResult]) -> None:
    """(20+14+40+45)/4 = 29.75."""
    from lotto.web import data as wd

    assert wd.get_last_digit_sum_stats(four_draws)["avg_sum"] == 29.75


def test_four_draws_min_max(four_draws: list[DrawResult]) -> None:
    """min=14, max=45."""
    from lotto.web import data as wd

    result = wd.get_last_digit_sum_stats(four_draws)

    assert result["min_sum"] == 14
    assert result["max_sum"] == 45


def test_four_draws_categories(four_draws: list[DrawResult]) -> None:
    """low=1(D2), mid=1(D1), high=2(D3,D4) 와 각 25/25/50 비율."""
    from lotto.web import data as wd

    result = wd.get_last_digit_sum_stats(four_draws)

    assert result["low_sum_count"] == 1
    assert result["mid_sum_count"] == 1
    assert result["high_sum_count"] == 2
    assert result["low_sum_pct"] == 25.0
    assert result["mid_sum_pct"] == 25.0
    assert result["high_sum_pct"] == 50.0


def test_four_draws_distribution_only_seen(four_draws: list[DrawResult]) -> None:
    """sum_distribution은 관측된 4개 값만 키로 갖는다(0 채움 없음)."""
    from lotto.web import data as wd

    result = wd.get_last_digit_sum_stats(four_draws)

    assert result["sum_distribution"] == {20: 1, 14: 1, 40: 1, 45: 1}


def test_four_draws_most_common_tie_smallest(four_draws: list[DrawResult]) -> None:
    """모든 합계가 count=1로 동률 → 최빈 합계는 가장 작은 값(14)."""
    from lotto.web import data as wd

    assert wd.get_last_digit_sum_stats(four_draws)["most_common_sum"] == 14


# ---------------------------------------------------------------------------
# 데이터 계층: 카테고리 경계 (low<15, mid 15~29, high>=30)
# ---------------------------------------------------------------------------


def test_boundary_sum_14_is_low() -> None:
    """합계 14는 low (<15).

    본번호 [4,10,20,30,40,1] → 끝자리 [4,0,0,0,0,1] 합=5? 아니므로 직접 구성.
    [4,12,13,15,20,30] → 끝자리 [4,2,3,5,0,0] 합=14.
    """
    from lotto.web import data as wd

    result = wd.get_last_digit_sum_stats([_mk(1, [4, 12, 13, 15, 20, 30])])

    assert result["min_sum"] == 14
    assert result["low_sum_count"] == 1
    assert result["mid_sum_count"] == 0


def test_boundary_sum_15_is_mid() -> None:
    """합계 15는 mid (15~29).

    [5,12,13,15,20,30] → 끝자리 [5,2,3,5,0,0] 합=15.
    """
    from lotto.web import data as wd

    result = wd.get_last_digit_sum_stats([_mk(1, [5, 12, 13, 15, 20, 30])])

    assert result["min_sum"] == 15
    assert result["mid_sum_count"] == 1
    assert result["low_sum_count"] == 0


def test_boundary_sum_29_is_mid() -> None:
    """합계 29는 mid (15~29).

    [9,18,17,26,29,20] → 끝자리 [9,8,7,6,9,0] 합=39? 직접 검산해 구성.
    [4,15,16,17,18,9] → 끝자리 [4,5,6,7,8,9] 합=39 (X).
    [1,12,13,14,18,9] → 끝자리 [1,2,3,4,8,9] 합=27 (X).
    [4,15,16,17,18,19] → 끝자리 [4,5,6,7,8,9] 합=39 (X).
    [3,14,15,16,18,33] → 끝자리 [3,4,5,6,8,3] 합=29.
    """
    from lotto.web import data as wd

    result = wd.get_last_digit_sum_stats([_mk(1, [3, 14, 15, 16, 18, 33])])

    assert result["min_sum"] == 29
    assert result["mid_sum_count"] == 1
    assert result["high_sum_count"] == 0


def test_boundary_sum_30_is_high() -> None:
    """합계 30은 high (>=30).

    [4,14,15,16,18,33] → 끝자리 [4,4,5,6,8,3] 합=30.
    """
    from lotto.web import data as wd

    result = wd.get_last_digit_sum_stats([_mk(1, [4, 14, 15, 16, 18, 33])])

    assert result["min_sum"] == 30
    assert result["high_sum_count"] == 1
    assert result["mid_sum_count"] == 0


def test_most_common_sum_picks_higher_count() -> None:
    """동률이 아니면 가장 빈도 높은 합계를 최빈으로 반환한다."""
    from lotto.web import data as wd

    # 합=3 회차 2개, 합=51 회차 1개 → 최빈은 3.
    draws = [
        _mk(1, [10, 20, 30, 40, 1, 2]),
        _mk(2, [10, 20, 30, 40, 1, 2]),
        _mk(3, [9, 19, 29, 39, 7, 8]),
    ]
    result = wd.get_last_digit_sum_stats(draws)

    assert result["most_common_sum"] == 3
    assert result["sum_distribution"] == {3: 2, 51: 1}


# ---------------------------------------------------------------------------
# 데이터 계층: 캐시 동작
# ---------------------------------------------------------------------------


def test_cache_populated_and_hit() -> None:
    """동일 입력 재호출 시 캐시된 동일 객체를 반환한다."""
    from lotto.web import data as wd

    draws = [_mk(1, [10, 20, 30, 40, 1, 2])]
    first = wd.get_last_digit_sum_stats(draws)
    second = wd.get_last_digit_sum_stats(draws)

    assert first is second  # 캐시 히트 시 동일 객체


def test_cache_invalidated() -> None:
    """invalidate_cache 후에는 새 결과 객체를 생성한다."""
    from lotto.web import data as wd

    draws = [_mk(1, [10, 20, 30, 40, 1, 2])]
    first = wd.get_last_digit_sum_stats(draws)
    wd.invalidate_cache()
    second = wd.get_last_digit_sum_stats(draws)

    assert first is not second
    assert first == second  # 값은 동일


def test_cache_empty_key_separate() -> None:
    """빈 입력도 캐시되며 비어있지 않은 입력과 충돌하지 않는다."""
    from lotto.web import data as wd

    empty = wd.get_last_digit_sum_stats([])
    nonempty = wd.get_last_digit_sum_stats([_mk(1, [10, 20, 30, 40, 1, 2])])

    assert empty["total_draws"] == 0
    assert nonempty["total_draws"] == 1


# ---------------------------------------------------------------------------
# 라우트: 페이지 / API
# ---------------------------------------------------------------------------


@contextmanager
def _patch_draws(draws: list[DrawResult]) -> Iterator[None]:
    """get_draws를 주어진 회차로 패치하는 컨텍스트 매니저."""
    with patch("lotto.web.data.get_draws", return_value=draws):
        yield


def test_page_returns_200_with_data(
    api_client: TestClient, four_draws: list[DrawResult]
) -> None:
    """데이터가 있을 때 /stats/last-digit-sum 페이지는 200을 반환한다."""
    with _patch_draws(four_draws):
        resp = api_client.get("/stats/last-digit-sum")

    assert resp.status_code == 200
    assert "끝자리 합계" in resp.text or "끝합" in resp.text


def test_page_returns_200_empty(api_client: TestClient) -> None:
    """데이터가 없어도 페이지는 200(빈 상태 안내)을 반환한다."""
    with _patch_draws([]):
        resp = api_client.get("/stats/last-digit-sum")

    assert resp.status_code == 200


def test_api_returns_stats(
    api_client: TestClient, four_draws: list[DrawResult]
) -> None:
    """API는 끝자리 합계 통계 JSON을 반환한다."""
    with _patch_draws(four_draws):
        resp = api_client.get("/api/stats/last-digit-sum")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    assert body["avg_sum"] == 29.75
    assert body["min_sum"] == 14
    assert body["max_sum"] == 45
    assert body["most_common_sum"] == 14


def test_api_empty(api_client: TestClient) -> None:
    """데이터 부재 시 API는 200과 total_draws=0을 반환한다."""
    with _patch_draws([]):
        resp = api_client.get("/api/stats/last-digit-sum")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 0
    assert body["sum_distribution"] == {}


def test_api_distribution_keys_serialized(
    api_client: TestClient, four_draws: list[DrawResult]
) -> None:
    """JSON 직렬화 시 sum_distribution 키는 문자열이며 관측 값만 포함한다."""
    with _patch_draws(four_draws):
        resp = api_client.get("/api/stats/last-digit-sum")

    body = resp.json()
    # JSON object 키는 항상 문자열.
    assert set(body["sum_distribution"].keys()) == {"20", "14", "40", "45"}


# ---------------------------------------------------------------------------
# SPEC-055와의 독립성
# ---------------------------------------------------------------------------


def test_independent_from_spec055_last_digit() -> None:
    """SPEC-055의 get_last_digit_stats와 키/형태가 다른 별도 함수다."""
    from lotto.web import data as wd

    draws = [_mk(1, [10, 20, 30, 40, 1, 2])]
    sum_stats = wd.get_last_digit_sum_stats(draws)
    digit_stats = wd.get_last_digit_stats(draws)

    # 합계 분석은 sum_distribution/avg_sum 키를 갖는다.
    assert "sum_distribution" in sum_stats
    assert "avg_sum" in sum_stats
    # SPEC-055(get_last_digit_stats)는 합계 분석과 무관한 별도 구조이며
    # sum_distribution/avg_sum 키를 갖지 않는다.
    assert "sum_distribution" not in digit_stats
    assert "avg_sum" not in digit_stats


if TYPE_CHECKING:
    _: AbstractContextManager[None]
