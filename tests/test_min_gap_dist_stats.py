"""SPEC-LOTTO-096: 최소 간격 구간 분포 분석 테스트.

데이터 계층(get_min_gap_dist_stats), 헬퍼(_min_gap_bucket),
캐시(_min_gap_dist_cache), 페이지/API 라우트를 RED-GREEN-REFACTOR로 검증한다.

min_gap(번호 간격 최솟값):
- 한 회차의 정렬된 본번호 6개(보너스 제외)에서 인접 차이 5개 중 최솟값.
- 6개 고정 구간 버킷("1","2","3","4-5","6-10","11+")으로 분류(zero-fill).
- avg_min_gap(회차별 min_gap 평균) / most_common_range(동률 시 앞선 구간)
  / min1_pct(min_gap=1인 회차 비율) / large_gap_pct(min_gap>=6 비율).

기존 get_gap_stats(SPEC-056, small/medium/large 분류 + avg_min_gap 단일 수치)와는
출력 구조가 완전히 다른 별개 기능이다.
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd


_MIN_GAP_KEYS = ["1", "2", "3", "4-5", "6-10", "11+"]


def _mk(no: int, nums: list[int], bonus: int = 45) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼."""
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# --------------------------------------------------------------------------- #
# 헬퍼 함수 (_min_gap_bucket)
# --------------------------------------------------------------------------- #


def test_bucket_1() -> None:
    """min_gap == 1은 '1' 버킷 (연속번호 쌍 존재)."""
    assert wd._min_gap_bucket(1) == "1"


def test_bucket_2() -> None:
    """min_gap == 2는 '2' 버킷."""
    assert wd._min_gap_bucket(2) == "2"


def test_bucket_3() -> None:
    """min_gap == 3은 '3' 버킷."""
    assert wd._min_gap_bucket(3) == "3"


def test_bucket_4() -> None:
    """min_gap == 4는 '4-5' 버킷."""
    assert wd._min_gap_bucket(4) == "4-5"


def test_bucket_5() -> None:
    """min_gap == 5는 '4-5' 버킷."""
    assert wd._min_gap_bucket(5) == "4-5"


def test_bucket_6() -> None:
    """min_gap == 6은 '6-10' 버킷."""
    assert wd._min_gap_bucket(6) == "6-10"


def test_bucket_10() -> None:
    """min_gap == 10은 '6-10' 버킷."""
    assert wd._min_gap_bucket(10) == "6-10"


def test_bucket_11() -> None:
    """min_gap == 11은 '11+' 버킷."""
    assert wd._min_gap_bucket(11) == "11+"


def test_bucket_20() -> None:
    """min_gap == 20은 '11+' 버킷."""
    assert wd._min_gap_bucket(20) == "11+"


# --------------------------------------------------------------------------- #
# 단일 회차 버킷 분류 검증
# --------------------------------------------------------------------------- #


def test_single_draw_consecutive() -> None:
    """[1,2,3,4,5,6]: gaps=[1,1,1,1,1], min_gap=1 → 버킷 '1'."""
    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    result = wd.get_min_gap_dist_stats(draws)
    assert result["min_gap_distribution"]["1"]["count"] == 1
    assert result["min_gap_distribution"]["2"]["count"] == 0


def test_single_draw_min2() -> None:
    """[1,3,5,7,9,11]: gaps=[2,2,2,2,2], min_gap=2 → 버킷 '2'."""
    draws = [_mk(1, [1, 3, 5, 7, 9, 11])]
    result = wd.get_min_gap_dist_stats(draws)
    assert result["min_gap_distribution"]["2"]["count"] == 1
    assert result["min_gap_distribution"]["1"]["count"] == 0


def test_single_draw_min3() -> None:
    """[1,4,7,10,13,16]: gaps=[3,3,3,3,3], min_gap=3 → 버킷 '3'."""
    draws = [_mk(1, [1, 4, 7, 10, 13, 16])]
    result = wd.get_min_gap_dist_stats(draws)
    assert result["min_gap_distribution"]["3"]["count"] == 1
    assert result["min_gap_distribution"]["2"]["count"] == 0


