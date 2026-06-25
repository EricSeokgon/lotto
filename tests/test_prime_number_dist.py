"""SPEC-LOTTO-139: 번호 소수(Prime Number) 분포 분석 테스트."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_prime_number_dist_analysis


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
    """테스트용 픽스처 — 소수 다양성을 위한 번호 조합."""
    return [
        make_draw(1, 2, 3, 5, 8, 10, 12),    # 소수: 2,3,5 → 3개
        make_draw(2, 7, 11, 13, 17, 20, 22),  # 소수: 7,11,13,17 → 4개
        make_draw(3, 4, 6, 8, 10, 12, 14),    # 소수: 없음 → 0개
        make_draw(4, 2, 7, 9, 15, 23, 29),    # 소수: 2,7,23,29 → 4개
        make_draw(5, 3, 5, 11, 16, 30, 41),   # 소수: 3,5,11,41 → 4개
    ]


def test_returns_none_when_empty() -> None:
    """빈 목록 입력 시 None 반환."""
    with patch("lotto.web.data.get_draws", return_value=[]):
        result = get_prime_number_dist_analysis()
    assert result is None


def test_returns_dict() -> None:
    """정상 데이터 시 dict 반환."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_prime_number_dist_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """반환 dict에 필수 키 존재."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_prime_number_dist_analysis()
    assert result is not None
    required = {
        "total", "prime_count", "avg_primes", "expected", "diff",
        "best_count", "dist_list", "freq_list", "recent",
    }
    for key in required:
        assert key in result, f"키 '{key}' 없음"


def test_prime_count_is_14() -> None:
    """소수 개수는 14개 (1~45 범위)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_prime_number_dist_analysis()
    assert result is not None
    assert result["prime_count"] == 14


def test_dist_list_length_is_7() -> None:
    """dist_list 길이 == 7 (count 0~6)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_prime_number_dist_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 7


def test_freq_list_length_is_14() -> None:
    """freq_list 길이 == 14 (소수 개수)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_prime_number_dist_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 14


def test_diff_equals_avg_minus_expected() -> None:
    """diff == avg_primes - expected (소수점 3자리)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_prime_number_dist_analysis()
    assert result is not None
    assert round(result["avg_primes"] - result["expected"], 3) == result["diff"]


def test_prime_numbers_in_freq_list() -> None:
    """freq_list 내 번호는 모두 실제 소수여야 함."""
    primes = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43}
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_prime_number_dist_analysis()
    assert result is not None
    for item in result["freq_list"]:
        assert item["number"] in primes, f"{item['number']}은 소수가 아님"


def test_recent_length_lte_20() -> None:
    """recent 리스트 길이 <= 20."""
    draws = [make_draw(i, 1, 2, 3, 4, 5, 6) for i in range(1, 26)]
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_prime_number_dist_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_prime_number_dist_page_200() -> None:
    """GET /stats/prime-number-dist → HTTP 200."""
    client = TestClient(app)
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        response = client.get("/stats/prime-number-dist")
    assert response.status_code == 200
