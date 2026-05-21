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
    """SPEC-LOTTO-006: /api/draws 가 데이터 있을 때 200과 페이지네이션 래퍼 반환."""
    from unittest.mock import MagicMock, patch

    from lotto.web.app import app

    mock_draw = MagicMock()
    mock_draw.drwNo = 1100
    mock_draw.model_dump.return_value = {"drwNo": 1100, "date": "2024-01-01"}

    with patch("lotto.web.routes.api.get_draws", return_value=[mock_draw]):
        c = TestClient(app)
        response = c.get("/api/draws")

    assert response.status_code == 200
    data = response.json()
    # SPEC-LOTTO-006 REQ-PAGE-002: 페이지네이션 래퍼 구조
    assert isinstance(data, dict)
    assert data["total"] == 1
    assert len(data["items"]) == 1


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


# ──────────────────────────────────────────────
# T-015: POST /api/scrape 테스트
# ──────────────────────────────────────────────

def test_post_scrape_returns_202():
    """POST /api/scrape 가 202 반환 (백그라운드 태스크 모킹)."""
    from unittest.mock import patch

    import lotto.web.routes.api as api_module
    from lotto.web.app import app

    # 수집 상태를 idle 로 리셋
    with api_module._collect_lock:
        api_module._collect_state["status"] = "idle"

    with patch("lotto.web.routes.api._scrape_worker"):
        c = TestClient(app)
        response = c.post("/api/scrape")

    assert response.status_code == 202
    assert response.json()["status"] == "started"


def test_post_scrape_returns_409_when_running():
    """이미 실행 중일 때 409 반환."""

    import lotto.web.routes.api as api_module
    from lotto.web.app import app

    # 수집 상태를 running 으로 설정
    with api_module._collect_lock:
        api_module._collect_state["status"] = "running"

    try:
        c = TestClient(app)
        response = c.post("/api/scrape")
        assert response.status_code == 409
    finally:
        # 테스트 후 상태 복원
        with api_module._collect_lock:
            api_module._collect_state["status"] = "idle"


# ──────────────────────────────────────────────
# T-016: /api/history CRUD 테스트
# ──────────────────────────────────────────────

def test_get_history_returns_list():
    """GET /api/history 가 리스트 반환."""
    from unittest.mock import patch

    from lotto.web.app import app

    with patch("lotto.web.data.compute_ticket_results", return_value=[]):
        c = TestClient(app)
        response = c.get("/api/history")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_post_history_returns_201():
    """POST /api/history 가 유효한 티켓으로 201 반환."""
    from unittest.mock import patch

    from lotto.web.app import app

    with patch("lotto.web.data.get_history", return_value=[]), \
         patch("lotto.web.data.save_history"):
        c = TestClient(app)
        response = c.post("/api/history", json={
            "drwNo": 1100,
            "numbers": [1, 2, 3, 4, 5, 6],
            "bought_at": "2024-01-15",
        })

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ok"
    assert "ticket" in body
    assert body["ticket"]["drwNo"] == 1100


def test_post_history_returns_400_on_duplicate_numbers():
    """번호 중복 시 400 반환."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/history", json={
        "drwNo": 1100,
        "numbers": [1, 1, 2, 3, 4, 5],  # 중복 후 6개 미만
        "bought_at": "2024-01-15",
    })
    assert response.status_code == 400


def test_post_history_returns_400_on_wrong_count():
    """번호 개수 5개 → 400 반환."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/history", json={
        "drwNo": 1100,
        "numbers": [1, 2, 3, 4, 5],
        "bought_at": "2024-01-15",
    })
    assert response.status_code == 400


