"""SPEC-LOTTO-037: 고급 필터 추천 API 통합 테스트.

사용자가 조건(합계 범위/홀짝 비율/포함·제외 번호)을 지정하여
조건에 맞는 번호를 추천받는 기능을 검증한다.
- POST /api/recommend/filtered : 조건 기반 번호 추천
- /recommend 페이지의 고급 필터 섹션 존재
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from starlette.testclient import TestClient

from lotto.web.app import app


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """앱 클라이언트 — 모듈 단위로 재사용."""
    with TestClient(app) as c:
        yield c


def _is_valid_combination(combo: list[int]) -> bool:
    """추천 조합이 1~45 범위의 중복 없는 6개 정렬 리스트인지 확인."""
    return (
        len(combo) == 6
        and len(set(combo)) == 6
        and all(1 <= n <= 45 for n in combo)
        and combo == sorted(combo)
    )


# ─── 기본 동작 ───────────────────────────────────────────────────────────────


class TestFilteredBasic:
    def test_empty_body_uses_defaults(self, client: TestClient) -> None:
        res = client.post("/api/recommend/filtered", json={})
        assert res.status_code == 200, res.text
        body = res.json()
        # 기본 count=5
        assert body["count"] == 5
        assert len(body["combinations"]) == 5
        for combo in body["combinations"]:
            assert _is_valid_combination(combo)

    def test_count_controls_number_of_results(self, client: TestClient) -> None:
        res = client.post("/api/recommend/filtered", json={"count": 3})
        assert res.status_code == 200
        body = res.json()
        assert body["count"] == 3
        assert len(body["combinations"]) == 3

    def test_response_keys(self, client: TestClient) -> None:
        res = client.post("/api/recommend/filtered", json={"count": 1})
        body = res.json()
        assert set(body.keys()) >= {"count", "combinations"}


# ─── 합계 범위 조건 ──────────────────────────────────────────────────────────


class TestSumConstraint:
    def test_sum_within_range(self, client: TestClient) -> None:
        res = client.post(
            "/api/recommend/filtered",
            json={"sum_min": 100, "sum_max": 180, "count": 5},
        )
        assert res.status_code == 200, res.text
        for combo in res.json()["combinations"]:
            assert _is_valid_combination(combo)
            assert 100 <= sum(combo) <= 180

    def test_sum_min_greater_than_max_returns_422(self, client: TestClient) -> None:
        res = client.post(
            "/api/recommend/filtered",
            json={"sum_min": 200, "sum_max": 100},
        )
        assert res.status_code == 422, res.text


# ─── 홀수 개수 조건 ──────────────────────────────────────────────────────────


class TestOddConstraint:
    def test_odd_count_within_range(self, client: TestClient) -> None:
        res = client.post(
            "/api/recommend/filtered",
            json={"odd_min": 2, "odd_max": 4, "count": 5},
        )
        assert res.status_code == 200, res.text
        for combo in res.json()["combinations"]:
            odd = sum(1 for n in combo if n % 2 == 1)
            assert 2 <= odd <= 4

    def test_odd_min_greater_than_max_returns_422(self, client: TestClient) -> None:
        res = client.post(
            "/api/recommend/filtered",
            json={"odd_min": 5, "odd_max": 2},
        )
        assert res.status_code == 422


# ─── 포함/제외 번호 조건 ─────────────────────────────────────────────────────


class TestIncludeExclude:
    def test_include_numbers_always_present(self, client: TestClient) -> None:
        res = client.post(
            "/api/recommend/filtered",
            json={"include_numbers": [7, 14], "count": 5},
        )
        assert res.status_code == 200, res.text
        for combo in res.json()["combinations"]:
            assert 7 in combo
            assert 14 in combo

    def test_exclude_numbers_never_present(self, client: TestClient) -> None:
        res = client.post(
            "/api/recommend/filtered",
            json={"exclude_numbers": [1, 2, 3], "count": 5},
        )
        assert res.status_code == 200
        for combo in res.json()["combinations"]:
            assert not ({1, 2, 3} & set(combo))

    def test_include_and_exclude_combined(self, client: TestClient) -> None:
        res = client.post(
            "/api/recommend/filtered",
            json={"include_numbers": [7, 14], "exclude_numbers": [1, 2, 3], "count": 3},
        )
        assert res.status_code == 200, res.text
        for combo in res.json()["combinations"]:
            assert {7, 14} <= set(combo)
            assert not ({1, 2, 3} & set(combo))

    def test_include_exclude_overlap_returns_422(self, client: TestClient) -> None:
        res = client.post(
            "/api/recommend/filtered",
            json={"include_numbers": [7, 14], "exclude_numbers": [7, 20]},
        )
        assert res.status_code == 422, res.text

    def test_include_more_than_six_returns_422(self, client: TestClient) -> None:
        res = client.post(
            "/api/recommend/filtered",
            json={"include_numbers": [1, 4, 6, 8, 10, 12, 14]},
        )
        assert res.status_code == 422


# ─── count 범위 검증 ─────────────────────────────────────────────────────────


class TestCountValidation:
    def test_count_zero_returns_422(self, client: TestClient) -> None:
        res = client.post("/api/recommend/filtered", json={"count": 0})
        assert res.status_code == 422

    def test_count_over_twenty_returns_422(self, client: TestClient) -> None:
        res = client.post("/api/recommend/filtered", json={"count": 21})
        assert res.status_code == 422

    def test_count_twenty_ok(self, client: TestClient) -> None:
        res = client.post("/api/recommend/filtered", json={"count": 20})
        assert res.status_code == 200
        assert res.json()["count"] == 20


# ─── 충족 불가능 조건 → 빈 리스트 (예외 아님) ────────────────────────────────


class TestUnsatisfiable:
    def test_impossible_sum_returns_empty(self, client: TestClient) -> None:
        # 6개 최소 합은 1+2+3+4+5+6=21. 합 0~5는 불가능.
        res = client.post(
            "/api/recommend/filtered",
            json={"sum_min": 0, "sum_max": 5, "count": 5},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        # 조건을 만족하는 조합을 못 찾으면 빈 리스트
        assert body["combinations"] == []


# ─── 번호 범위 유효성 ───────────────────────────────────────────────────────


class TestNumberRangeValidation:
    def test_include_number_out_of_range_returns_422(self, client: TestClient) -> None:
        res = client.post(
            "/api/recommend/filtered",
            json={"include_numbers": [0, 7]},
        )
        assert res.status_code == 422

    def test_exclude_number_out_of_range_returns_422(self, client: TestClient) -> None:
        res = client.post(
            "/api/recommend/filtered",
            json={"exclude_numbers": [46]},
        )
        assert res.status_code == 422


# ─── /recommend 페이지 고급 필터 섹션 (REQ-FILTER-002) ───────────────────────


class TestFilterSectionOnPage:
    def test_recommend_page_contains_filter_section(self, client: TestClient) -> None:
        res = client.get("/recommend")
        assert res.status_code == 200
        text = res.text
        assert "고급 필터" in text
        assert "/api/recommend/filtered" in text

    def test_recommend_page_has_filter_inputs(self, client: TestClient) -> None:
        res = client.get("/recommend")
        text = res.text
        # 합계/홀수/포함/제외 관련 라벨 또는 마커
        assert "합계" in text
        assert "홀수" in text
