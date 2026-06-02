"""SPEC-LOTTO-049: 합계 범위 분석 — sum_range_analysis() / evaluate_sum() 단위 테스트.

각 회차 본번호 6개 합계의 분포(12개 폭 20 버킷)를 산출하고, 평균/최소/최대,
최빈 구간, 공통 영역(p10~p90)을 검증한다. evaluate_sum()은 임의 조합의 합계가
공통 영역에 드는지와 백분위를 반환한다.
"""

from __future__ import annotations

from datetime import date

from lotto.models import DrawResult
from lotto.web.data import evaluate_sum, sum_range_analysis

_TOP_KEYS = {
    "total_draws",
    "avg_sum",
    "min_sum",
    "max_sum",
    "most_common_range",
    "distribution",
    "common_zone",
}
_DIST_KEYS = {"range", "low", "high", "count", "ratio"}
# 12개 버킷 라벨 (오름차순 — 마지막은 폭 15)
_EXPECTED_LABELS = [
    "21-40", "41-60", "61-80", "81-100", "101-120", "121-140",
    "141-160", "161-180", "181-200", "201-220", "221-240", "241-255",
]


def _mk(no: int, nums: list[int]) -> DrawResult:
    """DrawResult 생성 헬퍼 (보너스는 합계와 무관하므로 고정)."""
    return DrawResult(
        drwNo=no, date=date(2020, 1, 1),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=10,
    )


def _fixture_draws() -> list[DrawResult]:
    """6회차 픽스처. 합계: 30, 75, 100, 138, 138, 138.

    버킷 배치:
        30  → 21-40
        75  → 61-80
        100 → 81-100
        138 x3 → 121-140  (최빈 구간)

    정렬된 합계 [30, 75, 100, 138, 138, 138]
        avg = 619/6 = 103.17, min = 30, max = 138
        p10(nearest-rank) = 30, p90 = 138
    """
    return [
        _mk(1, [1, 2, 3, 4, 5, 15]),       # 30
        _mk(2, [1, 2, 3, 4, 20, 45]),      # 75
        _mk(3, [1, 2, 3, 5, 44, 45]),      # 100
        _mk(4, [1, 2, 3, 43, 44, 45]),     # 138
        _mk(5, [2, 3, 4, 42, 43, 44]),     # 138
        _mk(6, [3, 4, 5, 41, 42, 43]),     # 138
    ]


# ---------------------------------------------------------------------------
# sum_range_analysis — 통계
# ---------------------------------------------------------------------------
def test_avg_min_max_correct() -> None:
    """avg_sum(2자리)/min_sum/max_sum 가 픽스처와 일치한다."""
    result = sum_range_analysis(_fixture_draws())
    assert result["total_draws"] == 6
    assert result["avg_sum"] == 103.17
    assert result["min_sum"] == 30
    assert result["max_sum"] == 138


def test_distribution_has_12_buckets_ascending() -> None:
    """distribution 은 항상 12개 버킷을 오름차순으로 나열한다 (count 0 포함)."""
    result = sum_range_analysis(_fixture_draws())
    dist = result["distribution"]
    assert len(dist) == 12
    assert [b["range"] for b in dist] == _EXPECTED_LABELS
    for b in dist:
        assert set(b.keys()) == _DIST_KEYS


def test_bucket_counts_and_ratio_correct() -> None:
    """버킷별 count 와 ratio(4자리)가 정확하다."""
    result = sum_range_analysis(_fixture_draws())
    by_range = {b["range"]: b for b in result["distribution"]}
    assert by_range["21-40"]["count"] == 1
    assert by_range["61-80"]["count"] == 1
    assert by_range["81-100"]["count"] == 1
    assert by_range["121-140"]["count"] == 3
    assert by_range["241-255"]["count"] == 0
    # ratio = count / total_draws (4자리)
    assert by_range["121-140"]["ratio"] == round(3 / 6, 4)
    assert by_range["21-40"]["ratio"] == round(1 / 6, 4)
    # low/high 경계
    assert by_range["241-255"]["low"] == 241
    assert by_range["241-255"]["high"] == 255


