"""SPEC-LOTTO-118 이월 번호 분석 테스트."""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_carryover_analysis

client = TestClient(app)


def _make_draws(count: int) -> list[DrawResult]:
    """테스트용 DrawResult 목록 생성 (번호가 조금씩 겹치도록)."""
    draws = []
    for i in range(count):
        # 각 회차 번호: i 기반으로 6개 고유 번호 생성
        base = (i * 5) % 40 + 1
        nums = sorted({(base + j - 1) % 45 + 1 for j in range(6)})
        # 중복 제거 후 6개 보장
        seen: set[int] = set()
        unique: list[int] = []
        for n in nums:
            if n not in seen:
                seen.add(n)
                unique.append(n)
        while len(unique) < 6:
            candidate = (max(unique) % 45) + 1
            if candidate not in seen:
                seen.add(candidate)
                unique.append(candidate)
        unique = sorted(unique)
        draws.append(DrawResult(
            drwNo=i + 1,
            date=datetime.date(2020, 1, 4) + datetime.timedelta(weeks=i),
            n1=unique[0], n2=unique[1], n3=unique[2],
            n4=unique[3], n5=unique[4], n6=unique[5],
            bonus=7,
        ))
    return draws


def test_get_carryover_analysis_returns_none_when_empty() -> None:
    with patch("lotto.web.data.get_draws", return_value=[]):
        assert get_carryover_analysis() is None


def test_get_carryover_analysis_returns_none_when_single_draw() -> None:
    draws = _make_draws(1)
    with patch("lotto.web.data.get_draws", return_value=draws):
        assert get_carryover_analysis() is None


def test_get_carryover_analysis_returns_dict() -> None:
    draws = _make_draws(10)
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_carryover_analysis()
    assert result is not None
    assert isinstance(result, dict)


def test_get_carryover_analysis_has_required_keys() -> None:
    draws = _make_draws(10)
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_carryover_analysis()
    assert result is not None
    for key in ("total_pairs", "distribution", "avg_carryover", "most_common", "recent"):
        assert key in result


def test_get_carryover_analysis_distribution_keys() -> None:
    draws = _make_draws(10)
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_carryover_analysis()
    assert result is not None
    dist = result["distribution"]
    assert set(dist.keys()) == set(range(7))


def test_get_carryover_analysis_distribution_sums_to_total() -> None:
    draws = _make_draws(20)
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_carryover_analysis()
    assert result is not None
    assert sum(result["distribution"].values()) == result["total_pairs"]
    assert result["total_pairs"] == 19  # 20회차 → 19쌍


def test_get_carryover_analysis_avg_range() -> None:
    draws = _make_draws(10)
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_carryover_analysis()
    assert result is not None
    assert 0.0 <= result["avg_carryover"] <= 6.0


def test_get_carryover_analysis_recent_max_20() -> None:
    draws = _make_draws(30)
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_carryover_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_carryover_page_200() -> None:
    draws = _make_draws(10)
    with patch("lotto.web.data.get_draws", return_value=draws):
        response = client.get("/stats/carryover")
    assert response.status_code == 200


def test_carryover_page_no_data() -> None:
    with patch("lotto.web.data.get_draws", return_value=[]):
        response = client.get("/stats/carryover")
    assert response.status_code == 200
    assert "부족합니다" in response.text
