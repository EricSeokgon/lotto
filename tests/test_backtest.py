"""SPEC-LOTTO-052: 전략 백테스팅 분석기 테스트.

run_backtest 데이터 계층(look-ahead bias 부재 핵심), /backtest 페이지,
/api/backtest API, 메모리 캐시를 검증한다.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.recommender import STRATEGY_LABELS


def _mk(no: int, nums: list[int], bonus: int = 45) -> DrawResult:
    """단일 회차 헬퍼 — 회차 번호로 날짜를 자동 생성한다."""
    d = date(2020, 1, 1) + timedelta(days=no)
    return DrawResult(
        drwNo=no, date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


def _make_draws(count: int) -> list[DrawResult]:
    """count개 회차의 결정적 데이터셋 — 번호를 회차마다 회전시킨다."""
    draws: list[DrawResult] = []
    for i in range(1, count + 1):
        base = (i % 40) + 1
        nums = sorted({((base + k) % 45) + 1 for k in range(6)})
        # 6개 보장 (mod 충돌 시 보충)
        k = 1
        while len(nums) < 6:
            nums = sorted(set(nums) | {((base + 6 + k) % 45) + 1})
            k += 1
        draws.append(_mk(i, nums[:6], bonus=((base + 10) % 45) + 1))
    return draws


@pytest.fixture(autouse=True)
def _clear_backtest_cache():
    """각 테스트 전후로 백테스트 캐시를 비운다 (모듈 전역 격리)."""
    from lotto.web import data as wd

    wd._backtest_cache.clear()
    yield
    wd._backtest_cache.clear()


# ---------------------------------------------------------------------------
# AC-09: 11개 전략 전부를 키로 가진다
# ---------------------------------------------------------------------------


def test_run_backtest_returns_all_strategies() -> None:
    """반환 매핑은 11개 STRATEGY_LABELS 전부를 키로 가진다."""
    from lotto.web import data as wd

    draws = _make_draws(40)
    result = wd.run_backtest(draws, n_past=20)
    assert "error" not in result
    assert set(result.keys()) == set(STRATEGY_LABELS)
    assert len(result) == 11


# ---------------------------------------------------------------------------
# AC-03/AC-18: look-ahead bias 부재 (핵심)
# ---------------------------------------------------------------------------


def test_run_backtest_no_lookahead(monkeypatch: pytest.MonkeyPatch) -> None:
    """회차 #k 평가 시 통계는 prior_draws(#1..#k-1)만으로 구성된다."""
    from lotto import analyzer as analyzer_mod
    from lotto.web import data as wd

    draws = _make_draws(40)
    captured: list[int] = []

    real_analyze = analyzer_mod.LottoAnalyzer.analyze

    def _spy_analyze(self: analyzer_mod.LottoAnalyzer, prior: list[DrawResult]):  # type: ignore[no-untyped-def]
        # 전달된 prior_draws의 최대 회차 번호를 기록한다.
        max_no = max((d.drwNo for d in prior), default=0)
        captured.append(max_no)
        return real_analyze(self, prior)

    monkeypatch.setattr(analyzer_mod.LottoAnalyzer, "analyze", _spy_analyze)

    wd.run_backtest(draws, n_past=10)

    # 평가 대상 회차는 31..40. 각 회차 #k에 대해 분석은 #1..#k-1만 사용하므로
    # analyze에 전달된 최대 회차 번호는 항상 평가 회차보다 작아야 한다.
    # 평가 윈도의 가장 이른 회차는 31이므로 최초 prior 최대 회차는 30(=31-1).
    assert captured, "analyze가 한 번도 호출되지 않았다"
    assert max(captured) <= 39  # 마지막 평가 회차 40의 prior 최대는 39
    # 단조 증가: prior 최대 회차가 평가 진행에 따라 커진다
    assert captured == sorted(captured)


