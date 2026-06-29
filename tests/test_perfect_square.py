"""SPEC-LOTTO-157: 완전제곱수 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 완전제곱수: 1, 4, 9, 16, 25, 36
SAMPLE_DRAWS = [
    DrawResult(n1=1, n2=4, n3=9, n4=16, n5=25, n6=36, bonus=7, drwNo=1, date="2002-12-07"),
    DrawResult(n1=2, n2=3, n3=5, n4=6, n5=7, n6=8, bonus=10, drwNo=2, date="2002-12-14"),
    DrawResult(n1=1, n2=9, n3=25, n4=10, n5=20, n6=30, bonus=45, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_perfect_square_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_square_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_square_analysis()
    assert result is not None
    for key in ("total", "square_count", "squares_list", "avg", "expected", "diff",
                "best_count", "best_count_pct", "zero_pct", "dist_list", "freq_list", "recent"):
        assert key in result


def test_square_count_is_6(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_square_analysis()
    assert result is not None
    assert result["square_count"] == 6


def test_squares_list_correct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_square_analysis()
    assert result is not None
    assert result["squares_list"] == [1, 4, 9, 16, 25, 36]


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_square_analysis()
    assert result is not None
    assert abs(result["expected"] - round(6 / 45 * 6, 3)) < 0.001


def test_dist_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_square_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 7  # 0~6개


def test_freq_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_square_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 6


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_square_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_perfect_square_page_200():
    response = client.get("/stats/perfect-square")
    assert response.status_code == 200
