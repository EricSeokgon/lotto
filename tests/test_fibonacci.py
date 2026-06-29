"""SPEC-LOTTO-160: 피보나치 수 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 피보나치 수: 1, 2, 3, 5, 8, 13, 21, 34
SAMPLE_DRAWS = [
    DrawResult(n1=1, n2=2, n3=3, n4=5, n5=8, n6=13, bonus=7, drwNo=1, date="2002-12-07"),
    DrawResult(n1=4, n2=6, n3=7, n4=9, n5=10, n6=11, bonus=12, drwNo=2, date="2002-12-14"),
    DrawResult(n1=1, n2=21, n3=34, n4=10, n5=20, n6=30, bonus=45, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_fibonacci_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_fibonacci_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_fibonacci_analysis()
    assert result is not None
    for key in ("total", "fib_count", "fib_list", "avg", "expected", "diff",
                "best_count", "best_count_pct", "zero_pct", "dist_list", "freq_list", "recent"):
        assert key in result


def test_fib_count_is_8(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_fibonacci_analysis()
    assert result is not None
    assert result["fib_count"] == 8


def test_fib_list_correct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_fibonacci_analysis()
    assert result is not None
    assert result["fib_list"] == [1, 2, 3, 5, 8, 13, 21, 34]


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_fibonacci_analysis()
    assert result is not None
    assert abs(result["expected"] - round(8 / 45 * 6, 3)) < 0.001


def test_dist_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_fibonacci_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 9  # 0~8개


def test_freq_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_fibonacci_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 8


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_fibonacci_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_fibonacci_page_200():
    response = client.get("/stats/fibonacci")
    assert response.status_code == 200
