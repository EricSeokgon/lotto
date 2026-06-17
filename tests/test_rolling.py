"""SPEC-LOTTO-054: 롤링 윈도우 빈도 분석 테스트.

데이터 계층(get_rolling_frequency / _classify_trend), 캐시, 페이지/API 라우트를
RED-GREEN-REFACTOR로 검증한다.
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


def _make_draws(count: int) -> list[DrawResult]:
    """count개의 회차를 생성한다. 모든 회차는 본번호 1~6, 보너스 45.

    회차 번호는 1..count로 증가하므로 최근 W회차는 drwNo가 큰 쪽이다.
    """
    return [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, count + 1)]


@pytest.fixture
def api_client() -> TestClient:
    """매 테스트 새 TestClient — 라우터는 모듈 공유."""
    from lotto.web.app import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# 데이터 계층: get_rolling_frequency (빈도)
# ---------------------------------------------------------------------------


def test_rolling_freq_basic() -> None:
    """AC-01: 각 윈도우 W에서 freq[n]이 최근 W회차의 정확한 출현 회차 수와 일치한다."""
    from lotto.web import data as wd

    # 회차 1~10: 본번호 1~6 / 회차 11~20: 본번호 7~12 (최근 10회는 11~20)
    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 11)]
    draws += [_mk(i, [7, 8, 9, 10, 11, 12]) for i in range(11, 21)]

    result = wd.get_rolling_frequency(draws, windows=(10, 20))

    # W=10: 최근 10회(11~20)는 본번호 7~12만 등장
    assert result[10]["freq"][7] == 10
    assert result[10]["freq"][1] == 0
    # W=20: 전체 20회. 1~6은 10회(1~10), 7~12는 10회(11~20)
    assert result[20]["freq"][1] == 10
    assert result[20]["freq"][7] == 10
    assert result[20]["freq"][13] == 0


def test_rolling_window_uses_most_recent() -> None:
    """REQ-RW-002: 윈도우는 입력 순서와 무관하게 drwNo 기준 최근 W회차를 사용한다."""
    from lotto.web import data as wd

    # 일부러 회차 순서를 뒤섞어 입력해도 최근 회차(큰 drwNo)가 윈도우에 잡혀야 한다
    old = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 6)]
    recent = [_mk(i, [40, 41, 42, 43, 44, 45], bonus=1) for i in range(6, 11)]
    shuffled = recent + old  # 최근 회차를 앞에 둔 역순 입력

    result = wd.get_rolling_frequency(shuffled, windows=(5,))

    # 최근 5회(6~10)는 본번호 40~45만 등장
    assert result[5]["freq"][40] == 5
    assert result[5]["freq"][1] == 0


# ---------------------------------------------------------------------------
# 데이터 계층: 추세 델타
# ---------------------------------------------------------------------------


def test_rolling_delta_calculation() -> None:
    """AC-02: delta[n] = freq_window[n]/W - freq_total[n]/total_draws 와 일치한다."""
    from lotto.web import data as wd

    # 회차 1~10: 1~6 / 회차 11~20: 1,2,3,4,5,7 (번호 6은 최근 10회에서 빠짐)
    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 11)]
    draws += [_mk(i, [1, 2, 3, 4, 5, 7]) for i in range(11, 21)]

    result = wd.get_rolling_frequency(draws, windows=(10,))
    # 번호 7: 최근 10회 10번, 전체 20회 중 10번 → 10/10 - 10/20 = 1.0 - 0.5 = 0.5
    assert result[10]["delta"][7] == pytest.approx(10 / 10 - 10 / 20)
    # 번호 6: 최근 10회 0번, 전체 20회 중 10번 → 0/10 - 10/20 = -0.5
    assert result[10]["delta"][6] == pytest.approx(0 / 10 - 10 / 20)
    # 번호 1: 최근 10회 10번, 전체 20번 → 10/10 - 20/20 = 0.0
    assert result[10]["delta"][1] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 데이터 계층: 추세 분류 (상승/하락/보합)
# ---------------------------------------------------------------------------


def test_rolling_trend_rising() -> None:
    """AC-03: delta > +0.02 인 번호는 '상승'으로 분류된다."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 11)]
    draws += [_mk(i, [1, 2, 3, 4, 5, 7]) for i in range(11, 21)]

    result = wd.get_rolling_frequency(draws, windows=(10,))
    # 번호 7: delta = 0.5 > 0.02 → 상승
    assert result[10]["trend"][7] == "상승"


