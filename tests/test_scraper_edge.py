"""SPEC-LOTTO-003 REQ-SCRAPER-001/002: 스크래퍼 엣지 케이스 안정성 테스트."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from lotto.scraper import _parse_draw_row, scrape_all


def _make_mock_response(html: str) -> MagicMock:
    """requests.Response 목 객체 생성 헬퍼."""
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# ──────────────────────────────────────────────
# REQ-SCRAPER-001: _parse_draw_row 엣지 케이스
# ──────────────────────────────────────────────


def test_parse_draw_row_short_row_returns_none_no_exception() -> None:
    """행이 11개 미만이면 예외 없이 None 반환."""
    row = ["1130회", "2024.07.27", "7"]
    result = _parse_draw_row(row)
    assert result is None


def test_parse_draw_row_short_row_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """짧은 행에 대해 경고 로그가 기록된다."""
    row = ["1130회", "2024.07.27"]
    with caplog.at_level(logging.WARNING, logger="lotto.scraper"):
        result = _parse_draw_row(row)
    assert result is None
    # 경고 로그가 최소 1회 기록됨
    assert any(
        rec.name == "lotto.scraper" and rec.levelname == "WARNING"
        for rec in caplog.records
    )


def test_parse_draw_row_non_integer_number_returns_none() -> None:
    """번호 셀이 정수가 아니면 None 반환."""
    row = ["1130회", "2024.07.27", "7", "21억", "abc", "19", "21", "25", "27", "28", "40"]
    result = _parse_draw_row(row)
    assert result is None


def test_parse_draw_row_non_integer_number_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """비정수 번호 셀에 대해 경고 로그가 기록된다."""
    row = ["1130회", "2024.07.27", "7", "21억", "abc", "19", "21", "25", "27", "28", "40"]
    with caplog.at_level(logging.WARNING, logger="lotto.scraper"):
        result = _parse_draw_row(row)
    assert result is None
    assert any(
        rec.name == "lotto.scraper" and rec.levelname == "WARNING"
        for rec in caplog.records
    )


def test_parse_draw_row_malformed_date_dash_returns_none() -> None:
    """날짜가 대시(-) 구분 형식이면 None 반환."""
    row = ["1130회", "2024-07-27", "7", "2100000000", "15", "19", "21", "25", "27", "28", "40"]
    result = _parse_draw_row(row)
    assert result is None


def test_parse_draw_row_malformed_date_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """잘못된 날짜 형식에 대해 경고 로그가 기록된다."""
    row = ["1130회", "2024-07-27", "7", "2100000000", "15", "19", "21", "25", "27", "28", "40"]
    with caplog.at_level(logging.WARNING, logger="lotto.scraper"):
        result = _parse_draw_row(row)
    assert result is None
    assert any(
        rec.name == "lotto.scraper" and rec.levelname == "WARNING"
        for rec in caplog.records
    )


def test_parse_draw_row_non_integer_bonus_returns_none() -> None:
    """보너스 셀이 정수가 아니면 None 반환."""
    row = ["1130회", "2024.07.27", "7", "2100000000", "15", "19", "21", "25", "27", "28", "X"]
    result = _parse_draw_row(row)
    assert result is None


def test_parse_draw_row_non_integer_drw_no_returns_none() -> None:
    """회차 셀이 정수가 아니면 None 반환."""
    row = ["없음", "2024.07.27", "7", "2100000000", "15", "19", "21", "25", "27", "28", "40"]
    result = _parse_draw_row(row)
    assert result is None


# ──────────────────────────────────────────────
# REQ-SCRAPER-002: scrape_all 견고성
# ──────────────────────────────────────────────


def test_scrape_all_no_table_returns_empty_list() -> None:
    """HTML에 table 태그가 없으면 빈 리스트 반환, 예외 없음."""
    html = "<div>테이블 없음</div>"

    with patch("requests.Session.get") as mock_get:
        mock_get.side_effect = [_make_mock_response(html), _make_mock_response(html)]
        results = scrape_all()

    assert results == []


def test_scrape_all_skips_invalid_rows_keeps_valid() -> None:
    """유효 행과 무효 행이 혼재한 경우 유효 행만 결과에 포함된다."""
    # URL1: 유효 1행 + 무효(짧은) 1행
    html_mixed = """
    <table>
    <tr><th>헤더1</th><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/></tr>
    <tr><th>헤더2</th><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/></tr>
    <tr><td>1100회</td><td>2024.01.15</td><td>10</td><td>1000000</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td></tr>
    <tr><td>BAD</td><td>2024-01-22</td><td>10</td><td>1000000</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td></tr>
    </table>
    """
    # URL2: 빈 테이블
    html_empty = "<div>없음</div>"

    with patch("requests.Session.get") as mock_get:
        mock_get.side_effect = [
            _make_mock_response(html_mixed),
            _make_mock_response(html_empty),
        ]
        results = scrape_all()

    assert len(results) == 1
    assert results[0].drwNo == 1100


def test_scrape_all_all_invalid_rows_returns_empty() -> None:
    """모든 행이 무효이면 빈 리스트를 반환하고 예외가 없다."""
    html = """
    <table>
    <tr><th>헤더1</th><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/></tr>
    <tr><th>헤더2</th><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/></tr>
    <tr><td>BAD</td><td>2024-01-22</td><td>10</td><td>1000000</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td></tr>
    </table>
    """

    with patch("requests.Session.get") as mock_get:
        mock_get.side_effect = [
            _make_mock_response(html),
            _make_mock_response("<div/>"),
        ]
        results = scrape_all()

    assert results == []
