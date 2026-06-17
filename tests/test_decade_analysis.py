"""SPEC-LOTTO-059: 십의 자리 구간 분포 분석 테스트.

데이터 계층(get_decade_stats), 캐시, 페이지/API 라우트를
RED-GREEN-REFACTOR로 검증한다.

구간 정의(회차별 본번호 6개, 보너스 제외):
- "01-09": 1~9 (크기 9)
- "10-19": 10~19 (크기 10)
- "20-29": 20~29 (크기 10)
- "30-39": 30~39 (크기 10)
- "40-45": 40~45 (크기 6)

명시적 범위 비교로 분류한다(n // 10 사용 금지).
1~9는 "01-09"에 매핑되며 "decade 0"이 아니다.
불변식: 회차마다 5개 구간의 카운트 합 == 6.
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

# 기대값 산출용 로컬 구간 정의(구현과 독립적으로 정의)
_GROUPS: list[tuple[str, int, int, int]] = [
    ("01-09", 1, 9, 9),
    ("10-19", 10, 19, 10),
    ("20-29", 20, 29, 10),
    ("30-39", 30, 39, 10),
    ("40-45", 40, 45, 6),
]
_LABELS = [g[0] for g in _GROUPS]


def _mk(no: int, nums: list[int], bonus: int = 13) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    bonus는 본번호와 겹치지 않는 값(13)을 기본으로 둔다.
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


def _classify(nums: list[int]) -> dict[str, int]:
    """본번호 6개를 5개 구간별 카운트로 분류한 기대값을 산출한다."""
    counts = dict.fromkeys(_LABELS, 0)
    for n in nums:
        for label, low, high, _size in _GROUPS:
            if low <= n <= high:
                counts[label] += 1
                break
    return counts


@pytest.fixture
def api_client() -> TestClient:
    """매 테스트 새 TestClient — 라우터는 모듈 공유."""
    from lotto.web.app import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# 데이터 계층: get_decade_stats
# ---------------------------------------------------------------------------


def test_decade_stats_empty_zeros() -> None:
    """빈 데이터는 total_draws=0, 5개 구간(avg_count=0.0)을 반환한다."""
    from lotto.web import data as wd

    result = wd.get_decade_stats([])

    assert result["total_draws"] == 0
    assert len(result["groups"]) == 5
    for g in result["groups"]:
        assert g["avg_count"] == 0.0
        assert g["distribution"] == {}


def test_decade_stats_none_zeros() -> None:
    """None 입력도 빈 데이터와 동일하게 처리한다."""
    from lotto.web import data as wd

    result = wd.get_decade_stats(None)

    assert result["total_draws"] == 0
    assert len(result["groups"]) == 5


def test_decade_stats_empty_expected_avg_computed() -> None:
    """빈 데이터여도 expected_avg는 (size/45)*6으로 계산된다."""
    from lotto.web import data as wd

    result = wd.get_decade_stats([])
    by_label = {g["label"]: g for g in result["groups"]}

    assert by_label["01-09"]["expected_avg"] == 1.2  # 9/45*6
    assert by_label["40-45"]["expected_avg"] == 0.8  # 6/45*6


def test_decade_stats_empty_deviation_is_negative_expected() -> None:
    """빈 데이터의 deviation은 0 - expected_avg이다."""
    from lotto.web import data as wd

    result = wd.get_decade_stats([])
    by_label = {g["label"]: g for g in result["groups"]}

    assert by_label["01-09"]["deviation"] == -1.2
    assert by_label["40-45"]["deviation"] == -0.8


def test_decade_stats_single_draw_counts() -> None:
    """단일 회차 [5,15,25,35,42,1] → 구간별 카운트 검증."""
    from lotto.web import data as wd

    # 5,1 → 01-09(2), 15 → 10-19(1), 25 → 20-29(1), 35 → 30-39(1), 42 → 40-45(1)
    result = wd.get_decade_stats([_mk(1, [1, 5, 15, 25, 35, 42])])
    by_label = {g["label"]: g for g in result["groups"]}

    assert by_label["01-09"]["avg_count"] == 2.0
    assert by_label["10-19"]["avg_count"] == 1.0
    assert by_label["20-29"]["avg_count"] == 1.0
    assert by_label["30-39"]["avg_count"] == 1.0
    assert by_label["40-45"]["avg_count"] == 1.0


def test_decade_stats_number_1_maps_to_first_group() -> None:
    """숫자 1은 'decade 0'이 아니라 '01-09'에 매핑된다."""
    from lotto.web import data as wd

    result = wd.get_decade_stats([_mk(1, [1, 2, 3, 4, 5, 6])])
    by_label = {g["label"]: g for g in result["groups"]}

    assert by_label["01-09"]["avg_count"] == 6.0


def test_decade_stats_number_9_in_first_group() -> None:
    """9는 '01-09', 10은 '10-19' 경계 분류를 검증한다."""
    from lotto.web import data as wd

    result = wd.get_decade_stats([_mk(1, [8, 9, 10, 11, 40, 45])])
    by_label = {g["label"]: g for g in result["groups"]}

    assert by_label["01-09"]["avg_count"] == 2.0  # 8, 9
    assert by_label["10-19"]["avg_count"] == 2.0  # 10, 11
    assert by_label["40-45"]["avg_count"] == 2.0  # 40, 45


def test_decade_stats_counts_sum_to_six_invariant() -> None:
    """불변식: 각 회차에서 5개 구간 카운트 합 == 6 (avg 합 == 6)."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 5, 15, 25, 35, 42]),
        _mk(2, [9, 10, 20, 30, 40, 45]),
        _mk(3, [2, 4, 6, 8, 11, 19]),
    ]
    result = wd.get_decade_stats(draws)
    total_avg = sum(g["avg_count"] for g in result["groups"])

    assert round(total_avg, 2) == 6.0


