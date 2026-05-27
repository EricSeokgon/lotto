"""SPEC-LOTTO-020: 데이터 내보내기 (CSV/JSON) API 엔드포인트 테스트.

# @MX:NOTE: [AUTO] /api/export/draws, /api/export/history 응답 헤더 및 콘텐츠 검증

REQ-EXP-001: GET /api/export/draws → CSV 스트리밍 다운로드
REQ-EXP-002: GET /api/export/history → CSV 다운로드
REQ-EXP-003: GET /api/export/history?format=json → JSON 다운로드
"""

from __future__ import annotations

import csv
import datetime
import io
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult


@pytest.fixture
def client():
    """테스트 클라이언트 픽스처."""
    from lotto.web.app import app

    return TestClient(app)


@pytest.fixture
def sample_draws() -> list[DrawResult]:
    """샘플 회차 데이터 (3개)."""
    return [
        DrawResult(
            drwNo=1, date=datetime.date(2002, 12, 7),
            n1=10, n2=23, n3=29, n4=33, n5=37, n6=40, bonus=16,
        ),
        DrawResult(
            drwNo=2, date=datetime.date(2002, 12, 14),
            n1=9, n2=13, n3=21, n4=25, n5=32, n6=42, bonus=2,
        ),
        DrawResult(
            drwNo=3, date=datetime.date(2002, 12, 21),
            n1=11, n2=16, n3=19, n4=21, n5=27, n6=31, bonus=30,
        ),
    ]


@pytest.fixture
def sample_history() -> list[dict]:
    """샘플 구매 이력 데이터."""
    return [
        {
            "id": "ticket-1",
            "drwNo": 1,
            "numbers": [10, 23, 29, 33, 37, 40],
            "bought_at": "2002-12-06",
        },
        {
            "id": "ticket-2",
            "drwNo": 2,
            "numbers": [1, 2, 3, 4, 5, 6],
            "bought_at": "2002-12-13",
        },
    ]


# ─── REQ-EXP-001: 추첨 데이터 CSV 내보내기 ─────────────────────────────────


def test_export_draws_returns_200_csv(client, sample_draws):
    """GET /api/export/draws 가 200 OK + text/csv Content-Type을 반환한다."""
    with patch("lotto.web.routes.api.get_draws", return_value=sample_draws):
        response = client.get("/api/export/draws")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")


def test_export_draws_content_disposition_has_today_date(client, sample_draws):
    """Content-Disposition 헤더에 today YYYYMMDD 파일명이 포함된다."""
    today = datetime.date.today().strftime("%Y%m%d")

    with patch("lotto.web.routes.api.get_draws", return_value=sample_draws):
        response = client.get("/api/export/draws")

    disposition = response.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert f"lotto_draws_{today}.csv" in disposition


def test_export_draws_has_correct_columns(client, sample_draws):
    """CSV 헤더에 drwNo, date, n1~n6, bonus 컬럼이 포함된다."""
    with patch("lotto.web.routes.api.get_draws", return_value=sample_draws):
        response = client.get("/api/export/draws")

    reader = csv.reader(io.StringIO(response.text))
    header = next(reader)
    assert header == ["drwNo", "date", "n1", "n2", "n3", "n4", "n5", "n6", "bonus"]


def test_export_draws_includes_all_rows(client, sample_draws):
    """CSV 본문에 모든 회차 행이 포함된다."""
    with patch("lotto.web.routes.api.get_draws", return_value=sample_draws):
        response = client.get("/api/export/draws")

    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)
    # 헤더 + 3 데이터 행
    assert len(rows) == 4
    # 첫 데이터 행의 drwNo 검증
    assert rows[1][0] == "1"
    assert rows[1][8] == "16"  # bonus


