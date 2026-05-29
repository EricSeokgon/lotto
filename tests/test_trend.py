"""SPEC-LOTTO-026: 번호 트렌드 히트맵 분석 테스트.

REQ-TREND-001: trend_heatmap() — 번호(1~45) × 기간(연도/분기) 출현 빈도 행렬
REQ-TREND-002: GET /api/trend-heatmap 엔드포인트 (yearly/quarterly, invalid, empty)
REQ-TREND-003: hot_cold_analysis() — 최근 N회 vs 전체 평균 핫/콜드 비교
REQ-TREND-004: GET /api/hot-cold 엔드포인트 (default, custom, few draws, empty)
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult


def _make_draw(
    drw_no: int,
    numbers: list[int],
    bonus: int = 1,
    draw_date: date | None = None,
) -> DrawResult:
    """헬퍼 — 6개 번호 리스트와 날짜로 DrawResult 생성."""
    nums = sorted(numbers)
    return DrawResult(
        drwNo=drw_no,
        date=draw_date or date(2002, 12, 7),
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


# ─────────────────────────────────────────────────────────────
# REQ-TREND-001: trend_heatmap() 단위 테스트
# ─────────────────────────────────────────────────────────────


def test_trend_heatmap_returns_required_keys() -> None:
    """REQ-TREND-001: 결과 딕셔너리에 period/periods/numbers/matrix 키가 존재."""
    from lotto.web import data as wd

    draws = [_make_draw(1, [1, 2, 3, 4, 5, 6], draw_date=date(2020, 1, 4))]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.trend_heatmap("yearly")

    assert isinstance(result, dict)
    assert {"period", "periods", "numbers", "matrix"} <= set(result.keys())
    assert result["period"] == "yearly"
    # 번호 축은 항상 1~45
    assert result["numbers"] == list(range(1, 46))


def test_trend_heatmap_yearly_groups_by_year() -> None:
    """REQ-TREND-001: yearly는 추첨 연도별로 그룹핑한다."""
    from lotto.web import data as wd

    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6], draw_date=date(2020, 1, 4)),
        _make_draw(2, [1, 2, 7, 8, 9, 10], draw_date=date(2021, 1, 2)),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.trend_heatmap("yearly")

    assert result["periods"] == ["2020", "2021"]
    # matrix는 numbers(45) × periods(2) 구조
    assert len(result["matrix"]) == 45
    assert all(len(row) == 2 for row in result["matrix"])

    # 번호 1번 행: 2020에 1회, 2021에 1회
    row_one = result["matrix"][0]  # numbers[0] == 1
    assert row_one == [1, 1]
    # 번호 3번 행: 2020에 1회, 2021에 0회
    row_three = result["matrix"][2]
    assert row_three == [1, 0]
    # 번호 7번 행: 2020에 0회, 2021에 1회
    row_seven = result["matrix"][6]
    assert row_seven == [0, 1]


def test_trend_heatmap_quarterly_groups_by_quarter() -> None:
    """REQ-TREND-001: quarterly는 YYYY-Qn 형식으로 그룹핑한다."""
    from lotto.web import data as wd

    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6], draw_date=date(2020, 2, 1)),   # Q1
        _make_draw(2, [1, 7, 8, 9, 10, 11], draw_date=date(2020, 8, 1)),  # Q3
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.trend_heatmap("quarterly")

    assert result["period"] == "quarterly"
    assert result["periods"] == ["2020-Q1", "2020-Q3"]
    # 번호 1번: Q1에 1회, Q3에 1회
    assert result["matrix"][0] == [1, 1]
    # 번호 2번: Q1에 1회, Q3에 0회
    assert result["matrix"][1] == [1, 0]


def test_trend_heatmap_periods_sorted_chronologically() -> None:
    """REQ-TREND-001: periods는 시간순 정렬되어야 한다."""
    from lotto.web import data as wd

    draws = [
        _make_draw(3, [1, 2, 3, 4, 5, 6], draw_date=date(2022, 1, 1)),
        _make_draw(1, [1, 2, 3, 4, 5, 6], draw_date=date(2020, 1, 1)),
        _make_draw(2, [1, 2, 3, 4, 5, 6], draw_date=date(2021, 1, 1)),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.trend_heatmap("yearly")
    assert result["periods"] == ["2020", "2021", "2022"]


def test_trend_heatmap_empty_when_no_draws() -> None:
    """REQ-TREND-001: 데이터 없으면 빈 periods/matrix, numbers는 유지."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=None):
        result = wd.trend_heatmap("yearly")
    assert result["periods"] == []
    assert result["matrix"] == []
    assert result["numbers"] == list(range(1, 46))

    with patch.object(wd, "get_draws", return_value=[]):
        result = wd.trend_heatmap("yearly")
    assert result["periods"] == []
    assert result["matrix"] == []


