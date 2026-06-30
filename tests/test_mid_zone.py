"""SPEC-LOTTO-166: 중구간(16~30) 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

SAMPLE_DRAWS = [
    DrawResult(n1=16, n2=17, n3=18, n4=19, n5=20, n6=21, bonus=22, drwNo=1, date="2002-12-07"),
    DrawResult(n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7, drwNo=2, date="2002-12-14"),
    DrawResult(n1=16, n2=20, n3=25, n4=5, n5=35, n6=40, bonus=45, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_mid_zone_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_mid_zone_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_mid_zone_analysis()
    assert result is not None
    for key in ("total", "zone_count", "zone_list", "avg", "expected", "diff",
                "best_count", "best_count_pct", "zero_pct", "dist_list", "freq_list", "recent"):
        assert key in result


def test_zone_count_is_15(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_mid_zone_analysis()
    assert result is not None
    assert result["zone_count"] == 15


def test_zone_list_is_16_to_30(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_mid_zone_analysis()
    assert result is not None
    assert result["zone_list"] == list(range(16, 31))


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_mid_zone_analysis()
    assert result is not None
    assert abs(result["expected"] - round(15 / 45 * 6, 3)) < 0.001


def test_dist_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_mid_zone_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 7  # 0~6개


def test_freq_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_mid_zone_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 15


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_mid_zone_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_mid_zone_page_200():
    response = client.get("/stats/mid-zone")
    assert response.status_code == 200
