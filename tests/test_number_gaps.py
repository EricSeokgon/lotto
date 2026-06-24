"""SPEC-LOTTO-123 번호 간격(Gap) 분석 테스트."""

from __future__ import annotations

import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_number_gap_analysis

client = TestClient(app)


def _mk(no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """DrawResult 헬퍼."""
    return DrawResult(
        drwNo=no,
        date=datetime.date(2020, 1, 1) + datetime.timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2],
        n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# ---------------------------------------------------------------------------
# 샘플 데이터
# ---------------------------------------------------------------------------

_DRAWS = [
    # gaps: [1,1,1,1,1] → min=1, max=1, consec=5, avg=(6-1)/5=1.0
    _mk(1, [1, 2, 3, 4, 5, 6]),
    # gaps: [9,10,10,10,10] → min=9, max=10, consec=0, avg=(40-1)/5=7.8
    _mk(2, [1, 10, 20, 30, 40, 41]),   # 재정렬 후: [1,10,20,30,40,41], gaps=[9,10,10,10,1]
    # gaps: [4,4,4,4,4] → min=4, max=4, consec=0, avg=(21-1)/5=4.0
    _mk(3, [1, 5, 9, 13, 17, 21]),
]


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------


def test_get_number_gap_returns_none_when_empty() -> None:
    """빈 데이터면 None을 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=[]):
        result = get_number_gap_analysis()
    assert result is None


def test_get_number_gap_returns_dict() -> None:
    """데이터가 있으면 dict를 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_number_gap_analysis()
    assert isinstance(result, dict)


def test_get_number_gap_has_required_keys() -> None:
    """반환 dict에 필수 키가 모두 있다."""
    from lotto.web import data as wd

    required = {
        "total", "avg_gap", "best_min_gap", "best_min_gap_pct",
        "best_max_gap", "best_max_gap_pct", "best_consec", "best_consec_pct",
        "min_gap_list", "max_gap_list", "consec_dist",
    }
    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_number_gap_analysis()
    assert result is not None
    assert required.issubset(result.keys())


def test_avg_gap_range() -> None:
    """평균 간격은 0 초과 8.8 미만이어야 한다 (1~45 범위 제약)."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_number_gap_analysis()
    assert result is not None
    assert 0 < result["avg_gap"] < 8.8


def test_consec_dist_keys() -> None:
    """consec_dist 키는 0~5 정수여야 한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_number_gap_analysis()
    assert result is not None
    assert set(result["consec_dist"].keys()) == set(range(6))


def test_consec_dist_sum_equals_total() -> None:
    """consec_dist 값의 합은 전체 회차 수와 같아야 한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_number_gap_analysis()
    assert result is not None
    assert sum(result["consec_dist"].values()) == result["total"]


def test_min_gap_list_is_sorted() -> None:
    """min_gap_list는 gap 오름차순으로 정렬되어 있어야 한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_number_gap_analysis()
    assert result is not None
    gaps = [item["gap"] for item in result["min_gap_list"]]
    assert gaps == sorted(gaps)


def test_min_gap_list_sum_equals_total() -> None:
    """min_gap_list count 합은 전체 회차 수와 같아야 한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_number_gap_analysis()
    assert result is not None
    total_count = sum(item["count"] for item in result["min_gap_list"])
    assert total_count == result["total"]


def test_number_gaps_page_200() -> None:
    """번호 간격 분석 페이지가 200 OK를 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        response = client.get("/stats/number-gaps")
    assert response.status_code == 200
    assert "번호 간격" in response.text


def test_number_gaps_page_no_data() -> None:
    """데이터 없을 때 경고 메시지를 표시한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=[]):
        response = client.get("/stats/number-gaps")
    assert response.status_code == 200
    assert "데이터가 없습니다" in response.text
