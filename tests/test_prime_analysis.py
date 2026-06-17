"""SPEC-LOTTO-058: 소수/합성수 분포 분석 테스트.

데이터 계층(get_prime_stats), 캐시, 페이지/API 라우트를
RED-GREEN-REFACTOR로 검증한다.

분류 정의(회차별 본번호 6개, 보너스 제외):
- 소수(prime): 1~45 범위의 소수 14개 {2,3,5,7,11,13,17,19,23,29,31,37,41,43}
- 합성수(composite): 1과 소수를 제외한 나머지 30개
- one: 숫자 1 (소수도 합성수도 아님)
- 불변식: 회차마다 prime + composite + one == 6
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult

# 1~45 소수 집합(기대값 산출용 로컬 상수, 구현과 독립적으로 정의)
_PRIMES = frozenset({2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43})


def _mk(no: int, nums: list[int], bonus: int = 44) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    bonus는 본번호와 겹치지 않는 값(44, 합성수)을 기본으로 둔다.
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


def _classify(nums: list[int]) -> tuple[int, int, int]:
    """본번호 6개를 (prime, composite, one)으로 분류한 기대값을 산출한다."""
    prime = composite = one = 0
    for n in nums:
        if n == 1:
            one += 1
        elif n in _PRIMES:
            prime += 1
        else:
            composite += 1
    return prime, composite, one


@pytest.fixture
def api_client() -> TestClient:
    """매 테스트 새 TestClient — 라우터는 모듈 공유."""
    from lotto.web.app import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# 데이터 계층: get_prime_stats
# ---------------------------------------------------------------------------


def test_prime_stats_empty_all_zeros() -> None:
    """빈 데이터는 모든 수치 0, 빈 dict의 일관된 구조를 반환한다."""
    from lotto.web import data as wd

    result = wd.get_prime_stats([])

    assert result["total_draws"] == 0
    assert result["avg_prime"] == 0.0
    assert result["avg_composite"] == 0.0
    assert result["prime_distribution"] == {}
    assert result["prime_distribution_pct"] == {}
    assert result["most_common_prime_count"] == 0
    assert result["composite_distribution"] == {}
    assert result["one_appeared_count"] == 0
    assert result["one_appeared_pct"] == 0.0


def test_prime_stats_none_all_zeros() -> None:
    """None 입력도 빈 데이터와 동일하게 처리한다."""
    from lotto.web import data as wd

    result = wd.get_prime_stats(None)

    assert result["total_draws"] == 0
    assert result["prime_distribution"] == {}


def test_prime_single_mixed_classification() -> None:
    """[1,2,3,4,5,6] → one=1, prime=3(2,3,5), composite=2(4,6)."""
    from lotto.web import data as wd

    result = wd.get_prime_stats([_mk(1, [1, 2, 3, 4, 5, 6])])

    assert result["prime_distribution"][3] == 1
    assert result["composite_distribution"][2] == 1
    assert result["one_appeared_count"] == 1
    assert result["avg_prime"] == 3.0
    assert result["avg_composite"] == 2.0


def test_prime_single_all_prime() -> None:
    """[7,11,13,17,23,29] → 전부 소수: prime=6, composite=0, one=0."""
    from lotto.web import data as wd

    result = wd.get_prime_stats([_mk(1, [7, 11, 13, 17, 23, 29])])

    assert result["prime_distribution"][6] == 1
    assert result["composite_distribution"][0] == 1
    assert result["one_appeared_count"] == 0
    assert result["avg_prime"] == 6.0
    assert result["avg_composite"] == 0.0


def test_prime_single_all_composite() -> None:
    """[4,6,8,9,10,12] → 전부 합성수: prime=0, composite=6, one=0."""
    from lotto.web import data as wd

    result = wd.get_prime_stats([_mk(1, [4, 6, 8, 9, 10, 12])])

    assert result["prime_distribution"][0] == 1
    assert result["composite_distribution"][6] == 1
    assert result["one_appeared_count"] == 0
    assert result["avg_prime"] == 0.0
    assert result["avg_composite"] == 6.0


def test_prime_invariant_sum_equals_six() -> None:
    """모든 회차에서 prime + composite + one == 6 (불변식)."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [7, 11, 13, 17, 23, 29]),
        _mk(3, [4, 6, 8, 9, 10, 12]),
        _mk(4, [1, 4, 6, 8, 9, 10]),
    ]
    result = wd.get_prime_stats(draws)

    total = result["total_draws"]
    prime_total = sum(k * v for k, v in result["prime_distribution"].items())
    composite_total = sum(
        k * v for k, v in result["composite_distribution"].items()
    )
    one_total = result["one_appeared_count"]
    # 회차당 6개이므로 전체 합은 total * 6
    assert prime_total + composite_total + one_total == total * 6


def test_prime_one_appeared_count() -> None:
    """one_appeared_count는 숫자 1을 포함한 회차 수다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),      # 1 포함
        _mk(2, [7, 11, 13, 17, 23, 29]),  # 1 미포함
        _mk(3, [1, 4, 6, 8, 9, 10]),      # 1 포함
    ]
    result = wd.get_prime_stats(draws)

    expected = sum(1 for d in draws if 1 in d.numbers())
    assert result["one_appeared_count"] == expected
    assert result["one_appeared_count"] == 2
    assert result["one_appeared_pct"] == round(2 / 3 * 100, 2)


def test_prime_most_common_tie_smallest() -> None:
    """최빈 소수 개수 동률 시 가장 작은 값을 선택한다."""
    from lotto.web import data as wd

    # prime=3 한 회차, prime=6 한 회차 → 동률 → 더 작은 3 선택
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),       # prime=3
        _mk(2, [7, 11, 13, 17, 23, 29]),   # prime=6
    ]
    result = wd.get_prime_stats(draws)

    assert result["most_common_prime_count"] == 3


def test_prime_most_common_clear_winner() -> None:
    """최빈 소수 개수가 명확히 빈도가 가장 높은 값을 선택한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),       # prime=3
        _mk(2, [1, 2, 3, 5, 4, 6]),       # prime=3
        _mk(3, [7, 11, 13, 17, 23, 29]),   # prime=6
    ]
    result = wd.get_prime_stats(draws)

    assert result["most_common_prime_count"] == 3


