"""SPEC-LOTTO-034: 주간 통계 리포트 — 순수 계산 함수 + API + analyze 페이지 테스트.

REQ: GET /api/weekly-report?weeks=N, /analyze 페이지 주간 리포트 섹션.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import date

import pytest
from starlette.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """앱 클라이언트 — 모듈 단위 공유."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_draws() -> list[DrawResult]:
    """6회차 샘플 — 주간 리포트 계산 검증용.

    회차 1: 7,12,21,22,33,40 / 보너스 5   합=135
    회차 2: 3,7,15,25,35,44 / 보너스 9   합=129
    회차 3: 1,2,7,10,28,45 / 보너스 11   합=93
    회차 4: 7,13,21,29,33,41 / 보너스 6   합=144
    회차 5: 5,7,17,23,30,42 / 보너스 8   합=124
    회차 6: 8,14,22,31,38,43 / 보너스 2   합=156

    번호 7 → 1~5회차에 출현(5회), 6회차 미출현.
    """
    def mk(no: int, d: date, nums: list[int], bonus: int) -> DrawResult:
        return DrawResult(
            drwNo=no, date=d, n1=nums[0], n2=nums[1], n3=nums[2],
            n4=nums[3], n5=nums[4], n6=nums[5], bonus=bonus,
        )

    return [
        mk(1, date(2026, 4, 4), [7, 12, 21, 22, 33, 40], 5),
        mk(2, date(2026, 4, 11), [3, 7, 15, 25, 35, 44], 9),
        mk(3, date(2026, 4, 18), [1, 2, 7, 10, 28, 45], 11),
        mk(4, date(2026, 4, 25), [7, 13, 21, 29, 33, 41], 6),
        mk(5, date(2026, 5, 2), [5, 7, 17, 23, 30, 42], 8),
        mk(6, date(2026, 5, 9), [8, 14, 22, 31, 38, 43], 2),
    ]


