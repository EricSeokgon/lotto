"""SPEC-LOTTO-144: 3의 배수 분포 분석 테스트."""

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web import data as wd

client = TestClient(app)

SAMPLE_DRAWS = [
    DrawResult(n1=3, n2=6, n3=9, n4=12, n5=15, n6=18, bonus=21, drwNo=1, date="2002-12-07"),
    DrawResult(n1=1, n2=2, n3=4, n4=5, n5=7, n6=8, bonus=10, drwNo=2, date="2002-12-14"),
    DrawResult(n1=3, n2=10, n3=15, n4=20, n5=21, n6=27, bonus=30, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    result = wd.get_multiples3_analysis()
    assert result is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples3_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples3_analysis()
    assert result is not None
    for key in ["total", "mult3_count", "avg", "expected", "diff",
                "best_count", "dist_list", "freq_list", "recent"]:
        assert key in result, f"Missing key: {key}"


def test_mult3_count_is_15(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples3_analysis()
    assert result is not None
    assert result["mult3_count"] == 15


def test_expected_is_2(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples3_analysis()
    assert result is not None
    assert result["expected"] == 2.0


def test_dist_list_length_is_7(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples3_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 7


def test_freq_list_length_is_15(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples3_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 15


def test_diff_calculation(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples3_analysis()
    assert result is not None
    assert round(result["avg"] - result["expected"], 3) == result["diff"]


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples3_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_multiples3_page_200():
    response = client.get("/stats/multiples-3")
    assert response.status_code == 200
