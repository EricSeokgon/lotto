"""SPEC-LOTTO-168: 연속번호 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

SAMPLE_DRAWS = [
    # 1,2,3 연속 → 쌍 2개 (1-2, 2-3)
    DrawResult(n1=1, n2=2, n3=3, n4=10, n5=20, n6=30, bonus=40, drwNo=1, date="2002-12-07"),
    # 연속 없음
    DrawResult(n1=1, n2=3, n3=5, n4=7, n5=9, n6=11, bonus=13, drwNo=2, date="2002-12-14"),
    # 7,8 연속 → 쌍 1개
    DrawResult(n1=7, n2=8, n3=15, n4=25, n5=35, n6=45, bonus=2, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_consecutive_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_consecutive_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_consecutive_analysis()
    assert result is not None
    for key in ("total", "avg", "best_count", "best_count_pct", "zero_pct",
                "has_consecutive_pct", "dist_list", "recent"):
        assert key in result


def test_total_is_correct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_consecutive_analysis()
    assert result is not None
    assert result["total"] == 3


def test_zero_pct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_consecutive_analysis()
    assert result is not None
    # 3회차 중 1회차(drwNo=2)만 연속 없음 → 33.3%
    assert abs(result["zero_pct"] - round(1 / 3 * 100, 1)) < 0.1


def test_has_consecutive_pct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_consecutive_analysis()
    assert result is not None
    # 3회차 중 2회차 연속 포함 → 66.7%
    assert abs(result["has_consecutive_pct"] - round(2 / 3 * 100, 1)) < 0.1


def test_dist_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_consecutive_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 6  # 0~5쌍


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_consecutive_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_recent_has_consecutive_key(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_consecutive_analysis()
    assert result is not None
    for row in result["recent"]:
        assert "consecutive" in row
        assert "pairs" in row
        assert "count" in row


def test_consecutive_page_200():
    response = client.get("/stats/consecutive")
    assert response.status_code == 200
