"""SPEC-LOTTO-177: 육각수 포함 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 육각수 {1, 6, 15, 28, 45}
SAMPLE_DRAWS = [
    # 1, 6 포함 → 2개
    DrawResult(n1=1, n2=6, n3=2, n4=3, n5=4, n6=7, bonus=8, drwNo=1, date="2002-12-07"),
    # 없음 → 0개
    DrawResult(n1=2, n2=3, n3=4, n4=7, n5=8, n6=9, bonus=10, drwNo=2, date="2002-12-14"),
    # 15, 28, 45 포함 → 3개
    DrawResult(n1=15, n2=28, n3=45, n4=2, n5=3, n6=4, bonus=5, drwNo=3, date="2002-12-21"),
    # 1 포함 → 1개
    DrawResult(n1=1, n2=2, n3=3, n4=4, n5=7, n6=8, bonus=9, drwNo=4, date="2002-12-28"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_hexagonal_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_hexagonal_analysis()
    assert isinstance(result, dict)


def test_hexagon_count(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_hexagonal_analysis()
    assert result["hexagon_count"] == 5


def test_hexagon_list(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_hexagonal_analysis()
    assert sorted(result["hexagon_list"]) == [1, 6, 15, 28, 45]


def test_dist_list_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_hexagonal_analysis()
    for row in result["dist_list"]:
        assert "count" in row
        assert "draws" in row
        assert "pct" in row


def test_dist_sum_equals_total(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_hexagonal_analysis()
    total_draws = sum(row["draws"] for row in result["dist_list"])
    assert total_draws == result["total"]


def test_page_route_ok(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    resp = client.get("/stats/hexagonal")
    assert resp.status_code == 200


def test_page_route_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    resp = client.get("/stats/hexagonal")
    assert resp.status_code == 200


def test_freq_list_formula(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_hexagonal_analysis()
    formulas = {row["number"]: row["formula"] for row in result["freq_list"]}
    assert formulas[1] == "1×(2×1-1)"
    assert formulas[45] == "5×(2×5-1)"


def test_recent_limited_to_20(monkeypatch):
    many_draws = [
        DrawResult(n1=2, n2=3, n3=4, n4=7, n5=8, n6=9, bonus=10, drwNo=i, date="2002-12-07")
        for i in range(1, 31)
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: many_draws)
    result = wd.get_hexagonal_analysis()
    assert len(result["recent"]) == 20