def test_single_draw_min4() -> None:
    """[1,5,9,13,17,21]: gaps=[4,4,4,4,4], min_gap=4 → 버킷 '4-5'."""
    draws = [_mk(1, [1, 5, 9, 13, 17, 21])]
    result = wd.get_min_gap_dist_stats(draws)
    assert result["min_gap_distribution"]["4-5"]["count"] == 1
    assert result["min_gap_distribution"]["3"]["count"] == 0


def test_single_draw_min5() -> None:
    """[1,6,11,16,21,26]: gaps=[5,5,5,5,5], min_gap=5 → 버킷 '4-5'."""
    draws = [_mk(1, [1, 6, 11, 16, 21, 26])]
    result = wd.get_min_gap_dist_stats(draws)
    assert result["min_gap_distribution"]["4-5"]["count"] == 1


def test_single_draw_min6() -> None:
    """[1,7,13,19,25,31]: gaps=[6,6,6,6,6], min_gap=6 → 버킷 '6-10'."""
    draws = [_mk(1, [1, 7, 13, 19, 25, 31])]
    result = wd.get_min_gap_dist_stats(draws)
    assert result["min_gap_distribution"]["6-10"]["count"] == 1
    assert result["min_gap_distribution"]["4-5"]["count"] == 0


def test_single_draw_mixed_min1() -> None:
    """[1,12,23,34,35,36]: gaps=[11,11,11,1,1], min_gap=1 → 버킷 '1'."""
    draws = [_mk(1, [1, 12, 23, 34, 35, 36])]
    result = wd.get_min_gap_dist_stats(draws)
    assert result["min_gap_distribution"]["1"]["count"] == 1
    assert result["min_gap_distribution"]["11+"]["count"] == 0


def test_single_draw_min11_plus() -> None:
    """[1,13,25,37,38,39]: 정렬 후 gaps=[12,12,12,1,1], min_gap=1 → 버킷 '1'.
    min_gap=11이 되려면 모든 간격이 11 이상이어야 한다.
    [1,12,23,34,35,45]: gaps=[11,11,11,1,10], min_gap=1 → 버킷 '1'.
    순수 min_gap=11: [1,12,23,34,45] 는 5개. 6개로 만들려면:
    [1,12,23,34,45] + 한 번 더 → 불가. 실제 예:
    [2,13,24,35,36,45]: gaps=[11,11,11,1,9], min_gap=1 → '1'.
    min_gap >= 11을 위해서는 6개 중 인접 쌍 최솟값이 11 이상이어야 함.
    예: 1~45에서 6개 간격 모두 >= 11: 1, 12+, 23+, 34+, 45+ → 5자리만 가능.
    실제 가능한 예: 1, 12, 23, 34, 45 → 5개. 6개는 불가능(1-45 범위).
    따라서 SPEC-096의 '11+' 버킷은 이론적으로 실제 데이터에서 거의 나타나지 않음.
    테스트에서는 임의로 min_gap=11 단일회차를 직접 _min_gap_bucket으로 확인한다.
    """
    # 직접 버킷 함수로 11+를 검증
    assert wd._min_gap_bucket(11) == "11+"
    assert wd._min_gap_bucket(15) == "11+"
    assert wd._min_gap_bucket(44) == "11+"


# --------------------------------------------------------------------------- #
# 빈 데이터 처리
# --------------------------------------------------------------------------- #


def test_empty_draws_returns_zero_structure() -> None:
    """draws=[] → total_draws=0, 6개 버킷 전부 0, avg/pct 전부 0."""
    result = wd.get_min_gap_dist_stats([])
    assert result["total_draws"] == 0
    assert result["avg_min_gap"] == 0.0
    assert result["min1_pct"] == 0.0
    assert result["large_gap_pct"] == 0.0
    for k in _MIN_GAP_KEYS:
        assert result["min_gap_distribution"][k]["count"] == 0
        assert result["min_gap_distribution"][k]["pct"] == 0.0