def test_post_history_returns_400_on_out_of_range():
    """번호가 범위 초과 (46) → 400 반환."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/history", json={
        "drwNo": 1100,
        "numbers": [1, 2, 3, 4, 5, 46],
        "bought_at": "2024-01-15",
    })
    assert response.status_code == 400


def test_delete_history_returns_200():
    """DELETE /api/history/{id} 가 200 반환."""
    from unittest.mock import patch

    from lotto.web.app import app

    existing = [{"id": "test-id-123", "drwNo": 1100, "numbers": [1, 2, 3, 4, 5, 6]}]

    with patch("lotto.web.data.get_history", return_value=existing), \
         patch("lotto.web.data.save_history"):
        c = TestClient(app)
        response = c.delete("/api/history/test-id-123")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_delete_history_returns_404_not_found():
    """존재하지 않는 티켓 ID 삭제 시 404 반환."""
    from unittest.mock import patch

    from lotto.web.app import app

    with patch("lotto.web.data.get_history", return_value=[]):
        c = TestClient(app)
        response = c.delete("/api/history/nonexistent-id")

    assert response.status_code == 404


def test_post_history_invalid_date_format():
    """날짜 형식 오류 (YYYY/MM/DD) → 422 반환."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/history", json={
        "drwNo": 1100,
        "numbers": [1, 2, 3, 4, 5, 6],
        "bought_at": "2024/01/15",  # 잘못된 형식
    })
    assert response.status_code == 422


def test_post_history_invalid_drw_no():
    """drwNo = 0 → 422 반환."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/history", json={
        "drwNo": 0,
        "numbers": [1, 2, 3, 4, 5, 6],
        "bought_at": "2024-01-15",
    })
    assert response.status_code == 422


# ──────────────────────────────────────────────
# T-017: /api/collect 및 /api/collect/status 테스트
# ──────────────────────────────────────────────

def test_get_collect_status_returns_dict():
    """GET /api/collect/status 가 상태 딕셔너리 반환."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.get("/api/collect/status")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body


def test_post_collect_returns_409_when_running():
    """수집 중일 때 POST /api/collect 가 409 반환."""
    import lotto.web.routes.api as api_module
    from lotto.web.app import app

    with api_module._collect_lock:
        api_module._collect_state["status"] = "running"

    try:
        c = TestClient(app)
        response = c.post("/api/collect")
        assert response.status_code == 409
    finally:
        with api_module._collect_lock:
            api_module._collect_state["status"] = "idle"


def test_post_collect_full_param():
    """POST /api/collect?full=true 가 202 반환."""
    from unittest.mock import patch

    import lotto.web.routes.api as api_module
    from lotto.web.app import app

    with api_module._collect_lock:
        api_module._collect_state["status"] = "idle"

    with patch("lotto.web.routes.api._collect_worker"), \
         patch("lotto.collector.LottoCollector.load_existing", return_value=[]):
        c = TestClient(app)
        response = c.post("/api/collect?full=true")
    assert response.status_code == 202
    assert response.json()["status"] == "started"


def test_post_collect_count_param():
    """POST /api/collect?count=10 가 202 반환."""
    from unittest.mock import patch

    import lotto.web.routes.api as api_module
    from lotto.web.app import app

    with api_module._collect_lock:
        api_module._collect_state["status"] = "idle"

    with patch("lotto.web.routes.api._collect_worker"), \
         patch("lotto.collector.LottoCollector.load_existing", return_value=[]):
        c = TestClient(app)
        response = c.post("/api/collect?count=10")
    assert response.status_code == 202


def test_post_collect_incremental_with_existing():
    """기존 데이터 있을 때 증분 수집 시작 회차가 마지막+1."""
    from unittest.mock import MagicMock, patch

    import lotto.web.routes.api as api_module
    from lotto.web.app import app

    with api_module._collect_lock:
        api_module._collect_state["status"] = "idle"

    mock_draw = MagicMock()
    mock_draw.drwNo = 1100

    with patch("lotto.web.routes.api._collect_worker"), \
         patch("lotto.collector.LottoCollector.load_existing", return_value=[mock_draw]):
        c = TestClient(app)
        response = c.post("/api/collect")

    assert response.status_code == 202
    assert response.json()["start_from"] == 1101


# ──────────────────────────────────────────────
# T-018: /api/draws/manual 테스트
# ──────────────────────────────────────────────

