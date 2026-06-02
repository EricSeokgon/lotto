"""SPEC-LOTTO-049: GET /api/stats/sum-range + /evaluate API 통합 테스트.

분석 엔드포인트는 항상 200, evaluate 는 6개 서로 다른 1~45 번호를 검증(위반 시 422)한다.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult

_TOP_KEYS = {
    "total_draws",
    "avg_sum",
    "min_sum",
    "max_sum",
    "most_common_range",
    "distribution",
    "common_zone",
}
_EVAL_KEYS = {"sum", "in_common_zone", "common_zone", "percentile"}


def _mk(no: int, nums: list[int]) -> DrawResult:
    return DrawResult(
        drwNo=no, date=date(2020, 1, 1),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=10,
    )


def _draws() -> list[DrawResult]:
    return [
        _mk(1, [1, 2, 3, 4, 5, 15]),       # 30
        _mk(2, [1, 2, 3, 4, 20, 45]),      # 75
        _mk(3, [1, 2, 3, 43, 44, 45]),     # 138
    ]


@pytest.fixture
def api_client() -> TestClient:
    from lotto.web.app import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /api/stats/sum-range — 항상 200
# ---------------------------------------------------------------------------
def test_sum_range_returns_200_and_keys(api_client: TestClient) -> None:
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_draws()):
        response = api_client.get("/api/stats/sum-range")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == _TOP_KEYS
    assert body["total_draws"] == 3
    assert len(body["distribution"]) == 12


def test_sum_range_no_data_returns_200(api_client: TestClient) -> None:
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=None):
        response = api_client.get("/api/stats/sum-range")
    assert response.status_code == 200
    body = response.json()
    assert body["total_draws"] == 0
    assert body["most_common_range"] is None


# ---------------------------------------------------------------------------
# GET /api/stats/sum-range/evaluate
# ---------------------------------------------------------------------------
def test_evaluate_valid_returns_200(api_client: TestClient) -> None:
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=_draws()):
        response = api_client.get(
            "/api/stats/sum-range/evaluate?n=1&n=2&n=3&n=4&n=5&n=15"
        )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == _EVAL_KEYS
    assert body["sum"] == 30


def test_evaluate_too_few_numbers_returns_422(api_client: TestClient) -> None:
    response = api_client.get("/api/stats/sum-range/evaluate?n=1&n=2&n=3")
    assert response.status_code == 422


def test_evaluate_out_of_range_returns_422(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/stats/sum-range/evaluate?n=1&n=2&n=3&n=4&n=5&n=46"
    )
    assert response.status_code == 422


def test_evaluate_duplicate_returns_422(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/stats/sum-range/evaluate?n=1&n=2&n=3&n=4&n=5&n=5"
    )
    assert response.status_code == 422