def test_trend_heatmap_default_period_is_yearly() -> None:
    """REQ-TREND-001: period 인자 생략 시 yearly가 기본."""
    from lotto.web import data as wd

    draws = [_make_draw(1, [1, 2, 3, 4, 5, 6], draw_date=date(2020, 1, 4))]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.trend_heatmap()
    assert result["period"] == "yearly"


# ─────────────────────────────────────────────────────────────
# REQ-TREND-002: GET /api/trend-heatmap 엔드포인트
# ─────────────────────────────────────────────────────────────


def test_api_trend_heatmap_yearly_returns_200() -> None:
    """REQ-TREND-002: yearly 조회는 200 + 행렬 구조 반환."""
    from lotto.web.app import app

    draws = [
        _make_draw(1, [1, 2, 3, 4, 5, 6], draw_date=date(2020, 1, 4)),
        _make_draw(2, [1, 2, 7, 8, 9, 10], draw_date=date(2021, 1, 2)),
    ]
    with patch("lotto.web.routes.api.get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/api/trend-heatmap?period=yearly")

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "yearly"
    assert body["periods"] == ["2020", "2021"]
    assert body["numbers"] == list(range(1, 46))
    assert len(body["matrix"]) == 45


def test_api_trend_heatmap_quarterly_returns_200() -> None:
    """REQ-TREND-002: quarterly 조회는 200 + Q 라벨 반환."""
    from lotto.web.app import app

    draws = [_make_draw(1, [1, 2, 3, 4, 5, 6], draw_date=date(2020, 2, 1))]
    with patch("lotto.web.routes.api.get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/api/trend-heatmap?period=quarterly")

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "quarterly"
    assert body["periods"] == ["2020-Q1"]


def test_api_trend_heatmap_default_period_yearly() -> None:
    """REQ-TREND-002: period 미지정 시 yearly 기본."""
    from lotto.web.app import app

    draws = [_make_draw(1, [1, 2, 3, 4, 5, 6], draw_date=date(2020, 1, 4))]
    with patch("lotto.web.routes.api.get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/api/trend-heatmap")

    assert response.status_code == 200
    assert response.json()["period"] == "yearly"


def test_api_trend_heatmap_invalid_period_returns_400() -> None:
    """REQ-TREND-002: 잘못된 period 값은 400."""
    from lotto.web.app import app

    draws = [_make_draw(1, [1, 2, 3, 4, 5, 6], draw_date=date(2020, 1, 4))]
    with patch("lotto.web.routes.api.get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/api/trend-heatmap?period=daily")

    assert response.status_code == 400
    assert "detail" in response.json()


def test_api_trend_heatmap_empty_data_returns_200() -> None:
    """REQ-TREND-002: 데이터 없어도 200 (빈 리스트)."""
    from lotto.web.app import app

    with patch("lotto.web.routes.api.get_draws", return_value=None):
        c = TestClient(app)
        response = c.get("/api/trend-heatmap?period=yearly")

    assert response.status_code == 200
    body = response.json()
    assert body["periods"] == []
    assert body["matrix"] == []


# ─────────────────────────────────────────────────────────────
# REQ-TREND-003: hot_cold_analysis() 단위 테스트
# ─────────────────────────────────────────────────────────────


def test_hot_cold_returns_required_keys() -> None:
    """REQ-TREND-003: 결과에 recent_n/hot/cold 키가 존재."""
    from lotto.web import data as wd

    draws = [_make_draw(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 31)]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.hot_cold_analysis(recent_n=20)

    assert {"recent_n", "hot", "cold"} <= set(result.keys())
    assert result["recent_n"] == 20


def test_hot_cold_hot_and_cold_lengths() -> None:
    """REQ-TREND-003: hot/cold는 각각 최대 10개 항목."""
    from lotto.web import data as wd

    # 45개 번호가 고르게 섞이도록 30회차 생성
    draws = []
    for i in range(1, 31):
        base = ((i - 1) * 6) % 45 + 1
        nums = sorted({((base + k - 1) % 45) + 1 for k in range(6)})
        while len(nums) < 6:
            nums = sorted(set(nums) | {(nums[-1] % 45) + 1})
        draws.append(_make_draw(i, nums[:6]))

    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.hot_cold_analysis(recent_n=20)

    assert len(result["hot"]) <= 10
    assert len(result["cold"]) <= 10