@pytest.fixture(autouse=True)
def patch_draws(
    monkeypatch: pytest.MonkeyPatch,
    sample_draws: list[DrawResult],
) -> None:
    """API가 sample_draws를 사용하도록 패치한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)


# ---------------------------------------------------------------------------
# 1. data.weekly_report 순수 계산 함수
# ---------------------------------------------------------------------------


def test_weekly_report_draws_included_caps_at_available(
    sample_draws: list[DrawResult],
) -> None:
    """weeks가 가용 회차보다 크면 draws_included는 가용 전체로 잘린다."""
    from lotto.web.data import weekly_report

    result = weekly_report(100, sample_draws)
    assert result["weeks"] == 100
    assert result["draws_included"] == 6


def test_weekly_report_uses_latest_n_draws(
    sample_draws: list[DrawResult],
) -> None:
    """최신 N회차만 집계 대상이다 (weeks=2 → 회차 5,6)."""
    from lotto.web.data import weekly_report

    result = weekly_report(2, sample_draws)
    assert result["draws_included"] == 2
    # 회차 5,6의 합 = 124, 156 → 평균 140.0
    assert result["avg_sum"] == 140.0


def test_weekly_report_top10_counts(sample_draws: list[DrawResult]) -> None:
    """top10에 가장 많이 나온 번호가 count와 함께 포함된다 (weeks=6)."""
    from lotto.web.data import weekly_report

    result = weekly_report(6, sample_draws)
    # 전체 6회차에서 번호 7은 회차 1~5에 출현 → 5회로 top10 1위
    top = result["top10_numbers"]
    assert top[0]["number"] == 7
    assert top[0]["count"] == 5
    assert len(top) <= 10


def test_weekly_report_bottom10_includes_zero_count(
    sample_draws: list[DrawResult],
) -> None:
    """bottom10은 미출현(0회) 번호를 포함한다."""
    from lotto.web.data import weekly_report

    result = weekly_report(1, sample_draws)
    # weeks=1 → 회차 6만: 8,14,22,31,38,43
    bottom = result["bottom10_numbers"]
    assert len(bottom) <= 10
    # 가장 적게 나온 번호는 count 0
    assert bottom[0]["count"] == 0


def test_weekly_report_avg_sum_rounded(sample_draws: list[DrawResult]) -> None:
    """avg_sum은 소수 1자리로 반올림된다 (weeks=2 → (124+156)/2 = 140.0)."""
    from lotto.web.data import weekly_report

    result = weekly_report(2, sample_draws)
    assert result["avg_sum"] == 140.0


def test_weekly_report_odd_even_ratio(sample_draws: list[DrawResult]) -> None:
    """odd_even_ratio는 회차당 평균 홀/짝 개수다 (weeks=1 → 회차 6)."""
    from lotto.web.data import weekly_report

    result = weekly_report(1, sample_draws)
    # 회차 6: 8(짝),14(짝),22(짝),31(홀),38(짝),43(홀) → 홀 2, 짝 4
    assert result["odd_even_ratio"]["odd"] == 2.0
    assert result["odd_even_ratio"]["even"] == 4.0


def test_weekly_report_most_common_range(sample_draws: list[DrawResult]) -> None:
    """most_common_range는 5개 구간 중 가장 빈번한 구간 문자열이다."""
    from lotto.web.data import weekly_report

    result = weekly_report(5, sample_draws)
    assert result["most_common_range"] in (
        "1-10", "11-20", "21-30", "31-40", "41-45",
    )


def test_weekly_report_range_keys_present(sample_draws: list[DrawResult]) -> None:
    """most_common_range는 정의된 5개 구간 라벨 중 하나여야 한다 (weeks=1)."""
    from lotto.web.data import weekly_report

    result = weekly_report(1, sample_draws)
    # 회차 6: 8(1-10),14(11-20),22(21-30),31(31-40),38(31-40),43(41-45)
    # → 31-40 구간이 2개로 최다
    assert result["most_common_range"] == "31-40"


# ---------------------------------------------------------------------------
# 2. 빈 데이터 처리
# ---------------------------------------------------------------------------


def test_weekly_report_empty_data() -> None:
    """빈 데이터는 0과 빈 리스트, 빈 문자열을 반환한다."""
    from lotto.web.data import weekly_report

    result = weekly_report(4, [])
    assert result["weeks"] == 4
    assert result["draws_included"] == 0
    assert result["top10_numbers"] == []
    assert result["bottom10_numbers"] == []
    assert result["avg_sum"] == 0.0
    assert result["odd_even_ratio"] == {"odd": 0.0, "even": 0.0}
    assert result["most_common_range"] == ""


# ---------------------------------------------------------------------------
# 3. GET /api/weekly-report
# ---------------------------------------------------------------------------


def test_api_weekly_report_default_weeks(client: TestClient) -> None:
    """weeks 미지정 시 기본 4주로 응답한다."""
    res = client.get("/api/weekly-report")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["weeks"] == 4
    assert "top10_numbers" in body
    assert "bottom10_numbers" in body
    assert "avg_sum" in body
    assert "odd_even_ratio" in body
    assert "most_common_range" in body


def test_api_weekly_report_explicit_weeks(client: TestClient) -> None:
    """weeks=2 지정 시 해당 값으로 응답한다."""
    res = client.get("/api/weekly-report?weeks=2")
    assert res.status_code == 200, res.text
    assert res.json()["weeks"] == 2


def test_api_weekly_report_weeks_too_large_422(client: TestClient) -> None:
    """weeks가 52 초과면 422를 반환한다."""
    res = client.get("/api/weekly-report?weeks=53")
    assert res.status_code == 422, res.text


def test_api_weekly_report_weeks_too_small_422(client: TestClient) -> None:
    """weeks가 1 미만이면 422를 반환한다."""
    res = client.get("/api/weekly-report?weeks=0")
    assert res.status_code == 422, res.text


def test_api_weekly_report_max_weeks_ok(client: TestClient) -> None:
    """weeks=52 경계값은 정상 응답한다."""
    res = client.get("/api/weekly-report?weeks=52")
    assert res.status_code == 200, res.text
    assert res.json()["weeks"] == 52


# ---------------------------------------------------------------------------
# 4. /analyze 페이지 주간 리포트 섹션
# ---------------------------------------------------------------------------


def test_analyze_page_has_weekly_report_section(client: TestClient) -> None:
    """/analyze 페이지에 주간 리포트 섹션 마커가 존재한다."""
    res = client.get("/analyze")
    assert res.status_code == 200
    html = res.text
    assert "weeklyReport" in html
    assert "주간 리포트" in html
