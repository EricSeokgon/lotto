"""SPEC-LOTTO-169: 번호 합계 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

SAMPLE_DRAWS = [
    # 합계 = 1+2+3+4+5+6 = 21 (극소)
    DrawResult(n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7, drwNo=1, date="2002-12-07"),
    # 합계 = 10+20+30+40+41+42 = 183 (고)
    DrawResult(n1=10, n2=20, n3=30, n4=40, n5=41, n6=42, bonus=43, drwNo=2, date="2002-12-14"),
    # 합계 = 15+25+35+20+21+22 = 138 (평균 근처)
    DrawResult(n1=15, n2=20, n3=21, n4=22, n5=25, n6=35, bonus=10, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_sum_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_sum_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_sum_analysis()
    assert result is not None
    for key in ("total", "theoretical_avg", "actual_avg", "diff",
                "min_sum", "max_sum", "best_range", "best_range_pct", "ranges", "recent"):
        assert key in result


def test_theoretical_avg_is_138(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_sum_analysis()
    assert result is not None
    assert abs(result["theoretical_avg"] - 138.0) < 0.01


def test_min_max_sum(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_sum_analysis()
    assert result is not None
    assert result["min_sum"] == 21
    assert result["max_sum"] == 183


def test_ranges_count(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_sum_analysis()
    assert result is not None
    assert len(result["ranges"]) == 6


def test_ranges_pct_sum(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_sum_analysis()
    assert result is not None
    total_pct = sum(r["pct"] for r in result["ranges"])
    assert abs(total_pct - 100.0) < 0.5


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_sum_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_recent_has_sum_key(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_sum_analysis()
    assert result is not None
    for row in result["recent"]:
        assert "sum" in row
        assert "diff" in row


def test_sum_page_200():
    response = client.get("/stats/sum")
    assert response.status_code == 200
