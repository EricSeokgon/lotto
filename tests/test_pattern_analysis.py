"""SPEC-LOTTO-019: 번호 패턴 분석 테스트.

REQ-PAT-001: pattern_analysis() — 홀짝 / 범위 / 연속 / 합계 / 끝자리 분포
REQ-PAT-002: GET /api/pattern-analysis 엔드포인트
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult


# ─────────────────────────────────────────────────────────────
# REQ-PAT-001: pattern_analysis() 단위 테스트
# ─────────────────────────────────────────────────────────────


def _make_draw(drw_no: int, numbers: list[int], bonus: int = 1) -> DrawResult:
    """헬퍼 — 6개 번호 리스트로 DrawResult 생성."""
    nums = sorted(numbers)
    return DrawResult(
        drwNo=drw_no,
        date=date(2002, 12, 7),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


def test_pattern_analysis_returns_dict_with_required_keys():
    """REQ-PAT-001: 결과 딕셔너리에 필수 키가 모두 존재해야 한다."""
    from lotto.web import data as wd

    draw = _make_draw(1, [1, 2, 10, 20, 30, 40], bonus=5)
    with patch.object(wd, "get_draws", return_value=[draw]):
        result = wd.pattern_analysis()

    assert isinstance(result, dict)
    assert {"odd_even", "range_dist", "consecutive", "sum_range", "last_digit", "total_draws"} <= set(
        result.keys()
    )


def test_pattern_analysis_empty_when_no_draws():
    """REQ-PAT-001: 데이터 없으면 total_draws=0의 빈 구조 반환."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=None):
        result = wd.pattern_analysis()
    assert result["total_draws"] == 0

    with patch.object(wd, "get_draws", return_value=[]):
        result = wd.pattern_analysis()
    assert result["total_draws"] == 0


