"""SPEC-LOTTO-085: 일의 자리 중복 분포 분석 테스트.

데이터 계층(get_last_digit_pair_stats), 헬퍼(_count_last_digit_pairs),
캐시(_last_digit_pair_cache), 페이지/API 라우트를 RED-GREEN-REFACTOR로 검증한다.

일의 자리 중복(last-digit pair):
- 한 회차 본번호 6개(보너스 제외)를 일의 자리(n % 10)별로 그룹화.
- 같은 일의 자리를 2개 이상 가진 그룹의 수를 센다(0~3, 3 초과는 3으로 상한).
- 그룹 수를 4개 고정 키("0"~"3")로 분류(zero-fill).
- has_pair_pct(>=1 비율) / most_common_pair_count(동률 시 작은 값)
  / avg_pair_count(평균).

SPEC-063/079(끝자리 합계 분포), SPEC-055(끝자리별 누적 빈도)와는 출력 구조와
정의가 완전히 다른 별개 기능이다. 본 기능은 "같은 일의 자리를 가진 번호가 2개
이상인 그룹의 수"를 센다.
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


_LAST_DIGIT_PAIR_KEYS = ["0", "1", "2", "3"]


def _mk(no: int, nums: list[int], bonus: int = 44) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼."""
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# 손계산 검증용 4개 회차 픽스처.
# D1 [1,11,2,12,3,13]   일자리 1·2·3 각 2개 → 3그룹 → "3"
# D2 [1,2,3,4,5,6]      모두 다른 일자리      → 0그룹 → "0"
# D3 [5,15,25,6,16,26]  일자리 5·6 각 3개     → 2그룹 → "2"
# D4 [1,11,21,31,41,2]  일자리 1 5개, 2 1개   → 1그룹 → "1"
def _fixture_draws() -> list[DrawResult]:
    return [
        _mk(1, [1, 11, 2, 12, 3, 13]),
        _mk(2, [1, 2, 3, 4, 5, 6]),
        _mk(3, [5, 15, 25, 6, 16, 26]),
        _mk(4, [1, 11, 21, 31, 41, 2]),
    ]


# --------------------------------------------------------------------------- #
# 헬퍼 함수 (_count_last_digit_pairs)
# --------------------------------------------------------------------------- #


def test_count_all_distinct() -> None:
    """[1,2,3,4,5,6] → 모두 다른 일의 자리 → 0 (AC-07)."""
    assert wd._count_last_digit_pairs([1, 2, 3, 4, 5, 6]) == 0


def test_count_one_group_five_numbers() -> None:
    """[1,11,21,31,41,2] → 일의 자리 1이 5개 → 1그룹 → 1 (AC-08)."""
    assert wd._count_last_digit_pairs([1, 11, 21, 31, 41, 2]) == 1


def test_count_two_groups_of_three() -> None:
    """[5,15,25,6,16,26] → 일의 자리 5·6 각 3개 → 2그룹 → 2 (AC-09)."""
    assert wd._count_last_digit_pairs([5, 15, 25, 6, 16, 26]) == 2


def test_count_three_groups_of_two() -> None:
    """[1,11,2,12,3,13] → 일의 자리 1·2·3 각 2개 → 3그룹 → 3 (AC-10)."""
    assert wd._count_last_digit_pairs([1, 11, 2, 12, 3, 13]) == 3


def test_count_two_groups_mixed() -> None:
    """[1,11,2,22,3,4] → 일의 자리 1·2 각 2개 → 2그룹 → 2 (AC-11)."""
    assert wd._count_last_digit_pairs([1, 11, 2, 22, 3, 4]) == 2


def test_count_caps_at_three() -> None:
    """4그룹 발생 시 min(4,3)=3 으로 상한 처리 (AC-12).

    [1,11,2,12,3,13,...] 형태는 6개 한계상 불가능하나, 가상 입력으로 상한 검증.
    일의 자리 1,2,3,4 각 2개씩(8개 입력) → 4그룹 → min(4,3)=3.
    """
    assert wd._count_last_digit_pairs([1, 11, 2, 12, 3, 13, 4, 14]) == 3


def test_count_single_pair() -> None:
    """[1,11,2,3,4,5] → 일의 자리 1만 2개 → 1 (AC-13)."""
    assert wd._count_last_digit_pairs([1, 11, 2, 3, 4, 5]) == 1


