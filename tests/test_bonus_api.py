"""SPEC-LOTTO-003 REQ-BONUS-003: GET /api/stats 응답에 bonus_frequency 포함."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import FrequencyStats, Statistics
from lotto.web.app import app


def _make_stats_with_bonus() -> Statistics:
    """보너스 빈도가 들어 있는 Statistics를 생성합니다."""
    absolute = dict.fromkeys(range(1, 46), 0)
    absolute.update({7: 3, 11: 2})
    relative = dict.fromkeys(range(1, 46), 0.0)
    relative.update({7: 0.6, 11: 0.4})
    bonus_freq = FrequencyStats(absolute=absolute, relative=relative)
    return Statistics(total_rounds=5, bonus_frequency=bonus_freq)


def test_api_stats_response_contains_bonus_frequency_key() -> None:
    """GET /api/stats 응답 JSON에 bonus_frequency 키가 존재한다."""
    stats = _make_stats_with_bonus()

    with patch("lotto.web.routes.api.get_stats", return_value=stats):
        c = TestClient(app)
        response = c.get("/api/stats")

    assert response.status_code == 200
    data = response.json()
    assert "bonus_frequency" in data


def test_api_stats_bonus_frequency_has_absolute_and_relative() -> None:
    """bonus_frequency 응답 내부에 absolute, relative 키가 존재한다."""
    stats = _make_stats_with_bonus()

    with patch("lotto.web.routes.api.get_stats", return_value=stats):
        c = TestClient(app)
        response = c.get("/api/stats")

    data = response.json()
    bonus = data["bonus_frequency"]
    assert "absolute" in bonus
    assert "relative" in bonus


def test_api_stats_bonus_frequency_values_serialized() -> None:
    """bonus_frequency.absolute 값이 정수로 직렬화된다."""
    stats = _make_stats_with_bonus()

    with patch("lotto.web.routes.api.get_stats", return_value=stats):
        c = TestClient(app)
        response = c.get("/api/stats")

    data = response.json()
    # JSON에서 dict 키는 문자열로 직렬화되므로 "7" 형태로 확인
    assert data["bonus_frequency"]["absolute"]["7"] == 3
    assert data["bonus_frequency"]["absolute"]["11"] == 2
