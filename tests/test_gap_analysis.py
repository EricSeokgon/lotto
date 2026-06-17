"""SPEC-LOTTO-056: 번호 간격 패턴 분석 테스트.

데이터 계층(get_gap_stats), 캐시, 페이지/API 라우트를
RED-GREEN-REFACTOR로 검증한다.

간격(gap) 정의:
- 각 회차의 정렬된 본번호 6개(보너스 제외)에서 인접한 두 번호 차이 5개.
- 예) 정렬 [1, 4, 10, 11, 20, 30] → gaps = [3, 6, 1, 9, 10]
- 분류: 1~5=소(small), 6~10=중(medium), 11+=대(large).
- position i = sorted[i+1] - sorted[i] (i=0..4).
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
# 데이터 계층: get_gap_stats
# ---------------------------------------------------------------------------


def test_gap_stats_empty_all_zeros() -> None:
    """빈 데이터는 모든 수치 0, 빈 리스트의 일관된 구조를 반환한다."""
    from lotto.web import data as wd

    result = wd.get_gap_stats([])

    assert result["total_draws"] == 0
    assert result["avg_gap"] == 0.0
    assert result["small_count"] == 0
    assert result["medium_count"] == 0
    assert result["large_count"] == 0
    assert result["small_pct"] == 0.0
    assert result["medium_pct"] == 0.0
    assert result["large_pct"] == 0.0
    assert result["most_common_gaps"] == []
    assert result["avg_min_gap"] == 0.0
    assert result["avg_max_gap"] == 0.0
    assert result["position_avg"] == [0.0, 0.0, 0.0, 0.0, 0.0]


def test_gap_stats_single_draw_gaps() -> None:
    """단일 회차의 간격 계산이 정확하다.

    [1, 4, 10, 11, 20, 30] → gaps = [3, 6, 1, 9, 10].
    """
    from lotto.web import data as wd

    result = wd.get_gap_stats([_mk(1, [1, 4, 10, 11, 20, 30])])

    assert result["total_draws"] == 1
    # gaps = [3, 6, 1, 9, 10], 합 29 / 5 = 5.8
    assert result["avg_gap"] == pytest.approx(5.8)


def test_gap_stats_position_avg_values() -> None:
    """position_avg[i]는 sorted[i+1]-sorted[i]의 회차 평균이다.

    [1, 4, 10, 11, 20, 30] → [3, 6, 1, 9, 10] 단일 회차이므로 그대로.
    """
    from lotto.web import data as wd

    result = wd.get_gap_stats([_mk(1, [1, 4, 10, 11, 20, 30])])

    assert result["position_avg"] == pytest.approx([3.0, 6.0, 1.0, 9.0, 10.0])


def test_gap_stats_position_avg_has_five_elements() -> None:
    """position_avg는 항상 정확히 5개 원소를 가진다."""
    from lotto.web import data as wd

    result = wd.get_gap_stats([_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 4)])

    assert len(result["position_avg"]) == 5


def test_gap_stats_small_boundary() -> None:
    """gap=5는 소(small), gap=6은 중(medium) 경계에서 정확히 분류된다.

    [1, 6, 12, 13, 14, 15] → gaps = [5, 6, 1, 1, 1].
    small: 5,1,1,1 = 4개 / medium: 6 = 1개 / large: 0개.
    """
    from lotto.web import data as wd

    result = wd.get_gap_stats([_mk(1, [1, 6, 12, 13, 14, 15])])

    assert result["small_count"] == 4
    assert result["medium_count"] == 1
    assert result["large_count"] == 0


def test_gap_stats_large_boundary() -> None:
    """gap=10은 중(medium), gap=11은 대(large) 경계에서 정확히 분류된다.

    [1, 11, 21, 32, 33, 34] → gaps = [10, 10, 11, 1, 1].
    small: 1,1 = 2개 / medium: 10,10 = 2개 / large: 11 = 1개.
    """
    from lotto.web import data as wd

    result = wd.get_gap_stats([_mk(1, [1, 11, 21, 32, 33, 34])])

    assert result["small_count"] == 2
    assert result["medium_count"] == 2
    assert result["large_count"] == 1


def test_gap_stats_total_gaps_is_draws_times_five() -> None:
    """소+중+대 카운트 합 = total_draws * 5 (회차당 5개 간격)."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 4, 10, 11, 20, 30]) for i in range(1, 8)]
    result = wd.get_gap_stats(draws)

    total = result["small_count"] + result["medium_count"] + result["large_count"]
    assert total == result["total_draws"] * 5
    assert total == 7 * 5


