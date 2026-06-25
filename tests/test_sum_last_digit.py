"""SPEC-LOTTO-131: 번호 합계 끝자리 분석 테스트."""

from __future__ import annotations

import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd


def _make_draw(drw_no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """6개 본번호로 DrawResult를 만든다."""
    n1, n2, n3, n4, n5, n6 = nums
    return DrawResult(
        drwNo=drw_no,
        date=datetime.date(2002, 12, 7) + datetime.timedelta(days=7 * drw_no),
        n1=n1, n2=n2, n3=n3, n4=n4, n5=n5, n6=n6, bonus=bonus,
    )


def _fixture_draws() -> list[DrawResult]:
    """테스트용 픽스처.

    D1 [1,2,3,4,5,6]        sum=21  last_digit=1
    D2 [40,41,42,43,44,45]  sum=255 last_digit=5
    D3 [10,20,30,1,2,3]     sum=66  last_digit=6
    """
    return [
        _make_draw(1, [1, 2, 3, 4, 5, 6]),
        _make_draw(2, [40, 41, 42, 43, 44, 45]),
        _make_draw(3, [10, 20, 30, 1, 2, 3]),
    ]


def test_returns_none_when_empty() -> None:
    """데이터가 없으면 None 반환."""
    with patch.object(wd, "get_draws", return_value=[]):
        result = wd.get_sum_last_digit_analysis()
    assert result is None


def test_returns_dict() -> None:
    """정상 데이터 → dict 반환."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_sum_last_digit_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """필수 키 포함 여부 확인."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_sum_last_digit_analysis()
    assert result is not None
    for key in ("total", "avg_sum", "best_digit", "worst_digit",
                "odd_count", "even_count", "digit_list", "recent"):
        assert key in result, f"필수 키 누락: {key}"


def test_digit_list_length_is_10() -> None:
    """digit_list는 정확히 10개 항목(0~9)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_sum_last_digit_analysis()
    assert result is not None
    assert len(result["digit_list"]) == 10


def test_digit_list_sum_equals_total() -> None:
    """digit_list count 합계 == total."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_sum_last_digit_analysis()
    assert result is not None
    count_sum = sum(item["count"] for item in result["digit_list"])
    assert count_sum == result["total"]


def test_odd_plus_even_equals_total() -> None:
    """odd_count + even_count == total."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_sum_last_digit_analysis()
    assert result is not None
    assert result["odd_count"] + result["even_count"] == result["total"]


def test_best_digit_in_range() -> None:
    """best_digit은 0~9 범위."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_sum_last_digit_analysis()
    assert result is not None
    assert 0 <= result["best_digit"] <= 9


def test_avg_sum_in_range() -> None:
    """avg_sum은 21~255 범위(로또 6/45 합계 범위)."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_sum_last_digit_analysis()
    assert result is not None
    assert 21 <= result["avg_sum"] <= 255


def test_recent_length_lte_20() -> None:
    """recent 항목 수 <= 20."""
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        result = wd.get_sum_last_digit_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_sum_last_digit_page_200() -> None:
    """GET /stats/sum-last-digit → HTTP 200."""
    from lotto.web.app import app
    client = TestClient(app)
    with patch.object(wd, "get_draws", return_value=_fixture_draws()):
        resp = client.get("/stats/sum-last-digit")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
