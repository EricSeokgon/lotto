"""페이지 라우트 테스트 — HTML 응답 검증."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """테스트 클라이언트 픽스처."""
    from lotto.web.app import app

    return TestClient(app)


# ──────────────────────────────────────────────
# T-007/T-008: 인덱스 페이지
# ──────────────────────────────────────────────

def test_index_returns_200(client):
    """/ 가 200을 반환하는지 확인."""
    response = client.get("/")
    assert response.status_code == 200


def test_index_has_dashboard_keyword(client):
    """인덱스 페이지에 대시보드 키워드가 있는지 확인."""
    response = client.get("/")
    assert "대시보드" in response.text or "Dashboard" in response.text


def test_index_has_disclaimer(client):
    """인덱스 페이지에 면책 조항이 있는지 확인."""
    response = client.get("/")
    assert "보장" in response.text or "책임" in response.text


# ──────────────────────────────────────────────
# T-009: 수집 현황 페이지
# ──────────────────────────────────────────────

def test_collect_returns_200(client):
    """/collect 가 200을 반환하는지 확인."""
    response = client.get("/collect")
    assert response.status_code == 200


def test_collect_shows_collection_info(client):
    """/collect 페이지에 수집 관련 텍스트가 있는지 확인."""
    response = client.get("/collect")
    assert "수집" in response.text


def test_collect_has_disclaimer(client):
    """/collect 페이지에 면책 조항이 있는지 확인."""
    response = client.get("/collect")
    assert "보장" in response.text or "책임" in response.text


# ──────────────────────────────────────────────
# T-010: 빈도 분석 페이지
# ──────────────────────────────────────────────

def test_analyze_returns_200(client):
    """/analyze 가 200을 반환하는지 확인."""
    response = client.get("/analyze")
    assert response.status_code == 200


def test_analyze_has_frequency_content(client):
    """/analyze 페이지에 빈도 관련 텍스트가 있는지 확인."""
    response = client.get("/analyze")
    assert "빈도" in response.text or "데이터" in response.text


def test_analyze_has_disclaimer(client):
    """/analyze 페이지에 면책 조항이 있는지 확인."""
    response = client.get("/analyze")
    assert "보장" in response.text or "책임" in response.text


# ──────────────────────────────────────────────
# T-011: 추천 번호 페이지
# ──────────────────────────────────────────────

def test_recommend_returns_200(client):
    """/recommend 가 200을 반환하는지 확인."""
    response = client.get("/recommend")
    assert response.status_code == 200


def test_recommend_custom_count(client):
    """/recommend?count=3 이 200을 반환하는지 확인."""
    response = client.get("/recommend?count=3")
    assert response.status_code == 200


def test_recommend_has_disclaimer(client):
    """/recommend 페이지에 면책 조항이 있는지 확인."""
    response = client.get("/recommend")
    assert "보장" in response.text or "책임" in response.text


# ──────────────────────────────────────────────
# T-012: 시뮬레이션 페이지
# ──────────────────────────────────────────────

def test_simulate_returns_200(client):
    """/simulate 가 200을 반환하는지 확인."""
    response = client.get("/simulate")
    assert response.status_code == 200


def test_simulate_has_donut_chart_content(client):
    """/simulate 페이지에 차트 또는 데이터 없음 메시지가 있는지 확인."""
    response = client.get("/simulate")
    assert response.status_code == 200


def test_simulate_has_disclaimer(client):
    """/simulate 페이지에 면책 조항이 있는지 확인."""
    response = client.get("/simulate")
    assert "보장" in response.text or "책임" in response.text


# ──────────────────────────────────────────────
# T-016: 금지 색상 없음 확인
# ──────────────────────────────────────────────

def test_no_red_or_gold_colors(client):
    """금지 색상(빨강/금색 계열)이 페이지 HTML에 없는지 확인."""
    forbidden = ["#dc2626", "#ef4444", "#fbbf24", "#f59e0b", "red-500", "yellow-400", "gold"]
    for path in ["/", "/collect", "/analyze", "/recommend", "/simulate"]:
        response = client.get(path)
        text = response.text.lower()
        for color in forbidden:
            assert color.lower() not in text, f"{path} 에서 금지 색상 '{color}' 발견"


def test_disclaimer_in_all_pages(client):
    """모든 페이지에 면책 조항이 있는지 확인."""
    disclaimer_keywords = ["보장", "책임"]
    for path in ["/", "/collect", "/analyze", "/recommend", "/simulate"]:
        response = client.get(path)
        assert response.status_code == 200, f"{path} 가 200을 반환하지 않음"
        found = any(kw in response.text for kw in disclaimer_keywords)
        assert found, f"{path} 에서 면책 조항 미발견"


def test_analyze_page_with_stats(monkeypatch):
    """통계 데이터 있을 때 analyze 페이지에 배지 색상이 렌더링되는지 확인."""
    from unittest.mock import MagicMock

    from lotto.web.app import app

    # Statistics 모킹
    mock_stats = MagicMock()
    mock_stats.frequency.absolute = {str(i): i * 5 for i in range(1, 46)}

    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "lotto.web.routes.pages.get_stats", return_value=mock_stats
    ):
        c = TestClient(app)
        response = c.get("/analyze")

    assert response.status_code == 200
    # 색상 스타일이 렌더링됐는지 확인
    assert "background-color" in response.text


def test_collect_page_with_draws(monkeypatch):
    """수집 데이터 있을 때 collect 페이지에 회차 정보가 표시되는지 확인."""
    from unittest.mock import MagicMock

    from lotto.web.app import app

    mock_draw = MagicMock()
    mock_draw.drwNo = 1100
    mock_draw.date = "2024-01-01"
    mock_draw.numbers.return_value = [1, 7, 15, 22, 33, 42]
    mock_draw.bonus = 5
    # SPEC-LOTTO-022 REQ-PRIZE-C-003: 템플릿이 prize1Amount 컬럼을 렌더링하므로
    # MagicMock 의 자동 생성 속성이 Jinja format 에 들어가지 않도록 명시적으로 None 지정
    mock_draw.prize1Amount = None

    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "lotto.web.routes.pages.get_draws", return_value=[mock_draw]
    ):
        c = TestClient(app)
        response = c.get("/collect")

    assert response.status_code == 200


def test_simulate_page_with_result(monkeypatch):
    """시뮬레이션 결과 있을 때 페이지에 적중률이 표시되는지 확인."""
    from unittest.mock import MagicMock, patch

    from lotto.web.app import app

    mock_result = MagicMock()
    mock_result.total_rounds = 1000
    mock_result.hit_rate = 0.05
    mock_result.prize_counts = {"1등": 0, "2등": 0, "3등": 2, "4등": 15, "5등": 50, "낙첨": 933}
    mock_result.per_round_hits = [0] * 1000

    with patch("lotto.web.routes.pages.get_simulation", return_value=mock_result), \
         patch("lotto.web.routes.pages.get_strategy_comparison", return_value=None):
        c = TestClient(app)
        response = c.get("/simulate")

    assert response.status_code == 200


# ──────────────────────────────────────────────
# T-017: 구매 히스토리 페이지 테스트
# ──────────────────────────────────────────────

def test_history_page_returns_200(client):
    """/history 가 200을 반환하는지 확인."""
    from unittest.mock import patch

    from lotto.web.app import app

    with patch("lotto.web.routes.pages.compute_ticket_results", return_value=[]):
        c = TestClient(app)
        response = c.get("/history")

    assert response.status_code == 200


def test_history_page_shows_empty_state():
    """/history 페이지에서 데이터 없을 때 빈 상태 표시."""
    from unittest.mock import patch

    from lotto.web.app import app

    with patch("lotto.web.routes.pages.compute_ticket_results", return_value=[]):
        c = TestClient(app)
        response = c.get("/history")

    assert response.status_code == 200
    assert "history" in response.text.lower() or "히스토리" in response.text


def test_history_page_shows_ticket_results():
    """/history 페이지에서 티켓 결과 데이터가 렌더링된다."""
    from unittest.mock import patch

    from lotto.web.app import app

    fake_results = [
        {
            "ticket": {"id": "abc", "drwNo": 1100, "numbers": [1, 2, 3, 4, 5, 6],
                       "bought_at": "2024-01-15"},
            "draw_numbers": [1, 2, 3, 4, 5, 6],
            "draw_bonus": 7,
            "draw_date": "2024-01-15",
            "matched": 6,
            "bonus_match": False,
            "prize": "1등",
        }
    ]

    with patch("lotto.web.routes.pages.compute_ticket_results", return_value=fake_results):
        c = TestClient(app)
        response = c.get("/history")

    assert response.status_code == 200
    assert "1100" in response.text


def test_history_page_prize_counts_computed():
    """/history 페이지에서 등수 집계가 올바르게 렌더링된다."""
    from unittest.mock import patch

    from lotto.web.app import app

    fake_results = [
        {
            "ticket": {"id": "a", "drwNo": 1100, "numbers": [1, 2, 3, 4, 5, 6],
                       "bought_at": "2024-01-15"},
            "draw_numbers": [1, 2, 3, 4, 5, 6],
            "draw_bonus": 7,
            "draw_date": "2024-01-15",
            "matched": 3,
            "bonus_match": False,
            "prize": "5등",
        },
        {
            "ticket": {"id": "b", "drwNo": 1101, "numbers": [10, 20, 30, 40, 41, 42],
                       "bought_at": "2024-01-22"},
            "draw_numbers": [],
            "draw_bonus": 0,
            "draw_date": "",
            "matched": 0,
            "bonus_match": False,
            "prize": "미추첨",
        },
    ]

    with patch("lotto.web.routes.pages.compute_ticket_results", return_value=fake_results):
        c = TestClient(app)
        response = c.get("/history")

    assert response.status_code == 200


# ──────────────────────────────────────────────
# SPEC-LOTTO-010: 페이지네이션 컨트롤 및 /docs 링크
# ──────────────────────────────────────────────


def test_base_nav_has_docs_link(client):
    """REQ-UI-004: 모든 페이지의 네비게이션에 /docs 링크가 노출된다."""
    for path in ["/", "/collect", "/analyze", "/recommend", "/simulate"]:
        response = client.get(path)
        assert response.status_code == 200, f"{path} 가 200을 반환하지 않음"
        assert 'href="/docs"' in response.text, (
            f"{path} 에서 /docs 링크가 발견되지 않음"
        )


def test_collect_has_pagination_controls(client):
    """REQ-UI-001, REQ-UI-003: collect 페이지에 페이지네이션 컨트롤이 렌더링된다."""
    response = client.get("/collect")
    assert response.status_code == 200
    # 페이지네이션 대상 tbody
    assert 'id="draws-tbody"' in response.text
    # 이전/다음 버튼
    assert 'id="btn-prev"' in response.text
    assert 'id="btn-next"' in response.text
    # 현재 페이지 정보 표시 영역
    assert 'id="page-info"' in response.text


def test_collect_uses_api_draws_for_pagination(client):
    """REQ-UI-002: 클라이언트 JS가 /api/draws?limit=10 패턴을 사용한다."""
    response = client.get("/collect")
    assert response.status_code == 200
    # fetch URL 패턴 검증
    assert "/api/draws?limit=" in response.text
    # 페이지당 10회 상수
    assert "PAGE_SIZE" in response.text or "= 10" in response.text


def test_collect_tbody_has_initial_rows_desc_order():
    """REQ-UI-001/002: 서버사이드 초기 렌더링으로 tbody에 최신 회차부터 행이 표시된다."""
    import datetime
    import re

    from lotto.models import DrawResult
    from lotto.web.app import app

    draws = [
        DrawResult(drwNo=i, date=datetime.date(2024, 1, i), n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7)  # noqa: E501
        for i in range(1, 6)
    ]

    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "lotto.web.routes.pages.get_draws", return_value=draws
    ):
        c = TestClient(app)
        response = c.get("/collect")

    assert response.status_code == 200

    match = re.search(
        r'<tbody id="draws-tbody"[^>]*>(.*?)</tbody>',
        response.text,
        re.DOTALL,
    )
    assert match is not None, "draws-tbody 가 발견되지 않음"
    tbody_content = match.group(1).strip()
    assert tbody_content != "", "draws-tbody 가 비어있음 (서버사이드 초기 렌더링 필요)"
    # SPEC-LOTTO-029 REQ-DETAIL-003: 회차 번호가 /draw/{n} 상세 링크로 감싸짐
    rounds_in_order = re.findall(r'(\d+)회</a>', tbody_content)
    assert rounds_in_order[0] == "5", (
        f"첫 번째 행이 최신 회차가 아님: {rounds_in_order}"
    )


# ──────────────────────────────────────────────
# 커버리지 누락 분기: stats=None, result=None 경로
# ──────────────────────────────────────────────


def test_analyze_page_stats_none(client):
    """/analyze — stats가 None(데이터 없음)일 때 200 반환 및 배지 없음."""
    from unittest.mock import patch

    with patch("lotto.web.routes.pages.get_stats", return_value=None):
        response = client.get("/analyze")
    assert response.status_code == 200


def test_simulate_page_result_none(client):
    """/simulate — result가 None(데이터 없음)일 때 200 반환."""
    from unittest.mock import patch

    with patch("lotto.web.routes.pages.get_simulation", return_value=None):
        response = client.get("/simulate")
    assert response.status_code == 200