def test_pattern_analysis_odd_even_keys_and_sum():
    """REQ-PAT-001: odd_even 히스토그램 키는 '0'~'6'이고 값 합이 total_draws."""
    from lotto.web import data as wd

    # 3draws: 홀수개수 - draw1: 4(1,3,5,7), draw2: 0(짝수만), draw3: 6(전부 홀수)
    draws = [
        _make_draw(1, [1, 3, 5, 7, 10, 20], bonus=8),   # 4 odd
        _make_draw(2, [2, 4, 6, 8, 10, 12], bonus=14),  # 0 odd
        _make_draw(3, [1, 3, 5, 7, 9, 11], bonus=13),   # 6 odd
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.pattern_analysis()

    assert set(result["odd_even"].keys()) == {"0", "1", "2", "3", "4", "5", "6"}
    assert sum(result["odd_even"].values()) == 3
    assert result["odd_even"]["4"] == 1
    assert result["odd_even"]["0"] == 1
    assert result["odd_even"]["6"] == 1


def test_pattern_analysis_range_dist_keys_exact():
    """REQ-PAT-001: range_dist 키는 정확히 5개 버킷."""
    from lotto.web import data as wd

    # 각 범위에 1개씩 들어가도록 구성: 5(1-9), 15(10-19), 25(20-29), 35(30-39), 45(40-45) + 8(1-9)
    draw = _make_draw(1, [5, 8, 15, 25, 35, 45], bonus=1)
    with patch.object(wd, "get_draws", return_value=[draw]):
        result = wd.pattern_analysis()

    assert set(result["range_dist"].keys()) == {"1-9", "10-19", "20-29", "30-39", "40-45"}
    assert result["range_dist"]["1-9"] == 2  # 5, 8
    assert result["range_dist"]["10-19"] == 1  # 15
    assert result["range_dist"]["20-29"] == 1  # 25
    assert result["range_dist"]["30-39"] == 1  # 35
    assert result["range_dist"]["40-45"] == 1  # 45
    # 총합은 draws * 6
    assert sum(result["range_dist"].values()) == 6


def test_pattern_analysis_consecutive_ratio_bounds():
    """REQ-PAT-001: consecutive는 0.0~1.0 사이 float."""
    from lotto.web import data as wd

    # draw1: 연속 있음(1,2), draw2: 연속 없음
    draws = [
        _make_draw(1, [1, 2, 10, 20, 30, 40], bonus=5),
        _make_draw(2, [3, 7, 15, 22, 31, 40], bonus=5),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.pattern_analysis()

    assert isinstance(result["consecutive"], float)
    assert 0.0 <= result["consecutive"] <= 1.0
    # 2개 중 1개 연속 → 0.5
    assert result["consecutive"] == pytest.approx(0.5, rel=1e-6)


def test_pattern_analysis_consecutive_all_zero():
    """연속 번호가 전혀 없는 회차만 있으면 0.0."""
    from lotto.web import data as wd

    draws = [_make_draw(1, [1, 3, 5, 7, 9, 11], bonus=13)]  # 모두 2씩 차이
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.pattern_analysis()
    assert result["consecutive"] == 0.0


def test_pattern_analysis_consecutive_all_one():
    """모든 회차가 연속이면 1.0."""
    from lotto.web import data as wd

    draws = [
        _make_draw(1, [1, 2, 10, 20, 30, 40], bonus=5),
        _make_draw(2, [3, 4, 15, 22, 31, 41], bonus=5),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.pattern_analysis()
    assert result["consecutive"] == 1.0


def test_pattern_analysis_sum_range_buckets():
    """REQ-PAT-001: sum_range는 합계의 10단위 버킷 분포."""
    from lotto.web import data as wd

    # draw1 합계: 1+2+10+20+30+40 = 103 → "100-109"
    # draw2 합계: 5+15+25+35+40+45 = 165 → "160-169"
    draws = [
        _make_draw(1, [1, 2, 10, 20, 30, 40], bonus=5),
        _make_draw(2, [5, 15, 25, 35, 40, 45], bonus=1),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.pattern_analysis()

    assert isinstance(result["sum_range"], dict)
    # 모든 key는 str, value는 int
    for k, v in result["sum_range"].items():
        assert isinstance(k, str)
        assert isinstance(v, int)
    assert result["sum_range"].get("100-109") == 1
    assert result["sum_range"].get("160-169") == 1


def test_pattern_analysis_last_digit_keys_and_count():
    """REQ-PAT-001: last_digit 키는 '0'~'9', 총합은 draws * 6."""
    from lotto.web import data as wd

    # numbers: 1,2,3,4,5,10 → 끝자리: 1,2,3,4,5,0 (각 1개)
    draws = [_make_draw(1, [1, 2, 3, 4, 5, 10], bonus=6)]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.pattern_analysis()

    assert set(result["last_digit"].keys()) == {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}
    assert sum(result["last_digit"].values()) == 6
    assert result["last_digit"]["0"] == 1  # 10
    assert result["last_digit"]["1"] == 1
    assert result["last_digit"]["5"] == 1


def test_pattern_analysis_total_draws_matches_input():
    """REQ-PAT-001: total_draws는 입력 회차 수와 일치."""
    from lotto.web import data as wd

    draws = [
        _make_draw(i, [1, 2, 3, 4, 5, 6], bonus=7) for i in range(1, 6)
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.pattern_analysis()
    assert result["total_draws"] == 5


# ─────────────────────────────────────────────────────────────
# REQ-PAT-001: GET /api/pattern-analysis 엔드포인트
# ─────────────────────────────────────────────────────────────


def test_api_pattern_analysis_returns_200_when_data_exists():
    """GET /api/pattern-analysis는 데이터 있으면 200 + 필수 키 반환."""
    from lotto.web.app import app

    draw = _make_draw(1, [1, 2, 10, 20, 30, 40], bonus=5)
    with patch("lotto.web.routes.api.get_draws", return_value=[draw]):
        c = TestClient(app)
        response = c.get("/api/pattern-analysis")

    assert response.status_code == 200
    body = response.json()
    assert "odd_even" in body
    assert "range_dist" in body
    assert "consecutive" in body
    assert "sum_range" in body
    assert "last_digit" in body
    assert "total_draws" in body
    assert body["total_draws"] == 1


def test_api_pattern_analysis_returns_503_when_no_data():
    """GET /api/pattern-analysis는 draws 없으면 503 반환."""
    from lotto.web.app import app

    with patch("lotto.web.routes.api.get_draws", return_value=None):
        c = TestClient(app)
        response = c.get("/api/pattern-analysis")

    assert response.status_code == 503
    body = response.json()
    assert "detail" in body
