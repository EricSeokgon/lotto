"""SPEC-LOTTO-119 번호 조합 가이드 테스트."""

from __future__ import annotations

import datetime
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_combo_guide

client = TestClient(app)


def _make_draw(drw_no: int, nums: list[int]) -> DrawResult:
    return DrawResult(
        drwNo=drw_no,
        date=datetime.date(2020, 1, 4),
        n1=nums[0], n2=nums[1], n3=nums[2],
        n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=45,
    )


SAMPLE_DRAWS = [
    _make_draw(1, [1, 2, 3, 4, 5, 6]),    # odd=3, sum=21, consec=5
    _make_draw(2, [7, 14, 21, 28, 35, 42]), # odd=4, sum=147, consec=0
    _make_draw(3, [3, 11, 22, 33, 40, 44]), # odd=3, sum=153, consec=0
    _make_draw(4, [5, 10, 15, 20, 25, 30]), # odd=3, sum=105, consec=0
    _make_draw(5, [2, 13, 24, 31, 38, 45]), # odd=3, sum=153, consec=0
]


def test_get_combo_guide_returns_none_when_empty():
    with patch("lotto.web.data.get_draws", return_value=[]):
        assert get_combo_guide() is None


def test_get_combo_guide_returns_dict():
    with patch("lotto.web.data.get_draws", return_value=SAMPLE_DRAWS):
        result = get_combo_guide()
    assert isinstance(result, dict)


def test_get_combo_guide_has_required_keys():
    with patch("lotto.web.data.get_draws", return_value=SAMPLE_DRAWS):
        result = get_combo_guide()
    assert result is not None
    for key in ("total", "odd_dist", "best_odd", "best_odd_pct",
                 "sum_labels", "sum_dist", "best_sum_label", "best_sum_pct",
                 "consec_dist", "best_consec", "best_consec_pct",
                 "zone_dist", "best_zone", "best_zone_pct",
                 "low_dist", "best_low", "best_low_pct"):
        assert key in result, f"Missing key: {key}"


def test_get_combo_guide_total():
    with patch("lotto.web.data.get_draws", return_value=SAMPLE_DRAWS):
        result = get_combo_guide()
    assert result is not None
    assert result["total"] == len(SAMPLE_DRAWS)


def test_get_combo_guide_odd_dist_sums_to_total():
    with patch("lotto.web.data.get_draws", return_value=SAMPLE_DRAWS):
        result = get_combo_guide()
    assert result is not None
    assert sum(result["odd_dist"].values()) == result["total"]


def test_get_combo_guide_sum_dist_sums_to_total():
    with patch("lotto.web.data.get_draws", return_value=SAMPLE_DRAWS):
        result = get_combo_guide()
    assert result is not None
    assert sum(result["sum_dist"]) == result["total"]


def test_get_combo_guide_consec_dist_sums_to_total():
    with patch("lotto.web.data.get_draws", return_value=SAMPLE_DRAWS):
        result = get_combo_guide()
    assert result is not None
    assert sum(result["consec_dist"].values()) == result["total"]


def test_get_combo_guide_zone_dist_sums_to_total():
    with patch("lotto.web.data.get_draws", return_value=SAMPLE_DRAWS):
        result = get_combo_guide()
    assert result is not None
    assert sum(result["zone_dist"].values()) == result["total"]


def test_get_combo_guide_low_dist_sums_to_total():
    with patch("lotto.web.data.get_draws", return_value=SAMPLE_DRAWS):
        result = get_combo_guide()
    assert result is not None
    assert sum(result["low_dist"].values()) == result["total"]


def test_get_combo_guide_best_odd_pct_range():
    with patch("lotto.web.data.get_draws", return_value=SAMPLE_DRAWS):
        result = get_combo_guide()
    assert result is not None
    assert 0.0 <= result["best_odd_pct"] <= 100.0


def test_combo_guide_page_200():
    with patch("lotto.web.data.get_draws", return_value=SAMPLE_DRAWS):
        response = client.get("/stats/combo-guide")
    assert response.status_code == 200


def test_combo_guide_page_no_data():
    with patch("lotto.web.data.get_draws", return_value=[]):
        response = client.get("/stats/combo-guide")
    assert response.status_code == 200
    assert "데이터가 없습니다" in response.text
