"""SPEC-LOTTO-105: 번호 위치별 분포 분석 (Position Distribution) 테스트.

손계산 가능한 소규모 DrawResult 픽스처(3회차)로 위치 1·6의 양 끝단
avg/median/min/max/std/top_numbers를 결정적으로 검증한다.
빈/단일 회차·top_n 경계·동률 정렬·API 검증(422)을 포함한다.
(AC-POS-001 ~ AC-POS-023)
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.data import get_position_distribution, invalidate_cache


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
    """acceptance.md Fixture A — 3회차 손계산 픽스처.

    | 회차 | 본번호 | 보너스 |
    |------|--------|--------|
    | 1 | 1, 5, 10, 20, 30, 40 | 7 |
    | 2 | 2, 6, 12, 22, 32, 42 | 8 |
    | 3 | 1, 7, 15, 25, 35, 45 | 9 |

    위치별 관측값:
    - 위치1 [1,2,1], 위치2 [5,6,7], 위치3 [10,12,15],
      위치4 [20,22,25], 위치5 [30,32,35], 위치6 [40,42,45]
    """
    return [
        make_draw(1, 1, 5, 10, 20, 30, 40, 7),
        make_draw(2, 2, 6, 12, 22, 32, 42, 8),
        make_draw(3, 1, 7, 15, 25, 35, 45, 9),
    ]


# ---------------------------------------------------------------------------
# 핵심 함수 동작 (AC-POS-001 ~ AC-POS-010)
# ---------------------------------------------------------------------------


def test_top_level_keys_and_counts() -> None:
    """AC-POS-001: total_draws/top_n/positions/disclaimer 키, total_draws=3, len=6."""
    result = get_position_distribution(fixture_a())
    assert set(result.keys()) >= {"total_draws", "top_n", "positions", "disclaimer"}
    assert result["total_draws"] == 3
    assert len(result["positions"]) == 6


def test_position_indices_and_item_keys() -> None:
    """AC-POS-002: positions[0].position==1, positions[5].position==6, 항목 키 구성."""
    result = get_position_distribution(fixture_a())
    positions = result["positions"]
    assert positions[0]["position"] == 1
    assert positions[5]["position"] == 6
    expected_keys = {
        "position",
        "avg",
        "median",
        "min_ever",
        "max_ever",
        "std",
        "top_numbers",
    }
    for item in positions:
        assert set(item.keys()) == expected_keys


def test_position1_avg_median() -> None:
    """AC-POS-003: 위치1 avg==1.33, median==1.0 (소수 2자리)."""
    result = get_position_distribution(fixture_a())
    pos1 = result["positions"][0]
    assert pos1["avg"] == 1.33
    assert pos1["median"] == 1.0


def test_position1_min_max() -> None:
    """AC-POS-004: 위치1 min_ever==1, max_ever==2."""
    result = get_position_distribution(fixture_a())
    pos1 = result["positions"][0]
    assert pos1["min_ever"] == 1
    assert pos1["max_ever"] == 2


def test_position1_std() -> None:
    """AC-POS-005: 위치1 std==0.58 (표본 표준편차)."""
    result = get_position_distribution(fixture_a())
    assert result["positions"][0]["std"] == 0.58


def test_position1_top_numbers() -> None:
    """AC-POS-006: 위치1 top_numbers 빈도 내림차순·동률 작은 번호 우선."""
    result = get_position_distribution(fixture_a(), top_n=2)
    assert result["positions"][0]["top_numbers"] == [
        {"number": 1, "count": 2, "pct": 66.67},
        {"number": 2, "count": 1, "pct": 33.33},
    ]


def test_position6_full_stats() -> None:
    """AC-POS-007: 위치6 avg/median/min/max/std."""
    result = get_position_distribution(fixture_a())
    pos6 = result["positions"][5]
    assert pos6["avg"] == 42.33
    assert pos6["median"] == 42.0
    assert pos6["min_ever"] == 40
    assert pos6["max_ever"] == 45
    assert pos6["std"] == 2.52


def test_position2_tie_ascending_order() -> None:
    """AC-POS-008: 위치2 동률 번호는 오름차순 [5,6,7] 순서로 반환."""
    result = get_position_distribution(fixture_a(), top_n=3)
    numbers = [item["number"] for item in result["positions"][1]["top_numbers"]]
    assert numbers == [5, 6, 7]


def test_bonus_numbers_excluded() -> None:
    """AC-POS-009: 보너스 번호(7,8,9)는 top_numbers에 위치 무관하게 본번호로만 등장."""
    result = get_position_distribution(fixture_a(), top_n=45)
    # 보너스 8, 9는 본번호에 없으므로 어떤 위치에도 등장하지 않아야 한다.
    for pos in result["positions"]:
        appeared = {item["number"] for item in pos["top_numbers"]}
        assert 8 not in appeared
        assert 9 not in appeared
    # 7은 위치2의 본번호이므로 위치2에만 등장한다(보너스로 인한 오염 없음).
    pos2_numbers = {item["number"] for item in result["positions"][1]["top_numbers"]}
    assert 7 in pos2_numbers


def test_deterministic() -> None:
    """AC-POS-010: 동일 입력 두 번 호출 시 완전히 동일한 결과."""
    draws = fixture_a()
    first = get_position_distribution(draws)
    second = get_position_distribution(draws)
    assert first == second


# ---------------------------------------------------------------------------
# 엣지 케이스 (AC-POS-011 ~ AC-POS-015)
# ---------------------------------------------------------------------------


def test_empty_list_returns_zero_filled() -> None:
    """AC-POS-011: 빈 리스트 → total_draws=0, 6위치 0 채움, 예외 없음."""
    result = get_position_distribution([])
    assert result["total_draws"] == 0
    assert len(result["positions"]) == 6
    for idx, pos in enumerate(result["positions"]):
        assert pos["position"] == idx + 1
        assert pos["avg"] == 0.0
        assert pos["median"] == 0.0
        assert pos["min_ever"] == 0
        assert pos["max_ever"] == 0
        assert pos["std"] == 0.0
        assert pos["top_numbers"] == []
    assert "disclaimer" in result


def test_none_returns_zero_filled() -> None:
    """AC-POS-012: None → 빈 결과(AC-POS-011과 동일), 예외 없음."""
    result = get_position_distribution(None)
    assert result["total_draws"] == 0
    assert len(result["positions"]) == 6
    for pos in result["positions"]:
        assert pos["avg"] == 0.0
        assert pos["median"] == 0.0
        assert pos["min_ever"] == 0
        assert pos["max_ever"] == 0
        assert pos["std"] == 0.0
        assert pos["top_numbers"] == []


def test_single_draw_std_zero() -> None:
    """AC-POS-013: 단일 회차 → 각 위치 표본 1개 → std=0.0, avg/median=단일값."""
    result = get_position_distribution([make_draw(1, 3, 8, 14, 21, 29, 41, 5)])
    pos1 = result["positions"][0]
    assert pos1["std"] == 0.0
    assert pos1["avg"] == 3.0
    assert pos1["median"] == 3.0
    assert pos1["min_ever"] == 3
    assert pos1["max_ever"] == 3
    for pos in result["positions"]:
        assert pos["std"] == 0.0


def test_single_draw_top_numbers_no_padding() -> None:
    """AC-POS-014: 단일 회차 top_n=5여도 각 위치 top_numbers 길이는 1 (패딩 없음)."""
    result = get_position_distribution(
        [make_draw(1, 3, 8, 14, 21, 29, 41, 5)], top_n=5
    )
    for pos in result["positions"]:
        assert len(pos["top_numbers"]) == 1


def test_top_n_one_boundary() -> None:
    """AC-POS-015: Fixture A top_n=1 → 각 위치 top_numbers 길이 1, 동률은 작은 번호."""
    result = get_position_distribution(fixture_a(), top_n=1)
    for pos in result["positions"]:
        assert len(pos["top_numbers"]) == 1
    assert result["positions"][0]["top_numbers"] == [
        {"number": 1, "count": 2, "pct": 66.67}
    ]
    # 위치2는 동률(각 1회) → 가장 작은 번호 5만 반환
    assert result["positions"][1]["top_numbers"][0]["number"] == 5


# ---------------------------------------------------------------------------
# API 동작 (AC-POS-016 ~ AC-POS-020)
# ---------------------------------------------------------------------------


class TestPositionApi:
    """GET /api/stats/position 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app

        return TestClient(app)

    def test_api_200_and_keys(self) -> None:
        """AC-POS-016: 200, total_draws/top_n/positions(6)/disclaimer 키."""
        with patch("lotto.web.data.get_draws", return_value=fixture_a()):
            resp = self._client().get("/api/stats/position")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) >= {
            "total_draws",
            "top_n",
            "positions",
            "disclaimer",
        }
        assert len(body["positions"]) == 6

    def test_api_top_n_5(self) -> None:
        """AC-POS-017: top_n=5 → 각 위치 top_numbers 길이 5 이하, top_n==5."""
        with patch("lotto.web.data.get_draws", return_value=fixture_a()):
            resp = self._client().get("/api/stats/position?top_n=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["top_n"] == 5
        for pos in body["positions"]:
            assert len(pos["top_numbers"]) <= 5

    def test_api_default_top_n(self) -> None:
        """AC-POS-018: top_n 생략 → 기본값 5."""
        with patch("lotto.web.data.get_draws", return_value=fixture_a()):
            resp = self._client().get("/api/stats/position")
        assert resp.json()["top_n"] == 5

    def test_api_top_n_zero_422(self) -> None:
        """AC-POS-019: top_n=0 → 422."""
        resp = self._client().get("/api/stats/position?top_n=0")
        assert resp.status_code == 422

    def test_api_top_n_46_422(self) -> None:
        """AC-POS-019: top_n=46 → 422."""
        resp = self._client().get("/api/stats/position?top_n=46")
        assert resp.status_code == 422

    def test_api_top_n_boundaries_ok(self) -> None:
        """AC-POS-019: top_n=1, top_n=45 경계는 200."""
        with patch("lotto.web.data.get_draws", return_value=fixture_a()):
            client = self._client()
            assert client.get("/api/stats/position?top_n=1").status_code == 200
            assert client.get("/api/stats/position?top_n=45").status_code == 200

    def test_api_empty_data_200(self) -> None:
        """AC-POS-016/REQ-POS-014: 데이터 부재 시에도 200, total_draws=0."""
        with patch("lotto.web.data.get_draws", return_value=None):
            resp = self._client().get("/api/stats/position")
        assert resp.status_code == 200
        assert resp.json()["total_draws"] == 0


# ---------------------------------------------------------------------------
# 페이지 동작 (AC-POS-020)
# ---------------------------------------------------------------------------


class TestPositionPage:
    """GET /stats/position 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app

        return TestClient(app)

    def test_page_renders_with_disclaimer(self) -> None:
        """AC-POS-020: 200, disclaimer 텍스트 포함."""
        with patch("lotto.web.data.get_draws", return_value=fixture_a()):
            resp = self._client().get("/stats/position")
        assert resp.status_code == 200
        assert "회고" in resp.text  # disclaimer 문구의 일부

    def test_page_empty_data_200(self) -> None:
        """데이터 부재 시에도 200."""
        with patch("lotto.web.data.get_draws", return_value=None):
            resp = self._client().get("/stats/position")
        assert resp.status_code == 200

    def test_page_top_n_query_accepted(self) -> None:
        """top_n 쿼리 적용 시 200."""
        with patch("lotto.web.data.get_draws", return_value=fixture_a()):
            resp = self._client().get("/stats/position?top_n=3")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 캐싱·품질 (AC-POS-021 ~ AC-POS-023)
# ---------------------------------------------------------------------------


def test_cache_reuse_and_invalidate() -> None:
    """AC-POS-021: 동일 길이 draws 반복 호출 시 캐시 재사용, invalidate 후 재계산."""
    invalidate_cache()
    draws = fixture_a()
    first = get_position_distribution(draws, top_n=5)
    # 동일 입력 재호출 → 캐시된 동일 객체 반환
    second = get_position_distribution(draws, top_n=5)
    assert first is second
    invalidate_cache()
    third = get_position_distribution(draws, top_n=5)
    assert third is not first
    assert third == first


def test_cache_key_includes_top_n() -> None:
    """AC-POS-021: top_n이 다르면 다른 캐시 엔트리(top_numbers 길이 차이)."""
    invalidate_cache()
    draws = fixture_a()
    r1 = get_position_distribution(draws, top_n=1)
    r2 = get_position_distribution(draws, top_n=3)
    assert len(r1["positions"][1]["top_numbers"]) == 1
    assert len(r2["positions"][1]["top_numbers"]) == 3


def test_no_match_case_or_zip_strict() -> None:
    """AC-POS-022: 소스에 match/case, zip(strict=)가 없음."""
    import inspect

    from lotto.web import data as wd

    src = inspect.getsource(wd.get_position_distribution)
    assert "match " not in src
    assert "zip(" not in src or "strict=" not in src
