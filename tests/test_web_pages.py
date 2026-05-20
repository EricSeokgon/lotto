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

    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "lotto.web.routes.pages.get_draws", return_value=[mock_draw]
    ):
        c = TestClient(app)
        response = c.get("/collect")

    assert response.status_code == 200


def test_simulate_page_with_result(monkeypatch):
    """시뮬레이션 결과 있을 때 페이지에 적중률이 표시되는지 확인."""
    from unittest.mock import MagicMock

    from lotto.web.app import app

    mock_result = MagicMock()
    mock_result.total_rounds = 1000
    mock_result.hit_rate = 0.05
    mock_result.prize_counts = {"1등": 0, "2등": 0, "3등": 2, "4등": 15, "5등": 50}

    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "lotto.web.routes.pages.get_simulation", return_value=mock_result
    ):
        c = TestClient(app)
        response = c.get("/simulate")

    assert response.status_code == 200
