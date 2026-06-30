"""SPEC-LOTTO-173: 하샤드 수 포함 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 하샤드 수 {1..9, 10, 12, 18, 20, 21, 24, 27, 30, 36, 40, 42, 45}
SAMPLE_DRAWS = [
    # 1, 2, 3 포함 → 3개
    DrawResult(n1=1, n2=2, n3=3, n4=11, n5=13, n6=17, bonus=19, drwNo=1, date="2002-12-07"),
    # 없음 → 0개 (소수들로만)
    DrawResult(n1=11, n2=13, n3=17, n4=19, n5=23, n6=29, bonus=31, drwNo=2, date="2002-12-14"),
    # 10, 12, 18 포함 → 3개
    DrawResult(n1=10, n2=12, n3=18, n4=11, n5=13, n6=17, bonus=19, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_harshad_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_harshad_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_harshad_analysis()
    assert result is not None
    for key in ("total", "harshad_count", "harshad_list", "avg", "expected",
                "diff", "best_count", "best_count_pct", "zero_pct", "dist_list",
                "freq_list", "recent"):
        assert key in result


def test_harshad_count_is_21(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_harshad_analysis()
    assert result is not None
    assert result["harshad_count"] == 21


def test_harshad_list_correct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_harshad_analysis()
    assert result is not None
    expected_list = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 18, 20, 21, 24, 27, 30, 36, 40, 42, 45]
    assert result["harshad_list"] == expected_list


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_harshad_analysis()
    assert result is not None
    assert abs(result["expected"] - round(21 / 45 * 6, 3)) < 0.001


def test_dist_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_harshad_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 7  # 0~6개


def test_freq_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_harshad_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 21


def test_recent_has_harshads_key(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_harshad_analysis()
    assert result is not None
    for row in result["recent"]:
        assert "harshads" in row
        assert "count" in row


def test_harshad_page_200():
    response = client.get("/stats/harshad")
    assert response.status_code == 200
