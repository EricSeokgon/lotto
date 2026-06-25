"""SPEC-LOTTO-136: 번호 위치별 분포 분석 테스트."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_position_dist_analysis


def make_draw(
    draw_no: int,
    n1: int,
    n2: int,
    n3: int,
    n4: int,
    n5: int,
    n6: int,
    bonus: int = 45,
) -> DrawResult:
    """테스트용 DrawResult 생성 헬퍼."""
    return DrawResult(
        drwNo=draw_no,
        date=date(2020, 1, 1),
        n1=n1,
        n2=n2,
        n3=n3,
        n4=n4,
        n5=n5,
        n6=n6,
        bonus=bonus,
    )


def sample_draws() -> list[DrawResult]:
    """테스트용 픽스처 — 위치별 분포 검증을 위한 다양한 번호 조합."""
    return [
        make_draw(1, 1, 5, 10, 20, 30, 40),
        make_draw(2, 2, 6, 11, 21, 31, 41),
        make_draw(3, 3, 7, 12, 22, 32, 42),
        make_draw(4, 4, 8, 13, 23, 33, 43),
        make_draw(5, 1, 9, 14, 24, 34, 44),
    ]


def test_returns_none_when_empty() -> None:
    """빈 목록 입력 시 None 반환."""
    with patch("lotto.web.data.get_draws", return_value=[]):
        result = get_position_dist_analysis()
    assert result is None


def test_returns_dict() -> None:
    """정상 데이터 시 dict 반환."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_position_dist_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """반환 dict에 total, positions, recent 키 존재."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_position_dist_analysis()
    assert result is not None
    assert "total" in result
    assert "positions" in result
    assert "recent" in result


def test_positions_length_is_6() -> None:
    """positions 리스트 길이 == 6."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_position_dist_analysis()
    assert result is not None
    assert len(result["positions"]) == 6


def test_position_keys() -> None:
    """각 position 항목에 필수 키 존재."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_position_dist_analysis()
    assert result is not None
    required = {"pos", "avg", "min", "max", "mode", "mode_count", "top5", "bucket_list"}
    for p in result["positions"]:
        for key in required:
            assert key in p, f"키 '{key}' 없음: {p}"


def test_position_numbers_sorted() -> None:
    """위치 1의 평균 < 위치 6의 평균 (오름차순 정렬 후 위치 특성)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_position_dist_analysis()
    assert result is not None
    positions = result["positions"]
    assert positions[0]["avg"] < positions[5]["avg"]


def test_bucket_list_length_is_5() -> None:
    """각 position의 bucket_list 길이 == 5."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_position_dist_analysis()
    assert result is not None
    for p in result["positions"]:
        assert len(p["bucket_list"]) == 5, f"위치 {p['pos']} bucket_list 길이 오류"


def test_top5_length_lte_5() -> None:
    """각 position의 top5 길이 <= 5."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_position_dist_analysis()
    assert result is not None
    for p in result["positions"]:
        assert len(p["top5"]) <= 5, f"위치 {p['pos']} top5 길이 오류"


def test_recent_length_lte_20() -> None:
    """recent 리스트 길이 <= 20."""
    # 25회차 데이터 생성
    draws = [make_draw(i, 1, 2, 3, 4, 5, 6) for i in range(1, 26)]
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_position_dist_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


def test_position_dist_page_200() -> None:
    """GET /stats/position-dist → HTTP 200."""
    client = TestClient(app)
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        response = client.get("/stats/position-dist")
    assert response.status_code == 200