def test_hot_cold_item_structure() -> None:
    """REQ-TREND-003: hot/cold 항목은 number/recent_count/avg_count/diff 포함."""
    from lotto.web import data as wd

    draws = [_make_draw(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 31)]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.hot_cold_analysis(recent_n=20)

    if result["hot"]:
        item = result["hot"][0]
        assert {"number", "recent_count", "avg_count", "diff"} <= set(item.keys())


def test_hot_cold_hot_sorted_by_diff_desc() -> None:
    """REQ-TREND-003: hot은 diff 내림차순(가장 핫한 번호가 먼저)."""
    from lotto.web import data as wd

    # 1~6번은 항상 출현 → 최근 카운트 높음 → hot 상위
    draws = [_make_draw(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 31)]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.hot_cold_analysis(recent_n=20)

    diffs = [item["diff"] for item in result["hot"]]
    assert diffs == sorted(diffs, reverse=True)


def test_hot_cold_default_recent_n_is_20() -> None:
    """REQ-TREND-003: recent_n 생략 시 20이 기본."""
    from lotto.web import data as wd

    draws = [_make_draw(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 31)]
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.hot_cold_analysis()
    assert result["recent_n"] == 20


def test_hot_cold_fewer_draws_than_recent_n() -> None:
    """REQ-TREND-003: 총 회차 < recent_n이면 가용 전체 사용 (에러 없음)."""
    from lotto.web import data as wd

    draws = [_make_draw(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 6)]  # 5회차만
    with patch.object(wd, "get_draws", return_value=draws):
        result = wd.hot_cold_analysis(recent_n=20)

    # 요청 recent_n은 그대로 반영하되 가용한 5회차로 계산
    assert result["recent_n"] == 20
    assert isinstance(result["hot"], list)
    assert isinstance(result["cold"], list)


def test_hot_cold_empty_when_no_draws() -> None:
    """REQ-TREND-003: 데이터 없으면 빈 hot/cold."""
    from lotto.web import data as wd

    with patch.object(wd, "get_draws", return_value=None):
        result = wd.hot_cold_analysis(recent_n=20)
    assert result["hot"] == []
    assert result["cold"] == []

    with patch.object(wd, "get_draws", return_value=[]):
        result = wd.hot_cold_analysis(recent_n=20)
    assert result["hot"] == []
    assert result["cold"] == []


# ─────────────────────────────────────────────────────────────
# REQ-TREND-004: GET /api/hot-cold 엔드포인트
# ─────────────────────────────────────────────────────────────


def test_api_hot_cold_default_returns_200() -> None:
    """REQ-TREND-004: 기본 조회는 200 + hot/cold 리스트."""
    from lotto.web.app import app

    draws = [_make_draw(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 31)]
    with patch("lotto.web.routes.api.get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/api/hot-cold")

    assert response.status_code == 200
    body = response.json()
    assert body["recent_n"] == 20
    assert isinstance(body["hot"], list)
    assert isinstance(body["cold"], list)


def test_api_hot_cold_custom_recent_n() -> None:
    """REQ-TREND-004: recent_n 쿼리 파라미터 반영."""
    from lotto.web.app import app

    draws = [_make_draw(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 51)]
    with patch("lotto.web.routes.api.get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/api/hot-cold?recent_n=10")

    assert response.status_code == 200
    assert response.json()["recent_n"] == 10


def test_api_hot_cold_minimum_recent_n() -> None:
    """REQ-TREND-004: recent_n 최소값 1 미만은 422 (Query 검증)."""
    from lotto.web.app import app

    draws = [_make_draw(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 31)]
    with patch("lotto.web.routes.api.get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/api/hot-cold?recent_n=0")

    assert response.status_code == 422


def test_api_hot_cold_few_draws_returns_200() -> None:
    """REQ-TREND-004: 총 회차 < recent_n이어도 200 (에러 없음)."""
    from lotto.web.app import app

    draws = [_make_draw(i, [1, 2, 3, 4, 5, 6]) for i in range(1, 6)]
    with patch("lotto.web.routes.api.get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/api/hot-cold?recent_n=20")

    assert response.status_code == 200
    assert response.json()["recent_n"] == 20


def test_api_hot_cold_empty_data_returns_200() -> None:
    """REQ-TREND-004: 데이터 없어도 200 (빈 hot/cold)."""
    from lotto.web.app import app

    with patch("lotto.web.routes.api.get_draws", return_value=None):
        c = TestClient(app)
        response = c.get("/api/hot-cold")

    assert response.status_code == 200
    body = response.json()
    assert body["hot"] == []
    assert body["cold"] == []
