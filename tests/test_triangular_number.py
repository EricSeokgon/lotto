"""SPEC-LOTTO-158: 삼각수 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 삼각수: 1, 3, 6, 10, 15, 21, 28, 36, 45
SAMPLE_DRAWS = [
    DrawResult(n1=1, n2=3, n3=6, n4=10, n5=15, n6=21, bonus=7, drwNo=1, date="2002-12-07"),
    DrawResult(n1=2, n2=4, n3=5, n4=7, n5=8, n6=9, bonus=11, drwNo=2, date="2002-12-14"),
    DrawResult(n1=1, n2=6, n3=28, n4=36, n5=45, n6=10, bonus=20, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_triangular_number_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_number_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_number_analysis()
    assert result is not None
    for key in ("total", "tri_count", "tri_list", "avg", "expected", "diff",
                "best_count", "best_count_pct", "zero_pct", "dist_list", "freq_list", "recent"):
        assert key in result


def test_tri_count_is_9(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_number_analysis()
    assert result is not None
    assert result["tri_count"] == 9


def test_tri_list_correct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_number_analysis()
    assert result is not None
    assert result["tri_list"] == [1, 3, 6, 10, 15, 21, 28, 36, 45]


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_number_analysis()
    assert result is not None
    assert abs(result["expected"] - round(9 / 45 * 6, 3)) < 0.001


def test_dist_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_number_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 10  # 0~9개


def test_freq_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_number_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 9


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_number_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_triangular_number_page_200():
    response = client.get("/stats/triangular-number")
    assert response.status_code == 200
