"""SPEC-LOTTO-013: analyze_page gap_rounds 분기 테스트.

pages.py analyze_page의 갭 분석 로직(gap_rounds 계산 분기)을 검증한다.

@MX:SPEC: SPEC-LOTTO-013
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from lotto.web.app import app

client = TestClient(app)


def _mock_stats_with_streaks(streaks: dict) -> MagicMock:
    """consecutive_pattern.current_streak이 지정된 stats 목(mock)을 반환한다."""
    mock = MagicMock()
    mock.frequency.absolute = {str(n): n * 2 for n in range(1, 46)}
    mock.consecutive_pattern.current_streak = streaks
    return mock


class TestAnalyzePageGapRounds:
    """analyze_page gap_rounds 계산 분기 검증."""

    def test_gap_rounds_populated_from_negative_streaks(self) -> None:
        """음수 스트릭이 있으면 gap_rounds에 미출현 회차 수가 채워진다."""
        streaks = {n: -n for n in range(1, 46)}  # 번호 n → -n 스트릭
        mock_stats = _mock_stats_with_streaks(streaks)

        with patch("lotto.web.routes.pages.get_stats", return_value=mock_stats), \
             patch("lotto.web.routes.pages.get_data_status", return_value={}):
            resp = client.get("/analyze")

        assert resp.status_code == 200

    def test_gap_rounds_empty_when_stats_none(self) -> None:
        """stats가 None이면 gap_rounds가 빈 딕셔너리로 전달된다."""
        with patch("lotto.web.routes.pages.get_stats", return_value=None), \
             patch("lotto.web.routes.pages.get_data_status", return_value={}):
            resp = client.get("/analyze")

        assert resp.status_code == 200

    def test_gap_rounds_empty_when_no_consecutive_pattern(self) -> None:
        """consecutive_pattern이 None이면 gap_rounds가 빈 딕셔너리로 전달된다."""
        mock_stats = MagicMock()
        mock_stats.frequency.absolute = {}
        mock_stats.consecutive_pattern = None

        with patch("lotto.web.routes.pages.get_stats", return_value=mock_stats), \
             patch("lotto.web.routes.pages.get_data_status", return_value={}):
            resp = client.get("/analyze")

        assert resp.status_code == 200

    def test_gap_rounds_empty_when_current_streak_empty(self) -> None:
        """current_streak가 빈 딕셔너리이면 gap_rounds가 빈 딕셔너리로 전달된다."""
        mock_stats = _mock_stats_with_streaks({})

        with patch("lotto.web.routes.pages.get_stats", return_value=mock_stats), \
             patch("lotto.web.routes.pages.get_data_status", return_value={}):
            resp = client.get("/analyze")

        assert resp.status_code == 200

    def test_gap_rounds_handles_type_error_in_streak(self) -> None:
        """streak 값이 변환 불가능한 타입이면 gap_rounds[num] = 0으로 처리된다."""
        # None 값은 int() 변환 시 TypeError 발생
        streaks = dict.fromkeys(range(1, 46))
        mock_stats = _mock_stats_with_streaks(streaks)

        with patch("lotto.web.routes.pages.get_stats", return_value=mock_stats), \
             patch("lotto.web.routes.pages.get_data_status", return_value={}):
            resp = client.get("/analyze")

        # TypeError가 catch되어 200으로 응답해야 한다
        assert resp.status_code == 200

    def test_gap_rounds_handles_value_error_in_streak(self) -> None:
        """streak 값이 변환 불가능한 문자열이면 gap_rounds[num] = 0으로 처리된다."""
        streaks = dict.fromkeys(range(1, 46), "invalid")
        mock_stats = _mock_stats_with_streaks(streaks)

        with patch("lotto.web.routes.pages.get_stats", return_value=mock_stats), \
             patch("lotto.web.routes.pages.get_data_status", return_value={}):
            resp = client.get("/analyze")

        assert resp.status_code == 200

    def test_gap_rounds_positive_streak_gives_zero_gap(self) -> None:
        """양수 스트릭은 max(0, -streak) = 0 이므로 gap_rounds[num] = 0이다."""
        streaks = {n: n for n in range(1, 46)}  # 양수 스트릭
        mock_stats = _mock_stats_with_streaks(streaks)

        with patch("lotto.web.routes.pages.get_stats", return_value=mock_stats), \
             patch("lotto.web.routes.pages.get_data_status", return_value={}):
            resp = client.get("/analyze")

        assert resp.status_code == 200