def test_gap_stats_pct_sum_to_100() -> None:
    """소/중/대 비율 합은 부동소수 오차 내에서 100.0이다."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 6, 12, 18, 30, 41]) for i in range(1, 6)]
    result = wd.get_gap_stats(draws)

    total_pct = result["small_pct"] + result["medium_pct"] + result["large_pct"]
    assert total_pct == pytest.approx(100.0)


def test_gap_stats_most_common_gaps_sorted_desc() -> None:
    """most_common_gaps는 count 내림차순으로 정렬된다.

    [1, 2, 3, 4, 5, 6] → gaps = [1, 1, 1, 1, 1] (모두 1).
    가장 흔한 간격은 1이어야 한다.
    """
    from lotto.web import data as wd

    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 6)]
    result = wd.get_gap_stats(draws)

    counts = [item["count"] for item in result["most_common_gaps"]]
    assert counts == sorted(counts, reverse=True)
    # 모든 간격이 1이므로 최빈 간격은 1
    assert result["most_common_gaps"][0]["gap"] == 1


def test_gap_stats_most_common_gaps_top_10() -> None:
    """most_common_gaps는 최대 10개로 제한된다.

    서로 다른 11개 이상 간격이 등장해도 상위 10개만 반환한다.
    """
    from lotto.web import data as wd

    # 다양한 간격을 만들기 위해 여러 패턴의 회차 구성
    draws = [
        _mk(1, [1, 2, 4, 7, 11, 16]),    # gaps 1,2,3,4,5
        _mk(2, [1, 7, 14, 22, 31, 41]),  # gaps 6,7,8,9,10
        _mk(3, [1, 13, 14, 26, 27, 40]),  # gaps 12,1,12,1,13
    ]
    result = wd.get_gap_stats(draws)

    assert len(result["most_common_gaps"]) <= 10


def test_gap_stats_avg_min_max_gap() -> None:
    """avg_min_gap/avg_max_gap는 회차별 최소/최대 간격의 평균이다.

    회차1 [1, 4, 10, 11, 20, 30] → gaps [3,6,1,9,10] → min 1, max 10
    회차2 [1, 2, 3, 4, 5, 6]      → gaps [1,1,1,1,1]  → min 1, max 1
    avg_min = (1+1)/2 = 1.0, avg_max = (10+1)/2 = 5.5
    """
    from lotto.web import data as wd

    draws = [_mk(1, [1, 4, 10, 11, 20, 30]), _mk(2, [1, 2, 3, 4, 5, 6])]
    result = wd.get_gap_stats(draws)

    assert result["avg_min_gap"] == pytest.approx(1.0)
    assert result["avg_max_gap"] == pytest.approx(5.5)


def test_gap_stats_avg_gap_multi_draw() -> None:
    """avg_gap는 전체 회차 모든 간격의 평균이다.

    회차1 [1,4,10,11,20,30] gaps [3,6,1,9,10] 합 29
    회차2 [1,2,3,4,5,6]      gaps [1,1,1,1,1]  합 5
    전체 합 34 / 10개 간격 = 3.4
    """
    from lotto.web import data as wd

    draws = [_mk(1, [1, 4, 10, 11, 20, 30]), _mk(2, [1, 2, 3, 4, 5, 6])]
    result = wd.get_gap_stats(draws)

    assert result["avg_gap"] == pytest.approx(3.4)


def test_gap_stats_excludes_bonus() -> None:
    """간격 계산은 본번호 6개만 사용하고 보너스를 제외한다.

    본번호 [1,2,3,4,5,6] 보너스 45 → gaps 모두 1 (보너스 45 미포함).
    """
    from lotto.web import data as wd

    result = wd.get_gap_stats([_mk(1, [1, 2, 3, 4, 5, 6], bonus=45)])

    # 보너스가 포함됐다면 큰 간격이 생겼을 것 — 모두 1이어야 한다
    assert result["small_count"] == 5
    assert result["large_count"] == 0


# ---------------------------------------------------------------------------
# 캐시
# ---------------------------------------------------------------------------


def test_gap_stats_cache_populated() -> None:
    """첫 호출 후 _gap_cache 가 채워진다."""
    from lotto.web import data as wd

    assert wd._gap_cache == {}
    wd.get_gap_stats([_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 6)])
    assert wd._gap_cache != {}


def test_gap_stats_cache_returns_same_object() -> None:
    """동일 데이터 재요청 시 캐시된 동일 객체를 재사용한다(재계산 없음)."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 11)]
    first = wd.get_gap_stats(draws)
    second = wd.get_gap_stats(draws)
    assert first is second


def test_gap_stats_cache_invalidated() -> None:
    """invalidate_cache() 후에는 결과가 재계산된다."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 11)]
    first = wd.get_gap_stats(draws)
    wd.invalidate_cache()
    second = wd.get_gap_stats(draws)
    assert first is not second
    assert first["avg_gap"] == second["avg_gap"]


# ---------------------------------------------------------------------------
# API 라우트
# ---------------------------------------------------------------------------


def test_api_gap(api_client: TestClient) -> None:
    """GET /api/stats/gap 은 간격 통계 JSON을 반환한다."""
    draws = [_mk(i, [1, 4, 10, 11, 20, 30]) for i in range(1, 11)]
    with patch("lotto.web.routes.api.wd.get_draws", return_value=draws):
        resp = api_client.get("/api/stats/gap")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_draws"] == 10
    assert len(data["position_avg"]) == 5


def test_api_gap_empty(api_client: TestClient) -> None:
    """데이터 부재 시 API는 200과 빈 통계를 반환한다."""
    with patch("lotto.web.routes.api.wd.get_draws", return_value=None):
        resp = api_client.get("/api/stats/gap")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_draws"] == 0
    assert data["small_count"] == 0


# ---------------------------------------------------------------------------
# 페이지 라우트
# ---------------------------------------------------------------------------


def test_gap_page_renders(api_client: TestClient) -> None:
    """GET /stats/gap 은 200으로 간격 분석 표를 렌더한다."""
    draws = [_mk(i, [1, 4, 10, 11, 20, 30]) for i in range(1, 11)]
    with patch("lotto.web.routes.pages.wd.get_draws", return_value=draws):
        resp = api_client.get("/stats/gap")
    assert resp.status_code == 200


def test_gap_page_empty(api_client: TestClient) -> None:
    """데이터 부재 시 페이지는 200과 안내 상태로 렌더된다."""
    with patch("lotto.web.routes.pages.wd.get_draws", return_value=None):
        resp = api_client.get("/stats/gap")
    assert resp.status_code == 200
