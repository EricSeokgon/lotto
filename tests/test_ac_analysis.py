"""SPEC-LOTTO-057: AC값(산술 복잡도) 분석 테스트.

데이터 계층(get_ac_stats), 캐시, 페이지/API 라우트를
RED-GREEN-REFACTOR로 검증한다.

AC(Arithmetic Complexity) 정의:
- 각 회차의 정렬된 본번호 6개(보너스 제외)에서 모든 C(6,2)=15개 쌍의
  차이(j>i: numbers[j]-numbers[i])를 구한다.
- 서로 다른 차이의 개수 U를 세고 AC = U - 5 (범위 0..10).
- 예) [1,2,3,4,5,6] → unique diffs={1,2,3,4,5} → U=5 → AC=0
- 예) [1,7,14,22,31,45] → 15개 차이 모두 서로 다름 → U=15 → AC=10
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult


def _mk(no: int, nums: list[int], bonus: int = 45) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
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
# 데이터 계층: get_ac_stats
# ---------------------------------------------------------------------------


def test_ac_stats_empty_all_zeros() -> None:
    """빈 데이터는 모든 수치 0, 빈 dict의 일관된 구조를 반환한다."""
    from lotto.web import data as wd

    result = wd.get_ac_stats([])

    assert result["total_draws"] == 0
    assert result["avg_ac"] == 0.0
    assert result["ac_distribution"] == {}
    assert result["ac_distribution_pct"] == {}
    assert result["most_common_ac"] == 0
    assert result["high_ac_count"] == 0
    assert result["high_ac_pct"] == 0.0
    assert result["low_ac_count"] == 0
    assert result["low_ac_pct"] == 0.0


def test_ac_single_draw_min_complexity() -> None:
    """[1,2,3,4,5,6]는 unique diffs={1,2,3,4,5} → U=5 → AC=0."""
    from lotto.web import data as wd

    result = wd.get_ac_stats([_mk(1, [1, 2, 3, 4, 5, 6])])

    assert result["total_draws"] == 1
    assert result["avg_ac"] == 0.0
    assert result["ac_distribution"][0] == 1
    assert result["most_common_ac"] == 0


def test_ac_single_draw_max_complexity() -> None:
    """[1,7,14,22,31,45]는 15개 차이 모두 서로 달라 U=15 → AC=10."""
    from lotto.web import data as wd

    result = wd.get_ac_stats([_mk(1, [1, 7, 14, 22, 31, 45])])

    assert result["total_draws"] == 1
    assert result["avg_ac"] == 10.0
    assert result["ac_distribution"][10] == 1
    assert result["most_common_ac"] == 10
    assert result["high_ac_count"] == 1


def test_ac_mid_complexity() -> None:
    """[1,2,3,5,8,13]는 unique diffs 11개 → U=11 → AC=6."""
    from lotto.web import data as wd

    result = wd.get_ac_stats([_mk(1, [1, 2, 3, 5, 8, 13])])

    assert result["avg_ac"] == 6.0
    assert result["ac_distribution"][6] == 1


def test_ac_distribution_covers_full_range() -> None:
    """ac_distribution 키는 count가 0이어도 0..10 모두 존재한다."""
    from lotto.web import data as wd

    result = wd.get_ac_stats([_mk(1, [1, 2, 3, 4, 5, 6])])

    for ac in range(11):
        assert ac in result["ac_distribution"]
        assert ac in result["ac_distribution_pct"]


def test_ac_high_count() -> None:
    """high_ac_count는 AC >= 7 인 회차 수다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),        # AC=0
        _mk(2, [1, 7, 14, 22, 31, 45]),    # AC=10
        _mk(3, [2, 9, 17, 26, 36, 44]),    # 고복잡도
    ]
    result = wd.get_ac_stats(draws)

    high = sum(1 for d in draws if _ac_of(d) >= 7)
    assert result["high_ac_count"] == high
    assert result["high_ac_pct"] == round(high / 3 * 100, 2)


def test_ac_low_count() -> None:
    """low_ac_count는 AC <= 3 인 회차 수다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),        # AC=0
        _mk(2, [1, 2, 3, 4, 5, 7]),        # 저복잡도
        _mk(3, [1, 7, 14, 22, 31, 45]),    # AC=10
    ]
    result = wd.get_ac_stats(draws)

    low = sum(1 for d in draws if _ac_of(d) <= 3)
    assert result["low_ac_count"] == low
    assert result["low_ac_pct"] == round(low / 3 * 100, 2)


def test_ac_most_common_tie_smallest() -> None:
    """최빈 AC 동률 시 가장 작은 AC 값을 선택한다."""
    from lotto.web import data as wd

    # AC=0 한 회차, AC=10 한 회차 → 동률 → 더 작은 0 선택
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),        # AC=0
        _mk(2, [1, 7, 14, 22, 31, 45]),    # AC=10
    ]
    result = wd.get_ac_stats(draws)

    assert result["most_common_ac"] == 0


def test_ac_avg_correctness() -> None:
    """avg_ac는 회차별 AC의 평균(소수 2자리)이다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),        # AC=0
        _mk(2, [1, 2, 3, 5, 8, 13]),       # AC=6
    ]
    result = wd.get_ac_stats(draws)

    assert result["avg_ac"] == round((0 + 6) / 2, 2)


