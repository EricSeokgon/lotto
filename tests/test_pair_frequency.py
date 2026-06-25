"""SPEC-LOTTO-133: 번호 쌍(pair) 동시 출현 빈도 분석 테스트."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.data import get_pair_frequency_analysis


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
    """손계산 픽스처 — 3회차.

    회차1: 1,2,3,4,5,6 → 쌍 (1,2),(1,3),...,(5,6) = 15쌍 각 1회
    회차2: 1,2,3,4,5,7 → (1,2),(1,3),...,(5,7) = 15쌍
    회차3: 1,2,3,4,5,8 → (1,2),(1,3),...,(5,8) = 15쌍
    → (1,2),(1,3),(1,4),(1,5) 등 1~5 내부 쌍은 3회 모두 등장
    """
    return [
        make_draw(1, 1, 2, 3, 4, 5, 6),
        make_draw(2, 1, 2, 3, 4, 5, 7),
        make_draw(3, 1, 2, 3, 4, 5, 8),
    ]


def test_returns_none_when_empty() -> None:
    """빈 리스트 입력 시 None 반환."""
    with patch("lotto.web.data.get_draws", return_value=[]):
        result = get_pair_frequency_analysis()
    assert result is None


def test_returns_dict() -> None:
    """정상 데이터 입력 시 dict 반환."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_pair_frequency_analysis()
    assert isinstance(result, dict)


def test_required_keys() -> None:
    """반환 dict에 필수 키 모두 존재."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_pair_frequency_analysis()
    assert result is not None
    required_keys = (
        "total", "expected", "total_unique_pairs", "never_appeared",
        "top_pairs", "rare_pairs", "top_partners",
    )
    for key in required_keys:
        assert key in result, f"키 누락: {key}"


def test_top_pairs_max_20() -> None:
    """top_pairs는 최대 20개."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_pair_frequency_analysis()
    assert result is not None
    assert len(result["top_pairs"]) <= 20


def test_rare_pairs_max_20() -> None:
    """rare_pairs는 최대 20개."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_pair_frequency_analysis()
    assert result is not None
    assert len(result["rare_pairs"]) <= 20


def test_top_partners_has_45_keys() -> None:
    """top_partners는 1~45 번호 모두 포함."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_pair_frequency_analysis()
    assert result is not None
    partners = result["top_partners"]
    assert set(partners.keys()) == set(range(1, 46))


def test_top_partners_max_5_each() -> None:
    """top_partners 각 번호의 파트너는 최대 5개."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_pair_frequency_analysis()
    assert result is not None
    for n in range(1, 46):
        assert len(result["top_partners"][n]) <= 5


def test_never_appeared_plus_unique_is_990() -> None:
    """never_appeared + total_unique_pairs == 990."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_pair_frequency_analysis()
    assert result is not None
    assert result["never_appeared"] + result["total_unique_pairs"] == 990


def test_pair_frequency_sorted_descending() -> None:
    """top_pairs는 출현 횟수 내림차순 정렬."""
    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        result = get_pair_frequency_analysis()
    assert result is not None
    top = result["top_pairs"]
    if len(top) >= 2:
        assert top[0]["count"] >= top[-1]["count"]


def test_pair_frequency_page_200() -> None:
    """GET /stats/pair-frequency → 200 OK."""
    from lotto.web.app import app

    with patch("lotto.web.data.get_draws", return_value=sample_draws()):
        client = TestClient(app)
        response = client.get("/stats/pair-frequency")
    assert response.status_code == 200
