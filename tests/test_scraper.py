"""scraper.py 테스트 — _TableParser, _parse_table, _parse_draw_row, scrape_all."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import pytest

# ──────────────────────────────────────────────
# _TableParser 테스트
# ──────────────────────────────────────────────

def test_table_parser_parses_header_row():
    """헤더 행의 th 셀을 올바르게 파싱한다."""
    from lotto.scraper import _TableParser

    parser = _TableParser()
    parser.feed("<table><tr><th>회차</th><th>날짜</th></tr></table>")
    assert len(parser.rows) == 1
    assert parser.rows[0] == ["회차", "날짜"]


def test_table_parser_parses_data_row():
    """td 셀을 올바르게 파싱한다."""
    from lotto.scraper import _TableParser

    parser = _TableParser()
    parser.feed("<table><tr><td>1130회</td><td>2024.07.27</td></tr></table>")
    assert parser.rows[0] == ["1130회", "2024.07.27"]


def test_table_parser_strips_whitespace():
    """셀 내 공백을 제거한다."""
    from lotto.scraper import _TableParser

    parser = _TableParser()
    parser.feed("<table><tr><td>  1130회  </td></tr></table>")
    assert parser.rows[0][0] == "1130회"


def test_table_parser_skips_empty_cell_data():
    """공백만 있는 셀 데이터는 무시한다."""
    from lotto.scraper import _TableParser

    parser = _TableParser()
    parser.feed("<table><tr><td>   </td><td>값</td></tr></table>")
    assert parser.rows[0] == ["", "값"]


def test_table_parser_empty_row_not_appended():
    """빈 tr은 rows에 추가되지 않는다."""
    from lotto.scraper import _TableParser

    parser = _TableParser()
    parser.feed("<table><tr></tr><tr><td>데이터</td></tr></table>")
    assert len(parser.rows) == 1
    assert parser.rows[0] == ["데이터"]


def test_table_parser_multiple_rows():
    """여러 행을 정상 파싱한다."""
    from lotto.scraper import _TableParser

    parser = _TableParser()
    html = (
        "<table>"
        "<tr><th>A</th><th>B</th></tr>"
        "<tr><td>1</td><td>2</td></tr>"
        "<tr><td>3</td><td>4</td></tr>"
        "</table>"
    )
    parser.feed(html)
    assert len(parser.rows) == 3


def test_table_parser_multi_text_in_cell():
    """셀 내 여러 텍스트 노드를 공백으로 합친다."""
    from lotto.scraper import _TableParser

    parser = _TableParser()
    parser.feed("<table><tr><td>hello <span>world</span></td></tr></table>")
    assert parser.rows[0][0] == "hello world"


# ──────────────────────────────────────────────
# _parse_table 테스트
# ──────────────────────────────────────────────

SAMPLE_HTML = """
<table>
<tr><th>회차</th><th>날짜</th><th>당첨자</th><th>당첨금</th><th>1</th><th>2</th><th>3</th><th>4</th><th>5</th><th>6</th><th>보너스</th></tr>
<tr><th>헤더2</th><th>col2</th><th>col3</th><th>col4</th><th>c5</th><th>c6</th><th>c7</th><th>c8</th><th>c9</th><th>c10</th><th>c11</th></tr>
<tr><td>1130회</td><td>2024.07.27</td><td>7</td><td>2100000000</td><td>15</td><td>19</td><td>21</td><td>25</td><td>27</td><td>28</td><td>40</td></tr>
</table>
"""


def test_parse_table_returns_rows():
    """샘플 HTML에서 3개 행을 파싱한다."""
    from lotto.scraper import _parse_table

    rows = _parse_table(SAMPLE_HTML)
    assert len(rows) == 3


def test_parse_table_no_table_tag():
    """table 태그 없는 HTML에서 빈 리스트 반환."""
    from lotto.scraper import _parse_table

    rows = _parse_table("<div>내용</div>")
    assert rows == []


def test_parse_table_data_row_values():
    """데이터 행의 값이 정확한지 확인."""
    from lotto.scraper import _parse_table

    rows = _parse_table(SAMPLE_HTML)
    # 3번째 행이 데이터 행
    data_row = rows[2]
    assert data_row[0] == "1130회"
    assert data_row[1] == "2024.07.27"
    assert data_row[4] == "15"


# ──────────────────────────────────────────────
# _parse_draw_row 테스트
# ──────────────────────────────────────────────

def test_parse_draw_row_valid_returns_draw_result():
    """유효한 행 데이터를 DrawResult로 변환한다."""
    from lotto.scraper import _parse_draw_row

    row = ["1130회", "2024.07.27", "7", "2100000000", "15", "19", "21", "25", "27", "28", "40"]
    result = _parse_draw_row(row)
    assert result is not None
    assert result.drwNo == 1130
    assert result.date == datetime.date(2024, 7, 27)
    assert result.n1 == 15
    assert result.n6 == 28
    assert result.bonus == 40


def test_parse_draw_row_date_with_spaces():
    """날짜 필드 공백을 제거하고 파싱한다."""
    from lotto.scraper import _parse_draw_row

    row = ["1100회", " 2024. 01. 15 ", "10", "1000000", "1", "2", "3", "4", "5", "6", "7"]
    result = _parse_draw_row(row)
    assert result is not None
    assert result.date == datetime.date(2024, 1, 15)


def test_parse_draw_row_too_short_returns_none():
    """열이 11개 미만이면 None 반환."""
    from lotto.scraper import _parse_draw_row

    row = ["1130회", "2024.07.27", "7"]
    result = _parse_draw_row(row)
    assert result is None


def test_parse_draw_row_invalid_drw_no_returns_none():
    """회차 번호가 숫자가 아니면 None 반환."""
    from lotto.scraper import _parse_draw_row

    row = ["없음", "2024.07.27", "7", "2100000000", "15", "19", "21", "25", "27", "28", "40"]
    result = _parse_draw_row(row)
    assert result is None


def test_parse_draw_row_invalid_date_returns_none():
    """날짜 형식이 잘못되면 None 반환."""
    from lotto.scraper import _parse_draw_row

    row = ["1130회", "2024-07-27", "7", "2100000000", "15", "19", "21", "25", "27", "28", "40"]
    result = _parse_draw_row(row)
    assert result is None


def test_parse_draw_row_invalid_number_returns_none():
    """번호 필드가 숫자가 아니면 None 반환."""
    from lotto.scraper import _parse_draw_row

    row = ["1130회", "2024.07.27", "7", "2100000000", "abc", "19", "21", "25", "27", "28", "40"]
    result = _parse_draw_row(row)
    assert result is None


# ──────────────────────────────────────────────
# scrape_all 테스트
# ──────────────────────────────────────────────

def _make_mock_response(html: str) -> MagicMock:
    """requests.Response 목 객체 생성 헬퍼."""
    mock_resp = MagicMock()
    mock_resp.text = html
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def test_scrape_all_returns_sorted_draws():
    """두 URL 모두 성공 시 drwNo 오름차순 정렬 반환."""
    from lotto.scraper import scrape_all

    html1 = """
    <table>
    <tr><th>헤더1</th><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/></tr>
    <tr><th>헤더2</th><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/></tr>
    <tr><td>1100회</td><td>2024.01.15</td><td>10</td><td>1000000</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td></tr>
    </table>
    """
    html2 = """
    <table>
    <tr><th>헤더1</th><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/></tr>
    <tr><th>헤더2</th><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/></tr>
    <tr><td>1130회</td><td>2024.07.27</td><td>7</td><td>2100000000</td><td>15</td><td>19</td><td>21</td><td>25</td><td>27</td><td>28</td><td>40</td></tr>
    </table>
    """

    with patch("requests.Session.get") as mock_get:
        mock_get.side_effect = [_make_mock_response(html1), _make_mock_response(html2)]
        results = scrape_all()

    assert len(results) == 2
    assert results[0].drwNo == 1100
    assert results[1].drwNo == 1130


def test_scrape_all_deduplicates_same_draw():
    """같은 회차가 두 URL에서 나오면 중복 제거."""
    from lotto.scraper import scrape_all

    same_row = (
        "<tr><td>1130회</td><td>2024.07.27</td><td>7</td><td>2100000000</td>"
        "<td>15</td><td>19</td><td>21</td><td>25</td><td>27</td><td>28</td><td>40</td></tr>"
    )
    html = (
        "<table>"
        "<tr><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/></tr>"
        "<tr><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/></tr>"
        f"{same_row}</table>"
    )

    with patch("requests.Session.get") as mock_get:
        mock_get.side_effect = [_make_mock_response(html), _make_mock_response(html)]
        results = scrape_all()

    assert len(results) == 1


def test_scrape_all_raises_on_http_error():
    """requests 예외 발생 시 RuntimeError 전파."""
    import requests as _requests

    from lotto.scraper import scrape_all

    with patch("requests.Session.get") as mock_get:
        mock_get.side_effect = _requests.RequestException("연결 실패")
        with pytest.raises(RuntimeError, match="URL 접근 실패"):
            scrape_all()


def test_scrape_all_calls_on_progress():
    """on_progress 콜백이 각 행마다 호출된다."""
    from lotto.scraper import scrape_all

    html = """
    <table>
    <tr><th>헤더1</th><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/></tr>
    <tr><th>헤더2</th><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/></tr>
    <tr><td>1100회</td><td>2024.01.15</td><td>10</td><td>1000000</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td><td>7</td></tr>
    </table>
    """
    progress_calls = []

    def on_progress(drw_no, row_idx, total):
        progress_calls.append((drw_no, row_idx, total))

    empty_table = "<table><tr><th/></tr></table>"
    with patch("requests.Session.get") as mock_get:
        mock_get.side_effect = [_make_mock_response(html), _make_mock_response(empty_table)]
        scrape_all(on_progress=on_progress)

    assert len(progress_calls) == 1
    drw_no, row_idx, total = progress_calls[0]
    assert drw_no == 1100
    assert row_idx == 1
    assert total == 1


def test_scrape_all_skips_invalid_rows():
    """파싱 실패한 행은 건너뛰고 on_progress에 drwNo=0 전달."""
    from lotto.scraper import scrape_all

    html = """
    <table>
    <tr><th>헤더1</th><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/></tr>
    <tr><th>헤더2</th><th/><th/><th/><th/><th/><th/><th/><th/><th/><th/></tr>
    <tr><td>잘못된</td><td>데이터</td><td>x</td></tr>
    </table>
    """
    progress_calls = []

    def on_progress(drw_no, row_idx, total):
        progress_calls.append(drw_no)

    empty_table = "<table><tr><th/></tr></table>"
    with patch("requests.Session.get") as mock_get:
        mock_get.side_effect = [_make_mock_response(html), _make_mock_response(empty_table)]
        results = scrape_all(on_progress=on_progress)

    # 짧은 행(3개)은 data_rows 필터(len>=11)에서 제외되므로 아무것도 처리 안됨
    assert results == []


def test_scrape_all_empty_html_returns_empty():
    """table 없는 HTML에서 빈 목록 반환."""
    from lotto.scraper import scrape_all

    with patch("requests.Session.get") as mock_get:
        mock_get.side_effect = [
            _make_mock_response("<html><body>내용없음</body></html>"),
            _make_mock_response("<html><body>내용없음</body></html>"),
        ]
        results = scrape_all()

    assert results == []