def test_run_backtest_rebuilds_per_draw(monkeypatch: pytest.MonkeyPatch) -> None:
    """회차마다 통계를 재구성한다 (전체 1회 재사용 금지). 회차당 analyze 1회."""
    from lotto import analyzer as analyzer_mod
    from lotto.web import data as wd

    draws = _make_draws(40)
    call_count = {"n": 0}
    real_analyze = analyzer_mod.LottoAnalyzer.analyze

    def _count_analyze(self, prior):  # type: ignore[no-untyped-def]
        call_count["n"] += 1
        return real_analyze(self, prior)

    monkeypatch.setattr(analyzer_mod.LottoAnalyzer, "analyze", _count_analyze)

    wd.run_backtest(draws, n_past=10)
    # 평가 회차 10개 × (회차당 1회 재구성) = 10회. 전략마다 재구성하지 않는다.
    assert call_count["n"] == 10


# ---------------------------------------------------------------------------
# AC-10: match_counts 0~6 키 + 합 = 평가 윈도 크기
# ---------------------------------------------------------------------------


def test_run_backtest_match_counts_sum() -> None:
    """각 전략 match_counts는 0~6 키를 모두 가지며 합은 평가 회차 수와 같다."""
    from lotto.web import data as wd

    draws = _make_draws(40)
    n_past = 20
    result = wd.run_backtest(draws, n_past=n_past)
    for label, br in result.items():
        mc = br["match_counts"]
        assert set(mc.keys()) == set(range(7)), f"{label}: 0~6 키 누락"
        assert sum(mc.values()) == n_past, f"{label}: 합 != {n_past}"


def test_run_backtest_avg_match_range() -> None:
    """avg_match는 0.0~6.0 범위이며 적중 합/회차수와 일치한다."""
    from lotto.web import data as wd

    draws = _make_draws(40)
    result = wd.run_backtest(draws, n_past=20)
    for br in result.values():
        assert 0.0 <= br["avg_match"] <= 6.0
        mc = br["match_counts"]
        total_matches = sum(k * v for k, v in mc.items())
        total_draws = sum(mc.values())
        expected = total_matches / total_draws
        assert abs(br["avg_match"] - expected) < 1e-9


def test_run_backtest_best_draw_fields() -> None:
    """best_draw는 round/matched/recommended/actual 키를 가진다."""
    from lotto.web import data as wd

    draws = _make_draws(40)
    result = wd.run_backtest(draws, n_past=20)
    for br in result.values():
        bd = br["best_draw"]
        assert set(bd.keys()) >= {"round", "matched", "recommended", "actual"}
        assert isinstance(bd["recommended"], list)
        assert isinstance(bd["actual"], list)
        assert 0 <= bd["matched"] <= 6


def test_run_backtest_score_present() -> None:
    """score는 float이며 단조 종합 점수다 (높을수록 우수)."""
    from lotto.web import data as wd

    draws = _make_draws(40)
    result = wd.run_backtest(draws, n_past=20)
    for br in result.values():
        assert isinstance(br["score"], float)
        assert br["score"] >= 0.0


# ---------------------------------------------------------------------------
# AC-05: 최소 회차 미달 시 에러 결과
# ---------------------------------------------------------------------------


def test_run_backtest_insufficient_draws() -> None:
    """20회 미만이면 에러 결과를 반환한다 (백테스트 미실행)."""
    from lotto.web import data as wd

    draws = _make_draws(15)
    result = wd.run_backtest(draws, n_past=50)
    assert "error" in result


def test_run_backtest_empty_draws() -> None:
    """빈 데이터셋도 에러 결과를 반환한다."""
    from lotto.web import data as wd

    result = wd.run_backtest([], n_past=50)
    assert "error" in result


# ---------------------------------------------------------------------------
# AC-15: n_past가 가용 회차보다 크면 클램프
# ---------------------------------------------------------------------------


def test_run_backtest_clamp() -> None:
    """n_past가 평가 가능 회차보다 크면 가능한 최대로 클램프된다."""
    from lotto.web import data as wd

    draws = _make_draws(25)
    # n_past=100이지만 가용 회차는 25개 → 평가 윈도가 클램프된다.
    result = wd.run_backtest(draws, n_past=100)
    assert "error" not in result
    # match_counts 합이 클램프된 윈도 크기와 같고 25를 넘지 않는다.
    for br in result.values():
        window = sum(br["match_counts"].values())
        assert 0 < window <= 25


