"""SPEC-LOTTO-159: 세제곱수 분포 분석 테스트."""
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web import data as wd
from lotto.web.app import app

client = TestClient(app)

# 세제곱수: 1, 8, 27 (4³=64 범위 초과)
SAMPLE_DRAWS = [
    DrawResult(n1=1, n2=8, n3=27, n4=2, n5=3, n6=4, bonus=5, drwNo=1, date="2002-12-07"),
    DrawResult(n1=2, n2=3, n3=4, n4=5, n5=6, n6=7, bonus=10, drwNo=2, date="2002-12-14"),
    DrawResult(n1=1, n2=8, n3=10, n4=20, n5=30, n6=40, bonus=45, drwNo=3, date="2002-12-21"),
]


def test_returns_none_when_empty(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: [])
    assert wd.get_perfect_cube_analysis() is None


def test_returns_dict(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_cube_analysis()
    assert isinstance(result, dict)


def test_required_keys(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_cube_analysis()
    assert result is not None
    for key in ("total", "cube_count", "cubes_list", "avg", "expected", "diff",
                "best_count", "best_count_pct", "zero_pct", "dist_list", "freq_list", "recent"):
        assert key in result


def test_cube_count_is_3(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_cube_analysis()
    assert result is not None
    assert result["cube_count"] == 3


def test_cubes_list_correct(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_cube_analysis()
    assert result is not None
    assert result["cubes_list"] == [1, 8, 27]


def test_expected_value(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_cube_analysis()
    assert result is not None
    assert abs(result["expected"] - round(3 / 45 * 6, 3)) < 0.001


def test_dist_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_cube_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 4  # 0~3개


def test_freq_list_length(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_cube_analysis()
    assert result is not None
    assert len(result["freq_list"]) == 3


def test_recent_length_lte_20(monkeypatch):
    monkeypatch.setattr(wd, "get_draws", lambda: SAMPLE_DRAWS)
    result = wd.get_perfect_cube_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_perfect_cube_page_200():
    response = client.get("/stats/perfect-cube")
    assert response.status_code == 200