# --------------------------------------------------------------------------- #
# get_last_digit_pair_stats — 응답 구조
# --------------------------------------------------------------------------- #


def test_response_has_all_top_level_keys() -> None:
    """반환 dict는 5개 최상위 키를 모두 포함한다 (AC-14)."""
    stats = wd.get_last_digit_pair_stats(_fixture_draws())
    for key in (
        "total_draws",
        "has_pair_pct",
        "most_common_pair_count",
        "avg_pair_count",
        "last_digit_pair_distribution",
    ):
        assert key in stats


def test_distribution_always_has_four_keys() -> None:
    """last_digit_pair_distribution은 항상 4개 고정 키만 포함 (AC-15)."""
    stats = wd.get_last_digit_pair_stats(_fixture_draws())
    assert set(stats["last_digit_pair_distribution"].keys()) == set(_LAST_DIGIT_PAIR_KEYS)


def test_distribution_cells_have_count_and_pct() -> None:
    """각 분포 항목은 count·pct 두 키를 가진다 (AC-16)."""
    stats = wd.get_last_digit_pair_stats(_fixture_draws())
    for key in _LAST_DIGIT_PAIR_KEYS:
        cell = stats["last_digit_pair_distribution"][key]
        assert "count" in cell
        assert "pct" in cell


def test_counts_sum_to_total() -> None:
    """모든 분포 count 합은 total_draws와 같다 (AC-17)."""
    stats = wd.get_last_digit_pair_stats(_fixture_draws())
    total = sum(c["count"] for c in stats["last_digit_pair_distribution"].values())
    assert total == stats["total_draws"] == 4


def test_pct_rounded_two_decimals() -> None:
    """3개 회차 → pct는 33.33 형태로 소수 2자리 반올림된다 (AC-18)."""
    draws = [
        _mk(1, [1, 11, 2, 12, 3, 13]),   # 3그룹
        _mk(2, [1, 2, 3, 4, 5, 6]),      # 0그룹
        _mk(3, [5, 15, 25, 6, 16, 26]),  # 2그룹
    ]
    dist = wd.get_last_digit_pair_stats(draws)["last_digit_pair_distribution"]
    assert dist["3"]["pct"] == 33.33
    assert dist["0"]["pct"] == 33.33
    assert dist["2"]["pct"] == 33.33


# --------------------------------------------------------------------------- #
# 파생 지표 (4회차 픽스처)
# --------------------------------------------------------------------------- #


def test_distribution_counts_match_fixture() -> None:
    """D1~D4 분포 count — '0'=1, '1'=1, '2'=1, '3'=1 (AC-19)."""
    dist = wd.get_last_digit_pair_stats(_fixture_draws())["last_digit_pair_distribution"]
    assert dist["0"]["count"] == 1
    assert dist["1"]["count"] == 1
    assert dist["2"]["count"] == 1
    assert dist["3"]["count"] == 1


def test_distribution_pct_values() -> None:
    """D1~D4 pct — 각 25.0 (AC-20)."""
    dist = wd.get_last_digit_pair_stats(_fixture_draws())["last_digit_pair_distribution"]
    assert dist["0"]["pct"] == 25.0
    assert dist["1"]["pct"] == 25.0
    assert dist["2"]["pct"] == 25.0
    assert dist["3"]["pct"] == 25.0


def test_avg_pair_count_fixture() -> None:
    """D1~D4 → (3+0+2+1)/4 = 1.5 (AC-21)."""
    stats = wd.get_last_digit_pair_stats(_fixture_draws())
    assert stats["avg_pair_count"] == 1.5


def test_has_pair_pct_fixture() -> None:
    """D1~D4 → 중복>=1 인 D1·D3·D4 3건/4건 → 75.0 (AC-22)."""
    stats = wd.get_last_digit_pair_stats(_fixture_draws())
    assert stats["has_pair_pct"] == 75.0


def test_most_common_pair_count_tie_smaller_wins() -> None:
    """D1~D4 → 0·1·2·3 각 1회 동률 → 더 작은 0이 이긴다 (AC-23)."""
    stats = wd.get_last_digit_pair_stats(_fixture_draws())
    assert stats["most_common_pair_count"] == 0


