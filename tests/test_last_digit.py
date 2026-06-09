"""SPEC-LOTTO-055: 끝자리 분포 분석 테스트.

데이터 계층(get_last_digit_stats), 캐시, 페이지/API 라우트를
RED-GREEN-REFACTOR로 검증한다.

끝자리 그룹 정의:
- 0: 10,20,30,40 (4개)   - 5: 5,15,25,35,45 (5개)
- 1: 1,11,21,31,41 (5개)  - 6: 6,16,26,36 (4개)
- 2: 2,12,22,32,42 (5개)  - 7: 7,17,27,37 (4개)
- 3: 3,13,23,33,43 (5개)  - 8: 8,18,28,38 (4개)
- 4: 4,14,24,34,44 (5개)  - 9: 9,19,29,39 (4개)
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult


def _mk(no: int, nums: list[int], bonus: int = 45) -> DrawResult:
    """회차 번호와 본번호 6개로 DrawResult를 생성하는 헬퍼.

    날짜는 회차 번호에 비례하여 자동 생성한다(테스트 본질과 무관).
    """
    return DrawResult(
        drwNo=no,
        date=date(2020, 1, 1) + timedelta(days=no),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


@pytest.fixture
def api_client() -> TestClient:
    """매 테스트 새 TestClient — 라우터는 모듈 공유."""
    from lotto.web.app import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# 데이터 계층: get_last_digit_stats
# ---------------------------------------------------------------------------


def test_last_digit_all_digits_present() -> None:
    """REQ-LD-001/009: 결과는 항상 끝자리 0~9 전체를 키로 포함한다."""
    from lotto.web import data as wd

    draws = [_mk(1, [1, 2, 3, 4, 5, 6])]
    result = wd.get_last_digit_stats(draws)

    assert set(result.keys()) == set(range(10))
    # 각 값은 LastDigitStat 6개 필드를 포함한다 (REQ-LD-002)
    for d in range(10):
        stat = result[d]
        assert stat["digit"] == d
        assert set(stat.keys()) == {
            "digit", "count", "pct", "numbers", "avg_expected", "deviation",
        }


def test_last_digit_numbers_groups() -> None:
    """REQ-LD-003: 끝자리 d의 numbers는 n % 10 == d인 1~45 번호 오름차순이다."""
    from lotto.web import data as wd

    result = wd.get_last_digit_stats([_mk(1, [1, 2, 3, 4, 5, 6])])

    assert result[0]["numbers"] == [10, 20, 30, 40]
    assert result[1]["numbers"] == [1, 11, 21, 31, 41]
    assert result[5]["numbers"] == [5, 15, 25, 35, 45]
    assert result[6]["numbers"] == [6, 16, 26, 36]
    assert result[9]["numbers"] == [9, 19, 29, 39]


def test_last_digit_count_basic() -> None:
    """REQ-LD-004: 알려진 회차들에서 끝자리별 출현 횟수가 정확히 집계된다."""
    from lotto.web import data as wd

    # 회차 1: 1,11,21,2,12,3 → 끝자리 1:3회(1,11,21), 2:2회(2,12), 3:1회(3)
    # 회차 2: 1,11,5,15,25,35 → 끝자리 1:2회(1,11), 5:4회(5,15,25,35)
    draws = [
        _mk(1, [1, 2, 3, 11, 12, 21]),
        _mk(2, [1, 5, 11, 15, 25, 35]),
    ]
    result = wd.get_last_digit_stats(draws)

    assert result[1]["count"] == 5  # 1,11,21 + 1,11
    assert result[2]["count"] == 2  # 2,12
    assert result[3]["count"] == 1  # 3
    assert result[5]["count"] == 4  # 5,15,25,35
    assert result[0]["count"] == 0  # 끝자리 0 미출현


def test_last_digit_pct_formula() -> None:
    """REQ-LD-006: pct = count / (total_draws * 6) * 100, 소수 2자리."""
    from lotto.web import data as wd

    # 회차 1개, 6개 슬롯. 끝자리 1: 1,11,21 → 3회 → 3/6*100 = 50.0
    draws = [_mk(1, [1, 2, 3, 11, 12, 21])]
    result = wd.get_last_digit_stats(draws)

    assert result[1]["count"] == 3
    assert result[1]["pct"] == pytest.approx(50.0)
    assert result[2]["pct"] == pytest.approx(round(2 / 6 * 100, 2))
    assert result[0]["pct"] == pytest.approx(0.0)


def test_last_digit_avg_expected() -> None:
    """REQ-LD-007: avg_expected = (group_size / 45) * 6 * total_draws."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 11)]  # 10회차
    result = wd.get_last_digit_stats(draws)

    # 끝자리 1 그룹은 5개(1,11,21,31,41) → (5/45)*6*10
    assert result[1]["avg_expected"] == pytest.approx((5 / 45) * 6 * 10)
    # 끝자리 0 그룹은 4개(10,20,30,40) → (4/45)*6*10
    assert result[0]["avg_expected"] == pytest.approx((4 / 45) * 6 * 10)


