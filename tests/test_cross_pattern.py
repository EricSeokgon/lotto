"""SPEC-LOTTO-106: 홀짝·고저 조합 매트릭스 분석 테스트.

손계산 가능한 소규모 DrawResult 픽스처(3회차)로 (odd_count, high_count) 교차
빈도 매트릭스, 상위 조합 정렬, 주변합, 평균, 빈 입력 가드 및 API/페이지를 검증한다.

Fixture A (acceptance.md):
| 회차 | 본번호 | odd_count | high_count |
|------|--------|-----------|------------|
| 1 | 1, 3, 5, 7, 9, 11 | 6 | 0 |
| 2 | 2, 24, 25, 26, 28, 30 | 1 | 5 |
| 3 | 1, 3, 24, 26, 28, 30 | 2 | 4 |
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.data import get_cross_pattern_stats


def make_draw(
    draw_no: int,
    n1: int,
    n2: int,
    n3: int,
    n4: int,
    n5: int,
    n6: int,
    bonus: int,
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


def fixture_a() -> list[DrawResult]:
    """acceptance.md Fixture A — 3회차 손계산 픽스처."""
    return [
        make_draw(1, 1, 3, 5, 7, 9, 11, 13),
        make_draw(2, 2, 24, 25, 26, 28, 30, 13),
        make_draw(3, 1, 3, 24, 26, 28, 30, 13),
    ]


# ---------------------------------------------------------------------------
# 핵심 계산 (data layer)
# ---------------------------------------------------------------------------


def test_total_draws() -> None:
    """AC-CROSS-001: total_draws == 3."""
    result = get_cross_pattern_stats(fixture_a())
    assert result["total_draws"] == 3


def test_top_level_keys() -> None:
    """AC-CROSS-002: 반환 dict가 모든 핵심 키를 포함한다."""
    result = get_cross_pattern_stats(fixture_a())
    assert set(result.keys()) >= {
        "total_draws",
        "top_n",
        "matrix",
        "top_combinations",
        "marginal_odd",
        "marginal_high",
        "avg_odd",
        "avg_high",
        "disclaimer",
    }


def test_matrix_has_49_keys() -> None:
    """AC-CROSS-003: matrix는 정확히 49개 키, 각 키는 odd_{i}_high_{j} 형식."""
    result = get_cross_pattern_stats(fixture_a())
    matrix = result["matrix"]
    assert len(matrix) == 49
    expected = {f"odd_{i}_high_{j}" for i in range(7) for j in range(7)}
    assert set(matrix.keys()) == expected


def test_matrix_odd6_high0() -> None:
    """AC-CROSS-004: matrix['odd_6_high_0'] == 1."""
    result = get_cross_pattern_stats(fixture_a())
    assert result["matrix"]["odd_6_high_0"] == 1


def test_matrix_odd1_high5() -> None:
    """AC-CROSS-005: matrix['odd_1_high_5'] == 1."""
    result = get_cross_pattern_stats(fixture_a())
    assert result["matrix"]["odd_1_high_5"] == 1


def test_matrix_odd2_high4() -> None:
    """AC-CROSS-006: matrix['odd_2_high_4'] == 1."""
    result = get_cross_pattern_stats(fixture_a())
    assert result["matrix"]["odd_2_high_4"] == 1


def test_matrix_others_zero() -> None:
    """AC-CROSS-007: 3개 키 외 나머지 46개 합은 0."""
    result = get_cross_pattern_stats(fixture_a())
    matrix = result["matrix"]
    nonzero_keys = {"odd_6_high_0", "odd_1_high_5", "odd_2_high_4"}
    others_sum = sum(v for k, v in matrix.items() if k not in nonzero_keys)
    assert others_sum == 0


def test_marginal_odd() -> None:
    """AC-CROSS-008: marginal_odd 손계산값."""
    result = get_cross_pattern_stats(fixture_a())
    assert result["marginal_odd"] == {
        "0": 0,
        "1": 1,
        "2": 1,
        "3": 0,
        "4": 0,
        "5": 0,
        "6": 1,
    }


def test_marginal_high() -> None:
    """AC-CROSS-009: marginal_high 손계산값."""
    result = get_cross_pattern_stats(fixture_a())
    assert result["marginal_high"] == {
        "0": 1,
        "1": 0,
        "2": 0,
        "3": 0,
        "4": 1,
        "5": 1,
        "6": 0,
    }


def test_avg_odd() -> None:
    """AC-CROSS-010: avg_odd == 3.0."""
    result = get_cross_pattern_stats(fixture_a())
    assert result["avg_odd"] == 3.0


def test_avg_high() -> None:
    """AC-CROSS-011: avg_high == 3.0."""
    result = get_cross_pattern_stats(fixture_a())
    assert result["avg_high"] == 3.0


# ---------------------------------------------------------------------------
# top_combinations 정렬 / 형식
# ---------------------------------------------------------------------------


def test_top_combinations_length() -> None:
    """AC-CROSS-012: top_n=3 → 3개."""
    result = get_cross_pattern_stats(fixture_a(), top_n=3)
    assert len(result["top_combinations"]) == 3


def test_top_combinations_tie_ordering() -> None:
    """AC-CROSS-013: 동률 정렬 → (1,5),(2,4),(6,0) (odd asc, high asc)."""
    result = get_cross_pattern_stats(fixture_a(), top_n=3)
    pairs = [
        (c["odd_count"], c["high_count"]) for c in result["top_combinations"]
    ]
    assert pairs == [(1, 5), (2, 4), (6, 0)]


def test_top_combinations_item_keys() -> None:
    """AC-CROSS-014: 각 항목은 odd_count/high_count/count/pct 키."""
    result = get_cross_pattern_stats(fixture_a(), top_n=3)
    for item in result["top_combinations"]:
        assert set(item.keys()) >= {"odd_count", "high_count", "count", "pct"}


def test_top_combinations_pct() -> None:
    """AC-CROSS-015: 첫 항목 pct == 33.33."""
    result = get_cross_pattern_stats(fixture_a(), top_n=3)
    assert result["top_combinations"][0]["pct"] == 33.33


def test_top_combinations_fewer_than_top_n() -> None:
    """AC-CROSS-016: 기본 top_n=10이나 조합 종류가 3개면 3개만 반환."""
    result = get_cross_pattern_stats(fixture_a())
    assert result["top_n"] == 10
    assert len(result["top_combinations"]) == 3


# ---------------------------------------------------------------------------
# 경계 / 빈 입력
# ---------------------------------------------------------------------------


def test_none_input() -> None:
    """AC-CROSS-017: None 입력 → 0 채움 구조 (예외 없음)."""
    result = get_cross_pattern_stats(None)
    assert result["total_draws"] == 0
    assert len(result["matrix"]) == 49
    assert all(v == 0 for v in result["matrix"].values())
    assert result["top_combinations"] == []
    assert result["avg_odd"] == 0.0
    assert result["avg_high"] == 0.0


def test_empty_input() -> None:
    """AC-CROSS-018: [] 입력 → 0 채움 구조."""
    result = get_cross_pattern_stats([])
    assert result["total_draws"] == 0
    assert len(result["matrix"]) == 49
    assert all(v == 0 for v in result["matrix"].values())
    assert result["top_combinations"] == []
    assert result["marginal_odd"] == {str(i): 0 for i in range(7)}
    assert result["marginal_high"] == {str(i): 0 for i in range(7)}


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


class TestCrossPatternApi:
    """GET /api/stats/cross-pattern 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app

        return TestClient(app)

    def test_api_200_and_keys(self) -> None:
        """AC-CROSS-019: 200, 핵심 키 포함, top_n 기본 10."""
        with patch("lotto.web.data.get_draws", return_value=fixture_a()):
            resp = self._client().get("/api/stats/cross-pattern")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) >= {
            "total_draws",
            "top_n",
            "matrix",
            "top_combinations",
            "marginal_odd",
            "marginal_high",
            "avg_odd",
            "avg_high",
            "disclaimer",
        }
        assert body["top_n"] == 10

    def test_api_top_n_validation(self) -> None:
        """AC-CROSS-020: 0/50 → 422, 1/49 → 200."""
        client = self._client()
        assert client.get("/api/stats/cross-pattern?top_n=0").status_code == 422
        assert client.get("/api/stats/cross-pattern?top_n=50").status_code == 422
        with patch("lotto.web.data.get_draws", return_value=fixture_a()):
            assert (
                client.get("/api/stats/cross-pattern?top_n=1").status_code == 200
            )
            assert (
                client.get("/api/stats/cross-pattern?top_n=49").status_code == 200
            )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


class TestCrossPatternPage:
    """GET /stats/cross-pattern 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app

        return TestClient(app)

    def test_page_200_and_label(self) -> None:
        """AC-CROSS-021: 200, '조합 매트릭스' 문자열 포함."""
        with patch("lotto.web.data.get_draws", return_value=fixture_a()):
            resp = self._client().get("/stats/cross-pattern")
        assert resp.status_code == 200
        assert "조합 매트릭스" in resp.text

    def test_page_empty_data_200(self) -> None:
        """AC-CROSS-022: 데이터 부재 시에도 200."""
        with patch("lotto.web.data.get_draws", return_value=None):
            resp = self._client().get("/stats/cross-pattern")
        assert resp.status_code == 200
