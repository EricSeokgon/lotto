"""SPEC-LOTTO-174: 삼각수 포함 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 삼각수 {1,3,6,10,15,21,28,36,45}
SAMPLE_DRAWS = [
    # 1, 3, 6 포함 → 3개
    DrawResult(n1=1, n2=3, n3=6, n4=2, n5=4, n6=5, bonus=7, drwNo=1, date="2002-12-07"),
    # 없음 → 0개
    DrawResult(n1=2, n2=4, n3=5, n4=7, n5=8, n6=9, bonus=11, drwNo=2, date="2002-12-14"),
    # 10, 15 포함 → 2개
    DrawResult(n1=10, n2=15, n3=11, n4=13, n5=17, n6=19, bonus=23, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_triangular_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_analysis()
    assert result is not None
    for key in ("total", "triangular_count", "triangular_list", "avg", "expected",
                "diff", "best_count", "best_count_pct", "zero_pct", "dist_list",
                "freq_list", "recent"):
        assert key in result


def test_triangular_count_is_9(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_analysis()
    assert result is not None
    assert result["triangular_count"] == 9


def test_triangular_list_correct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_analysis()
    assert result is not None
    assert result["triangular_list"] == [1, 3, 6, 10, 15, 21, 28, 36, 45]


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_analysis()
    assert result is not None
    assert abs(result["expected"] - round(9 / 45 * 6, 3)) < 0.001


def test_freq_list_has_n_key(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_analysis()
    assert result is not None
    for row in result["freq_list"]:
        assert "n" in row
        assert "number" in row


def test_freq_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 9


def test_recent_has_triangulars_key(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_triangular_analysis()
    assert result is not None
    for row in result["recent"]:
        assert "triangulars" in row
        assert "count" in row


def test_triangular_page_200():
    response = client.get("/stats/triangular")
    assert response.status_code == 200
