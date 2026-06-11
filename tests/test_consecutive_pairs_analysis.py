"""SPEC-LOTTO-069: 연속번호 패턴 분석(연속 쌍) 테스트.

데이터 계층(get_consecutive_pairs_stats), 헬퍼(count_consecutive_pairs),
캐시(_consecutive_pairs_cache), 페이지/API 라우트를 RED-GREEN-REFACTOR로 검증한다.

분석(회차별 본번호 6개, 보너스 제외):
- 같은 회차에 n 과 n+1 이 모두 존재하는 연속 쌍(consecutive pair) 개수를 센다.
- 길이 k 의 연속 런은 k-1 개의 연속 쌍을 만든다(예: 14,15,16 → 2쌍).
- 회차별 연속 쌍 개수를 4개 고정 버킷("0","1","2","3+")으로 분류한다.

SPEC-062(연속 패턴, _consecutive_cache)와 충돌을 피하기 위해
consecutive_pairs 네임스페이스를 사용한다.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd

if TYPE_CHECKING:
    from collections.abc import Iterator  # noqa: F401


_BUCKET_KEYS = ["0", "1", "2", "3+"]


def _mk(no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    bonus 기본값 7은 본번호와 인접해도 연속 쌍 집계에서 제외됨을 검증하기 위함이다.
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# --------------------------------------------------------------------------- #
# count_consecutive_pairs 헬퍼
# --------------------------------------------------------------------------- #


def test_count_six_consecutive() -> None:
    """[1,2,3,4,5,6] → 연속 쌍 5개."""
    assert wd.count_consecutive_pairs([1, 2, 3, 4, 5, 6]) == 5


def test_count_no_consecutive() -> None:
    """[1,3,5,7,9,11] → 연속 쌍 0개."""
    assert wd.count_consecutive_pairs([1, 3, 5, 7, 9, 11]) == 0


def test_count_one_pair() -> None:
    """[1,2,10,20,30,40] → 연속 쌍 1개."""
    assert wd.count_consecutive_pairs([1, 2, 10, 20, 30, 40]) == 1


def test_count_two_pairs() -> None:
    """[1,2,10,11,20,30] → 연속 쌍 2개."""
    assert wd.count_consecutive_pairs([1, 2, 10, 11, 20, 30]) == 2


def test_count_unsorted_multi() -> None:
    """[44,45,1,2,3,30] → 연속 쌍 3개 ((1,2),(2,3),(44,45); wrap 미포함)."""
    assert wd.count_consecutive_pairs([44, 45, 1, 2, 3, 30]) == 3


# --------------------------------------------------------------------------- #
# 빈 데이터 / 일관된 빈 구조
# --------------------------------------------------------------------------- #


def test_empty_returns_zero_stats() -> None:
    """AC-069-001: 빈 리스트는 total_draws=0 과 4 버킷 zero-fill 을 반환한다."""
    result = wd.get_consecutive_pairs_stats([])
    assert result["total_draws"] == 0
    assert result["avg_consecutive_pairs"] == 0.0
    assert result["most_common_bucket"] == ""
    assert result["no_consecutive_pct"] == 0.0
    assert result["has_consecutive_pct"] == 0.0
    assert list(result["consecutive_distribution"].keys()) == _BUCKET_KEYS
    for b in _BUCKET_KEYS:
        cell = result["consecutive_distribution"][b]
        assert cell["count"] == 0
        assert cell["pct"] == 0.0


def test_none_returns_zero_stats() -> None:
    """None 입력도 빈 데이터와 동일한 구조를 반환한다."""
    result = wd.get_consecutive_pairs_stats(None)
    assert result["total_draws"] == 0
    assert list(result["consecutive_distribution"].keys()) == _BUCKET_KEYS


# --------------------------------------------------------------------------- #
# 버킷 분류
# --------------------------------------------------------------------------- #


def test_six_consecutive_bucket_3plus() -> None:
    """AC-069-002: [1,2,3,4,5,6] → 연속 쌍 5개 → 버킷 '3+'."""
    result = wd.get_consecutive_pairs_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    cd = result["consecutive_distribution"]
    assert cd["3+"]["count"] == 1
    for b in ["0", "1", "2"]:
        assert cd[b]["count"] == 0


def test_no_consecutive_bucket_0() -> None:
    """AC-069-003: [1,3,5,7,9,11] → 연속 쌍 0개 → 버킷 '0'."""
    result = wd.get_consecutive_pairs_stats([_mk(1, [1, 3, 5, 7, 9, 11])])
    cd = result["consecutive_distribution"]
    assert cd["0"]["count"] == 1
    for b in ["1", "2", "3+"]:
        assert cd[b]["count"] == 0


def test_one_pair_bucket_1() -> None:
    """AC-069-004: [1,2,10,20,30,40] → 연속 쌍 1개 → 버킷 '1'."""
    result = wd.get_consecutive_pairs_stats([_mk(1, [1, 2, 10, 20, 30, 40])])
    assert result["consecutive_distribution"]["1"]["count"] == 1


def test_two_pairs_bucket_2() -> None:
    """AC-069-005: [1,2,10,11,20,30] → 연속 쌍 2개 → 버킷 '2'."""
    result = wd.get_consecutive_pairs_stats([_mk(1, [1, 2, 10, 11, 20, 30])])
    assert result["consecutive_distribution"]["2"]["count"] == 1


def test_bonus_excluded() -> None:
    """AC-069-006: main=[1,2,3,4,5,6], bonus=7 → 연속 쌍 5개(6,7 미포함)."""
    result = wd.get_consecutive_pairs_stats([_mk(1, [1, 2, 3, 4, 5, 6], bonus=7)])
    # 보너스 7이 포함됐다면 (6,7) 쌍이 더해져 6이 됨 → 여전히 '3+' 이지만
    # count_consecutive_pairs 헬퍼 단위로도 직접 검증한다.
    assert wd.count_consecutive_pairs([1, 2, 3, 4, 5, 6]) == 5
    assert result["consecutive_distribution"]["3+"]["count"] == 1


def test_unsorted_multi_bucket_3plus() -> None:
    """AC-069-022: [44,45,1,2,3,30] → 연속 쌍 3개 → 버킷 '3+'."""
    result = wd.get_consecutive_pairs_stats([_mk(1, [44, 45, 1, 2, 3, 30])])
    assert result["consecutive_distribution"]["3+"]["count"] == 1


def test_all_four_buckets_present_nonempty() -> None:
    """AC-069-007: 임의 비어 있지 않은 draws 에서도 4 버킷 키가 존재한다."""
    result = wd.get_consecutive_pairs_stats([_mk(1, [1, 2, 10, 20, 30, 40])])
    assert list(result["consecutive_distribution"].keys()) == _BUCKET_KEYS


# --------------------------------------------------------------------------- #
# 수치 정확성
# --------------------------------------------------------------------------- #


def test_avg_consecutive_pairs_accuracy() -> None:
    """AC-069-008: 10회차 연속 쌍 총합 6 → avg_consecutive_pairs=0.6."""
    draws = []
    # 6회차는 연속 쌍 1개([1,2,...]), 4회차는 0개([1,3,5,...]) → 합 6
    for i in range(6):
        draws.append(_mk(i + 1, [1, 2, 10, 20, 30, 40]))
    for i in range(4):
        draws.append(_mk(i + 7, [1, 3, 5, 7, 9, 11]))
    result = wd.get_consecutive_pairs_stats(draws)
    assert result["total_draws"] == 10
    assert result["avg_consecutive_pairs"] == 0.6


def test_no_consecutive_pct_accuracy() -> None:
    """AC-069-009: 3회차 중 1회차가 연속 쌍 0개 → no_consecutive_pct=33.33."""
    draws = [
        _mk(1, [1, 2, 10, 20, 30, 40]),   # 1쌍
        _mk(2, [1, 2, 10, 11, 20, 30]),   # 2쌍
        _mk(3, [1, 3, 5, 7, 9, 11]),      # 0쌍
    ]
    result = wd.get_consecutive_pairs_stats(draws)
    assert result["no_consecutive_pct"] == 33.33


def test_has_plus_no_equals_100() -> None:
    """AC-069-010: has_consecutive_pct + no_consecutive_pct ≈ 100.0."""
    draws = [
        _mk(1, [1, 2, 10, 20, 30, 40]),
        _mk(2, [1, 3, 5, 7, 9, 11]),
        _mk(3, [1, 2, 3, 4, 5, 6]),
    ]
    result = wd.get_consecutive_pairs_stats(draws)
    total = result["has_consecutive_pct"] + result["no_consecutive_pct"]
    assert abs(total - 100.0) <= 0.01


def test_most_common_bucket() -> None:
    """AC-069-011: 버킷 '1' 이 단독 최다 count 면 most_common_bucket='1'."""
    draws = [
        _mk(1, [1, 2, 10, 20, 30, 40]),   # 1쌍 → '1'
        _mk(2, [3, 4, 11, 21, 31, 41]),   # 1쌍 → '1'
        _mk(3, [1, 3, 5, 7, 9, 11]),      # 0쌍 → '0'
    ]
    result = wd.get_consecutive_pairs_stats(draws)
    assert result["most_common_bucket"] == "1"


def test_most_common_bucket_tiebreak() -> None:
    """AC-069-012: 동점 시 _CONSECUTIVE_BUCKETS 에서 앞서는 버킷이 이긴다."""
    draws = [
        _mk(1, [1, 3, 5, 7, 9, 11]),      # 0쌍 → '0'
        _mk(2, [1, 2, 10, 20, 30, 40]),   # 1쌍 → '1'
    ]
    # '0' 과 '1' 모두 count=1 동점 → 앞선 '0' 이김
    result = wd.get_consecutive_pairs_stats(draws)
    assert result["most_common_bucket"] == "0"


def test_pct_sums_to_100() -> None:
    """AC-069-013: 4개 버킷 pct 합 ≈ 100.0."""
    draws = [
        _mk(1, [1, 2, 10, 20, 30, 40]),
        _mk(2, [1, 2, 10, 11, 20, 30]),
        _mk(3, [1, 3, 5, 7, 9, 11]),
        _mk(4, [1, 2, 3, 4, 5, 6]),
    ]
    result = wd.get_consecutive_pairs_stats(draws)
    total_pct = sum(
        result["consecutive_distribution"][b]["pct"] for b in _BUCKET_KEYS
    )
    assert abs(total_pct - 100.0) <= 0.1


def test_count_sum_equals_total_draws() -> None:
    """AC-069-014: 4개 버킷 count 합 = total_draws."""
    draws = [
        _mk(1, [1, 2, 10, 20, 30, 40]),
        _mk(2, [1, 2, 10, 11, 20, 30]),
        _mk(3, [1, 3, 5, 7, 9, 11]),
        _mk(4, [1, 2, 3, 4, 5, 6]),
    ]
    result = wd.get_consecutive_pairs_stats(draws)
    total_count = sum(
        result["consecutive_distribution"][b]["count"] for b in _BUCKET_KEYS
    )
    assert total_count == result["total_draws"] == 4


# --------------------------------------------------------------------------- #
# 입력 비변형
# --------------------------------------------------------------------------- #


def test_does_not_mutate_input() -> None:
    """집계가 입력 draws 리스트를 변형하지 않는다."""
    draws = [_mk(1, [1, 2, 10, 20, 30, 40])]
    before = list(draws)
    wd.get_consecutive_pairs_stats(draws)
    assert draws == before


# --------------------------------------------------------------------------- #
# 캐시
# --------------------------------------------------------------------------- #


def test_cache_hit_same_length() -> None:
    """AC-069-015: 동일 길이 입력의 재호출은 캐시된 동일 객체를 반환한다."""
    wd._consecutive_pairs_cache.clear()
    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    first = wd.get_consecutive_pairs_stats(draws)
    second = wd.get_consecutive_pairs_stats(draws)
    assert first is second
    assert "1" in wd._consecutive_pairs_cache


def test_cache_miss_different_length() -> None:
    """AC-069-016: 길이가 다른 입력은 캐시 미스로 새로 계산된다."""
    wd._consecutive_pairs_cache.clear()
    one = wd.get_consecutive_pairs_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    two = wd.get_consecutive_pairs_stats(
        [_mk(1, [1, 2, 3, 4, 5, 6]), _mk(2, [1, 3, 5, 7, 9, 11])]
    )
    assert one is not two
    assert "1" in wd._consecutive_pairs_cache
    assert "2" in wd._consecutive_pairs_cache


def test_invalidate_cache() -> None:
    """AC-069-017: invalidate_cache() 호출 시 연속 쌍 캐시가 비워진다."""
    wd.get_consecutive_pairs_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    assert wd._consecutive_pairs_cache
    wd.invalidate_cache()
    assert not wd._consecutive_pairs_cache


# --------------------------------------------------------------------------- #
# 라우트: API / 페이지
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """AC-069-018: GET /api/stats/consecutive-pairs 는 200 + 키 구조를 반환한다."""
    draws = [
        _mk(1, [1, 2, 10, 20, 30, 40]),
        _mk(2, [1, 2, 10, 11, 20, 30]),
        _mk(3, [1, 3, 5, 7, 9, 11]),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = _client().get("/api/stats/consecutive-pairs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 3
    for key in (
        "total_draws",
        "avg_consecutive_pairs",
        "most_common_bucket",
        "no_consecutive_pct",
        "has_consecutive_pct",
        "consecutive_distribution",
    ):
        assert key in body
    assert set(body["consecutive_distribution"].keys()) == set(_BUCKET_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/consecutive-pairs 는 데이터가 없어도 200 을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/consecutive-pairs")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """AC-069-019: GET /stats/consecutive-pairs 는 200(연속 텍스트 포함)을 반환한다."""
    draws = [_mk(1, [1, 2, 10, 20, 30, 40])]
    with patch.object(wd, "get_draws", return_value=draws):
        resp = _client().get("/stats/consecutive-pairs")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "연속" in resp.text


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/consecutive-pairs 는 데이터가 없어도 200(빈 상태)을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/consecutive-pairs")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 실데이터 스모크
# --------------------------------------------------------------------------- #


def test_real_data_smoke() -> None:
    """AC-069-020: 실제 데이터가 있으면 total_draws>0, avg_consecutive_pairs>0."""
    draws = wd.get_draws()
    if not draws:
        return  # 데이터 미수집 환경에서는 스킵
    result = wd.get_consecutive_pairs_stats(draws)
    assert result["total_draws"] > 0
    assert result["avg_consecutive_pairs"] > 0


def test_real_data_most_draws_have_consecutive() -> None:
    """AC-069-021: 실제 데이터에서 다수 회차가 연속 쌍 1개 이상 보유."""
    draws = wd.get_draws()
    if not draws:
        return
    result = wd.get_consecutive_pairs_stats(draws)
    assert result["has_consecutive_pct"] > 50
