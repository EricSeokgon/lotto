"""SPEC-LOTTO-117: 번호별 통합 점수 히트맵 테스트."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.data import get_number_heatmap


def make_draw(
    draw_no: int,
    n1: int,
    n2: int,
    n3: int,
    n4: int,
    n5: int,
    n6: int,
    bonus: int = 30,
) -> DrawResult:
    """테스트용 DrawResult 생성 헬퍼."""
    return DrawResult(
        drwNo=draw_no,
        date=date(2024, 1, 1),
        n1=n1,
        n2=n2,
        n3=n3,
        n4=n4,
        n5=n5,
        n6=n6,
        bonus=bonus,
    )


def fixture_draws() -> list[DrawResult]:
    """테스트용 10회차 픽스처."""
    return [
        make_draw(1, 1, 2, 3, 4, 5, 6, bonus=7),
        make_draw(2, 1, 8, 9, 10, 11, 12, bonus=13),
        make_draw(3, 2, 14, 15, 16, 17, 18, bonus=19),
        make_draw(4, 1, 20, 21, 22, 23, 24, bonus=25),
        make_draw(5, 3, 26, 27, 28, 29, 30, bonus=31),
        make_draw(6, 2, 32, 33, 34, 35, 36, bonus=37),
        make_draw(7, 4, 38, 39, 40, 41, 42, bonus=43),
        make_draw(8, 1, 5, 10, 15, 20, 25, bonus=30),
        make_draw(9, 2, 6, 11, 16, 21, 26, bonus=31),
        make_draw(10, 3, 7, 12, 17, 22, 27, bonus=32),
    ]


# ---------------------------------------------------------------------------
# 데이터 레이어 테스트
# ---------------------------------------------------------------------------


def test_get_number_heatmap_returns_none_when_no_draws() -> None:
    """빈 draws 목록이면 None을 반환한다."""
    with patch("lotto.web.data.get_draws", return_value=[]):
        result = get_number_heatmap()
    assert result is None


def test_get_number_heatmap_returns_45_items() -> None:
    """결과 리스트는 정확히 45개 항목을 가진다."""
    with patch("lotto.web.data.get_draws", return_value=fixture_draws()):
        result = get_number_heatmap()
    assert result is not None
    assert len(result) == 45


def test_get_number_heatmap_numbers_1_to_45() -> None:
    """number 필드는 1부터 45까지 순서대로 존재한다."""
    with patch("lotto.web.data.get_draws", return_value=fixture_draws()):
        result = get_number_heatmap()
    assert result is not None
    numbers = [item["number"] for item in result]
    assert numbers == list(range(1, 46))


def test_get_number_heatmap_all_scores_in_0_1_range() -> None:
    """모든 점수(freq, recent, gap, pair, composite)는 [0, 1] 범위 내에 있다."""
    with patch("lotto.web.data.get_draws", return_value=fixture_draws()):
        result = get_number_heatmap()
    assert result is not None
    for item in result:
        for key in ("freq_score", "recent_score", "gap_score", "pair_score", "composite"):
            val = item[key]
            assert 0.0 <= val <= 1.0, f"number={item['number']} {key}={val} not in [0,1]"


def test_get_number_heatmap_composite_is_average() -> None:
    """composite는 4개 점수의 평균이다 (부동소수점 오차 허용)."""
    with patch("lotto.web.data.get_draws", return_value=fixture_draws()):
        result = get_number_heatmap()
    assert result is not None
    for item in result:
        s = item["freq_score"] + item["recent_score"] + item["gap_score"] + item["pair_score"]
        expected = s / 4
        assert abs(item["composite"] - round(expected, 4)) < 1e-3, (
            f"number={item['number']} composite={item['composite']} expected={expected}"
        )


def test_get_number_heatmap_data_has_required_fields() -> None:
    """각 항목은 필수 필드를 모두 포함한다."""
    with patch("lotto.web.data.get_draws", return_value=fixture_draws()):
        result = get_number_heatmap()
    assert result is not None
    required_fields = {
        "number", "freq_score", "recent_score", "gap_score", "pair_score", "composite"
    }
    for item in result:
        assert required_fields == set(item.keys()), f"Missing fields in {item}"


# ---------------------------------------------------------------------------
# 라우트 테스트
# ---------------------------------------------------------------------------


def test_heatmap_page_200() -> None:
    """GET /stats/heatmap은 200을 반환한다."""
    from lotto.web.app import app

    client = TestClient(app)
    with patch("lotto.web.data.get_draws", return_value=fixture_draws()):
        resp = client.get("/stats/heatmap")
    assert resp.status_code == 200


def test_heatmap_page_no_data() -> None:
    """데이터 없음 상태에서도 /stats/heatmap은 200을 반환한다."""
    from lotto.web.app import app

    client = TestClient(app)
    with patch("lotto.web.data.get_draws", return_value=[]):
        resp = client.get("/stats/heatmap")
    assert resp.status_code == 200
    assert "데이터가 없습니다" in resp.text
