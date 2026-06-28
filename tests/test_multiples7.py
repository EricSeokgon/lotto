"""SPEC-LOTTO-146: 7의 배수 분포 분석 테스트."""

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

SAMPLE_DRAWS = [
    DrawResult(n1=7, n2=14, n3=21, n4=28, n5=35, n6=42, bonus=1, drwNo=1, date="2002-12-07"),
    DrawResult(n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=8, drwNo=2, date="2002-12-14"),
    DrawResult(n1=7, n2=11, n3=21, n4=22, n5=30, n6=40, bonus=45, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    result = wd.get_multiples7_analysis()
    assert result is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples7_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples7_analysis()
    assert result is not None
    for key in ["total", "mult7_count", "avg", "expected", "diff",
                "best_count", "dist_list", "freq_list", "recent"]:
        assert key in result, f"Missing key: {key}"


def test_mult7_count_is_6(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples7_analysis()
    assert result is not None
    assert result["mult7_count"] == 6


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples7_analysis()
    assert result is not None
    assert result["expected"] == round(6 / 45 * 6, 3)


def test_dist_list_length_is_7(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples7_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 7


def test_freq_list_length_is_6(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples7_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 6


def test_diff_calculation(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples7_analysis()
    assert result is not None
    assert round(result["avg"] - result["expected"], 3) == result["diff"]


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples7_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_multiples7_page_200():
    response = client.get("/stats/multiples-7")
    assert response.status_code == 200
