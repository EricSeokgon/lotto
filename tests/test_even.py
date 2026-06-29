"""SPEC-LOTTO-162: 짝수 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

SAMPLE_DRAWS = [
    DrawResult(n1=2, n2=4, n3=6, n4=8, n5=10, n6=12, bonus=14, drwNo=1, date="2002-12-07"),
    DrawResult(n1=1, n2=3, n3=5, n4=7, n5=9, n6=11, bonus=13, drwNo=2, date="2002-12-14"),
    DrawResult(n1=2, n2=3, n3=4, n4=5, n5=6, n6=7, bonus=8, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_even_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_even_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_even_analysis()
    assert result is not None
    for key in ("total", "even_count", "evens_list", "avg", "expected", "diff",
                "best_count", "best_count_pct", "zero_pct", "dist_list", "freq_list", "recent"):
        assert key in result


def test_even_count_is_22(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_even_analysis()
    assert result is not None
    assert result["even_count"] == 22


def test_evens_list_correct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_even_analysis()
    assert result is not None
    assert result["evens_list"] == list(range(2, 46, 2))


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_even_analysis()
    assert result is not None
    assert abs(result["expected"] - round(22 / 45 * 6, 3)) < 0.001


def test_dist_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_even_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 7  # 0~6개


def test_freq_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_even_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 22


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_even_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_even_page_200():
    response = client.get("/stats/even")
    assert response.status_code == 200
