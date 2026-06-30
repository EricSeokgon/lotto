"""SPEC-LOTTO-178: 칠각수 포함 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 칠각수 {1, 7, 18, 34}
SAMPLE_DRAWS = [
    # 1, 7 포함 → 2개
    DrawResult(n1=1, n2=7, n3=2, n4=3, n5=4, n6=8, bonus=9, drwNo=1, date="2002-12-07"),
    # 없음 → 0개
    DrawResult(n1=2, n2=3, n3=4, n4=8, n5=9, n6=10, bonus=11, drwNo=2, date="2002-12-14"),
    # 18, 34 포함 → 2개
    DrawResult(n1=18, n2=34, n3=2, n4=3, n5=4, n6=5, bonus=6, drwNo=3, date="2002-12-21"),
    # 1 포함 → 1개
    DrawResult(n1=1, n2=2, n3=3, n4=4, n5=8, n6=9, bonus=10, drwNo=4, date="2002-12-28"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_heptagonal_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_heptagonal_analysis()
    assert isinstance(result, dict)


def test_heptagon_count(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_heptagonal_analysis()
    assert result["heptagon_count"] == 4


def test_heptagon_list(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_heptagonal_analysis()
    assert sorted(result["heptagon_list"]) == [1, 7, 18, 34]


def test_dist_list_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_heptagonal_analysis()
    for row in result["dist_list"]:
        assert "count" in row
        assert "draws" in row
        assert "pct" in row


def test_dist_sum_equals_total(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_heptagonal_analysis()
    total_draws = sum(row["draws"] for row in result["dist_list"])
    assert total_draws == result["total"]


def test_page_route_ok(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    resp = client.get("/stats/heptagonal")
    assert resp.status_code == 200


def test_page_route_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    resp = client.get("/stats/heptagonal")
    assert resp.status_code == 200


def test_freq_list_formula(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_heptagonal_analysis()
    formulas = {row["number"]: row["formula"] for row in result["freq_list"]}
    assert formulas[1] == "1×(5×1-3)÷2"
    assert formulas[34] == "4×(5×4-3)÷2"


def test_recent_limited_to_20(monkeypatch):
    many_draws = [
        DrawResult(n1=2, n2=3, n3=4, n4=8, n5=9, n6=10, bonus=11, drwNo=i, date="2002-12-07")
        for i in range(1, 31)
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: many_draws)
    result = wd.get_heptagonal_analysis()
    assert len(result["recent"]) == 20
