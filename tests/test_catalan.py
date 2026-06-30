"""SPEC-LOTTO-172: 카탈란 수 포함 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 카탈란 수 {1, 2, 5, 14, 42}
SAMPLE_DRAWS = [
    # 1, 2, 5 포함 → 3개
    DrawResult(n1=1, n2=2, n3=5, n4=10, n5=20, n6=30, bonus=40, drwNo=1, date="2002-12-07"),
    # 없음 → 0개
    DrawResult(n1=3, n2=4, n3=6, n4=7, n5=8, n6=9, bonus=11, drwNo=2, date="2002-12-14"),
    # 14, 42 포함 → 2개
    DrawResult(n1=14, n2=42, n3=17, n4=19, n5=23, n6=29, bonus=31, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_catalan_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_catalan_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_catalan_analysis()
    assert result is not None
    for key in ("total", "catalan_count", "catalan_list", "catalan_info", "avg",
                "expected", "diff", "best_count", "best_count_pct", "zero_pct",
                "dist_list", "freq_list", "recent"):
        assert key in result


def test_catalan_count_is_5(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_catalan_analysis()
    assert result is not None
    assert result["catalan_count"] == 5


def test_catalan_list_correct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_catalan_analysis()
    assert result is not None
    assert result["catalan_list"] == [1, 2, 5, 14, 42]


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_catalan_analysis()
    assert result is not None
    assert abs(result["expected"] - round(5 / 45 * 6, 3)) < 0.001


def test_dist_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_catalan_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 6  # 0~5개


def test_freq_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_catalan_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 5


def test_recent_has_catalans_key(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_catalan_analysis()
    assert result is not None
    for row in result["recent"]:
        assert "catalans" in row
        assert "count" in row


def test_catalan_page_200():
    response = client.get("/stats/catalan")
    assert response.status_code == 200
