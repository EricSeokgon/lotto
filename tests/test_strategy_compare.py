"""SPEC-LOTTO-032: 전략 비교 (Strategy Comparison) — API + 데이터 레이어 테스트.

GET /api/simulation/compare?rounds=N 으로 8가지 추천 전략을 동일 기간에
백테스트하여 전략별 성과(ROI, 등수별 당첨 횟수, 최고 등수)를 비교한다.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import date

import pytest
from starlette.testclient import TestClient

from lotto.models import DrawResult, Statistics
from lotto.web.app import app


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """앱 클라이언트 — 모듈 단위 공유."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_draws() -> list[DrawResult]:
    """백테스트용 추첨 데이터 12회차."""
    base = [
        (1, 1, 2, 3, 4, 5, 6, 7),
        (2, 8, 9, 10, 11, 12, 13, 14),
        (3, 1, 10, 20, 30, 40, 45, 5),
        (4, 2, 11, 21, 31, 41, 44, 3),
        (5, 3, 12, 22, 32, 42, 43, 8),
        (6, 4, 13, 23, 33, 43, 44, 9),
        (7, 5, 14, 24, 34, 44, 45, 1),
        (8, 6, 15, 25, 35, 45, 40, 2),
        (9, 7, 16, 26, 36, 41, 42, 11),
        (10, 1, 17, 27, 37, 38, 39, 12),
        (11, 2, 18, 28, 30, 31, 32, 13),
        (12, 3, 19, 29, 33, 34, 35, 14),
    ]
    return [
        DrawResult(
            drwNo=d[0], date=date(2026, 1, d[0]),
            n1=d[1], n2=d[2], n3=d[3], n4=d[4], n5=d[5], n6=d[6], bonus=d[7],
        )
        for d in base
    ]


@pytest.fixture
def sample_stats(sample_draws: list[DrawResult]) -> Statistics:
    """sample_draws 기반 통계 — recommend_by_strategy 호출에 필요."""
    import warnings

    from lotto.analyzer import LottoAnalyzer

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return LottoAnalyzer().analyze(sample_draws)


