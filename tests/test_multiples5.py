"""SPEC-LOTTO-145: 5의 배수 분포 분석 테스트."""

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

SAMPLE_DRAWS = [
    DrawResult(n1=5, n2=10, n3=15, n4=20, n5=25, n6=30, bonus=35, drwNo=1, date="2002-12-07"),
    DrawResult(n1=1, n2=2, n3=3, n4=4, n5=6, n6=7, bonus=8, drwNo=2, date="2002-12-14"),
    DrawResult(n1=5, n2=11, n3=15, n4=21, n5=30, n6=40, bonus=45, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    result = wd.get_multiples5_analysis()
    assert result is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples5_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples5_analysis()
    assert result is not None
    for key in ["total", "mult5_count", "avg", "expected", "diff",
                "best_count", "dist_list", "freq_list", "recent"]:
        assert key in result, f"Missing key: {key}"


def test_mult5_count_is_9(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples5_analysis()
    assert result is not None
    assert result["mult5_count"] == 9


def test_expected_is_1_2(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples5_analysis()
    assert result is not None
    assert result["expected"] == 1.2


def test_dist_list_length_is_7(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples5_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 7


def test_freq_list_length_is_9(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples5_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 9


def test_diff_calculation(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples5_analysis()
    assert result is not None
    assert round(result["avg"] - result["expected"], 3) == result["diff"]


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples5_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_multiples5_page_200():
    response = client.get("/stats/multiples-5")
    assert response.status_code == 200
