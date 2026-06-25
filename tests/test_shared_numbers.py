"""SPEC-LOTTO-134: 연속 회차 공유 번호 분석 테스트."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.data import get_shared_numbers_analysis


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
    """손계산 픽스처 — 4회차.

    회차1: 1,2,3,4,5,6
    회차2: 1,2,3,4,5,7  → 1회와 공유: {1,2,3,4,5} = 5개
    회차3: 7,8,9,10,11,12 → 2회와 공유: {7} = 1개
    회차4: 1,2,3,40,41,42 → 3회와 공유: {} = 0개
    """
    return [
        make_draw(1, 1, 2, 3, 4, 5, 6),
        make_draw(2, 1, 2, 3, 4, 5, 7),
        make_draw(3, 7, 8, 9, 10, 11, 12),
        make_draw(4, 1, 2, 3, 40, 41, 42),
    ]


def test_returns_none_when_empty() -> None:
    """빈 리스트 입력 시 None 반환."""
    with patch("lotto.web.data.get_draws", return_value=[]):
        result = get_shared_numbers_analysis()
    assert result is None


def test_returns_none_when_single_draw() -> None:
    """회차가 1개일 때 None 반환."""
    draws = [make_draw(1, 1, 2, 3, 4, 5, 6)]
    with patch("lotto.web.data.get_draws", return_value=draws):
        result = get_shared_numbers_analysis()
    assert result is None


def test_returns_dict() -> None:
    """정상 데이터 입력 시 dict 반환."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_shared_numbers_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """반환 dict에 필수 키 모두 존재."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_shared_numbers_analysis()
    assert result is not None
    required_keys = (
        "total", "pairs", "avg_shared", "max_shared", "max_shared_pair",
        "min_shared", "min_shared_pair", "best_shared", "best_shared_pct",
        "no_shared_pct", "dist_list", "recent",
    )
    for key in required_keys:
        assert key in result, f"키 누락: {key}"


def test_pairs_count() -> None:
    """pairs = total - 1 검증."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_shared_numbers_analysis()
    assert result is not None
    assert result["total"] == 4
    assert result["pairs"] == 3


def test_max_shared() -> None:
    """최대 공유 번호 수 검증 (회차1-2: 5개 공유)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_shared_numbers_analysis()
    assert result is not None
    assert result["max_shared"] == 5
    assert result["max_shared_pair"] == [1, 2]


def test_min_shared() -> None:
    """최소 공유 번호 수 검증 (회차3-4: 0개 공유)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_shared_numbers_analysis()
    assert result is not None
    assert result["min_shared"] == 0
    assert result["min_shared_pair"] == [3, 4]


def test_dist_list_length() -> None:
    """dist_list 는 항상 7개 항목 (0~6)."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_shared_numbers_analysis()
    assert result is not None
    assert len(result["dist_list"]) == 7
    for item in result["dist_list"]:
        assert "shared" in item
        assert "count" in item
        assert "pct" in item


def test_recent_order() -> None:
    """recent 목록은 최신 순(역순)으로 정렬."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_shared_numbers_analysis()
    assert result is not None
    recent = result["recent"]
    assert len(recent) > 0
    # 첫 항목이 가장 최신 회차 쌍이어야 함
    assert recent[0]["draw_a"] > recent[-1]["draw_a"]


def test_page_endpoint() -> None:
    """웹 엔드포인트 /stats/shared-numbers 200 응답."""
    from lotto.web.app import app

    client = TestClient(app)
    draws = sample_draws()
    with patch("lotto.web.data.get_draws", return_value=draws):
        response = client.get("/stats/shared-numbers")
    assert response.status_code == 200
    assert "공유 번호" in response.text