def test_none_draws_returns_zero_structure() -> None:
    """draws=None → 빈 구조 반환 (total_draws=0)."""
    result = wd.get_min_gap_dist_stats(None)
    assert result["total_draws"] == 0
    assert result["avg_min_gap"] == 0.0


def test_empty_most_common_is_first_key() -> None:
    """빈 데이터일 때 most_common_range는 '1' (정의 순서 첫 번째 키)."""
    result = wd.get_min_gap_dist_stats([])
    assert result["most_common_range"] == "1"


# --------------------------------------------------------------------------- #
# 복수 회차 분포 집계
# --------------------------------------------------------------------------- #


def _fixture_draws() -> list[DrawResult]:
    """손계산 검증용 4개 회차 픽스처.

    D1 [1,2,3,4,5,6]       gaps=[1,1,1,1,1]    min=1  → '1'
    D2 [1,3,5,7,9,11]      gaps=[2,2,2,2,2]    min=2  → '2'
    D3 [1,4,7,10,13,16]    gaps=[3,3,3,3,3]    min=3  → '3'
    D4 [1,7,13,19,25,31]   gaps=[6,6,6,6,6]    min=6  → '6-10'
    """
    return [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [1, 3, 5, 7, 9, 11]),
        _mk(3, [1, 4, 7, 10, 13, 16]),
        _mk(4, [1, 7, 13, 19, 25, 31]),
    ]


def test_distribution_counts() -> None:
    """4개 회차 픽스처에서 각 버킷 count 검증."""
    result = wd.get_min_gap_dist_stats(_fixture_draws())
    dist = result["min_gap_distribution"]
    assert dist["1"]["count"] == 1
    assert dist["2"]["count"] == 1
    assert dist["3"]["count"] == 1
    assert dist["4-5"]["count"] == 0
    assert dist["6-10"]["count"] == 1
    assert dist["11+"]["count"] == 0


def test_total_draws() -> None:
    """4개 회차 → total_draws == 4."""
    result = wd.get_min_gap_dist_stats(_fixture_draws())
    assert result["total_draws"] == 4


def test_avg_min_gap() -> None:
    """avg_min_gap: (1+2+3+6)/4 = 3.0."""
    result = wd.get_min_gap_dist_stats(_fixture_draws())
    assert result["avg_min_gap"] == 3.0


def test_distribution_pct() -> None:
    """4개 회차: 각 버킷 pct = 25.0 (1개씩)."""
    result = wd.get_min_gap_dist_stats(_fixture_draws())
    dist = result["min_gap_distribution"]
    assert dist["1"]["pct"] == 25.0
    assert dist["2"]["pct"] == 25.0
    assert dist["3"]["pct"] == 25.0
    assert dist["4-5"]["pct"] == 0.0
    assert dist["6-10"]["pct"] == 25.0
    assert dist["11+"]["pct"] == 0.0


def test_min1_pct() -> None:
    """min1_pct: 1개(D1)가 min_gap=1 → 1/4 * 100 = 25.0%."""
    result = wd.get_min_gap_dist_stats(_fixture_draws())
    assert result["min1_pct"] == 25.0


def test_large_gap_pct() -> None:
    """large_gap_pct: min_gap>=6 회차 1개(D4) → 1/4 * 100 = 25.0%."""
    result = wd.get_min_gap_dist_stats(_fixture_draws())
    assert result["large_gap_pct"] == 25.0


def test_most_common_range() -> None:
    """4개 회차, 동률(1개씩) → 정의 순서 첫 번째 키 '1'."""
    result = wd.get_min_gap_dist_stats(_fixture_draws())
    assert result["most_common_range"] == "1"


