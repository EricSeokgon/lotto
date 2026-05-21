"""SPEC-LOTTO-005: PDF 리포트 다운로드 API 엔드포인트 테스트.

# @MX:NOTE: [AUTO] GET /api/report/pdf 엔드포인트의 응답 헤더 및 콘텐츠 검증
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """테스트 클라이언트 픽스처."""
    from lotto.web.app import app

    return TestClient(app)


def test_pdf_endpoint_returns_pdf(client):
    """/api/report/pdf 가 application/pdf Content-Type으로 200을 반환한다 (REQ-PDF-001)."""
    response = client.get("/api/report/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")


def test_pdf_endpoint_content_disposition(client):
    """응답에 attachment 및 filename Content-Disposition 헤더가 포함된다 (REQ-PDF-001)."""
    response = client.get("/api/report/pdf")

    assert response.status_code == 200
    disposition = response.headers.get("content-disposition", "")
    assert "attachment" in disposition
    assert "lotto_report.pdf" in disposition


def test_pdf_endpoint_body_is_pdf_bytes(client):
    """응답 body가 PDF 매직 바이트로 시작한다."""
    response = client.get("/api/report/pdf")

    assert response.status_code == 200
    assert response.content[:4] == b"%PDF"
    assert len(response.content) > 100


def test_pdf_endpoint_no_data():
    """데이터 없을 때도 200 반환 및 빈 섹션 PDF 생성 (REQ-PDF-006)."""
    from lotto.web.app import app

    # 모든 데이터 게이트웨이가 None 반환하도록 패치
    with (
        patch("lotto.web.routes.api.get_stats", return_value=None),
        patch("lotto.web.routes.api.get_recommendations", return_value=None),
        patch("lotto.web.routes.api.get_simulation", return_value=None),
    ):
        c = TestClient(app)
        response = c.get("/api/report/pdf")

    # 데이터 없어도 500이 아닌 200을 반환해야 함
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content[:4] == b"%PDF"


def test_pdf_endpoint_with_mocked_data():
    """데이터가 있을 때 정상 PDF 생성을 확인한다."""

    from lotto.analyzer import FrequencyStats, Statistics
    from lotto.recommender import Recommendation
    from lotto.simulator import SimulationResult
    from lotto.web.app import app

    stats = Statistics(
        frequency=FrequencyStats(absolute={i: 50 - i for i in range(1, 46)}),
        bonus_frequency=FrequencyStats(absolute={i: 10 + i for i in range(1, 46)}),
        total_rounds=100,
    )
    recs = [
        Recommendation(
            numbers=[1, 2, 3, 4, 5, 6],
            strategy_label="고빈도",
            strategy_desc="고빈도 전략",
            scores=dict.fromkeys([1, 2, 3, 4, 5, 6], 0.5),
        ),
    ]
    sim = SimulationResult(
        total_rounds=1000,
        prize_counts={"1등": 1, "2등": 2, "3등": 5, "4등": 50, "5등": 200, "낙첨": 742},
        hit_rate=0.258,
        details=[],
    )

    with (
        patch("lotto.web.routes.api.get_stats", return_value=stats),
        patch("lotto.web.routes.api.get_recommendations", return_value=recs),
        patch("lotto.web.routes.api.get_simulation", return_value=sim),
    ):
        c = TestClient(app)
        response = c.get("/api/report/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content[:4] == b"%PDF"
    assert len(response.content) > 500
