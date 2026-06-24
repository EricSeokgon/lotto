"""SPEC-LOTTO-124 소수 번호 분석 테스트."""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import PRIMES_1_45, get_prime_analysis

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
    # 소수: 2, 3, 5 → 3개
    _mk(1, [2, 3, 5, 8, 10, 12]),
    # 소수: 7, 11, 13, 17 → 4개
    _mk(2, [7, 11, 13, 17, 20, 22]),
    # 소수: 없음 → 0개
    _mk(3, [4, 6, 8, 10, 12, 14]),
]


# ---------------------------------------------------------------------------
# 단위 테스트
# ---------------------------------------------------------------------------

def test_returns_none_when_empty() -> None:
    """데이터 없을 때 None을 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=[]):
        result = get_prime_analysis()
    assert result is None


def test_returns_dict() -> None:
    """정상 데이터일 때 dict를 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_prime_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """필수 키가 모두 존재한다."""
    from lotto.web import data as wd

    required = {
        "total", "prime_count_dist", "best_count", "best_count_pct",
        "prime_rate", "expected_rate", "prime_total", "prime_list",
        "num_primes_in_range",
    }
    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_prime_analysis()
    assert result is not None
    assert required.issubset(result.keys())


def test_num_primes_is_14() -> None:
    """1~45 소수 수는 14개다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_prime_analysis()
    assert result is not None
    assert result["num_primes_in_range"] == 14
    assert len(PRIMES_1_45) == 14


def test_prime_count_dist_keys_0_to_6() -> None:
    """prime_count_dist 키는 0~6이다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_prime_analysis()
    assert result is not None
    assert set(result["prime_count_dist"].keys()) == set(range(7))


def test_prime_count_dist_sum_equals_total() -> None:
    """prime_count_dist 값의 합은 전체 회차 수와 같다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_prime_analysis()
    assert result is not None
    total_from_dist = sum(result["prime_count_dist"].values())
    assert total_from_dist == result["total"]


def test_prime_list_length_is_14() -> None:
    """prime_list 길이는 14 (소수 개수)다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_prime_analysis()
    assert result is not None
    assert len(result["prime_list"]) == 14


def test_prime_rate_range() -> None:
    """prime_rate는 0 이상 100 이하다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_prime_analysis()
    assert result is not None
    assert 0 <= result["prime_rate"] <= 100


def test_expected_rate_approx_31() -> None:
    """expected_rate는 14/45*100 ≈ 31.11이다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_DRAWS):
        result = get_prime_analysis()
    assert result is not None
    assert abs(result["expected_rate"] - 31.11) < 0.1


def test_prime_numbers_page_200() -> None:
    """소수 번호 분석 페이지가 200 OK를 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_prime_analysis", return_value={
        "total": 3,
        "prime_count_dist": {k: 0 for k in range(7)},
        "best_count": 2,
        "best_count_pct": 33.3,
        "prime_rate": 31.11,
        "expected_rate": 31.11,
        "prime_total": 7,
        "prime_list": [],
        "num_primes_in_range": 14,
    }):
        response = client.get("/stats/prime-numbers")
    assert response.status_code == 200
    assert "소수 번호 분석" in response.text
