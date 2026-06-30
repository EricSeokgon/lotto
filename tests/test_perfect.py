"""SPEC-LOTTO-175: 완전수 포함 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 완전수 {6, 28}
SAMPLE_DRAWS = [
    # 6 포함 → 1개
    DrawResult(n1=6, n2=2, n3=3, n4=4, n5=5, n6=7, bonus=8, drwNo=1, date="2002-12-07"),
    # 없음 → 0개
    DrawResult(n1=1, n2=2, n3=3, n4=4, n5=5, n6=7, bonus=8, drwNo=2, date="2002-12-14"),
    # 6, 28 포함 → 2개
    DrawResult(n1=6, n2=28, n3=3, n4=4, n5=5, n6=7, bonus=8, drwNo=3, date="2002-12-21"),
    # 28 포함 → 1개
    DrawResult(n1=28, n2=1, n3=2, n4=3, n5=4, n6=5, bonus=7, drwNo=4, date="2002-12-28"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_perfect_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_analysis()
    assert isinstance(result, dict)


def test_perfect_count(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_analysis()
    assert result["perfect_count"] == 2


def test_perfect_list(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_analysis()
    assert sorted(result["perfect_list"]) == [6, 28]


def test_dist_list_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_analysis()
    for row in result["dist_list"]:
        assert "count" in row
        assert "draws" in row
        assert "pct" in row


def test_dist_sum_equals_total(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_analysis()
    total_draws = sum(row["draws"] for row in result["dist_list"])
    assert total_draws == result["total"]


def test_freq_list_contents(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_analysis()
    nums = [row["number"] for row in result["freq_list"]]
    assert 6 in nums
    assert 28 in nums


def test_freq_count_6(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_analysis()
    row6 = next(r for r in result["freq_list"] if r["number"] == 6)
    # 회차 1, 3에 6 포함 → 2
    assert row6["count"] == 2


def test_recent_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_analysis()
    assert len(result["recent"]) == min(20, len(SAMPLE_DRAWS))


def test_http_perfect_page():
    resp = client.get("/stats/perfect")
    assert resp.status_code == 200
    assert "완전수" in resp.text
