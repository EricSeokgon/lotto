"""SPEC-LOTTO-153: 31의 배수 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

SAMPLE_DRAWS = [
    DrawResult(n1=31, n2=1, n3=2, n4=3, n5=4, n6=5, bonus=7, drwNo=1, date="2002-12-07"),
    DrawResult(n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=8, drwNo=2, date="2002-12-14"),
    DrawResult(n1=31, n2=10, n3=20, n4=30, n5=40, n6=6, bonus=45, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_multiples31_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples31_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples31_analysis()
    assert result is not None
    for key in ("total", "mult31_count", "avg", "expected", "diff", "best_count",
                "best_count_pct", "zero_pct", "dist_list", "freq_list", "recent"):
        assert key in result


def test_mult31_count_is_1(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples31_analysis()
    assert result is not None
    assert result["mult31_count"] == 1


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples31_analysis()
    assert result is not None
    assert abs(result["expected"] - round(1 / 45 * 6, 3)) < 0.001


def test_dist_list_length_is_2(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples31_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 2


def test_freq_list_length_is_1(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples31_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 1


def test_diff_calculation(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples31_analysis()
    assert result is not None
    assert abs(result["diff"] - round(result["avg"] - result["expected"], 3)) < 0.001


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_multiples31_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_multiples31_page_200():
    response = client.get("/stats/multiples-31")
    assert response.status_code == 200
