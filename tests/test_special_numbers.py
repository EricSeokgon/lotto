"""SPEC-LOTTO-135: 특수 번호(삼각수·제곱수) 분석 테스트."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.data import get_special_numbers_analysis


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
    """손계산 픽스처.

    회차1: 1(삼각·제곱),3(삼각),4(제곱),9(제곱),10(삼각),11
    회차2: 2,5,7,8,12,13 → 삼각수 0, 제곱수 0
    """
    return [
        make_draw(1, 1, 3, 4, 9, 10, 11),
        make_draw(2, 2, 5, 7, 8, 12, 13),
    ]


def test_returns_none_when_empty() -> None:
    """빈 리스트 입력 시 None 반환."""
    with patch("lotto.web.data.get_draws", return_value=[]):
        result = get_special_numbers_analysis()
    assert result is None


def test_returns_dict() -> None:
    """데이터 있으면 dict 반환."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_special_numbers_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """필수 키 모두 포함."""
    required = {
        "total", "tri_count", "sq_count", "both_count",
        "avg_tri", "avg_sq", "expected_tri", "expected_sq",
        "best_tri", "best_sq", "tri_dist_list", "sq_dist_list",
        "tri_freq_list", "sq_freq_list", "recent",
    }
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_special_numbers_analysis()
    assert result is not None
    assert required.issubset(result.keys())


def test_tri_count_is_9() -> None:
    """삼각수 집합 크기 = 9 (1,3,6,10,15,21,28,36,45)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_special_numbers_analysis()
    assert result is not None
    assert result["tri_count"] == 9


def test_sq_count_is_6() -> None:
    """제곱수 집합 크기 = 6 (1,4,9,16,25,36)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_special_numbers_analysis()
    assert result is not None
    assert result["sq_count"] == 6


def test_both_count_is_2() -> None:
    """교집합 크기 = 2 ({1, 36})."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_special_numbers_analysis()
    assert result is not None
    assert result["both_count"] == 2


def test_tri_dist_list_length_is_7() -> None:
    """삼각수 분포 리스트 길이 = 7 (0~6개)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_special_numbers_analysis()
    assert result is not None
    assert len(result["tri_dist_list"]) == 7


def test_sq_dist_list_length_is_7() -> None:
    """제곱수 분포 리스트 길이 = 7 (0~6개)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_special_numbers_analysis()
    assert result is not None
    assert len(result["sq_dist_list"]) == 7


def test_recent_length_lte_20() -> None:
    """최근 회차 목록은 최대 20개."""
    draws = [make_draw(i, 1, 2, 3, 4, 5, 6) for i in range(1, 30)]
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_special_numbers_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_special_numbers_page_200() -> None:
    """HTTP GET /stats/special-numbers → 200 OK."""
    from lotto.web.app import app

    client = TestClient(app)
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        response = client.get("/stats/special-numbers")
    assert response.status_code == 200
