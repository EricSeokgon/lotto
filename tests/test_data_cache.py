"""SPEC-LOTTO-009: get_draws/get_stats TTL 캐시 및 invalidate_cache 테스트.

REQ-CACHE-001/002/003/004 검증.

# @MX:NOTE: [AUTO] 캐시 테스트는 각 케이스 시작/종료 시 invalidate_cache로 격리한다.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clear_cache_around_tests():
    """각 테스트 전후로 모듈 캐시를 비워 테스트 간 격리를 보장한다."""
    from lotto.web import data as wd

    wd.invalidate_cache()
    yield
    wd.invalidate_cache()


def _draws_path_setup(tmp_path, monkeypatch):
    """DRAWS_PATH를 존재하는 임시 파일로 패치."""
    from lotto.web import data as wd

    p = tmp_path / "draws.csv"
    p.write_text("dummy")
    monkeypatch.setattr(wd, "DRAWS_PATH", p)
    return p


def _stats_path_setup(tmp_path, monkeypatch):
    """STATS_PATH를 존재하는 임시 파일로 패치."""
    from lotto.web import data as wd

    p = tmp_path / "stats.json"
    p.write_text("{}")
    monkeypatch.setattr(wd, "STATS_PATH", p)
    return p


# ──────────────────────────────────────────────
# REQ-CACHE-001: get_draws TTL 캐시
# ──────────────────────────────────────────────


def test_get_draws_cached(tmp_path, monkeypatch):
    """AC-CACHE-001-1: 60초 이내 재호출은 디스크 로드를 재실행하지 않는다."""
    from lotto.web import data as wd

    _draws_path_setup(tmp_path, monkeypatch)

    mock_collector = MagicMock()
    mock_collector.return_value.load_existing.return_value = [
        MagicMock(drwNo=1), MagicMock(drwNo=2),
    ]

    with patch("lotto.collector.LottoCollector", mock_collector):
        result1 = wd.get_draws()
        result2 = wd.get_draws()

    # 디스크 로드는 1회만 실행되어야 한다
    assert mock_collector.return_value.load_existing.call_count == 1
    assert result1 is result2  # 캐시된 동일 객체 반환


def test_get_draws_cache_expires(tmp_path, monkeypatch):
    """AC-CACHE-001-2: TTL 만료 후에는 디스크에서 다시 로드한다."""
    from lotto.web import data as wd

    _draws_path_setup(tmp_path, monkeypatch)

    # 시간 흐름을 제어하기 위한 가짜 time
    fake_now = [1000.0]

    def fake_time():
        return fake_now[0]

    monkeypatch.setattr(wd.time, "time", fake_time)

    mock_collector = MagicMock()
    mock_collector.return_value.load_existing.return_value = [MagicMock(drwNo=1)]

    with patch("lotto.collector.LottoCollector", mock_collector):
        wd.get_draws()
        # 61초 진행 → TTL(60초) 초과
        fake_now[0] += 61.0
        wd.get_draws()

    assert mock_collector.return_value.load_existing.call_count == 2


def test_get_draws_cache_returns_same_data(tmp_path, monkeypatch):
    """AC-CACHE-004-1: 캐시 적중과 미스가 동일한 결과를 반환한다."""
    from lotto.web import data as wd

    _draws_path_setup(tmp_path, monkeypatch)

    fake_draws = [MagicMock(drwNo=10), MagicMock(drwNo=20), MagicMock(drwNo=30)]
    mock_collector = MagicMock()
    mock_collector.return_value.load_existing.return_value = fake_draws

    with patch("lotto.collector.LottoCollector", mock_collector):
        first = wd.get_draws()
        cached = wd.get_draws()

    assert first == cached
    assert len(cached) == 3
    assert cached[0].drwNo == 10


# ──────────────────────────────────────────────
# REQ-CACHE-002: get_stats TTL 캐시
# ──────────────────────────────────────────────


def test_get_stats_cached(tmp_path, monkeypatch):
    """AC-CACHE-002-1: 60초 이내 재호출 시 LottoAnalyzer.load_stats를 재실행하지 않는다."""
    from lotto.web import data as wd

    _stats_path_setup(tmp_path, monkeypatch)

    fake_stats_obj = MagicMock()
    mock_analyzer = MagicMock()
    mock_analyzer.load_stats.return_value = fake_stats_obj

    with patch("lotto.analyzer.LottoAnalyzer", mock_analyzer):
        wd.get_stats()
        wd.get_stats()

    assert mock_analyzer.load_stats.call_count == 1


def test_get_stats_cache_expires(tmp_path, monkeypatch):
    """AC-CACHE-002-2: TTL 만료 후에는 통계를 다시 로드한다."""
    from lotto.web import data as wd

    _stats_path_setup(tmp_path, monkeypatch)

    fake_now = [2000.0]
    monkeypatch.setattr(wd.time, "time", lambda: fake_now[0])

    fake_stats_obj = MagicMock()
    mock_analyzer = MagicMock()
    mock_analyzer.load_stats.return_value = fake_stats_obj

    with patch("lotto.analyzer.LottoAnalyzer", mock_analyzer):
        wd.get_stats()
        fake_now[0] += 61.0
        wd.get_stats()

    assert mock_analyzer.load_stats.call_count == 2


# ──────────────────────────────────────────────
# REQ-CACHE-003: invalidate_cache
# ──────────────────────────────────────────────


def test_invalidate_cache_forces_reload_for_draws(tmp_path, monkeypatch):
    """AC-CACHE-003-1: invalidate_cache 후 get_draws는 디스크에서 다시 로드한다."""
    from lotto.web import data as wd

    _draws_path_setup(tmp_path, monkeypatch)

    mock_collector = MagicMock()
    mock_collector.return_value.load_existing.return_value = [MagicMock(drwNo=1)]

    with patch("lotto.collector.LottoCollector", mock_collector):
        wd.get_draws()
        wd.invalidate_cache()
        wd.get_draws()

    assert mock_collector.return_value.load_existing.call_count == 2


def test_invalidate_cache_clears_both_caches(tmp_path, monkeypatch):
    """AC-CACHE-003-2: invalidate_cache는 draws와 stats 캐시를 모두 비운다."""
    from lotto.web import data as wd

    _draws_path_setup(tmp_path, monkeypatch)
    _stats_path_setup(tmp_path, monkeypatch)

    mock_collector = MagicMock()
    mock_collector.return_value.load_existing.return_value = [MagicMock(drwNo=1)]
    mock_analyzer = MagicMock()
    mock_analyzer.load_stats.return_value = MagicMock()

    with patch("lotto.collector.LottoCollector", mock_collector), \
         patch("lotto.analyzer.LottoAnalyzer", mock_analyzer):
        wd.get_draws()
        wd.get_stats()
        wd.invalidate_cache()
        wd.get_draws()
        wd.get_stats()

    assert mock_collector.return_value.load_existing.call_count == 2
    assert mock_analyzer.load_stats.call_count == 2


def test_invalidate_cache_is_idempotent():
    """AC-CACHE-003-3: invalidate_cache는 캐시가 비어 있어도 안전하게 호출 가능하다."""
    from lotto.web import data as wd

    # 어떤 상태에서도 예외 없이 호출 가능해야 한다
    wd.invalidate_cache()
    wd.invalidate_cache()


# ──────────────────────────────────────────────
# REQ-CACHE-003: 백그라운드 워커가 캐시를 무효화하는지 확인
# ──────────────────────────────────────────────


def test_collect_worker_calls_invalidate_cache(monkeypatch):
    """AC-CACHE-003-3: _collect_worker 완료 후 invalidate_cache가 호출된다.

    Error path(수집 0건) 검증 — collected가 비어도 워커는 캐시를 비워야 한다.
    """
    from lotto.web.routes import api

    # fetch_draw가 None만 반환 → 5회 연속 실패 후 즉시 종료 (error path)
    mock_collector_instance = MagicMock()
    mock_collector_instance.load_existing.return_value = []
    mock_collector_instance.fetch_draw.return_value = None

    monkeypatch.setattr(
        "lotto.collector.LottoCollector", lambda *a, **kw: mock_collector_instance
    )
    monkeypatch.setattr("time.sleep", lambda *a, **kw: None)

    invalidate_mock = MagicMock()
    monkeypatch.setattr(api, "invalidate_cache", invalidate_mock)

    api._collect_worker(full=False, start_from=1, max_drw_no=10)

    assert invalidate_mock.called, "error path에서도 invalidate_cache 호출 필요"


def test_scrape_worker_calls_invalidate_cache(monkeypatch):
    """AC-CACHE-003-3: _scrape_worker 완료 후 invalidate_cache가 호출된다."""
    from lotto.web.routes import api

    # 크롤링 성공 시나리오
    fake_draws = [MagicMock(drwNo=1)]
    monkeypatch.setattr("lotto.scraper.scrape_all", lambda on_progress=None: fake_draws)

    mock_collector_instance = MagicMock()
    monkeypatch.setattr(
        "lotto.collector.LottoCollector", lambda *a, **kw: mock_collector_instance
    )
    monkeypatch.setattr(api, "_run_analyze_sync", lambda: None)

    invalidate_mock = MagicMock()
    monkeypatch.setattr("lotto.web.data.invalidate_cache", invalidate_mock)
    if hasattr(api, "invalidate_cache"):
        monkeypatch.setattr(api, "invalidate_cache", invalidate_mock)

    api._scrape_worker()

    assert invalidate_mock.called, "scrape worker 완료 후 invalidate_cache가 호출되어야 한다"
