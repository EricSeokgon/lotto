"""SPEC-LOTTO-176: 오각수 포함 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 오각수 {1, 5, 12, 22, 35}
SAMPLE_DRAWS = [
    # 1, 5 포함 → 2개
    DrawResult(n1=1, n2=5, n3=2, n4=3, n5=4, n6=6, bonus=7, drwNo=1, date="2002-12-07"),
    # 없음 → 0개
    DrawResult(n1=2, n2=3, n3=4, n4=6, n5=7, n6=8, bonus=9, drwNo=2, date="2002-12-14"),
    # 12, 22, 35 포함 → 3개
    DrawResult(n1=12, n2=22, n3=35, n4=2, n5=3, n6=4, bonus=5, drwNo=3, date="2002-12-21"),
    # 1 포함 → 1개
    DrawResult(n1=1, n2=2, n3=3, n4=4, n5=6, n6=7, bonus=8, drwNo=4, date="2002-12-28"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_pentagonal_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_pentagonal_analysis()
    assert isinstance(result, dict)


def test_pentagon_count(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_pentagonal_analysis()
    assert result["pentagon_count"] == 5


def test_pentagon_list(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_pentagonal_analysis()
    assert sorted(result["pentagon_list"]) == [1, 5, 12, 22, 35]


def test_dist_list_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_pentagonal_analysis()
    for row in result["dist_list"]:
        assert "count" in row
        assert "draws" in row
        assert "pct" in row


def test_dist_sum_equals_total(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_pentagonal_analysis()
    total_draws = sum(row["draws"] for row in result["dist_list"])
    assert total_draws == result["total"]


def test_freq_list_numbers(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_pentagonal_analysis()
    nums = [row["number"] for row in result["freq_list"]]
    for p in [1, 5, 12, 22, 35]:
        assert p in nums


def test_freq_count_1(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_pentagonal_analysis()
    row1 = next(r for r in result["freq_list"] if r["number"] == 1)
    # 회차 1, 4에 1 포함 → 2
    assert row1["count"] == 2


def test_recent_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_pentagonal_analysis()
    assert len(result["recent"]) == min(20, len(SAMPLE_DRAWS))


def test_http_pentagonal_page():
    resp = client.get("/stats/pentagonal")
    assert resp.status_code == 200
    assert "오각수" in resp.text
