"""SPEC-LOTTO-164: 합성수 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 합성수 예시: 4,6,8,9,10,12,14,15,16,18,20,21,22,24,25,26,27,28,30,...
SAMPLE_DRAWS = [
    DrawResult(n1=4, n2=6, n3=8, n4=9, n5=10, n6=12, bonus=14, drwNo=1, date="2002-12-07"),
    DrawResult(n1=2, n2=3, n3=5, n4=7, n5=11, n6=13, bonus=17, drwNo=2, date="2002-12-14"),
    DrawResult(n1=4, n2=6, n3=9, n4=7, n5=11, n6=25, bonus=30, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_composite_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert result is not None
    for key in ("total", "composite_count", "composites_list", "avg", "expected", "diff",
                "best_count", "best_count_pct", "zero_pct", "dist_list", "freq_list", "recent"):
        assert key in result


def test_composite_count_is_30(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert result is not None
    assert result["composite_count"] == 30


def test_composites_list_excludes_primes_and_one(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert result is not None
    assert 1 not in result["composites_list"]
    assert 2 not in result["composites_list"]
    assert 3 not in result["composites_list"]
    assert 4 in result["composites_list"]


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert result is not None
    assert abs(result["expected"] - round(30 / 45 * 6, 3)) < 0.001


def test_dist_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 7  # 0~6개


def test_freq_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 30


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_composite_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_composite_page_200():
    response = client.get("/stats/composite")
    assert response.status_code == 200
