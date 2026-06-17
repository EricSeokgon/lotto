"""SPEC-LOTTO-076: 4의 배수 포함 개수 분포 분석 테스트.

데이터 계층(get_mult4_stats), 캐시(_mult4_cache),
페이지/API 라우트를 RED-GREEN-REFACTOR로 검증한다.

4의 배수 포함 개수(mult4 count):
- 한 회차 본번호 6개(보너스 제외) 중 4의 배수(4로 나누어 떨어지는)의 개수.
- 1~45 중 4의 배수는 {4,8,12,16,20,24,28,32,36,40,44} 11개.
- 값의 범위는 0(없음)~6(모두 4의 배수).
- 분포 키는 "0".."6" 7개 고정 버킷(미관측은 zero-fill).
- avg_mult4_count / most_common_count(동률 시 작은 값) / high_mult4_pct(>=3 비율).

SPEC-073(3의 배수)·SPEC-074(짝수)·SPEC-075(5의 배수)와는 계산 대상이 다른 별개 기능이다.
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


_MULT4_KEYS = ["0", "1", "2", "3", "4", "5", "6"]


def _mk(no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    bonus 기본값 7(4의 배수 아님)이지만, 4배수 보너스를 지정해도 본번호 집계에는
    포함되지 않아야 함을 별도 테스트에서 검증한다.
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# 손계산 검증용 4개 회차 픽스처.
# D1 [1,2,3,5,7,9]        → 4배수 없음           → 0 (최솟값)
# D2 [4,8,12,16,20,24]    → 4배수 전부           → 6 (최댓값)
# D3 [4,5,6,7,8,9]        → 4배수 {4,8}          → 2
# D4 [10,20,30,40,41,42]  → 4배수 {20,40}        → 2
def _fixture_draws() -> list[DrawResult]:
    return [
        _mk(1, [1, 2, 3, 5, 7, 9]),
        _mk(2, [4, 8, 12, 16, 20, 24]),
        _mk(3, [4, 5, 6, 7, 8, 9]),
        _mk(4, [10, 20, 30, 40, 41, 42]),
    ]


# --------------------------------------------------------------------------- #
# 4배수 개수 계산 정확성
# --------------------------------------------------------------------------- #


def test_mult4_count_six_max() -> None:
    """[4,8,12,16,20,24] → 6개 전부 4배수 → 6 (최댓값)."""
    draws = [_mk(1, [4, 8, 12, 16, 20, 24])]
    stats = wd.get_mult4_stats(draws)
    assert stats["mult4_distribution"]["6"]["count"] == 1
    assert stats["avg_mult4_count"] == 6.0


def test_mult4_count_zero_min() -> None:
    """[1,2,3,5,7,9] → 4배수 없음 → 0 (최솟값)."""
    draws = [_mk(1, [1, 2, 3, 5, 7, 9])]
    stats = wd.get_mult4_stats(draws)
    assert stats["mult4_distribution"]["0"]["count"] == 1
    assert stats["avg_mult4_count"] == 0.0


def test_mult4_count_two_low() -> None:
    """[4,5,6,7,8,9] → 4배수 {4,8} → 2개."""
    draws = [_mk(1, [4, 5, 6, 7, 8, 9])]
    stats = wd.get_mult4_stats(draws)
    assert stats["mult4_distribution"]["2"]["count"] == 1
    assert stats["avg_mult4_count"] == 2.0


def test_mult4_count_two_high() -> None:
    """[10,20,30,40,41,42] → 4배수 {20,40} → 2개."""
    draws = [_mk(1, [10, 20, 30, 40, 41, 42])]
    stats = wd.get_mult4_stats(draws)
    assert stats["mult4_distribution"]["2"]["count"] == 1
    assert stats["avg_mult4_count"] == 2.0


def test_mult4_count_includes_44() -> None:
    """44는 4의 배수다(4*11). [44,3,5,7,9,11] → 1개."""
    draws = [_mk(1, [44, 3, 5, 7, 9, 11])]
    stats = wd.get_mult4_stats(draws)
    assert stats["mult4_distribution"]["1"]["count"] == 1


def test_bonus_excluded_from_mult4_count() -> None:
    """보너스 번호는 4배수 개수 계산에 포함되지 않는다."""
    # 본번호 [1,2,3,5,7,9] → 4배수 0개. bonus=4(4배수)이어도 0개가 유지되어야 한다.
    draws = [_mk(1, [1, 2, 3, 5, 7, 9], bonus=4)]
    stats = wd.get_mult4_stats(draws)
    assert stats["mult4_distribution"]["0"]["count"] == 1
    assert stats["avg_mult4_count"] == 0.0


# --------------------------------------------------------------------------- #
# 응답 구조 및 분포
# --------------------------------------------------------------------------- #


def test_response_has_all_top_level_keys() -> None:
    """반환 dict는 5개 최상위 키를 모두 포함한다."""
    stats = wd.get_mult4_stats(_fixture_draws())
    for key in (
        "total_draws",
        "avg_mult4_count",
        "most_common_count",
        "high_mult4_pct",
        "mult4_distribution",
    ):
        assert key in stats


def test_distribution_always_has_seven_keys() -> None:
    """mult4_distribution은 항상 '0'..'6' 7개 키를 포함한다."""
    stats = wd.get_mult4_stats(_fixture_draws())
    assert set(stats["mult4_distribution"].keys()) == set(_MULT4_KEYS)


def test_distribution_cells_have_count_and_pct() -> None:
    """각 분포 항목은 count·pct 두 키를 가진다."""
    stats = wd.get_mult4_stats(_fixture_draws())
    for key in _MULT4_KEYS:
        cell = stats["mult4_distribution"][key]
        assert "count" in cell
        assert "pct" in cell


def test_distribution_counts_match_fixture() -> None:
    """D1~D4 분포 count는 '0'=1, '2'=2, '6'=1, 나머지 0."""
    stats = wd.get_mult4_stats(_fixture_draws())
    dist = stats["mult4_distribution"]
    assert dist["0"]["count"] == 1
    assert dist["1"]["count"] == 0
    assert dist["2"]["count"] == 2
    assert dist["3"]["count"] == 0
    assert dist["4"]["count"] == 0
    assert dist["5"]["count"] == 0
    assert dist["6"]["count"] == 1


def test_bucket_counts_sum_to_total() -> None:
    """모든 버킷 count 합은 total_draws와 같다."""
    stats = wd.get_mult4_stats(_fixture_draws())
    total = sum(c["count"] for c in stats["mult4_distribution"].values())
    assert total == stats["total_draws"] == 4


def test_distribution_pct_values() -> None:
    """D1~D4 pct는 '0'=25.0, '2'=50.0, '6'=25.0, 나머지 0.0."""
    stats = wd.get_mult4_stats(_fixture_draws())
    dist = stats["mult4_distribution"]
    assert dist["0"]["pct"] == 25.0
    assert dist["2"]["pct"] == 50.0
    assert dist["6"]["pct"] == 25.0
    assert dist["1"]["pct"] == 0.0
    assert dist["3"]["pct"] == 0.0
    assert dist["4"]["pct"] == 0.0
    assert dist["5"]["pct"] == 0.0


def test_pct_values_sum_to_hundred() -> None:
    """pct 합은 부동소수 오차 범위 내에서 100.0이다."""
    stats = wd.get_mult4_stats(_fixture_draws())
    total_pct = sum(c["pct"] for c in stats["mult4_distribution"].values())
    assert abs(total_pct - 100.0) < 0.01


# --------------------------------------------------------------------------- #
# 파생 지표
# --------------------------------------------------------------------------- #


def test_avg_mult4_count_fixture() -> None:
    """D1~D4 → (0+6+2+2)/4 = 2.5."""
    stats = wd.get_mult4_stats(_fixture_draws())
    assert stats["avg_mult4_count"] == 2.5


def test_most_common_count_fixture() -> None:
    """D1~D4 → 개수 2가 2회(D3,D4)로 최빈 → 2."""
    stats = wd.get_mult4_stats(_fixture_draws())
    assert stats["most_common_count"] == 2


def test_most_common_count_tie_smaller_wins() -> None:
    """동률 시 더 작은 개수가 선택된다(고정 키 순서 선두 우선).

    개수 0,6 각 1회로 동률 → 가장 작은 0이 이긴다.
    """
    draws = [
        _mk(1, [1, 2, 3, 5, 7, 9]),       # 0개
        _mk(2, [4, 8, 12, 16, 20, 24]),   # 6개
    ]
    stats = wd.get_mult4_stats(draws)
    assert stats["most_common_count"] == 0


def test_most_common_count_clear_winner() -> None:
    """동률이 아닐 때는 최빈 개수가 그대로 선택된다."""
    draws = [
        _mk(1, [4, 5, 6, 7, 8, 9]),       # 2개
        _mk(2, [4, 5, 6, 7, 8, 9]),       # 2개
        _mk(3, [1, 2, 3, 5, 7, 9]),       # 0개
    ]
    stats = wd.get_mult4_stats(draws)
    assert stats["most_common_count"] == 2


def test_high_mult4_pct_fixture() -> None:
    """D1~D4 → count>=3 인 D2(6) 1건 / 4건 → 25.0."""
    stats = wd.get_mult4_stats(_fixture_draws())
    assert stats["high_mult4_pct"] == 25.0


def test_high_mult4_pct_zero_when_none() -> None:
    """모든 회차 count<3 이면 high_mult4_pct == 0.0."""
    draws = [
        _mk(1, [1, 2, 3, 5, 7, 9]),       # 0개
        _mk(2, [4, 5, 6, 7, 8, 9]),       # 2개
    ]
    stats = wd.get_mult4_stats(draws)
    assert stats["high_mult4_pct"] == 0.0


def test_high_mult4_pct_hundred() -> None:
    """모든 회차 count>=3 이면 high_mult4_pct == 100.0."""
    draws = [
        _mk(1, [4, 8, 12, 16, 5, 7]),     # 4개
        _mk(2, [4, 8, 12, 16, 20, 24]),   # 6개
    ]
    stats = wd.get_mult4_stats(draws)
    assert stats["high_mult4_pct"] == 100.0


def test_numeric_fields_rounded_two_decimals() -> None:
    """avg_mult4_count·high_mult4_pct·각 pct는 소수 2자리 반올림.

    3개 회차 → pct는 33.33.. 형태로 반올림 검증.
    """
    draws = [
        _mk(1, [4, 8, 12, 16, 5, 7]),     # 4개
        _mk(2, [4, 8, 12, 16, 20, 24]),   # 6개
        _mk(3, [1, 2, 3, 5, 7, 9]),       # 0개
    ]
    stats = wd.get_mult4_stats(draws)
    # avg = (4+6+0)/3 = 3.333.. → 3.33
    assert stats["avg_mult4_count"] == 3.33
    # high(>=3) = 2/3 = 66.666.. → 66.67
    assert stats["high_mult4_pct"] == 66.67
    assert stats["mult4_distribution"]["6"]["pct"] == 33.33


# --------------------------------------------------------------------------- #
# 경계 및 예외
# --------------------------------------------------------------------------- #


def test_empty_draws_returns_consistent_zero_structure() -> None:
    """빈 draws → 예외 없이 일관된 zero 구조."""
    stats = wd.get_mult4_stats([])
    assert stats["total_draws"] == 0
    assert stats["avg_mult4_count"] == 0.0
    assert stats["most_common_count"] == 0
    assert stats["high_mult4_pct"] == 0.0
    assert set(stats["mult4_distribution"].keys()) == set(_MULT4_KEYS)
    for key in _MULT4_KEYS:
        assert stats["mult4_distribution"][key]["count"] == 0
        assert stats["mult4_distribution"][key]["pct"] == 0.0


def test_single_draw() -> None:
    """단일 회차도 정상 집계된다."""
    stats = wd.get_mult4_stats([_mk(1, [4, 5, 6, 7, 8, 9])])
    assert stats["total_draws"] == 1
    assert stats["most_common_count"] == 2
    assert stats["mult4_distribution"]["2"]["count"] == 1


# --------------------------------------------------------------------------- #
# 캐시 동작
# --------------------------------------------------------------------------- #


def test_cache_populated_and_hit() -> None:
    """동일 입력 재호출 시 캐시된 동일 객체를 반환한다."""
    draws = _fixture_draws()
    first = wd.get_mult4_stats(draws)
    second = wd.get_mult4_stats(draws)
    assert first is second


def test_cache_invalidated() -> None:
    """invalidate_cache 후에는 새 결과 객체를 생성한다."""
    draws = _fixture_draws()
    first = wd.get_mult4_stats(draws)
    wd.invalidate_cache()
    second = wd.get_mult4_stats(draws)
    assert first is not second
    assert first == second


def test_invalidate_cache_clears_mult4_cache() -> None:
    """invalidate_cache가 _mult4_cache를 비운다."""
    wd.get_mult4_stats(_fixture_draws())
    assert len(wd._mult4_cache) > 0
    wd.invalidate_cache()
    assert len(wd._mult4_cache) == 0


# --------------------------------------------------------------------------- #
# 라우트
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_200_and_structure() -> None:
    """GET /api/stats/mult4 → 200 + 키 구조."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/api/stats/mult4")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 4
    for key in (
        "total_draws",
        "avg_mult4_count",
        "most_common_count",
        "high_mult4_pct",
        "mult4_distribution",
    ):
        assert key in body
    assert set(body["mult4_distribution"].keys()) == set(_MULT4_KEYS)


def test_api_endpoint_empty_returns_200() -> None:
    """GET /api/stats/mult4 은 데이터가 없어도 200을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/api/stats/mult4")
    assert resp.status_code == 200
    assert resp.json()["total_draws"] == 0


def test_page_endpoint_200() -> None:
    """GET /stats/mult4 → 200(HTML, "4" 포함)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = _client().get("/stats/mult4")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "4" in resp.text


def test_page_endpoint_200_when_empty() -> None:
    """GET /stats/mult4 은 데이터가 없어도 200(빈 상태)을 반환한다."""
    with patch.object(wd, "get_draws", return_value=[]):
        resp = _client().get("/stats/mult4")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 실데이터 스모크
# --------------------------------------------------------------------------- #


def test_real_data_smoke() -> None:
    """실제 데이터가 있으면 total_draws>0, avg_mult4_count는 0~6 범위."""
    draws = wd.get_draws()
    if not draws:
        return  # 데이터 미수집 환경에서는 스킵
    result = wd.get_mult4_stats(draws)
    assert result["total_draws"] > 0
    assert 0.0 <= result["avg_mult4_count"] <= 6.0
    assert 0 <= result["most_common_count"] <= 6
