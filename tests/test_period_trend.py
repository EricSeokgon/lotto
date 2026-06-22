"""SPEC-LOTTO-107: 기간별 번호 빈도 추이 분석 테스트.

전체 회차를 초기/중기/최근 3구간으로 균등 분할(슬라이스 공식 엄격 적용)하여
번호별 구간 출현 횟수·비율·델타·추세(rising/falling/stable)를 검증한다.
모든 기댓값은 acceptance.md의 9회차 손계산 픽스처에서 직접 산출·검증되었다.

Fixture (9 draws):
| 회차 | 본번호(sorted) |
|------|----------------|
| D1 | 1, 2, 3, 4, 5, 6 |
| D2 | 1, 7, 8, 9, 10, 11 |
| D3 | 2, 12, 13, 14, 15, 16 |
| D4 | 3, 17, 18, 19, 20, 21 |
| D5 | 4, 22, 23, 24, 25, 26 |
| D6 | 5, 27, 28, 29, 30, 31 |
| D7 | 6, 32, 33, 34, 35, 36 |
| D8 | 7, 37, 38, 39, 40, 41 |
| D9 | 1, 8, 42, 43, 44, 45 |

n=9 → early=D1..3, middle=D4..6, recent=D7..9 (각 구간 3회차)
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.data import get_period_trend


def make_draw(
    draw_no: int,
    n1: int,
    n2: int,
    n3: int,
    n4: int,
    n5: int,
    n6: int,
    bonus: int = 13,
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


def fixture_9() -> list[DrawResult]:
    """acceptance.md 9회차 손계산 픽스처."""
    return [
        make_draw(1, 1, 2, 3, 4, 5, 6),
        make_draw(2, 1, 7, 8, 9, 10, 11),
        make_draw(3, 2, 12, 13, 14, 15, 16),
        make_draw(4, 3, 17, 18, 19, 20, 21),
        make_draw(5, 4, 22, 23, 24, 25, 26),
        make_draw(6, 5, 27, 28, 29, 30, 31),
        make_draw(7, 6, 32, 33, 34, 35, 36),
        make_draw(8, 7, 37, 38, 39, 40, 41),
        make_draw(9, 1, 8, 42, 43, 44, 45),
    ]


def _num(result: dict, number: int) -> dict:
    """numbers 리스트에서 특정 번호 항목을 반환한다."""
    return result["numbers"][number - 1]


# ---------------------------------------------------------------------------
# 핵심 계산 (data layer)
# ---------------------------------------------------------------------------


def test_total_draws() -> None:
    """AC-PT-001: total_draws == 9."""
    assert get_period_trend(fixture_9())["total_draws"] == 9


def test_top_level_keys() -> None:
    """AC-PT-002: 반환 dict가 모든 핵심 키를 포함한다."""
    result = get_period_trend(fixture_9())
    assert set(result.keys()) >= {
        "total_draws",
        "top_n",
        "period_sizes",
        "numbers",
        "top_rising",
        "top_falling",
        "disclaimer",
    }


def test_period_sizes() -> None:
    """AC-PT-003: period_sizes == {early:3, middle:3, recent:3}."""
    result = get_period_trend(fixture_9())
    assert result["period_sizes"] == {"early": 3, "middle": 3, "recent": 3}


def test_numbers_length_and_bounds() -> None:
    """AC-PT-004: numbers 길이 45, index0=번호1, index44=번호45."""
    result = get_period_trend(fixture_9())
    assert len(result["numbers"]) == 45
    assert result["numbers"][0]["number"] == 1
    assert result["numbers"][44]["number"] == 45


def test_number_1_values() -> None:
    """AC-PT-005: 번호 1 — falling, delta=-1, pct 검증."""
    n1 = _num(get_period_trend(fixture_9()), 1)
    assert n1["count_early"] == 2
    assert n1["count_middle"] == 0
    assert n1["count_recent"] == 1
    assert n1["pct_early"] == 66.67
    assert n1["pct_middle"] == 0.0
    assert n1["pct_recent"] == 33.33
    assert n1["delta"] == -1
    assert n1["trend"] == "falling"


def test_number_2_falling() -> None:
    """AC-PT-006: 번호 2 — count_early=2, count_recent=0, delta=-2, falling."""
    n2 = _num(get_period_trend(fixture_9()), 2)
    assert n2["count_early"] == 2
    assert n2["count_recent"] == 0
    assert n2["delta"] == -2
    assert n2["trend"] == "falling"


def test_number_8_stable() -> None:
    """AC-PT-007: 번호 8 — D2에 포함되어 count_early=1, delta=0, stable."""
    n8 = _num(get_period_trend(fixture_9()), 8)
    assert n8["count_early"] == 1
    assert n8["count_recent"] == 1
    assert n8["delta"] == 0
    assert n8["trend"] == "stable"


def test_number_45_rising() -> None:
    """AC-PT-008: 번호 45 — count_early=0, count_recent=1, delta=1, rising."""
    n45 = _num(get_period_trend(fixture_9()), 45)
    assert n45["count_early"] == 0
    assert n45["count_recent"] == 1
    assert n45["delta"] == 1
    assert n45["trend"] == "rising"


def test_numbers_6_and_7_stable() -> None:
    """AC-PT-009: 번호 6·7 — delta=0, stable."""
    result = get_period_trend(fixture_9())
    for num in (6, 7):
        item = _num(result, num)
        assert item["delta"] == 0
        assert item["trend"] == "stable"


def test_trend_distribution() -> None:
    """AC-PT-010: trend 분포 stable=18, rising=14, falling=13."""
    result = get_period_trend(fixture_9())
    trends = [n["trend"] for n in result["numbers"]]
    assert trends.count("stable") == 18
    assert trends.count("rising") == 14
    assert trends.count("falling") == 13


# ---------------------------------------------------------------------------
# 정렬 (Sorting)
# ---------------------------------------------------------------------------


def test_top_rising_sort() -> None:
    """AC-PT-011: top_rising 길이=10, 첫 5개 번호=[32,33,34,35,36]."""
    result = get_period_trend(fixture_9())
    rising = result["top_rising"]
    assert len(rising) == 10
    assert [r["number"] for r in rising[:5]] == [32, 33, 34, 35, 36]
    # delta 내림차순 보장
    deltas = [r["delta"] for r in rising]
    assert deltas == sorted(deltas, reverse=True)


def test_top_falling_sort() -> None:
    """AC-PT-012: top_falling 첫 항목 번호2(delta=-2), 이후 delta=-1 number desc."""
    result = get_period_trend(fixture_9())
    falling = result["top_falling"]
    assert falling[0]["number"] == 2
    assert falling[0]["delta"] == -2
    # 나머지는 delta=-1, number 내림차순
    rest = falling[1:]
    assert all(f["delta"] == -1 for f in rest)
    nums = [f["number"] for f in rest]
    assert nums == sorted(nums, reverse=True)
    assert nums[:3] == [16, 15, 14]


def test_top_item_keys() -> None:
    """AC-PT-013: top_rising/top_falling 항목 키 구조."""
    result = get_period_trend(fixture_9())
    expected = {
        "number",
        "count_early",
        "count_middle",
        "count_recent",
        "delta",
        "trend",
    }
    assert set(result["top_rising"][0].keys()) >= expected
    assert set(result["top_falling"][0].keys()) >= expected


def test_top_n_length() -> None:
    """AC-PT-014: top_n=5 시 top_rising·top_falling 길이 각 5."""
    result = get_period_trend(fixture_9(), top_n=5)
    assert result["top_n"] == 5
    assert len(result["top_rising"]) == 5
    assert len(result["top_falling"]) == 5


# ---------------------------------------------------------------------------
# 엣지 케이스 (Edge Cases)
# ---------------------------------------------------------------------------


def test_none_input_zero_structure() -> None:
    """AC-PT-015: None 입력 → 0 채움 구조."""
    result = get_period_trend(None)
    assert result["total_draws"] == 0
    assert result["period_sizes"] == {"early": 0, "middle": 0, "recent": 0}
    assert len(result["numbers"]) == 45
    for item in result["numbers"]:
        assert item["count_early"] == 0
        assert item["count_middle"] == 0
        assert item["count_recent"] == 0
        assert item["pct_early"] == 0.0
        assert item["pct_recent"] == 0.0
        assert item["delta"] == 0
        assert item["trend"] == "stable"
    assert result["top_rising"] == []
    assert result["top_falling"] == []


def test_empty_input_zero_structure() -> None:
    """AC-PT-016: [] 입력 → None과 동일한 0 채움 구조."""
    result = get_period_trend([])
    assert result["total_draws"] == 0
    assert result["period_sizes"] == {"early": 0, "middle": 0, "recent": 0}
    assert result["top_rising"] == []
    assert result["top_falling"] == []


def test_single_draw_goes_to_recent() -> None:
    """AC-PT-017: n=1 → early/middle 비고 recent에 배치(슬라이스 공식)."""
    draw = make_draw(1, 3, 11, 17, 23, 30, 41)
    result = get_period_trend([draw])
    assert result["period_sizes"] == {"early": 0, "middle": 0, "recent": 1}
    n3 = _num(result, 3)
    assert n3["count_early"] == 0
    assert n3["count_recent"] == 1
    assert n3["delta"] == 1
    assert n3["trend"] == "rising"
    assert n3["pct_early"] == 0.0
    assert n3["pct_recent"] == 100.0


def test_two_draws_split() -> None:
    """AC-PT-018: n=2 → period_sizes {early:0, middle:1, recent:1}."""
    draws = [make_draw(1, 1, 2, 3, 4, 5, 6), make_draw(2, 7, 8, 9, 10, 11, 12)]
    result = get_period_trend(draws)
    assert result["period_sizes"] == {"early": 0, "middle": 1, "recent": 1}


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


class TestPeriodTrendApi:
    """GET /api/stats/period-trend 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app

        return TestClient(app)

    def test_api_200_and_keys(self) -> None:
        """AC-PT-019: 200, 핵심 키 포함, top_n 기본 10."""
        with patch("lotto.web.data.get_draws", return_value=fixture_9()):
            resp = self._client().get("/api/stats/period-trend")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) >= {
            "total_draws",
            "top_n",
            "period_sizes",
            "numbers",
            "top_rising",
            "top_falling",
            "disclaimer",
        }
        assert body["top_n"] == 10

    def test_api_top_n_validation(self) -> None:
        """AC-PT-019: 0/46 → 422, 1/45 → 200."""
        client = self._client()
        assert client.get("/api/stats/period-trend?top_n=0").status_code == 422
        assert client.get("/api/stats/period-trend?top_n=46").status_code == 422
        with patch("lotto.web.data.get_draws", return_value=fixture_9()):
            assert client.get("/api/stats/period-trend?top_n=1").status_code == 200
            assert client.get("/api/stats/period-trend?top_n=45").status_code == 200


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


class TestPeriodTrendPage:
    """GET /stats/period-trend 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app

        return TestClient(app)

    def test_page_200_and_label(self) -> None:
        """AC-PT-020: 200, '추이' 문자열 포함."""
        with patch("lotto.web.data.get_draws", return_value=fixture_9()):
            resp = self._client().get("/stats/period-trend")
        assert resp.status_code == 200
        assert "추이" in resp.text

    def test_page_empty_data_200(self) -> None:
        """AC-PT-020: 데이터 부재 시에도 200."""
        with patch("lotto.web.data.get_draws", return_value=None):
            resp = self._client().get("/stats/period-trend")
        assert resp.status_code == 200