def test_decade_stats_all_five_labels_present_in_order() -> None:
    """출력에 5개 구간 라벨이 고정 순서로 모두 존재한다."""
    from lotto.web import data as wd

    result = wd.get_decade_stats([_mk(1, [1, 5, 15, 25, 35, 42])])
    labels = [g["label"] for g in result["groups"]]

    assert labels == ["01-09", "10-19", "20-29", "30-39", "40-45"]


def test_decade_stats_group_sizes() -> None:
    """각 구간의 size가 정의된 값과 일치한다."""
    from lotto.web import data as wd

    result = wd.get_decade_stats([_mk(1, [1, 5, 15, 25, 35, 42])])
    by_label = {g["label"]: g for g in result["groups"]}

    assert by_label["01-09"]["size"] == 9
    assert by_label["10-19"]["size"] == 10
    assert by_label["20-29"]["size"] == 10
    assert by_label["30-39"]["size"] == 10
    assert by_label["40-45"]["size"] == 6


def test_decade_stats_distribution_keys_0_to_6_present() -> None:
    """각 구간의 distribution은 0~6 키를 모두 포함한다."""
    from lotto.web import data as wd

    result = wd.get_decade_stats([_mk(1, [1, 5, 15, 25, 35, 42])])

    for g in result["groups"]:
        assert set(g["distribution"].keys()) == set(range(7))


def test_decade_stats_distribution_counts() -> None:
    """distribution[count] = 해당 카운트가 나온 회차 수."""
    from lotto.web import data as wd

    # 두 회차 모두 01-09에 2개씩 → distribution[2] == 2
    draws = [
        _mk(1, [1, 5, 15, 25, 35, 42]),
        _mk(2, [2, 8, 16, 26, 36, 43]),
    ]
    result = wd.get_decade_stats(draws)
    by_label = {g["label"]: g for g in result["groups"]}

    assert by_label["01-09"]["distribution"][2] == 2
    assert by_label["01-09"]["distribution"][0] == 0