def test_export_draws_filter_from_drw(client, sample_draws):
    """from_drw 파라미터로 시작 회차 필터링이 동작한다."""
    with patch("lotto.web.routes.api.get_draws", return_value=sample_draws):
        response = client.get("/api/export/draws?from_drw=2")

    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)
    # 헤더 + 2회차, 3회차
    assert len(rows) == 3
    drw_nos = [int(r[0]) for r in rows[1:]]
    assert drw_nos == [2, 3]


def test_export_draws_filter_to_drw(client, sample_draws):
    """to_drw 파라미터로 끝 회차 필터링이 동작한다."""
    with patch("lotto.web.routes.api.get_draws", return_value=sample_draws):
        response = client.get("/api/export/draws?to_drw=2")

    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)
    # 헤더 + 1회차, 2회차
    assert len(rows) == 3
    drw_nos = [int(r[0]) for r in rows[1:]]
    assert drw_nos == [1, 2]


def test_export_draws_filter_range(client, sample_draws):
    """from_drw + to_drw 동시 적용 시 범위 필터링이 동작한다."""
    with patch("lotto.web.routes.api.get_draws", return_value=sample_draws):
        response = client.get("/api/export/draws?from_drw=2&to_drw=2")

    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)
    assert len(rows) == 2  # 헤더 + 2회차 1개
    assert int(rows[1][0]) == 2


def test_export_draws_empty_returns_header_only(client):
    """데이터가 없어도 200 + 헤더만 있는 CSV를 반환한다 (인수 조건)."""
    with patch("lotto.web.routes.api.get_draws", return_value=None):
        response = client.get("/api/export/draws")

    assert response.status_code == 200
    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0] == ["drwNo", "date", "n1", "n2", "n3", "n4", "n5", "n6", "bonus"]


def test_export_draws_empty_list_returns_header_only(client):
    """빈 리스트도 200 + 헤더만 반환한다."""
    with patch("lotto.web.routes.api.get_draws", return_value=[]):
        response = client.get("/api/export/draws")

    assert response.status_code == 200
    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)
    assert len(rows) == 1  # 헤더만


# ─── REQ-EXP-002: 구매 이력 CSV 내보내기 ──────────────────────────────────


def test_export_history_returns_200_csv(client, sample_history, sample_draws):
    """GET /api/export/history 가 200 OK + text/csv Content-Type을 반환한다."""
    with (
        patch("lotto.web.routes.api.get_history", return_value=sample_history),
        patch("lotto.web.routes.api.get_draws", return_value=sample_draws),
    ):
        response = client.get("/api/export/history")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")


def test_export_history_content_disposition_has_today_date(
    client, sample_history, sample_draws
):
    """Content-Disposition 헤더에 today 파일명이 포함된다."""
    today = datetime.date.today().strftime("%Y%m%d")

    with (
        patch("lotto.web.routes.api.get_history", return_value=sample_history),
        patch("lotto.web.routes.api.get_draws", return_value=sample_draws),
    ):
        response = client.get("/api/export/history")

    disposition = response.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert f"lotto_history_{today}.csv" in disposition


def test_export_history_has_correct_columns(client, sample_history, sample_draws):
    """CSV 헤더에 id, purchase_date, numbers, draw_no, prize_rank, prize_amount 컬럼이 포함된다."""
    with (
        patch("lotto.web.routes.api.get_history", return_value=sample_history),
        patch("lotto.web.routes.api.get_draws", return_value=sample_draws),
    ):
        response = client.get("/api/export/history")

    reader = csv.reader(io.StringIO(response.text))
    header = next(reader)
    assert header == [
        "id", "purchase_date", "numbers",
        "draw_no", "prize_rank", "prize_amount",
    ]


def test_export_history_includes_all_rows(client, sample_history, sample_draws):
    """CSV 본문에 모든 티켓 행이 포함된다."""
    with (
        patch("lotto.web.routes.api.get_history", return_value=sample_history),
        patch("lotto.web.routes.api.get_draws", return_value=sample_draws),
    ):
        response = client.get("/api/export/history")

    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)
    # 헤더 + 2개 티켓
    assert len(rows) == 3


