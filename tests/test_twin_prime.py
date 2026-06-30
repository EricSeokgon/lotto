"""SPEC-LOTTO-170: 쌍둥이 소수 포함 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 쌍둥이 소수 {3,5,7,11,13,17,19,29,31,41,43}
SAMPLE_DRAWS = [
    # 3,5,7 포함 → 3개
    DrawResult(n1=3, n2=5, n3=7, n4=10, n5=20, n6=30, bonus=40, drwNo=1, date="2002-12-07"),
    # 없음 → 0개
    DrawResult(n1=2, n2=4, n3=6, n4=8, n5=10, n6=12, bonus=14, drwNo=2, date="2002-12-14"),
    # 11,13 포함 → 2개
    DrawResult(n1=11, n2=13, n3=20, n4=30, n5=40, n6=44, bonus=45, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_twin_prime_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_twin_prime_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_twin_prime_analysis()
    assert result is not None
    for key in ("total", "twin_count", "twin_list", "twin_pairs", "avg", "expected",
                "diff", "best_count", "best_count_pct", "zero_pct", "dist_list",
                "freq_list", "recent"):
        assert key in result


def test_twin_count_is_11(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_twin_prime_analysis()
    assert result is not None
    assert result["twin_count"] == 11


def test_twin_list_correct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_twin_prime_analysis()
    assert result is not None
    assert result["twin_list"] == [3, 5, 7, 11, 13, 17, 19, 29, 31, 41, 43]


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_twin_prime_analysis()
    assert result is not None
    assert abs(result["expected"] - round(11 / 45 * 6, 3)) < 0.001


def test_dist_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_twin_prime_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 7  # 0~6개


def test_recent_has_twin_primes_key(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_twin_prime_analysis()
    assert result is not None
    for row in result["recent"]:
        assert "twin_primes" in row
        assert "count" in row


def test_zero_pct_correct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_twin_prime_analysis()
    assert result is not None
    # 3개 중 1개가 0개 회차 → 33.3%
    assert abs(result["zero_pct"] - round(1 / 3 * 100, 1)) < 0.5


def test_twin_prime_page_200():
    response = client.get("/stats/twin-prime")
    assert response.status_code == 200