def test_decade_stats_distribution_sums_to_total_draws() -> None:
    """각 구간의 distribution 값 합 == total_draws."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 5, 15, 25, 35, 42]),
        _mk(2, [9, 10, 20, 30, 40, 45]),
        _mk(3, [2, 4, 6, 8, 11, 19]),
    ]
    result = wd.get_decade_stats(draws)

    for g in result["groups"]:
        assert sum(g["distribution"].values()) == 3


def test_decade_stats_avg_count_rounded_two_decimals() -> None:
    """avg_count는 소수점 둘째 자리까지 반올림된다."""
    from lotto.web import data as wd

    # 3회차, 01-09 카운트 합 = 2+0+6 = 8 → 8/3 = 2.666... → 2.67
    draws = [
        _mk(1, [1, 5, 15, 25, 35, 42]),
        _mk(2, [11, 12, 20, 30, 40, 45]),
        _mk(3, [1, 2, 3, 4, 5, 6]),
    ]
    result = wd.get_decade_stats(draws)
    by_label = {g["label"]: g for g in result["groups"]}

    assert by_label["01-09"]["avg_count"] == 2.67


def test_decade_stats_expected_avg_values() -> None:
    """expected_avg = (size/45)*6, 2 decimals."""
    from lotto.web import data as wd

    result = wd.get_decade_stats([_mk(1, [1, 5, 15, 25, 35, 42])])
    by_label = {g["label"]: g for g in result["groups"]}

    assert by_label["01-09"]["expected_avg"] == 1.2  # 9/45*6
    assert by_label["10-19"]["expected_avg"] == 1.33  # 10/45*6 = 1.333
    assert by_label["40-45"]["expected_avg"] == 0.8  # 6/45*6


def test_decade_stats_deviation_equals_avg_minus_expected() -> None:
    """deviation = avg_count - expected_avg."""
    from lotto.web import data as wd

    result = wd.get_decade_stats([_mk(1, [1, 5, 15, 25, 35, 42])])
    by_label = {g["label"]: g for g in result["groups"]}

    g = by_label["01-09"]
    assert g["deviation"] == round(g["avg_count"] - g["expected_avg"], 2)
    assert g["deviation"] == 0.8  # 2.0 - 1.2


def test_decade_stats_most_and_least_frequent_group() -> None:
    """most/least_frequent_group이 avg_count 기준으로 정확히 선택된다."""
    from lotto.web import data as wd

    # 01-09에 2개 집중(최다), 40-45만 0개로 단독 최소(나머지 구간은 모두 1개 이상)
    result = wd.get_decade_stats([_mk(1, [1, 2, 11, 22, 33, 9])])

    # 01-09: 1,2,9 → 3개(최다), 10-19:11, 20-29:22, 30-39:33, 40-45:0(단독 최소)
    assert result["most_frequent_group"] == "01-09"
    assert result["least_frequent_group"] == "40-45"


def test_decade_stats_tie_breaking_most_frequent_first_in_order() -> None:
    """avg_count 동률 시 most_frequent_group은 고정 순서 첫 번째를 택한다."""
    from lotto.web import data as wd

    # 모든 구간 같은 분포가 되도록: 각 구간 한 번씩 등장하면 avg 모두 동률(작음)
    # 01-09와 10-19를 각 3개로 동률 만들기
    result = wd.get_decade_stats([_mk(1, [1, 2, 3, 11, 12, 13])])

    # 01-09(3), 10-19(3) 동률 → most는 "01-09" (먼저)
    assert result["most_frequent_group"] == "01-09"


def test_decade_stats_tie_breaking_least_frequent_first_in_order() -> None:
    """avg_count 동률(최소) 시 least_frequent_group은 고정 순서 첫 번째를 택한다."""
    from lotto.web import data as wd

    # 20-29, 30-39, 40-45가 모두 0 → least는 "20-29" (먼저)
    result = wd.get_decade_stats([_mk(1, [1, 2, 3, 11, 12, 13])])

    assert result["least_frequent_group"] == "20-29"


def test_decade_stats_matches_manual_classification() -> None:
    """여러 회차 집계가 수동 분류 기대값과 일치한다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, [1, 5, 15, 25, 35, 42]),
        _mk(2, [9, 10, 20, 30, 40, 45]),
        _mk(3, [2, 4, 6, 8, 11, 19]),
    ]
    expected_sums = dict.fromkeys(_LABELS, 0)
    for d in draws:
        c = _classify(d.numbers())
        for label in _LABELS:
            expected_sums[label] += c[label]

    result = wd.get_decade_stats(draws)
    by_label = {g["label"]: g for g in result["groups"]}
    for label in _LABELS:
        assert by_label[label]["avg_count"] == round(expected_sums[label] / 3, 2)


# ---------------------------------------------------------------------------
# 캐시
# ---------------------------------------------------------------------------


def test_decade_stats_cache_populated_after_first_call() -> None:
    """첫 호출 후 캐시가 채워진다."""
    from lotto.web import data as wd

    wd.invalidate_cache()
    draws = [_mk(1, [1, 5, 15, 25, 35, 42])]
    wd.get_decade_stats(draws)

    assert str(len(draws)) in wd._decade_cache


def test_decade_stats_cache_hit_returns_same_object() -> None:
    """두 번째 호출은 캐시된 동일 객체를 반환한다."""
    from lotto.web import data as wd

    wd.invalidate_cache()
    draws = [_mk(1, [1, 5, 15, 25, 35, 42])]
    first = wd.get_decade_stats(draws)
    second = wd.get_decade_stats(draws)

    assert first is second


def test_decade_stats_invalidate_clears_cache() -> None:
    """invalidate_cache()는 구간 분포 캐시를 비운다."""
    from lotto.web import data as wd

    wd.get_decade_stats([_mk(1, [1, 5, 15, 25, 35, 42])])
    wd.invalidate_cache()

    assert wd._decade_cache == {}


# ---------------------------------------------------------------------------
# 라우트: 페이지/API
# ---------------------------------------------------------------------------


def test_decade_page_renders(api_client: TestClient) -> None:
    """GET /stats/decade는 200으로 렌더된다."""

    with _patch_draws([_mk(1, [1, 5, 15, 25, 35, 42])]):
        resp = api_client.get("/stats/decade")

    assert resp.status_code == 200
    assert "구간" in resp.text


def test_decade_page_empty_state(api_client: TestClient) -> None:
    """데이터 부재 시에도 페이지는 200."""
    with _patch_draws([]):
        resp = api_client.get("/stats/decade")

    assert resp.status_code == 200


def test_decade_api_returns_json(api_client: TestClient) -> None:
    """GET /api/stats/decade는 구간 분포 JSON을 반환한다."""
    with _patch_draws([_mk(1, [1, 5, 15, 25, 35, 42])]):
        resp = api_client.get("/api/stats/decade")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_draws"] == 1
    assert len(body["groups"]) == 5
    assert body["most_frequent_group"] == "01-09"


def test_decade_api_empty(api_client: TestClient) -> None:
    """데이터 부재 시에도 API는 200으로 정상 응답."""
    with _patch_draws([]):
        resp = api_client.get("/api/stats/decade")

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