def test_most_common_range_when_max_in_bucket2() -> None:
    """2개 회차가 버킷 '2'에 있을 때 most_common_range == '2'."""
    draws = [
        _mk(1, [1, 3, 5, 7, 9, 11]),   # min=2 → '2'
        _mk(2, [1, 3, 5, 7, 9, 11]),   # min=2 → '2'
        _mk(3, [1, 2, 3, 4, 5, 6]),    # min=1 → '1'
    ]
    result = wd.get_min_gap_dist_stats(draws)
    assert result["most_common_range"] == "2"


# --------------------------------------------------------------------------- #
# 6개 버킷 키 항상 존재 확인 (N2)
# --------------------------------------------------------------------------- #


def test_all_six_keys_always_present() -> None:
    """결과에 6개 고정 버킷 키가 항상 존재한다."""
    result = wd.get_min_gap_dist_stats(_fixture_draws())
    for k in _MIN_GAP_KEYS:
        assert k in result["min_gap_distribution"]


def test_all_keys_in_empty_result() -> None:
    """빈 데이터에서도 6개 고정 버킷 키가 모두 존재한다."""
    result = wd.get_min_gap_dist_stats([])
    for k in _MIN_GAP_KEYS:
        assert k in result["min_gap_distribution"]


# --------------------------------------------------------------------------- #
# pct 합계 검증 (S3)
# --------------------------------------------------------------------------- #


def test_pct_sum_near_100() -> None:
    """6개 버킷 pct 합계가 100.0에 근접한다 (부동소수점 오차 허용)."""
    result = wd.get_min_gap_dist_stats(_fixture_draws())
    total = sum(v["pct"] for v in result["min_gap_distribution"].values())
    assert abs(total - 100.0) < 0.1


# --------------------------------------------------------------------------- #
# 캐시 동작 (S2, E3)
# --------------------------------------------------------------------------- #


def test_cache_hit() -> None:
    """동일 len(draws) 두 번 호출 시 캐시에서 반환한다."""
    wd._min_gap_dist_cache.clear()
    draws = _fixture_draws()
    r1 = wd.get_min_gap_dist_stats(draws)
    r2 = wd.get_min_gap_dist_stats(draws)
    assert r1 is r2  # 동일 객체 (캐시 히트)


def test_invalidate_cache_clears_min_gap_dist() -> None:
    """invalidate_cache() 호출 시 _min_gap_dist_cache 가 비워진다."""
    draws = _fixture_draws()
    wd.get_min_gap_dist_stats(draws)  # 캐시 채우기
    assert len(wd._min_gap_dist_cache) > 0
    wd.invalidate_cache()
    assert len(wd._min_gap_dist_cache) == 0


# --------------------------------------------------------------------------- #
# API 엔드포인트 (E1)
# --------------------------------------------------------------------------- #


def _client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


def test_api_endpoint_returns_200() -> None:
    """GET /api/stats/min_gap_dist → 200 OK."""
    client = _client()
    with patch("lotto.web.data.get_draws", return_value=_fixture_draws()):
        resp = client.get("/api/stats/min_gap_dist")
    assert resp.status_code == 200


def test_api_endpoint_response_structure() -> None:
    """API 응답에 필수 필드와 6개 버킷 키가 모두 존재한다."""
    client = _client()
    with patch("lotto.web.data.get_draws", return_value=_fixture_draws()):
        resp = client.get("/api/stats/min_gap_dist")
    body = resp.json()
    assert "total_draws" in body
    assert "avg_min_gap" in body
    assert "most_common_range" in body
    assert "min1_pct" in body
    assert "large_gap_pct" in body
    assert "min_gap_distribution" in body
    for k in _MIN_GAP_KEYS:
        assert k in body["min_gap_distribution"]


def test_api_endpoint_empty_data() -> None:
    """빈 데이터에서도 API 엔드포인트가 200을 반환한다."""
    client = _client()
    with patch("lotto.web.data.get_draws", return_value=[]):
        resp = client.get("/api/stats/min_gap_dist")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 0


