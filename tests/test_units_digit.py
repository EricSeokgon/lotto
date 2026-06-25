"""SPEC-LOTTO-137: 번호 끝자리(일의 자리) 분포 분석 테스트."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_units_digit_analysis


def make_draw(
    draw_no: int,
    n1: int,
    n2: int,
    n3: int,
    n4: int,
    n5: int,
    n6: int,
    bonus: int = 45,
) -> DrawResult:
    """테스트용 DrawResult 생성 헬퍼."""
    return DrawResult(
        drwNo=draw_no,
        date=date(2020, 1, 1),
        n1=n1,
        n2=n2,
        n3=n3,
        n4=n4,
        n5=n5,
        n6=n6,
        bonus=bonus,
    )


def sample_draws() -> list[DrawResult]:
    """테스트용 픽스처 — 끝자리 다양성을 위한 번호 조합."""
    return [
        make_draw(1, 1, 12, 23, 34, 5, 16),
        make_draw(2, 7, 18, 29, 30, 41, 2),
        make_draw(3, 3, 14, 25, 36, 7, 18),
        make_draw(4, 9, 20, 31, 42, 3, 14),
        make_draw(5, 5, 16, 27, 38, 9, 20),
    ]


def test_returns_none_when_empty() -> None:
    """빈 목록 입력 시 None 반환."""
    with patch("lotto.web.data.get_draws", return_value=[]):
        result = get_units_digit_analysis()
    assert result is None


def test_returns_dict() -> None:
    """정상 데이터 시 dict 반환."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_units_digit_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """반환 dict에 필수 키 존재."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_units_digit_analysis()
    assert result is not None
    required = {"total", "digit_stats", "most_digit", "least_digit", "most_digit_total", "least_digit_total", "recent"}
    for key in required:
        assert key in result, f"키 '{key}' 없음"


def test_digit_stats_length_is_10() -> None:
    """digit_stats 리스트 길이 == 10 (끝자리 0~9)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_units_digit_analysis()
    assert result is not None
    assert len(result["digit_stats"]) == 10


def test_digit_stat_keys() -> None:
    """각 digit_stat 항목에 필수 키 존재."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_units_digit_analysis()
    assert result is not None
    required = {"digit", "pool_size", "pool_nums", "total_appearances", "avg", "expected", "diff", "best_count", "dist_list"}
    for s in result["digit_stats"]:
        for key in required:
            assert key in s, f"키 '{key}' 없음: {s}"


def test_pool_size_sum_is_45() -> None:
    """모든 끝자리의 pool_size 합 == 45."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_units_digit_analysis()
    assert result is not None
    total_pool = sum(s["pool_size"] for s in result["digit_stats"])
    assert total_pool == 45


def test_dist_list_length_is_7() -> None:
    """각 끝자리의 dist_list 길이 == 7 (count 0~6)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_units_digit_analysis()
    assert result is not None
    for s in result["digit_stats"]:
        assert len(s["dist_list"]) == 7, f"끝자리 {s['digit']} dist_list 길이 오류"


def test_diff_calculation() -> None:
    """diff == round(avg - expected, 3)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_units_digit_analysis()
    assert result is not None
    for s in result["digit_stats"]:
        expected_diff = round(s["avg"] - s["expected"], 3)
        assert s["diff"] == expected_diff, f"끝자리 {s['digit']} diff 계산 오류"


def test_recent_length_lte_20() -> None:
    """recent 리스트 길이 <= 20."""
    draws = [make_draw(i, 1, 2, 3, 4, 5, 6) for i in range(1, 26)]
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_units_digit_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_units_digit_page_200() -> None:
    """GET /stats/units-digit → HTTP 200."""
    client = TestClient(app)
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        response = client.get("/stats/units-digit")
    assert response.status_code == 200