def test_post_draws_manual_returns_201():
    """POST /api/draws/manual 이 유효한 데이터로 201 반환."""
    from unittest.mock import patch

    from lotto.web.app import app

    with patch("lotto.collector.LottoCollector.load_existing", return_value=[]), \
         patch("lotto.collector.LottoCollector.save_csv"):
        c = TestClient(app)
        response = c.post("/api/draws/manual", json={
            "drwNo": 9999,
            "date": "2024-01-15",
            "numbers": [1, 2, 3, 4, 5, 6],
            "bonus": 7,
        })

    assert response.status_code == 201
    assert response.json()["status"] == "ok"


def test_post_draws_manual_returns_409_on_duplicate():
    """중복 회차 수동 입력 시 409 반환."""
    import datetime
    from unittest.mock import patch

    from lotto.models import DrawResult
    from lotto.web.app import app

    existing_draw = DrawResult(
        drwNo=9999,
        date=datetime.date(2024, 1, 15),
        n1=1, n2=2, n3=3, n4=4, n5=5, n6=6, bonus=7,
    )

    with patch("lotto.collector.LottoCollector.load_existing", return_value=[existing_draw]):
        c = TestClient(app)
        response = c.post("/api/draws/manual", json={
            "drwNo": 9999,
            "date": "2024-01-15",
            "numbers": [1, 2, 3, 4, 5, 6],
            "bonus": 7,
        })

    assert response.status_code == 409


def test_post_draws_manual_invalid_bonus_in_numbers():
    """보너스 번호가 당첨 번호와 중복 시 422 반환."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/draws/manual", json={
        "drwNo": 9999,
        "date": "2024-01-15",
        "numbers": [1, 2, 3, 4, 5, 6],
        "bonus": 3,  # 중복
    })
    assert response.status_code == 422


def test_post_draws_manual_invalid_date():
    """날짜 형식 오류 시 422 반환."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/draws/manual", json={
        "drwNo": 9999,
        "date": "20240115",
        "numbers": [1, 2, 3, 4, 5, 6],
        "bonus": 7,
    })
    assert response.status_code == 422


def test_post_draws_manual_invalid_drw_no():
    """drwNo < 1 시 422 반환."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/draws/manual", json={
        "drwNo": 0,
        "date": "2024-01-15",
        "numbers": [1, 2, 3, 4, 5, 6],
        "bonus": 7,
    })
    assert response.status_code == 422


def test_post_draws_manual_wrong_count():
    """번호 5개 시 422 반환."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/draws/manual", json={
        "drwNo": 9999,
        "date": "2024-01-15",
        "numbers": [1, 2, 3, 4, 5],
        "bonus": 7,
    })
    assert response.status_code == 422


def test_post_draws_manual_duplicate_numbers():
    """중복 번호 시 422 반환."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/draws/manual", json={
        "drwNo": 9999,
        "date": "2024-01-15",
        "numbers": [1, 1, 3, 4, 5, 6],
        "bonus": 7,
    })
    assert response.status_code == 422


def test_post_draws_manual_out_of_range():
    """번호 범위 초과 시 422 반환."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/draws/manual", json={
        "drwNo": 9999,
        "date": "2024-01-15",
        "numbers": [1, 2, 3, 4, 5, 46],
        "bonus": 7,
    })
    assert response.status_code == 422


def test_get_history_api_returns_list():
    """GET /api/history 가 빈 리스트 반환."""
    from unittest.mock import patch

    from lotto.web.app import app

    with patch("lotto.web.data.compute_ticket_results", return_value=[]):
        c = TestClient(app)
        response = c.get("/api/history")

    assert response.status_code == 200
    assert response.json() == []


def test_delete_history_not_found():
    """존재하지 않는 ticket_id 삭제 시 404 반환."""
    from unittest.mock import patch

    from lotto.web.app import app

    with patch("lotto.web.data.get_history", return_value=[]):
        c = TestClient(app)
        response = c.delete("/api/history/nonexistent-id")

    assert response.status_code == 404


def test_post_draws_manual_invalid_bonus():
    """보너스 번호 범위 초과 시 422 반환."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.post("/api/draws/manual", json={
        "drwNo": 9999,
        "date": "2024-01-15",
        "numbers": [1, 2, 3, 4, 5, 6],
        "bonus": 46,
    })
    assert response.status_code == 422