@pytest.fixture(autouse=True)
def patch_data(
    monkeypatch: pytest.MonkeyPatch,
    sample_draws: list[DrawResult],
    sample_stats: Statistics,
) -> None:
    """get_draws()/get_stats()가 샘플을 반환하도록 패치."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)
    monkeypatch.setattr(wd, "get_stats", lambda: sample_stats)


# ─── 데이터 레이어: strategy_compare ───────────────────────────────────────


class TestStrategyCompareData:
    """data.strategy_compare 함수 직접 검증."""

    def test_returns_dict_with_rounds_and_strategies(
        self, sample_draws: list[DrawResult], sample_stats: Statistics
    ) -> None:
        from lotto.web.data import strategy_compare

        result = strategy_compare(rounds=10, draws=sample_draws, stats=sample_stats)
        assert isinstance(result, dict)
        assert "rounds" in result
        assert "strategies" in result

    def test_each_strategy_has_required_fields(
        self, sample_draws: list[DrawResult], sample_stats: Statistics
    ) -> None:
        from lotto.web.data import strategy_compare

        result = strategy_compare(rounds=10, draws=sample_draws, stats=sample_stats)
        assert len(result["strategies"]) > 0
        for s in result["strategies"]:
            for key in (
                "strategy", "label", "total_spent", "total_prize", "roi",
                "match3_count", "match4_count", "match5_count",
                "match5b_count", "match6_count", "best_rank",
            ):
                assert key in s, f"missing {key}"

    def test_strategy_count_matches_label_count(
        self, sample_draws: list[DrawResult], sample_stats: Statistics
    ) -> None:
        from lotto.recommender import STRATEGY_LABELS
        from lotto.web.data import strategy_compare

        result = strategy_compare(rounds=10, draws=sample_draws, stats=sample_stats)
        assert len(result["strategies"]) == len(STRATEGY_LABELS)

    def test_total_spent_is_rounds_times_1000(
        self, sample_draws: list[DrawResult], sample_stats: Statistics
    ) -> None:
        from lotto.web.data import strategy_compare

        result = strategy_compare(rounds=10, draws=sample_draws, stats=sample_stats)
        used_rounds = result["rounds"]
        for s in result["strategies"]:
            assert s["total_spent"] == used_rounds * 1000

    def test_roi_formula(
        self, sample_draws: list[DrawResult], sample_stats: Statistics
    ) -> None:
        from lotto.web.data import strategy_compare

        result = strategy_compare(rounds=10, draws=sample_draws, stats=sample_stats)
        for s in result["strategies"]:
            spent = s["total_spent"]
            prize = s["total_prize"]
            expected = round((prize - spent) / spent * 100, 1) if spent else 0.0
            assert s["roi"] == expected

    def test_best_rank_is_valid_label(
        self, sample_draws: list[DrawResult], sample_stats: Statistics
    ) -> None:
        from lotto.web.data import strategy_compare

        result = strategy_compare(rounds=10, draws=sample_draws, stats=sample_stats)
        valid = {"1등", "2등", "3등", "4등", "5등", "낙첨"}
        for s in result["strategies"]:
            assert s["best_rank"] in valid

    def test_empty_draws_returns_empty_strategies(self) -> None:
        from lotto.web.data import strategy_compare

        result = strategy_compare(rounds=10, draws=[], stats=None)
        assert result["strategies"] == []
        assert result["rounds"] == 10

    def test_none_stats_returns_empty_strategies(
        self, sample_draws: list[DrawResult]
    ) -> None:
        from lotto.web.data import strategy_compare

        result = strategy_compare(rounds=10, draws=sample_draws, stats=None)
        assert result["strategies"] == []

    def test_match_counts_are_non_negative(
        self, sample_draws: list[DrawResult], sample_stats: Statistics
    ) -> None:
        from lotto.web.data import strategy_compare

        result = strategy_compare(rounds=10, draws=sample_draws, stats=sample_stats)
        for s in result["strategies"]:
            for key in (
                "match3_count", "match4_count", "match5_count",
                "match5b_count", "match6_count",
            ):
                assert s[key] >= 0


# ─── API: GET /api/simulation/compare ──────────────────────────────────────


class TestStrategyCompareAPI:
    """GET /api/simulation/compare 엔드포인트 검증."""

    def test_status_200(self, client: TestClient) -> None:
        res = client.get("/api/simulation/compare?rounds=10")
        assert res.status_code == 200, res.text

    def test_default_rounds_100(self, client: TestClient) -> None:
        res = client.get("/api/simulation/compare")
        assert res.status_code == 200
        # 가용 회차(12)로 잘려도 응답은 정상
        assert "rounds" in res.json()

    def test_response_shape(self, client: TestClient) -> None:
        res = client.get("/api/simulation/compare?rounds=10")
        body = res.json()
        assert "rounds" in body
        assert "strategies" in body
        assert isinstance(body["strategies"], list)

    def test_rounds_below_min_rejected(self, client: TestClient) -> None:
        # 최소 10 미만 → 422
        res = client.get("/api/simulation/compare?rounds=5")
        assert res.status_code == 422

    def test_rounds_above_max_rejected(self, client: TestClient) -> None:
        # 최대 500 초과 → 422
        res = client.get("/api/simulation/compare?rounds=501")
        assert res.status_code == 422

    def test_strategy_fields_present_in_api(self, client: TestClient) -> None:
        res = client.get("/api/simulation/compare?rounds=10")
        strategies = res.json()["strategies"]
        assert len(strategies) > 0
        first = strategies[0]
        for key in (
            "strategy", "label", "total_spent", "total_prize", "roi", "best_rank",
        ):
            assert key in first


class TestStrategyCompareEmptyData:
    """데이터 없을 때 빈 strategies 반환."""

    def test_no_draws_empty_strategies(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from lotto.web import data as wd

        monkeypatch.setattr(wd, "get_draws", lambda: None)
        monkeypatch.setattr(wd, "get_stats", lambda: None)
        res = client.get("/api/simulation/compare?rounds=10")
        assert res.status_code == 200
        assert res.json()["strategies"] == []
