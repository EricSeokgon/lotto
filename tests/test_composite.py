"""SPEC-LOTTO-143: 합성수(Composite Number) 분포 분석 테스트."""

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web import data as wd

client = TestClient(app)

SAMPLE_DRAWS = [
    DrawResult(n1=4, n2=6, n3=8, n4=9, n5=10, n6=12, bonus=14, drwNo=1, date="2002-12-07"),
    DrawResult(n1=2, n2=3, n3=5, n4=7, n5=11, n6=13, bonus=17, drwNo=2, date="2002-12-14"),
    DrawResult(n1=4, n2=14, n3=15, n4=16, n5=18, n6=20, bonus=21, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    result = wd.get_composite_analysis()
    assert result is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert result is not None
    for key in ["total", "composite_count", "avg_comp", "expected", "diff",
                "best_count", "dist_list", "freq_list", "bottom_list", "recent"]:
        assert key in result, f"Missing key: {key}"


def test_composite_count_is_30(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert result is not None
    assert result["composite_count"] == 30


def test_expected_is_4(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert result is not None
    assert result["expected"] == 4.0


def test_dist_list_length_is_7(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 7


def test_freq_list_lte_15(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert result is not None
    assert len(result["freq_list"]) <= 15


def test_bottom_list_lte_5(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert result is not None
    assert len(result["bottom_list"]) <= 5


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_composite_page_200():
    response = client.get("/stats/composite")
    assert response.status_code == 200