def test_last_digit_deviation() -> None:
    """REQ-LD-008: deviation = count - avg_expected (음수 가능)."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 11)]  # 10회차
    result = wd.get_last_digit_stats(draws)

    for d in range(10):
        stat = result[d]
        assert stat["deviation"] == pytest.approx(stat["count"] - stat["avg_expected"])

    # 끝자리 1은 매 회차 1번씩 출현(번호 1) → count 10, 기대 (5/45)*60 ≈ 6.67 → 양의 편차
    assert result[1]["count"] == 10
    assert result[1]["deviation"] > 0
    # 끝자리 0은 한 번도 안 나옴 → 음의 편차
    assert result[0]["count"] == 0
    assert result[0]["deviation"] < 0


def test_last_digit_no_bonus() -> None:
    """REQ-LD-005/015: 보너스 번호는 집계에 포함되지 않는다."""
    from lotto.web import data as wd

    # 본번호 끝자리 1만 1번(번호 1), 보너스는 끝자리 9(번호 9)
    draws = [_mk(1, [1, 2, 3, 4, 5, 6], bonus=9)]
    result = wd.get_last_digit_stats(draws)

    # 보너스 9가 집계됐다면 result[9]["count"] > 0 이 되어야 하지만 0이어야 한다
    assert result[9]["count"] == 0
    # 본번호 6개 끝자리(1,2,3,4,5,6)만 각 1회
    assert result[1]["count"] == 1
    assert result[6]["count"] == 1


def test_last_digit_empty_draws() -> None:
    """REQ-LD-013: 빈/None 입력은 10개 끝자리 모두 count 0, pct/편차/기대 0.0."""
    from lotto.web import data as wd

    cases: list[list[DrawResult] | None] = [[], None]
    for draws in cases:
        result = wd.get_last_digit_stats(draws)
        assert set(result.keys()) == set(range(10))
        for d in range(10):
            stat = result[d]
            assert stat["count"] == 0
            assert stat["pct"] == 0.0
            assert stat["avg_expected"] == 0.0
            assert stat["deviation"] == 0.0
        # 빈 데이터여도 numbers 그룹은 유지된다
        assert result[1]["numbers"] == [1, 11, 21, 31, 41]


# ---------------------------------------------------------------------------
# 데이터 계층: 캐시
# ---------------------------------------------------------------------------


def test_last_digit_cache() -> None:
    """REQ-LD-022: 동일 데이터 재요청 시 캐시된 결과를 재사용한다(재계산 없음)."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 11)]
    first = wd.get_last_digit_stats(draws)
    second = wd.get_last_digit_stats(draws)
    # 동일 객체를 반환하면 재계산하지 않은 것
    assert first is second


def test_last_digit_cache_invalidated() -> None:
    """REQ-LD-014: invalidate_cache() 후에는 결과가 재계산된다."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 11)]
    first = wd.get_last_digit_stats(draws)
    wd.invalidate_cache()
    second = wd.get_last_digit_stats(draws)
    assert first is not second
    # 값은 동일해야 한다
    assert first[1]["count"] == second[1]["count"]


# ---------------------------------------------------------------------------
# API 라우트
# ---------------------------------------------------------------------------


def test_api_last_digit(api_client: TestClient) -> None:
    """REQ-LD-012: GET /api/stats/last-digit 은 끝자리 오름차순 10개 JSON 리스트."""
    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 11)]
    with patch("lotto.web.routes.api.wd.get_draws", return_value=draws):
        resp = api_client.get("/api/stats/last-digit")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 10
    # 끝자리 오름차순 (0이 먼저)
    assert [item["digit"] for item in data] == list(range(10))


def test_api_last_digit_empty(api_client: TestClient) -> None:
    """REQ-LD-013: 데이터 부재 시 API는 200과 10개 빈 통계 리스트를 반환한다."""
    with patch("lotto.web.routes.api.wd.get_draws", return_value=None):
        resp = api_client.get("/api/stats/last-digit")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 10
    assert all(item["count"] == 0 for item in data)


# ---------------------------------------------------------------------------
# 페이지 라우트
# ---------------------------------------------------------------------------


def test_last_digit_page_renders(api_client: TestClient) -> None:
    """REQ-LD-010: GET /stats/last-digit 은 200으로 10개 끝자리 표를 렌더한다."""
    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 11)]
    with patch("lotto.web.routes.pages.wd.get_draws", return_value=draws):
        resp = api_client.get("/stats/last-digit")
    assert resp.status_code == 200


def test_last_digit_page_empty(api_client: TestClient) -> None:
    """REQ-LD-013: 데이터 부재 시 페이지는 200과 안내 상태로 렌더된다."""
    with patch("lotto.web.routes.pages.wd.get_draws", return_value=None):
        resp = api_client.get("/stats/last-digit")
    assert resp.status_code == 200
