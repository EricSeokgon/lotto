"""SPEC-LOTTO-006: /api/recommendations 전략 필터 테스트.

REQ-FILTER-001/002/003 검증.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _make_mock_rec(strategy_label: str, numbers: list[int] | None = None) -> MagicMock:
    """추천 결과 mock 객체를 생성합니다."""
    m = MagicMock()
    m.strategy_label = strategy_label
    m.model_dump.return_value = {
        "numbers": numbers or [1, 2, 3, 4, 5, 6],
        "strategy_label": strategy_label,
        "strategy_desc": "",
        "scores": {},
    }
    return m


def test_recommendations_no_filter_returns_list() -> None:
    """REQ-FILTER-002: strategy 파라미터 없으면 기존 동작 유지 (모든 전략 반환)."""
    from lotto.web.app import app

    # 8개 전략 mock
    mock_recs = [
        _make_mock_rec(label) for label in [
            "고빈도", "저빈도", "균형", "최근편향",
            "동반패턴", "홀짝균형", "번호대균형", "핫콜드혼합",
        ]
    ]
    with patch("lotto.web.routes.api.get_recommendations", return_value=mock_recs):
        c = TestClient(app)
        response = c.get("/api/recommendations?count=8")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # 8개 전략 라벨 모두 포함되어야 함
    labels = {item["strategy_label"] for item in data}
    assert "고빈도" in labels
    assert "저빈도" in labels


def test_recommendations_strategy_filter_match() -> None:
    """REQ-FILTER-001: strategy 파라미터로 특정 전략만 반환."""
    from lotto.web.app import app

    mock_recs = [
        _make_mock_rec("고빈도"),
        _make_mock_rec("저빈도"),
        _make_mock_rec("균형"),
        _make_mock_rec("최근편향"),
        _make_mock_rec("동반패턴"),
        _make_mock_rec("홀짝균형"),
        _make_mock_rec("번호대균형"),
        _make_mock_rec("핫콜드혼합"),
    ]
    with patch("lotto.web.routes.api.get_recommendations", return_value=mock_recs):
        c = TestClient(app)
        response = c.get("/api/recommendations?strategy=고빈도&count=8")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    for item in data:
        assert item["strategy_label"] == "고빈도"


def test_recommendations_invalid_strategy_returns_empty_list() -> None:
    """REQ-FILTER-003: 존재하지 않는 전략은 200 + 빈 리스트."""
    from lotto.web.app import app

    mock_recs = [_make_mock_rec("균형")]
    with patch("lotto.web.routes.api.get_recommendations", return_value=mock_recs):
        c = TestClient(app)
        response = c.get("/api/recommendations?strategy=존재하지않는전략")

    assert response.status_code == 200
    assert response.json() == []


def test_recommendations_strategy_filter_with_count() -> None:
    """REQ-FILTER-001: count과 함께 사용 시 필터 결과 반환."""
    from lotto.web.app import app

    # count=3 호출 시 backend가 3개를 반환하도록 mock
    mock_recs = [
        _make_mock_rec("저빈도"),
        _make_mock_rec("저빈도"),
        _make_mock_rec("저빈도"),
    ]
    with patch("lotto.web.routes.api.get_recommendations", return_value=mock_recs) as m:
        c = TestClient(app)
        response = c.get("/api/recommendations?strategy=저빈도&count=3")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    for item in data:
        assert item["strategy_label"] == "저빈도"
    # get_recommendations가 count=3으로 호출되었는지 검증
    m.assert_called_once_with(count=3)