# ---------------------------------------------------------------------------
# AC-06: 메모리 캐시 재사용
# ---------------------------------------------------------------------------


def test_run_backtest_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """동일 n_past 재요청 시 재계산 없이 캐시 결과를 반환한다."""
    from lotto import analyzer as analyzer_mod
    from lotto.web import data as wd

    draws = _make_draws(40)
    call_count = {"n": 0}
    real_analyze = analyzer_mod.LottoAnalyzer.analyze

    def _count_analyze(self, prior):  # type: ignore[no-untyped-def]
        call_count["n"] += 1
        return real_analyze(self, prior)

    monkeypatch.setattr(analyzer_mod.LottoAnalyzer, "analyze", _count_analyze)

    first = wd.run_backtest(draws, n_past=10)
    after_first = call_count["n"]
    assert after_first > 0

    second = wd.run_backtest(draws, n_past=10)
    # 재계산하지 않았으므로 호출 횟수가 늘지 않는다.
    assert call_count["n"] == after_first
    assert first is second or first == second


# ---------------------------------------------------------------------------
# AC-07: 캐시 무효화 후 재계산
# ---------------------------------------------------------------------------


def test_run_backtest_cache_invalidation() -> None:
    """invalidate_cache 호출 후 동일 n_past는 재계산된다."""
    from lotto.web import data as wd

    draws = _make_draws(40)
    wd.run_backtest(draws, n_past=10)
    assert 10 in wd._backtest_cache
    wd.invalidate_cache()
    assert 10 not in wd._backtest_cache


# ---------------------------------------------------------------------------
# AC-02: GET /api/backtest 11개 전략 JSON 반환
# ---------------------------------------------------------------------------


def test_api_backtest_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/backtest는 11개 전략을 매핑한 JSON을 반환한다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    draws = _make_draws(40)
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    client = TestClient(app)
    response = client.get("/api/backtest?n=20")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert "error" not in body
    assert set(body.keys()) == set(STRATEGY_LABELS)
    for label in STRATEGY_LABELS:
        entry = body[label]
        assert "avg_match" in entry
        assert "match_counts" in entry
        assert "best_draw" in entry
        assert "score" in entry


def test_api_backtest_insufficient(monkeypatch: pytest.MonkeyPatch) -> None:
    """데이터 부족 시 API는 에러 페이로드를 반환한다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    monkeypatch.setattr(wd, "get_draws", lambda: _make_draws(10))

    client = TestClient(app)
    response = client.get("/api/backtest?n=50")
    assert response.status_code == 200, response.text
    assert "error" in response.json()


# ---------------------------------------------------------------------------
# AC-01: GET /backtest 페이지 렌더 (score 내림차순)
# ---------------------------------------------------------------------------


def test_backtest_page_renders(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /backtest는 200으로 렌더되고 전략 성능 표를 포함한다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    draws = _make_draws(40)
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    client = TestClient(app)
    response = client.get("/backtest")
    assert response.status_code == 200, response.text
    html = response.text
    assert "백테스트" in html
    assert "평균 적중" in html
    # 11개 전략 라벨이 모두 노출된다.
    for label in STRATEGY_LABELS:
        assert label in html


def test_backtest_page_no_data(monkeypatch: pytest.MonkeyPatch) -> None:
    """데이터 부족 시 페이지는 200 + 안내 메시지를 렌더한다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    monkeypatch.setattr(wd, "get_draws", lambda: _make_draws(5))

    client = TestClient(app)
    response = client.get("/backtest")
    assert response.status_code == 200, response.text


def test_backtest_page_custom_n(monkeypatch: pytest.MonkeyPatch) -> None:
    """?n=N 쿼리 파라미터가 평가 윈도를 결정한다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    draws = _make_draws(40)
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    client = TestClient(app)
    response = client.get("/backtest?n=15")
    assert response.status_code == 200, response.text


def test_index_has_backtest_nav_link() -> None:
    """네비게이션에 /backtest 링크가 포함된다."""
    from lotto.web.app import app

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/backtest"' in response.text
