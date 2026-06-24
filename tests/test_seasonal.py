"""SPEC-LOTTO-120 계절별 번호 분석 테스트."""

from __future__ import annotations

import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.web.app import app
from lotto.web.data import get_seasonal_analysis

client = TestClient(app)


def _make_draw(drw_no: int, nums: list[int], month: int) -> object:
    """테스트용 DrawResult 생성."""
    from lotto.models import DrawResult

    return DrawResult(
        drwNo=drw_no,
        date=datetime.date(2020, month, 4),
        n1=nums[0],
        n2=nums[1],
        n3=nums[2],
        n4=nums[3],
        n5=nums[4],
        n6=nums[5],
        bonus=45,
    )


# 테스트용 회차 목록: 봄(3월) 2회, 여름(7월) 1회, 가을(10월) 1회, 겨울(1월) 1회
_SAMPLE_DRAWS = [
    _make_draw(1, [1, 2, 3, 4, 5, 6], 3),   # 봄
    _make_draw(2, [7, 8, 9, 10, 11, 12], 4),  # 봄
    _make_draw(3, [13, 14, 15, 16, 17, 18], 7),  # 여름
    _make_draw(4, [19, 20, 21, 22, 23, 24], 10),  # 가을
    _make_draw(5, [25, 26, 27, 28, 29, 30], 1),   # 겨울
]


def test_get_seasonal_returns_none_when_empty() -> None:
    """빈 데이터일 때 None을 반환한다."""
    with patch("lotto.web.data.get_draws", return_value=[]):
        result = get_seasonal_analysis()
    assert result is None


def test_get_seasonal_returns_dict() -> None:
    """정상 데이터일 때 dict를 반환한다."""
    with patch("lotto.web.data.get_draws", return_value=_SAMPLE_DRAWS):
        result = get_seasonal_analysis()
    assert isinstance(result, dict)


def test_get_seasonal_has_required_keys() -> None:
    """반환 dict에 season_order, season_draws, seasons 키가 있다."""
    with patch("lotto.web.data.get_draws", return_value=_SAMPLE_DRAWS):
        result = get_seasonal_analysis()
    assert result is not None
    assert "season_order" in result
    assert "season_draws" in result
    assert "seasons" in result


def test_get_seasonal_season_order() -> None:
    """season_order가 ['봄', '여름', '가을', '겨울'] 순서다."""
    with patch("lotto.web.data.get_draws", return_value=_SAMPLE_DRAWS):
        result = get_seasonal_analysis()
    assert result is not None
    assert result["season_order"] == ["봄", "여름", "가을", "겨울"]


def test_get_seasonal_draws_sum() -> None:
    """season_draws 값의 합계가 전체 회차 수와 같다."""
    with patch("lotto.web.data.get_draws", return_value=_SAMPLE_DRAWS):
        result = get_seasonal_analysis()
    assert result is not None
    total = sum(result["season_draws"].values())
    assert total == len(_SAMPLE_DRAWS)


def test_get_seasonal_top10_len() -> None:
    """각 계절의 top10 길이가 10 이하다."""
    with patch("lotto.web.data.get_draws", return_value=_SAMPLE_DRAWS):
        result = get_seasonal_analysis()
    assert result is not None
    for season in result["season_order"]:
        assert len(result["seasons"][season]["top10"]) <= 10


def test_get_seasonal_rate_range() -> None:
    """모든 rate 값이 0 이상 100 이하다."""
    with patch("lotto.web.data.get_draws", return_value=_SAMPLE_DRAWS):
        result = get_seasonal_analysis()
    assert result is not None
    for season in result["season_order"]:
        for item in result["seasons"][season]["top10"]:
            assert 0.0 <= item["rate"] <= 100.0


def test_get_seasonal_spring_draws() -> None:
    """봄(3, 4, 5월) 회차 수가 정확히 계산된다."""
    with patch("lotto.web.data.get_draws", return_value=_SAMPLE_DRAWS):
        result = get_seasonal_analysis()
    assert result is not None
    # _SAMPLE_DRAWS에서 봄(3월, 4월) 회차는 2개
    assert result["season_draws"]["봄"] == 2


def test_seasonal_page_200() -> None:
    """GET /stats/seasonal가 200을 반환한다."""
    with patch("lotto.web.data.get_draws", return_value=_SAMPLE_DRAWS):
        response = client.get("/stats/seasonal")
    assert response.status_code == 200


def test_seasonal_page_no_data() -> None:
    """데이터 없을 때 /stats/seasonal가 200을 반환하고 경고 메시지를 포함한다."""
    with patch("lotto.web.data.get_draws", return_value=[]):
        response = client.get("/stats/seasonal")
    assert response.status_code == 200
    assert "데이터가 없습니다" in response.text