# --------------------------------------------------------------------------- #
# 페이지 엔드포인트 (E2)
# --------------------------------------------------------------------------- #


def test_page_endpoint_returns_200() -> None:
    """GET /stats/min-gap-dist → 200 OK (HTML 페이지)."""
    client = _client()
    with patch("lotto.web.data.get_draws", return_value=_fixture_draws()):
        resp = client.get("/stats/min-gap-dist")
    assert resp.status_code == 200


def test_page_endpoint_returns_html() -> None:
    """페이지 응답이 text/html Content-Type을 가진다."""
    client = _client()
    with patch("lotto.web.data.get_draws", return_value=_fixture_draws()):
        resp = client.get("/stats/min-gap-dist")
    assert "text/html" in resp.headers.get("content-type", "")


def test_page_endpoint_empty_data() -> None:
    """빈 데이터에서도 페이지 엔드포인트가 200을 반환한다."""
    client = _client()
    with patch("lotto.web.data.get_draws", return_value=[]):
        resp = client.get("/stats/min-gap-dist")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 정밀도 검증 (N4)
# --------------------------------------------------------------------------- #


def test_avg_min_gap_two_decimal_places() -> None:
    """avg_min_gap은 소수 2자리로 반환된다."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),    # min=1
        _mk(2, [1, 3, 5, 7, 9, 11]),   # min=2
        _mk(3, [1, 4, 7, 10, 13, 16]), # min=3
    ]
    # avg = (1+2+3)/3 = 2.0
    result = wd.get_min_gap_dist_stats(draws)
    avg = result["avg_min_gap"]
    assert isinstance(avg, float)
    # 소수 2자리 검증: str 변환시 소수점 이하 최대 2자리
    s = str(avg)
    if "." in s:
        decimals = len(s.split(".")[1])
        assert decimals <= 2


def test_pct_two_decimal_places() -> None:
    """pct 값은 소수 2자리를 초과하지 않는다."""
    result = wd.get_min_gap_dist_stats(_fixture_draws())
    for v in result["min_gap_distribution"].values():
        s = str(v["pct"])
        if "." in s:
            decimals = len(s.split(".")[1])
            assert decimals <= 2


# --------------------------------------------------------------------------- #
# 보너스 번호 제외 (U1, N1)
# --------------------------------------------------------------------------- #


def test_bonus_number_excluded() -> None:
    """보너스 번호는 min_gap 계산에 포함되지 않는다.

    본번호 [1,2,3,4,5,6](연속, min=1)에 보너스 45.
    보너스가 포함되면 간격이 달라지지만, 제외해야 min=1.
    """
    draw = _mk(1, [1, 2, 3, 4, 5, 6], bonus=45)
    result = wd.get_min_gap_dist_stats([draw])
    assert result["min_gap_distribution"]["1"]["count"] == 1


# --------------------------------------------------------------------------- #
# 추가 경계값 테스트
# --------------------------------------------------------------------------- #


def test_avg_calc_with_two_draws() -> None:
    """2개 회차: avg_min_gap = (1 + 6) / 2 = 3.5."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),    # min=1
        _mk(2, [1, 7, 13, 19, 25, 31]), # min=6
    ]
    result = wd.get_min_gap_dist_stats(draws)
    assert result["avg_min_gap"] == 3.5


def test_min1_pct_all_consecutive() -> None:
    """모든 회차가 min_gap=1 → min1_pct = 100.0%."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),
        _mk(2, [5, 6, 20, 30, 40, 45]),  # min=1
    ]
    result = wd.get_min_gap_dist_stats(draws)
    assert result["min1_pct"] == 100.0


def test_large_gap_pct_none() -> None:
    """모든 min_gap < 6 → large_gap_pct = 0.0%."""
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 6]),    # min=1
        _mk(2, [1, 3, 5, 7, 9, 11]),   # min=2
    ]
    result = wd.get_min_gap_dist_stats(draws)
    assert result["large_gap_pct"] == 0.0
