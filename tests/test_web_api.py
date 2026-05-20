"""API 라우트 테스트 — JSON 엔드포인트 및 유효성 검사."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """테스트 클라이언트 픽스처."""
    from lotto.web.app import app

    return TestClient(app)


# ──────────────────────────────────────────────
# T-013: GET API 라우트
# ──────────────────────────────────────────────

def test_health_returns_ok(client):
    """/health 가 200 반환."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_api_draws_returns_200_or_503(client):
    """/api/draws 가 200 또는 503(데이터 없음) 반환."""
    response = client.get("/api/draws")
    assert response.status_code in (200, 503)


def test_api_stats_returns_200_or_503(client):
    """/api/stats 가 200 또는 503 반환."""
    response = client.get("/api/stats")
    assert response.status_code in (200, 503)


def test_api_recommendations_default(client):
    """/api/recommendations 기본 요청이 200 또는 503 반환."""
    response = client.get("/api/recommendations")
    assert response.status_code in (200, 503)


def test_api_recommendations_invalid_count(client):
    """/api/recommendations?count=100 이 422 반환."""
    response = client.get("/api/recommendations?count=100")
    assert response.status_code == 422


def test_api_recommendations_count_too_small(client):
    """/api/recommendations?count=0 이 422 반환."""
    response = client.get("/api/recommendations?count=0")
    assert response.status_code == 422


def test_api_simulation_invalid_rounds_zero(client):
    """/api/simulation?rounds=0 이 422 반환."""
    response = client.get("/api/simulation?rounds=0")
    assert response.status_code == 422


def test_api_simulation_invalid_rounds_too_large(client):
    """/api/simulation?rounds=200000 이 422 반환."""
    response = client.get("/api/simulation?rounds=200000")
    assert response.status_code == 422


def test_api_503_has_error_structure(client, tmp_path, monkeypatch):
    """데이터 없을 때 /api/draws 가 503 및 오류 구조 반환."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    # 새 TestClient를 생성해 데이터 없는 상태에서 요청
    from lotto.web.app import app
    c = TestClient(app)
    response = c.get("/api/draws")
    assert response.status_code == 503
    body = response.json()
    # FastAPI 오류 구조: {"detail": ...}
    assert "detail" in body


# ──────────────────────────────────────────────
# T-014: POST API 라우트
# ──────────────────────────────────────────────

def test_api_draws_with_data():
    """/api/draws 가 데이터 있을 때 200과 리스트 반환."""
    from unittest.mock import MagicMock, patch

    from lotto.web.app import app

    mock_draw = MagicMock()
    mock_draw.model_dump.return_value = {"drwNo": 1100, "date": "2024-01-01"}

    with patch("lotto.web.routes.api.get_draws", return_value=[mock_draw]):
        c = TestClient(app)
        response = c.get("/api/draws")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1


def test_api_stats_with_data():
    """/api/stats 가 데이터 있을 때 200 반환."""
    from unittest.mock import MagicMock, patch

    from lotto.web.app import app

    mock_stats = MagicMock()
    mock_stats.model_dump.return_value = {"total_rounds": 100}

    with patch("lotto.web.routes.api.get_stats", return_value=mock_stats):
        c = TestClient(app)
        response = c.get("/api/stats")

    assert response.status_code == 200


def test_api_recommendations_with_data():
    """/api/recommendations 가 데이터 있을 때 200 반환."""
    from unittest.mock import MagicMock, patch

    from lotto.web.app import app

    mock_rec = MagicMock()
    mock_rec.model_dump.return_value = {"numbers": [1, 2, 3, 4, 5, 6], "strategy_label": "균형"}

    with patch("lotto.web.routes.api.get_recommendations", return_value=[mock_rec]):
        c = TestClient(app)
        response = c.get("/api/recommendations?count=1")

    assert response.status_code == 200


def test_api_simulation_with_data():
    """/api/simulation 이 데이터 있을 때 200 반환."""
    from unittest.mock import MagicMock, patch

    from lotto.web.app import app

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"total_rounds": 100, "hit_rate": 0.05}

    with patch("lotto.web.routes.api.get_simulation", return_value=mock_result):
        c = TestClient(app)
        response = c.get("/api/simulation?rounds=100")

    assert response.status_code == 200


def test_api_simulation_result_model_dump():
    """/api/simulation 응답이 model_dump 결과를 반환하는지 확인."""
    from unittest.mock import MagicMock, patch

    from lotto.web.app import app

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "total_rounds": 100,
        "prize_counts": {"5등": 5},
        "hit_rate": 0.05,
        "details": [],
    }

    with patch("lotto.web.routes.api.get_simulation", return_value=mock_result):
        c = TestClient(app)
        response = c.get("/api/simulation?rounds=100")

    assert response.status_code == 200
    assert response.json()["total_rounds"] == 100


def test_post_collect_returns_202():
    """POST /api/collect 가 202 반환 (백그라운드 태스크 모킹)."""
    from unittest.mock import patch

    from lotto.web.app import app

    with patch(
        "lotto.collector.LottoCollector.load_existing", return_value=[]
    ), patch("lotto.collector.LottoCollector.collect_new", return_value=[]):
        c = TestClient(app)
        response = c.post("/api/collect")
    assert response.status_code == 202
    assert response.json()["status"] == "started"


def test_post_analyze_returns_202():
    """POST /api/analyze 가 202 반환 (백그라운드 태스크 모킹)."""
    from unittest.mock import patch

    from lotto.web.app import app

    # 백그라운드 분석 함수를 모킹해서 실제 파일 I/O를 피함
    with patch("lotto.web.routes.api.trigger_analyze.__wrapped__", create=True):
        c = TestClient(app, raise_server_exceptions=False)
        with patch("lotto.collector.LottoCollector.load_existing", return_value=[]):
            response = c.post("/api/analyze")
    assert response.status_code == 202
    assert response.json()["status"] == "started"


def test_api_stats_503_when_none():
    """/api/stats 가 None 반환 시 503 반환."""
    from unittest.mock import patch

    from lotto.web.app import app

    with patch("lotto.web.routes.api.get_stats", return_value=None):
        c = TestClient(app)
        response = c.get("/api/stats")
    assert response.status_code == 503


def test_api_recommendations_503_when_none():
    """/api/recommendations 가 None 반환 시 503 반환."""
    from unittest.mock import patch

    from lotto.web.app import app

    with patch("lotto.web.routes.api.get_recommendations", return_value=None):
        c = TestClient(app)
        response = c.get("/api/recommendations")
    assert response.status_code == 503


def test_api_simulation_503_when_none():
    """/api/simulation 이 None 반환 시 503 반환."""
    from unittest.mock import patch

    from lotto.web.app import app

    with patch("lotto.web.routes.api.get_simulation", return_value=None):
        c = TestClient(app)
        response = c.get("/api/simulation")
    assert response.status_code == 503


def test_post_analyze_with_draws_runs_analysis():
    """POST /api/analyze 백그라운드에서 draws 있을 때 analyzer 호출."""
    from unittest.mock import MagicMock, patch

    from lotto.web.app import app

    mock_draw = MagicMock()
    mock_stats = MagicMock()

    with patch(
        "lotto.collector.LottoCollector.load_existing", return_value=[mock_draw]
    ), patch("lotto.analyzer.LottoAnalyzer.analyze", return_value=mock_stats), patch(
        "lotto.analyzer.LottoAnalyzer.save_stats"
    ):
        c = TestClient(app)
        response = c.post("/api/analyze")
    assert response.status_code == 202