def test_ac_distribution_pct_sums_to_100() -> None:
    """ac_distribution_pct 값의 합은 약 100.0 이다(반올림 오차 허용).

    각 버킷을 소수 2자리로 반올림하므로 1/3 같은 값은 누적 오차가 발생한다.
    """
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [1, 7, 14, 22, 31, 45]),
        _mk(3, [1, 2, 3, 5, 8, 13]),
    ]
    result = wd.get_ac_stats(draws)

    assert sum(result["ac_distribution_pct"].values()) == pytest.approx(
        100.0, abs=0.1
    )


def test_ac_distribution_counts_sum_to_total() -> None:
    """ac_distribution count 합은 total_draws와 일치한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [1, 7, 14, 22, 31, 45]),
        _mk(3, [1, 2, 3, 5, 8, 13]),
    ]
    result = wd.get_ac_stats(draws)

    assert sum(result["ac_distribution"].values()) == result["total_draws"]


def test_ac_total_draws_matches_input() -> None:
    """total_draws는 입력 길이와 같다."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 8)]
    result = wd.get_ac_stats(draws)

    assert result["total_draws"] == 7


def test_ac_bonus_excluded() -> None:
    """보너스 번호는 AC 계산에서 제외한다(본번호 6개만 사용)."""
    from lotto.web import data as wd

    # 본번호는 동일, 보너스만 다른 두 회차 → AC 동일해야 한다
    r1 = wd.get_ac_stats([_mk(1, [1, 2, 3, 4, 5, 6], bonus=7)])
    wd.invalidate_cache()
    r2 = wd.get_ac_stats([_mk(1, [1, 2, 3, 4, 5, 6], bonus=45)])

    assert r1["avg_ac"] == r2["avg_ac"] == 0.0


def test_ac_cache_populated_after_first_call() -> None:
    """첫 호출 후 _ac_cache가 채워진다."""
    from lotto.web import data as wd

    wd.invalidate_cache()
    assert wd._ac_cache == {}

    wd.get_ac_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert wd._ac_cache != {}


def test_ac_cache_hit_returns_same_object() -> None:
    """동일 입력 재호출 시 캐시된 동일 객체를 반환한다."""
    from lotto.web import data as wd

    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    first = wd.get_ac_stats(draws)
    second = wd.get_ac_stats(draws)

    assert first is second


def test_ac_cache_cleared_by_invalidate() -> None:
    """invalidate_cache 호출 시 _ac_cache가 비워진다."""
    from lotto.web import data as wd

    wd.get_ac_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert wd._ac_cache != {}

    wd.invalidate_cache()
    assert wd._ac_cache == {}


# ---------------------------------------------------------------------------
# 페이지 라우트: GET /stats/ac
# ---------------------------------------------------------------------------


def test_ac_page_renders(api_client: TestClient) -> None:
    """데이터가 있으면 AC 분석 페이지가 200으로 렌더된다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [1, 7, 14, 22, 31, 45]),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = api_client.get("/stats/ac")

    assert resp.status_code == 200
    assert "AC" in resp.text


def test_ac_page_empty_state(api_client: TestClient) -> None:
    """데이터 부재 시에도 200으로 빈 상태 안내를 렌더한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=[]):
        resp = api_client.get("/stats/ac")

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# API 라우트: GET /api/stats/ac
# ---------------------------------------------------------------------------


def test_ac_api_returns_stats(api_client: TestClient) -> None:
    """API는 AC 통계 JSON을 반환한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [1, 7, 14, 22, 31, 45]),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = api_client.get("/api/stats/ac")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 2
    assert "ac_distribution" in body
    assert "most_common_ac" in body


def test_ac_api_empty(api_client: TestClient) -> None:
    """데이터 부재 시 API는 200과 0 수치를 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=[]):
        resp = api_client.get("/api/stats/ac")

    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


# ---------------------------------------------------------------------------
# 헬퍼: 단일 회차 AC 계산(테스트 기대값 산출용)
# ---------------------------------------------------------------------------


def _ac_of(draw: DrawResult) -> int:
    """단일 회차의 AC 값을 계산한다(테스트 기대값 검증용)."""
    from itertools import combinations

    nums = draw.numbers()
    diffs = {b - a for a, b in combinations(nums, 2)}
    return len(diffs) - 5