def test_prime_distribution_covers_full_range() -> None:
    """prime_distribution 키는 0..6 전부 존재한다(count 0이어도)."""
    from lotto.web import data as wd

    result = wd.get_prime_stats([_mk(1, [1, 2, 3, 4, 5, 6])])

    assert sorted(result["prime_distribution"].keys()) == list(range(7))


def test_composite_distribution_covers_full_range() -> None:
    """composite_distribution 키는 0..6 전부 존재한다(count 0이어도)."""
    from lotto.web import data as wd

    result = wd.get_prime_stats([_mk(1, [1, 2, 3, 4, 5, 6])])

    assert sorted(result["composite_distribution"].keys()) == list(range(7))


def test_prime_distribution_counts_sum_to_total() -> None:
    """prime_distribution count 합은 total_draws와 일치한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [7, 11, 13, 17, 23, 29]),
        _mk(3, [4, 6, 8, 9, 10, 12]),
    ]
    result = wd.get_prime_stats(draws)

    assert sum(result["prime_distribution"].values()) == result["total_draws"]


def test_composite_distribution_counts_sum_to_total() -> None:
    """composite_distribution count 합은 total_draws와 일치한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [7, 11, 13, 17, 23, 29]),
        _mk(3, [4, 6, 8, 9, 10, 12]),
    ]
    result = wd.get_prime_stats(draws)

    assert sum(result["composite_distribution"].values()) == result["total_draws"]


def test_prime_distribution_pct_sums_to_100() -> None:
    """prime_distribution_pct 값의 합은 약 100.0 이다(반올림 오차 허용)."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [7, 11, 13, 17, 23, 29]),
        _mk(3, [4, 6, 8, 9, 10, 12]),
    ]
    result = wd.get_prime_stats(draws)

    assert sum(result["prime_distribution_pct"].values()) == pytest.approx(
        100.0, abs=0.1
    )


def test_prime_avg_correctness() -> None:
    """avg_prime/avg_composite는 회차별 평균(소수 2자리)이다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),       # prime=3, composite=2
        _mk(2, [7, 11, 13, 17, 23, 29]),   # prime=6, composite=0
    ]
    result = wd.get_prime_stats(draws)

    assert result["avg_prime"] == round((3 + 6) / 2, 2)
    assert result["avg_composite"] == round((2 + 0) / 2, 2)


def test_prime_total_draws_matches_input() -> None:
    """total_draws는 입력 길이와 같다."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 8)]
    result = wd.get_prime_stats(draws)

    assert result["total_draws"] == 7


def test_prime_bonus_excluded() -> None:
    """보너스 번호는 분류에서 제외한다(본번호 6개만 사용)."""
    from lotto.web import data as wd

    # 본번호는 모두 소수, 보너스는 1(만약 포함되면 one_count가 증가)
    draws = [_mk(1, [2, 3, 5, 7, 11, 13], bonus=1)]
    result = wd.get_prime_stats(draws)

    assert result["prime_distribution"][6] == 1
    assert result["one_appeared_count"] == 0


# ---------------------------------------------------------------------------
# 캐시
# ---------------------------------------------------------------------------


def test_prime_cache_populated_after_first_call() -> None:
    """첫 호출 후 _prime_cache가 채워진다."""
    from lotto.web import data as wd

    wd.invalidate_cache()
    assert wd._prime_cache == {}

    wd.get_prime_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert wd._prime_cache != {}


def test_prime_cache_hit_returns_same_object() -> None:
    """동일 입력 재호출 시 캐시된 동일 객체를 반환한다."""
    from lotto.web import data as wd

    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    first = wd.get_prime_stats(draws)
    second = wd.get_prime_stats(draws)

    assert first is second


def test_prime_cache_cleared_by_invalidate() -> None:
    """invalidate_cache 호출 시 _prime_cache가 비워진다."""
    from lotto.web import data as wd

    wd.get_prime_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert wd._prime_cache != {}

    wd.invalidate_cache()
    assert wd._prime_cache == {}


# ---------------------------------------------------------------------------
# 페이지 라우트: GET /stats/prime
# ---------------------------------------------------------------------------


def test_prime_page_renders(api_client: TestClient) -> None:
    """데이터가 있으면 소수 분석 페이지가 200으로 렌더된다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [7, 11, 13, 17, 23, 29]),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = api_client.get("/stats/prime")

    assert resp.status_code == 200
    assert "소수" in resp.text


def test_prime_page_empty_state(api_client: TestClient) -> None:
    """데이터 부재 시에도 200으로 빈 상태 안내를 렌더한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=[]):
        resp = api_client.get("/stats/prime")

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# API 라우트: GET /api/stats/prime
# ---------------------------------------------------------------------------


def test_prime_api_returns_stats(api_client: TestClient) -> None:
    """API는 소수 통계 JSON을 반환한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [7, 11, 13, 17, 23, 29]),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = api_client.get("/api/stats/prime")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 2
    assert "prime_distribution" in body
    assert "composite_distribution" in body
    assert "most_common_prime_count" in body


def test_prime_api_empty(api_client: TestClient) -> None:
    """데이터 부재 시 API는 200과 0 수치를 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=[]):
        resp = api_client.get("/api/stats/prime")

    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0