def test_rolling_trend_falling() -> None:
    """AC-03: delta < -0.02 인 번호는 '하락'으로 분류된다."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 11)]
    draws += [_mk(i, [1, 2, 3, 4, 5, 7]) for i in range(11, 21)]

    result = wd.get_rolling_frequency(draws, windows=(10,))
    # 번호 6: delta = -0.5 < -0.02 → 하락
    assert result[10]["trend"][6] == "하락"


def test_rolling_trend_neutral_boundary() -> None:
    """AC-18: 경계값 정확히 ±0.02 는 엄격 부등호이므로 '보합'으로 분류된다."""
    from lotto.web import data as wd

    # 분류 헬퍼를 직접 검증하여 부동소수 누적 오차 없이 경계 동작을 명시한다
    assert wd._classify_trend(0.02) == "보합"
    assert wd._classify_trend(-0.02) == "보합"
    assert wd._classify_trend(0.0) == "보합"
    assert wd._classify_trend(0.02001) == "상승"
    assert wd._classify_trend(-0.02001) == "하락"


# ---------------------------------------------------------------------------
# 데이터 계층: 최고 상승/하락 상위 5개
# ---------------------------------------------------------------------------


def test_rolling_rising_top5() -> None:
    """AC-04: rising은 델타 내림차순 상위 5개, 동률은 번호 오름차순."""
    from lotto.web import data as wd

    # 회차 1~10: 1~6 / 회차 11~20: 7,8,9,10,11,12 (새 번호들이 모두 상승)
    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 11)]
    draws += [_mk(i, [7, 8, 9, 10, 11, 12]) for i in range(11, 21)]

    result = wd.get_rolling_frequency(draws, windows=(10,))
    rising = result[10]["rising"]
    assert len(rising) == 5
    # 7~12 모두 동일 델타(0.5-? 동률) → 번호 오름차순 상위 5개 = 7,8,9,10,11
    assert rising == [7, 8, 9, 10, 11]


def test_rolling_falling_bottom5() -> None:
    """AC-04: falling은 델타 오름차순 하위 5개, 동률은 번호 오름차순."""
    from lotto.web import data as wd

    draws = [_mk(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 11)]
    draws += [_mk(i, [7, 8, 9, 10, 11, 12]) for i in range(11, 21)]

    result = wd.get_rolling_frequency(draws, windows=(10,))
    falling = result[10]["falling"]
    assert len(falling) == 5
    # 1~6 모두 동일 음수 델타(동률) → 번호 오름차순 하위 5개 = 1,2,3,4,5
    assert falling == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# 데이터 계층: 윈도우 스킵 / 전 번호 커버 / 보너스 제외
# ---------------------------------------------------------------------------


def test_rolling_skip_oversized_window() -> None:
    """AC-07: 가용 회차보다 큰 윈도우는 예외 없이 결과에서 생략된다."""
    from lotto.web import data as wd

    draws = _make_draws(30)  # 30회만 가용
    result = wd.get_rolling_frequency(draws, windows=(10, 20, 50, 100))

    assert 10 in result
    assert 20 in result
    assert 50 not in result
    assert 100 not in result


def test_rolling_all_numbers_covered() -> None:
    """AC-05: freq/delta/trend 맵이 1~45 전 번호를 포함한다."""
    from lotto.web import data as wd

    draws = _make_draws(20)
    result = wd.get_rolling_frequency(draws, windows=(10,))

    for key in ("freq", "delta", "trend"):
        assert set(result[10][key].keys()) == set(range(1, 46))


def test_rolling_excludes_bonus() -> None:
    """AC-06: 보너스 번호는 빈도/델타/추세에 기여하지 않는다."""
    from lotto.web import data as wd

    # 본번호는 항상 1~6, 보너스는 45로 고정 → 45는 빈도 0이어야 한다
    draws = _make_draws(15)
    result = wd.get_rolling_frequency(draws, windows=(10,))

    assert result[10]["freq"][45] == 0


def test_rolling_empty_input() -> None:
    """AC-12/AC-15: 빈/None 입력은 예외 없이 빈 dict를 반환한다."""
    from lotto.web import data as wd

    assert wd.get_rolling_frequency([], windows=(10, 20)) == {}
    assert wd.get_rolling_frequency(None, windows=(10, 20)) == {}


def test_rolling_window_metadata() -> None:
    """RollingResult는 자신의 window 크기를 메타로 포함한다."""
    from lotto.web import data as wd

    draws = _make_draws(20)
    result = wd.get_rolling_frequency(draws, windows=(10, 20))
    assert result[10]["window"] == 10
    assert result[20]["window"] == 20


# ---------------------------------------------------------------------------
# 데이터 계층: 캐시
# ---------------------------------------------------------------------------


def test_rolling_cache() -> None:
    """AC-19: 동일 windows 재요청 시 캐시된 결과를 재사용한다(재계산 없음)."""
    from lotto.web import data as wd

    draws = _make_draws(20)
    first = wd.get_rolling_frequency(draws, windows=(10, 20))
    second = wd.get_rolling_frequency(draws, windows=(10, 20))
    # 동일 객체를 반환하면 재계산하지 않은 것
    assert first is second


def test_rolling_cache_invalidated() -> None:
    """AC-13: invalidate_cache() 후에는 결과가 재계산된다."""
    from lotto.web import data as wd

    draws = _make_draws(20)
    first = wd.get_rolling_frequency(draws, windows=(10,))
    wd.invalidate_cache()
    second = wd.get_rolling_frequency(draws, windows=(10,))
    assert first is not second
    # 값은 동일해야 한다
    assert first[10]["freq"] == second[10]["freq"]


# ---------------------------------------------------------------------------
# API 라우트
# ---------------------------------------------------------------------------


def test_api_rolling_default(api_client: TestClient) -> None:
    """AC-11: GET /api/stats/rolling 은 기본 윈도우(10,20,50,100) JSON을 반환한다."""
    draws = _make_draws(120)
    with patch("lotto.web.routes.api.wd.get_draws", return_value=draws):
        resp = api_client.get("/api/stats/rolling")
    assert resp.status_code == 200
    data = resp.json()
    # JSON 키는 문자열로 직렬화됨
    assert set(data.keys()) == {"10", "20", "50", "100"}
    assert data["10"]["window"] == 10


def test_api_rolling_custom_windows(api_client: TestClient) -> None:
    """AC-10: GET /api/stats/rolling?windows=10,20 은 해당 윈도우만 반환한다."""
    draws = _make_draws(120)
    with patch("lotto.web.routes.api.wd.get_draws", return_value=draws):
        resp = api_client.get("/api/stats/rolling?windows=10,20")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"10", "20"}


def test_api_rolling_empty(api_client: TestClient) -> None:
    """AC-12: 데이터 부재 시 API는 200과 빈 객체를 반환한다."""
    with patch("lotto.web.routes.api.wd.get_draws", return_value=None):
        resp = api_client.get("/api/stats/rolling")
    assert resp.status_code == 200
    assert resp.json() == {}


# ---------------------------------------------------------------------------
# 페이지 라우트
# ---------------------------------------------------------------------------


def test_rolling_page_renders(api_client: TestClient) -> None:
    """AC-08: GET /stats/rolling 은 200으로 전체 윈도우 표를 렌더한다."""
    draws = _make_draws(120)
    with patch("lotto.web.routes.pages.wd.get_rolling_frequency") as mock_fn:
        mock_fn.return_value = {
            10: {"window": 10, "freq": dict.fromkeys(range(1, 46), 0),
                 "delta": dict.fromkeys(range(1, 46), 0.0),
                 "trend": dict.fromkeys(range(1, 46), "보합"),
                 "rising": [1, 2, 3, 4, 5], "falling": [6, 7, 8, 9, 10]},
        }
        with patch("lotto.web.routes.pages.wd.get_draws", return_value=draws):
            resp = api_client.get("/stats/rolling")
    assert resp.status_code == 200
    mock_fn.assert_called_once()
    # 기본 호출은 4개 윈도우
    _, kwargs = mock_fn.call_args
    assert kwargs.get("windows") == (10, 20, 50, 100)


def test_rolling_page_single_window(api_client: TestClient) -> None:
    """AC-09: GET /stats/rolling?w=20 은 단일 윈도우 뷰로 호출된다."""
    draws = _make_draws(120)
    with patch("lotto.web.routes.pages.wd.get_rolling_frequency") as mock_fn:
        mock_fn.return_value = {
            20: {"window": 20, "freq": dict.fromkeys(range(1, 46), 0),
                 "delta": dict.fromkeys(range(1, 46), 0.0),
                 "trend": dict.fromkeys(range(1, 46), "보합"),
                 "rising": [1, 2, 3, 4, 5], "falling": [6, 7, 8, 9, 10]},
        }
        with patch("lotto.web.routes.pages.wd.get_draws", return_value=draws):
            resp = api_client.get("/stats/rolling?w=20")
    assert resp.status_code == 200
    _, kwargs = mock_fn.call_args
    assert kwargs.get("windows") == (20,)


def test_rolling_page_empty(api_client: TestClient) -> None:
    """AC-12: 데이터 부재 시 페이지는 200과 안내 상태로 렌더된다."""
    with patch("lotto.web.routes.pages.wd.get_draws", return_value=None):
        resp = api_client.get("/stats/rolling")
    assert resp.status_code == 200
