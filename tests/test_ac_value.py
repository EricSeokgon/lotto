"""SPEC-LOTTO-121 AC값 분석 테스트."""

from __future__ import annotations

import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import _calc_ac, get_ac_analysis

client = TestClient(app)


def _mk(no: int, nums: list[int], bonus: int = 7) -> DrawResult:
    """DrawResult 헬퍼."""
    return DrawResult(
        drwNo=no,
        date=datetime.date(2020, 1, 1) + datetime.timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2],
        n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# ---------------------------------------------------------------------------
# _calc_ac 단위 테스트
# ---------------------------------------------------------------------------


def test_calc_ac_consecutive() -> None:
    """[1,2,3,4,5,6] → diffs={1,2,3,4,5} → 5-5=0."""
    assert _calc_ac([1, 2, 3, 4, 5, 6]) == 0


def test_calc_ac_spread() -> None:
    """[1,10,20,30,40,45] → 15개 고유 차이 → AC=10."""
    result = _calc_ac([1, 10, 20, 30, 40, 45])
    assert result >= 7  # 고분산 조합은 AC가 높다


# ---------------------------------------------------------------------------
# get_ac_analysis 단위 테스트
# ---------------------------------------------------------------------------


def test_get_ac_analysis_returns_none_when_empty() -> None:
    """빈 데이터면 None을 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=[]):
        result = get_ac_analysis()
    assert result is None


def test_get_ac_analysis_returns_dict() -> None:
    """데이터가 있으면 dict를 반환한다."""
    from lotto.web import data as wd

    draws = [_mk(1, [1, 2, 3, 4, 5, 6]), _mk(2, [1, 10, 20, 30, 40, 45])]
    with patch.object(wd, "get_draws", return_value=draws):
        result = get_ac_analysis()
    assert isinstance(result, dict)


def test_get_ac_analysis_has_required_keys() -> None:
    """반환 dict에 필수 키가 모두 있다."""
    from lotto.web import data as wd

    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    with patch.object(wd, "get_draws", return_value=draws):
        result = get_ac_analysis()
    assert result is not None
    for key in ("total", "distribution", "best_ac", "best_ac_pct", "avg_ac", "recent"):
        assert key in result


def test_get_ac_analysis_distribution_keys() -> None:
    """distribution 딕셔너리 키는 0~10이다."""
    from lotto.web import data as wd

    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    with patch.object(wd, "get_draws", return_value=draws):
        result = get_ac_analysis()
    assert result is not None
    assert set(result["distribution"].keys()) == set(range(11))


def test_get_ac_analysis_distribution_sum() -> None:
    """distribution 카운트 합계 == total."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 6)]
    with patch.object(wd, "get_draws", return_value=draws):
        result = get_ac_analysis()
    assert result is not None
    assert sum(result["distribution"].values()) == result["total"]


def test_get_ac_analysis_avg_range() -> None:
    """avg_ac 범위는 0.0~10.0이다."""
    from lotto.web import data as wd

    draws = [_mk(1, [1, 2, 3, 4, 5, 6]), _mk(2, [1, 10, 20, 30, 40, 45])]
    with patch.object(wd, "get_draws", return_value=draws):
        result = get_ac_analysis()
    assert result is not None
    assert 0.0 <= result["avg_ac"] <= 10.0


def test_get_ac_analysis_recent_max_20() -> None:
    """recent 목록은 최대 20개이다."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 31)]
    with patch.object(wd, "get_draws", return_value=draws):
        result = get_ac_analysis()
    assert result is not None
    assert len(result["recent"]) <= 20


# ---------------------------------------------------------------------------
# 페이지 라우트 테스트
# ---------------------------------------------------------------------------


def test_ac_value_page_200() -> None:
    """데이터가 있으면 /stats/ac-value 페이지가 200을 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_ac_analysis", return_value={
        "total": 2,
        "distribution": dict.fromkeys(range(11), 0),
        "best_ac": 0,
        "best_ac_pct": 50.0,
        "avg_ac": 5.0,
        "recent": [],
    }):
        resp = client.get("/stats/ac-value")
    assert resp.status_code == 200
    assert "AC값" in resp.text


def test_ac_value_page_no_data() -> None:
    """데이터가 없어도 /stats/ac-value 페이지가 200을 반환한다."""
    from lotto.web import data as wd

    with patch.object(wd, "get_ac_analysis", return_value=None):
        resp = client.get("/stats/ac-value")
    assert resp.status_code == 200
    assert "데이터가 없습니다" in resp.text
