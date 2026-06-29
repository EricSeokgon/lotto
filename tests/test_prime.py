"""SPEC-LOTTO-161: 소수 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 소수: 2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43
SAMPLE_DRAWS = [
    DrawResult(n1=2, n2=3, n3=5, n4=7, n5=11, n6=13, bonus=17, drwNo=1, date="2002-12-07"),
    DrawResult(n1=4, n2=6, n3=8, n4=9, n5=10, n6=12, bonus=14, drwNo=2, date="2002-12-14"),
    DrawResult(n1=2, n2=7, n3=23, n4=10, n5=20, n6=30, bonus=43, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_prime_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_prime_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_prime_analysis()
    assert result is not None
    for key in ("total", "prime_count", "primes_list", "avg", "expected", "diff",
                "best_count", "best_count_pct", "zero_pct", "dist_list", "freq_list", "recent"):
        assert key in result


def test_prime_count_is_14(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_prime_analysis()
    assert result is not None
    assert result["prime_count"] == 14


def test_primes_list_correct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_prime_analysis()
    assert result is not None
    assert result["primes_list"] == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43]


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_prime_analysis()
    assert result is not None
    assert abs(result["expected"] - round(14 / 45 * 6, 3)) < 0.001


def test_dist_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_prime_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 15  # 0~14개


def test_freq_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_prime_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 14


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_prime_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_prime_page_200():
    response = client.get("/stats/prime")
    assert response.status_code == 200
