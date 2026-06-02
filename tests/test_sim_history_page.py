"""SPEC-LOTTO-048: GET /simulation-history 페이지 + 네비게이션 링크 테스트.

페이지 렌더링 → 200, 저장 데이터 표시, 데이터 부재 시 빈 상태,
인덱스 페이지에 /simulation-history 네비 링크 노출을 검증한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lotto.web.app import app


@pytest.fixture(autouse=True)
def isolate_sim_history_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """각 테스트마다 임시 sim_history.json 경로로 격리한다."""
    sim_history_file = tmp_path / "sim_history.json"
    monkeypatch.setattr("lotto.web.data._SIM_HISTORY_PATH", sim_history_file)


def _save(label: str) -> None:
    from lotto.web import data as wd

    wd.save_simulation_result({
        "label": label,
        "strategy": "random",
        "numbers": [1, 7, 14, 21, 35, 42],
        "iterations": 1000,
        "rank_counts": {
            "1등": 0, "2등": 1, "3등": 5, "4등": 50, "5등": 200, "낙첨": 744,
        },
        "total_spent": 1000000,
        "total_won": 250000,
        "roi": -0.75,
    })


def test_page_returns_200_html() -> None:
    """GET /simulation-history → 200 HTML, 페이지 제목 포함."""
    c = TestClient(app)
    res = c.get("/simulation-history")
    assert res.status_code == 200, res.text
    assert "시뮬레이션 기록" in res.text


def test_page_shows_saved_entries() -> None:
    """저장된 결과가 있으면 라벨이 페이지에 노출된다."""
    _save("표시될 전략")
    c = TestClient(app)
    res = c.get("/simulation-history")
    assert res.status_code == 200, res.text
    assert "표시될 전략" in res.text


def test_page_empty_state_when_none() -> None:
    """저장된 결과가 없으면 빈 상태 안내가 노출된다."""
    c = TestClient(app)
    res = c.get("/simulation-history")
    assert res.status_code == 200, res.text
    assert "저장된 시뮬레이션 결과가 없습니다" in res.text


def test_index_has_sim_history_nav_link() -> None:
    """GET / 응답 HTML에 /simulation-history 네비게이션 링크가 포함된다."""
    c = TestClient(app)
    res = c.get("/")
    assert res.status_code == 200
    assert 'href="/simulation-history"' in res.text