def test_most_common_range_correct() -> None:
    """최빈 구간은 count 최대 라벨이다."""
    result = sum_range_analysis(_fixture_draws())
    assert result["most_common_range"] == "121-140"


def test_most_common_range_tie_prefers_lower() -> None:
    """동률이면 더 낮은 구간을 택한다."""
    # 합계 30 (21-40) 한 개, 75 (61-80) 한 개 → 동률 1:1 → 21-40 선택
    draws = [
        _mk(1, [1, 2, 3, 4, 5, 15]),    # 30  → 21-40
        _mk(2, [1, 2, 3, 4, 20, 45]),   # 75  → 61-80
    ]
    result = sum_range_analysis(draws)
    assert result["most_common_range"] == "21-40"


def test_common_zone_p10_p90() -> None:
    """common_zone 은 관측 합계의 [p10, p90] (nearest-rank, 정수)이다."""
    result = sum_range_analysis(_fixture_draws())
    assert result["common_zone"] == {"low": 30, "high": 138}


def test_empty_draws_zero_structure() -> None:
    """빈 리스트 → total_draws=0, 0 통계, null 최빈, 12개 버킷 count 0, zone {0,0}."""
    result = sum_range_analysis([])
    assert set(result.keys()) == _TOP_KEYS
    assert result["total_draws"] == 0
    assert result["avg_sum"] == 0.0
    assert result["min_sum"] == 0
    assert result["max_sum"] == 0
    assert result["most_common_range"] is None
    assert len(result["distribution"]) == 12
    assert [b["range"] for b in result["distribution"]] == _EXPECTED_LABELS
    assert all(b["count"] == 0 for b in result["distribution"])
    assert all(b["ratio"] == 0.0 for b in result["distribution"])
    assert result["common_zone"] == {"low": 0, "high": 0}


def test_none_draws_zero_structure() -> None:
    """명시적 None → 빈 구조 (get_draws 호출 없이 데이터 없음 처리)."""
    result = sum_range_analysis(None)
    assert result["total_draws"] == 0
    assert result["most_common_range"] is None
    assert result["common_zone"] == {"low": 0, "high": 0}


def test_deterministic() -> None:
    """같은 입력에 대해 결과가 결정적이다."""
    draws = _fixture_draws()
    assert sum_range_analysis(draws) == sum_range_analysis(draws)


# ---------------------------------------------------------------------------
# evaluate_sum — 조합 체커
# ---------------------------------------------------------------------------
def test_evaluate_sum_inside_zone() -> None:
    """공통 영역 내부 합계 → in_common_zone=True, 백분위 반환."""
    # 합계 100 → zone [30,138] 내부, 100 이하 회차 3/6 = 0.5
    result = evaluate_sum([1, 2, 3, 5, 44, 45], _fixture_draws())
    assert result["sum"] == 100
    assert result["in_common_zone"] is True
    assert result["common_zone"] == {"low": 30, "high": 138}
    assert result["percentile"] == round(3 / 6, 4)


def test_evaluate_sum_outside_zone() -> None:
    """공통 영역 밖 합계 → in_common_zone=False."""
    # 합계 21 (1+2+3+4+5+6) < zone.low(30) → 외부, 21 이하 회차 0/6
    result = evaluate_sum([1, 2, 3, 4, 5, 6], _fixture_draws())
    assert result["sum"] == 21
    assert result["in_common_zone"] is False
    assert result["percentile"] == 0.0


def test_evaluate_sum_no_draws() -> None:
    """데이터 부재 시 percentile=0.0, zone {0,0}, 합계만 계산."""
    result = evaluate_sum([1, 2, 3, 4, 5, 6], [])
    assert result["sum"] == 21
    assert result["in_common_zone"] is False
    assert result["common_zone"] == {"low": 0, "high": 0}
    assert result["percentile"] == 0.0
