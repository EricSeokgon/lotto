"""SPEC-LOTTO-171: 반소수 포함 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 반소수 {4,6,9,10,14,15,21,22,25,26,33,34,35,38,39}
SAMPLE_DRAWS = [
    # 4,6,9 포함 → 3개
    DrawResult(n1=4, n2=6, n3=9, n4=1, n5=2, n6=3, bonus=5, drwNo=1, date="2002-12-07"),
    # 없음 → 0개
    DrawResult(n1=1, n2=2, n3=3, n4=5, n5=7, n6=11, bonus=13, drwNo=2, date="2002-12-14"),
    # 10,14 포함 → 2개
    DrawResult(n1=10, n2=14, n3=17, n4=19, n5=23, n6=29, bonus=31, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_semiprime_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_semiprime_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_semiprime_analysis()
    assert result is not None
    for key in ("total", "semiprime_count", "semiprime_list", "avg", "expected",
                "diff", "best_count", "best_count_pct", "zero_pct", "dist_list",
                "freq_list", "recent"):
        assert key in result


def test_semiprime_count_is_15(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_semiprime_analysis()
    assert result is not None
    assert result["semiprime_count"] == 15


def test_semiprime_list_correct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_semiprime_analysis()
    assert result is not None
    assert result["semiprime_list"] == [4, 6, 9, 10, 14, 15, 21, 22, 25, 26, 33, 34, 35, 38, 39]


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_semiprime_analysis()
    assert result is not None
    assert abs(result["expected"] - round(15 / 45 * 6, 3)) < 0.001


def test_dist_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_semiprime_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 7  # 0~6개


def test_freq_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_semiprime_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 15


def test_recent_has_semiprimes_key(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_semiprime_analysis()
    assert result is not None
    for row in result["recent"]:
        assert "semiprimes" in row
        assert "count" in row


def test_semiprime_page_200():
    response = client.get("/stats/semiprime")
    assert response.status_code == 200
