"""SPEC-LOTTO-122 번호 끝자리(일의 자리) 분석 테스트."""

from __future__ import annotations

import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_tail_digit_analysis

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
    _mk(1, [1, 2, 3, 4, 5, 6]),    # 끝자리: 1,2,3,4,5,6 → 6종
    _mk(2, [10, 20, 30, 40, 11, 21]),  # 끝자리: 0,0,0,0,1,1 → 2종
    _mk(3, [7, 17, 27, 37, 8, 18]),  # 끝자리: 7,7,7,7,8,8 → 2종
]


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------


def test_get_tail_digit_returns_none_when_empty() -> None:
    """빈 데이터면 None을 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=[]):
        result = get_tail_digit_analysis()
    assert result is None


def test_get_tail_digit_returns_dict() -> None:
    """데이터가 있으면 dict를 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_tail_digit_analysis()
    assert isinstance(result, dict)


def test_get_tail_digit_has_required_keys() -> None:
    """필수 키가 모두 존재한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_tail_digit_analysis()
    assert result is not None
    required = {"total", "total_numbers", "tail_data", "best_tail",
                "best_tail_pct", "cover_dist", "best_cover", "best_cover_pct"}
    assert required.issubset(result.keys())


def test_tail_data_length() -> None:
    """tail_data는 끝자리 0~9에 해당하는 10개 항목이다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_tail_digit_analysis()
    assert result is not None
    assert len(result["tail_data"]) == 10


def test_tail_data_sum_equals_total_numbers() -> None:
    """tail_data count 합계 == total * 6."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_tail_digit_analysis()
    assert result is not None
    total_count = sum(item["count"] for item in result["tail_data"])
    assert total_count == result["total_numbers"]
    assert result["total_numbers"] == result["total"] * 6


def test_cover_dist_keys() -> None:
    """cover_dist 키는 1~6이다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_tail_digit_analysis()
    assert result is not None
    assert set(result["cover_dist"].keys()) == {1, 2, 3, 4, 5, 6}


def test_cover_dist_sum_equals_total() -> None:
    """cover_dist 값의 합 == 전체 회차 수."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_tail_digit_analysis()
    assert result is not None
    assert sum(result["cover_dist"].values()) == result["total"]


def test_best_tail_pct_range() -> None:
    """best_tail_pct는 0 이상 100 이하이다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_tail_digit_analysis()
    assert result is not None
    assert 0 <= result["best_tail_pct"] <= 100


# ---------------------------------------------------------------------------
# 라우터 테스트
# ---------------------------------------------------------------------------


def test_tail_digits_page_200() -> None:
    """데이터가 있으면 200을 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        resp = client.get("/stats/tail-digits")
    assert resp.status_code == 200
    assert "끝자리" in resp.text


def test_tail_digits_page_no_data() -> None:
    """데이터가 없어도 200을 반환하고 경고 메시지를 표시한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=[]):
        resp = client.get("/stats/tail-digits")
    assert resp.status_code == 200
    assert "데이터가 없습니다" in resp.text
