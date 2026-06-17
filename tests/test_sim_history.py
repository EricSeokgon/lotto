"""SPEC-LOTTO-048: 시뮬레이션 결과 저장 영속화 단위 테스트.

REQ: save_simulation_result / list_simulation_results /
     delete_simulation_result / get_simulation_result.

각 테스트는 임시 sim_history.json 경로로 격리하여 실제 사용자 데이터를
오염시키지 않으며 결정론적으로 동작한다 (favorites/reservations 패턴 차용).
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from lotto.web import data as wd


@pytest.fixture(autouse=True)
def isolate_sim_history_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[None, None, None]:
    """각 테스트마다 임시 sim_history.json 경로로 격리한다."""
    sim_history_file = tmp_path / "sim_history.json"
    monkeypatch.setattr("lotto.web.data._SIM_HISTORY_PATH", sim_history_file)
    yield


def _entry(label: str = "내 전략 A") -> dict:
    """저장용 입력 엔트리 (id/created_at은 저장 함수가 부여)."""
    return {
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
    }


# ─── save ────────────────────────────────────────────────────────────────────


def test_save_returns_entry_with_id() -> None:
    """저장 시 8자리 id와 created_at(ISO)을 부여한 엔트리를 반환한다."""
    saved = wd.save_simulation_result(_entry())
    assert isinstance(saved["id"], str) and len(saved["id"]) == 8
    assert "created_at" in saved and "T" in saved["created_at"]
    assert saved["label"] == "내 전략 A"
    assert saved["strategy"] == "random"
    assert saved["numbers"] == [1, 7, 14, 21, 35, 42]
    assert saved["iterations"] == 1000
    assert saved["rank_counts"]["3등"] == 5  # noqa: PLR2004


# ─── list ──────────────────────────────────────────────────────────────────


def test_list_newest_first() -> None:
    """목록은 최신 저장이 가장 앞에 오도록 반환한다."""
    first = wd.save_simulation_result(_entry("첫번째"))
    second = wd.save_simulation_result(_entry("두번째"))
    results = wd.list_simulation_results()
    assert [r["id"] for r in results] == [second["id"], first["id"]]
    assert results[0]["label"] == "두번째"


def test_empty_store_returns_empty_list() -> None:
    """저장된 항목이 없으면 빈 리스트를 반환한다."""
    assert wd.list_simulation_results() == []


# ─── delete ────────────────────────────────────────────────────────────────


def test_delete_existing_returns_true() -> None:
    """존재하는 id를 삭제하면 True를 반환하고 목록에서 제거된다."""
    saved = wd.save_simulation_result(_entry())
    assert wd.delete_simulation_result(saved["id"]) is True
    assert wd.list_simulation_results() == []


def test_delete_missing_returns_false() -> None:
    """존재하지 않는 id 삭제는 False를 반환한다."""
    assert wd.delete_simulation_result("nonexist") is False


# ─── get ───────────────────────────────────────────────────────────────────


def test_get_by_id_returns_entry() -> None:
    """저장한 id로 단건을 조회할 수 있다."""
    saved = wd.save_simulation_result(_entry("조회용"))
    fetched = wd.get_simulation_result(saved["id"])
    assert fetched is not None
    assert fetched["id"] == saved["id"]
    assert fetched["label"] == "조회용"


def test_get_missing_returns_none() -> None:
    """존재하지 않는 id 조회는 None을 반환한다."""
    assert wd.get_simulation_result("nonexist") is None


# ─── persistence round-trip ──────────────────────────────────────────────────


def test_persistence_round_trip() -> None:
    """디스크에 기록한 뒤 다시 읽어도 동일한 데이터가 유지된다."""
    saved = wd.save_simulation_result(_entry("왕복"))
    # 새로 list를 읽어 디스크에서 복원되는지 확인
    results = wd.list_simulation_results()
    assert len(results) == 1
    restored = results[0]
    assert restored["id"] == saved["id"]
    assert restored["rank_counts"] == saved["rank_counts"]
    assert restored["roi"] == saved["roi"]