def test_export_history_empty_returns_header_only(client):
    """구매 이력이 없어도 200 + 헤더만 있는 CSV를 반환한다."""
    with (
        patch("lotto.web.routes.api.get_history", return_value=[]),
        patch("lotto.web.routes.api.get_draws", return_value=None),
    ):
        response = client.get("/api/export/history")

    assert response.status_code == 200
    reader = csv.reader(io.StringIO(response.text))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0] == [
        "id", "purchase_date", "numbers",
        "draw_no", "prize_rank", "prize_amount",
    ]


# ─── REQ-EXP-003: 구매 이력 JSON 내보내기 ─────────────────────────────────


def test_export_history_json_returns_200(client, sample_history, sample_draws):
    """GET /api/export/history?format=json 이 200 OK + application/json을 반환한다."""
    with (
        patch("lotto.web.routes.api.get_history", return_value=sample_history),
        patch("lotto.web.routes.api.get_draws", return_value=sample_draws),
    ):
        response = client.get("/api/export/history?format=json")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


def test_export_history_json_content_disposition(
    client, sample_history, sample_draws
):
    """JSON 모드도 attachment Content-Disposition + today 파일명을 갖는다."""
    today = datetime.date.today().strftime("%Y%m%d")

    with (
        patch("lotto.web.routes.api.get_history", return_value=sample_history),
        patch("lotto.web.routes.api.get_draws", return_value=sample_draws),
    ):
        response = client.get("/api/export/history?format=json")

    disposition = response.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert f"lotto_history_{today}.json" in disposition


def test_export_history_json_body_is_valid_json(
    client, sample_history, sample_draws
):
    """JSON 응답 본문이 파싱 가능한 JSON 리스트다."""
    with (
        patch("lotto.web.routes.api.get_history", return_value=sample_history),
        patch("lotto.web.routes.api.get_draws", return_value=sample_draws),
    ):
        response = client.get("/api/export/history?format=json")

    parsed = json.loads(response.text)
    assert isinstance(parsed, list)
    assert len(parsed) == 2


def test_export_history_json_empty_returns_empty_list(client):
    """이력이 없어도 200 + JSON 빈 배열을 반환한다."""
    with (
        patch("lotto.web.routes.api.get_history", return_value=[]),
        patch("lotto.web.routes.api.get_draws", return_value=None),
    ):
        response = client.get("/api/export/history?format=json")

    assert response.status_code == 200
    parsed = json.loads(response.text)
    assert parsed == []


# ─── REQ-EXP-004: 웹 UI 다운로드 버튼 ─────────────────────────────────────


def test_collect_page_has_export_button(client, sample_draws):
    """수집 페이지에 추첨 데이터 CSV 내보내기 링크가 표시된다."""
    with patch("lotto.web.routes.api.get_draws", return_value=sample_draws):
        response = client.get("/collect")

    assert response.status_code == 200
    html = response.text
    # 다운로드 링크 또는 버튼이 포함되어야 한다
    assert "/api/export/draws" in html


def test_history_page_has_csv_export_button(client, sample_history, sample_draws):
    """히스토리 페이지에 CSV 내보내기 링크가 표시된다."""
    with (
        patch("lotto.web.routes.api.get_history", return_value=sample_history),
        patch("lotto.web.routes.api.get_draws", return_value=sample_draws),
    ):
        response = client.get("/history")

    assert response.status_code == 200
    html = response.text
    assert "/api/export/history" in html


def test_history_page_has_json_export_button(
    client, sample_history, sample_draws
):
    """히스토리 페이지에 JSON 내보내기 링크가 표시된다."""
    with (
        patch("lotto.web.routes.api.get_history", return_value=sample_history),
        patch("lotto.web.routes.api.get_draws", return_value=sample_draws),
    ):
        response = client.get("/history")

    assert response.status_code == 200
    html = response.text
    assert "format=json" in html