def test_most_common_pair_count_clear_winner() -> None:
    """명확한 최빈값 — 0그룹 2회 / 1그룹 1회 → 0."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),   # 0그룹
        _mk(2, [7, 8, 9, 10, 12, 14]),  # 0그룹(모두 다른 일자리: 7,8,9,0,2,4)
        _mk(3, [1, 11, 2, 3, 4, 5]),  # 1그룹
    ]
    stats = wd.get_last_digit_pair_stats(draws)
    assert stats["most_common_pair_count"] == 0


# --------------------------------------------------------------------------- #
# 경계 및 예외
# --------------------------------------------------------------------------- #


def test_empty_draws_returns_consistent_zero_structure() -> None:
    """빈 draws → 예외 없이 일관된 zero 구조 (AC-01~05)."""
    stats = wd.get_last_digit_pair_stats([])
    assert stats["total_draws"] == 0
    assert stats["has_pair_pct"] == 0.0
    assert stats["most_common_pair_count"] == 0
    assert stats["avg_pair_count"] == 0.0
    assert set(stats["last_digit_pair_distribution"].keys()) == set(_LAST_DIGIT_PAIR_KEYS)
    for key in _LAST_DIGIT_PAIR_KEYS:
        assert stats["last_digit_pair_distribution"][key]["count"] == 0
        assert stats["last_digit_pair_distribution"][key]["pct"] == 0.0


def test_none_draws_returns_zero_structure() -> None:
    """None 입력도 예외 없이 빈 구조를 반환한다 (AC-06)."""
    stats = wd.get_last_digit_pair_stats(None)
    assert stats["total_draws"] == 0
    assert set(stats["last_digit_pair_distribution"].keys()) == set(_LAST_DIGIT_PAIR_KEYS)


def test_single_draw() -> None:
    """단일 회차 [1,11,2,3,4,5] → 1그룹 정상 집계 (AC-13)."""
    stats = wd.get_last_digit_pair_stats([_mk(1, [1, 11, 2, 3, 4, 5])])
    assert stats["total_draws"] == 1
    assert stats["most_common_pair_count"] == 1
    assert stats["last_digit_pair_distribution"]["1"]["count"] == 1


# --------------------------------------------------------------------------- #
# 캐시 동작
# --------------------------------------------------------------------------- #


def test_cache_populated_and_hit() -> None:
    """동일 입력 재호출 시 캐시된 동일 객체를 반환한다 (AC-24)."""
    draws = _fixture_draws()
    first = wd.get_last_digit_pair_stats(draws)
    second = wd.get_last_digit_pair_stats(draws)
    assert first is second


def test_cache_invalidated() -> None:
    """invalidate_cache 후에는 새 결과 객체를 생성한다 (AC-25)."""
    draws = _fixture_draws()
    first = wd.get_last_digit_pair_stats(draws)
    wd.invalidate_cache()
    second = wd.get_last_digit_pair_stats(draws)
    assert first is not second
    assert first == second


def test_invalidate_cache_clears_last_digit_pair_cache() -> None:
    """invalidate_cache가 _last_digit_pair_cache를 비운다 (AC-26)."""
    wd.get_last_digit_pair_stats(_fixture_draws())
    assert len(wd._last_digit_pair_cache) > 0
    wd.invalidate_cache()
    assert len(wd._last_digit_pair_cache) == 0


# --------------------------------------------------------------------------- #
# 라우트
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/last_digit_pair → 200 + 키 구조 (AC-27)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/last_digit_pair")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "has_pair_pct",
        "most_common_pair_count",
        "avg_pair_count",
        "last_digit_pair_distribution",
    ):
        assert key in body
    assert set(body["last_digit_pair_distribution"].keys()) == set(_LAST_DIGIT_PAIR_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/last_digit_pair 은 데이터가 없어도 200을 반환한다 (AC-28)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/last_digit_pair")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/last-digit-pair → 200(HTML) (AC-29)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/last-digit-pair")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/last-digit-pair 은 데이터가 없어도 200(빈 상태)을 반환한다 (AC-30)."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/last-digit-pair")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 실데이터 스모크
# --------------------------------------------------------------------------- #


def test_real_data_smoke() -> None:
    """실제 데이터가 있으면 total_draws>0, avg_pair_count는 0~3 범위 (AC-31)."""
    draws = wd.get_draws()
    if not draws:
        return  # 데이터 미수집 환경에서는 스킵
    result = wd.get_last_digit_pair_stats(draws)
    assert result["total_draws"] > 0
    assert 0.0 <= result["avg_pair_count"] <= 3.0
    assert result["most_common_pair_count"] in (0, 1, 2, 3)
