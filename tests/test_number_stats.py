"""SPEC-LOTTO-030: 번호별 상세 통계 — data 계산 + API + 페이지 통합 테스트.

REQ: GET /api/numbers/{number}/stats, /numbers 목록 페이지, /numbers/{number} 상세 페이지.
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
    """번호 통계용 추첨 데이터 5회차.

    번호 7 출현: 1회(2nd), 2회(1st), 4회(3rd) → 총 3회.
    번호 14는 7과 1회/2회/4회에서 동반 출현 → companion 후보.
    최신 회차는 5회. 7은 4회에 마지막 출현 → gap_since_last = 1.
    """
    return [
        # 1회: 7 포함 (정렬 시 위치 2번째), 14 동반
        DrawResult(
            drwNo=1, date=date(2002, 12, 7), n1=3, n2=7, n3=14, n4=20, n5=30, n6=40, bonus=5
        ),
        # 2회: 7 포함 (정렬 시 위치 1번째), 14 동반
        DrawResult(
            drwNo=2, date=date(2002, 12, 14), n1=7, n2=14, n3=21, n4=28, n5=35, n6=42, bonus=3
        ),
        # 3회: 7 미출현
        DrawResult(
            drwNo=3, date=date(2002, 12, 21), n1=1, n2=2, n3=3, n4=10, n5=11, n6=12, bonus=8
        ),
        # 4회: 7 포함 (정렬 시 위치 3번째), 14 동반
        DrawResult(
            drwNo=4, date=date(2002, 12, 28), n1=4, n2=5, n3=7, n4=14, n5=33, n6=44, bonus=9
        ),
        # 5회: 7 미출현 (최신 회차)
        DrawResult(
            drwNo=5, date=date(2003, 1, 4), n1=6, n2=13, n3=22, n4=31, n5=38, n6=45, bonus=2
        ),
    ]


@pytest.fixture(autouse=True)
def patch_draws(
    monkeypatch: pytest.MonkeyPatch,
    sample_draws: list[DrawResult],
) -> None:
    """API/페이지 라우트가 sample_draws를 사용하도록 패치."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)


# ---------------------------------------------------------------------------
# 1. data.number_stats 순수 계산 함수
# ---------------------------------------------------------------------------


def test_number_stats_total_count(sample_draws: list[DrawResult]) -> None:
    """번호 7의 총 출현 횟수는 3회."""
    from lotto.web.data import number_stats

    result = number_stats(7, sample_draws)
    assert result["number"] == 7
    assert result["total_count"] == 3
    assert result["total_draws"] == 5


def test_number_stats_frequency_pct(sample_draws: list[DrawResult]) -> None:
    """출현율 = 3/5 = 60.0%."""
    from lotto.web.data import number_stats

    result = number_stats(7, sample_draws)
    assert result["frequency_pct"] == 60.0


def test_number_stats_last_appeared_and_gap(sample_draws: list[DrawResult]) -> None:
    """마지막 출현 4회, 최신 5회 → gap_since_last = 1."""
    from lotto.web.data import number_stats

    result = number_stats(7, sample_draws)
    assert result["last_appeared"] == 4
    assert result["gap_since_last"] == 1


def test_number_stats_never_appeared(sample_draws: list[DrawResult]) -> None:
    """한 번도 안 나온 번호 → last_appeared/gap None, count 0."""
    from lotto.web.data import number_stats

    result = number_stats(8, sample_draws)  # 8은 본번호로 출현 없음 (보너스만)
    assert result["total_count"] == 0
    assert result["last_appeared"] is None
    assert result["gap_since_last"] is None
    assert result["frequency_pct"] == 0.0


def test_number_stats_by_position(sample_draws: list[DrawResult]) -> None:
    """번호 7의 위치 분포: 1회=2nd, 2회=1st, 4회=3rd."""
    from lotto.web.data import number_stats

    result = number_stats(7, sample_draws)
    pos = result["by_position"]
    assert pos["1st"] == 1
    assert pos["2nd"] == 1
    assert pos["3rd"] == 1
    assert pos["4th"] == 0
    assert pos["5th"] == 0
    assert pos["6th"] == 0


def test_number_stats_by_position_all_keys_present(sample_draws: list[DrawResult]) -> None:
    """위치 키는 항상 1st~6th 6개 모두 존재."""
    from lotto.web.data import number_stats

    result = number_stats(8, sample_draws)  # 미출현이어도 키는 존재
    pos = result["by_position"]
    assert set(pos.keys()) == {"1st", "2nd", "3rd", "4th", "5th", "6th"}
    assert all(v == 0 for v in pos.values())


def test_number_stats_companion_top5(sample_draws: list[DrawResult]) -> None:
    """번호 7의 동반 번호 top5 — 14가 3회로 1위, 자기 자신 제외."""
    from lotto.web.data import number_stats

    result = number_stats(7, sample_draws)
    companions = result["companion_top5"]
    assert len(companions) <= 5
    assert companions[0]["number"] == 14
    assert companions[0]["count"] == 3
    # 자기 자신은 동반 목록에 없어야 함
    assert all(c["number"] != 7 for c in companions)


def test_number_stats_recent_20_count(sample_draws: list[DrawResult]) -> None:
    """최근 20회(데이터 5회 전체) 내 7 출현 = 3회."""
    from lotto.web.data import number_stats

    result = number_stats(7, sample_draws)
    assert result["recent_20_count"] == 3


def test_number_stats_longest_absence(sample_draws: list[DrawResult]) -> None:
    """번호 7의 최장 미출현 구간. 출현 회차 1,2,4 / 최신 5.

    구간: 시작~1(0), 2~2(1회분 사이 0), 2~4(중간 3회 미출현=1), 4~5(마지막 이후 1).
    longest_absence는 연속 미출현 회차 수의 최댓값.
    """
    from lotto.web.data import number_stats

    result = number_stats(7, sample_draws)
    # 3회에서 1번 미출현, 5회에서 1번 미출현 → 최장 연속 미출현 = 1
    assert result["longest_absence"] == 1


def test_number_stats_avg_gap(sample_draws: list[DrawResult]) -> None:
    """평균 출현 간격 — 출현 회차 1,2,4 → 간격 (2-1),(4-2)=1,2 평균 1.5."""
    from lotto.web.data import number_stats

    result = number_stats(7, sample_draws)
    assert result["avg_gap"] == 1.5


def test_number_stats_empty_data() -> None:
    """빈 데이터 → 모든 카운트 0, 리스트 빈값, null."""
    from lotto.web.data import number_stats

    result = number_stats(7, [])
    assert result["number"] == 7
    assert result["total_count"] == 0
    assert result["total_draws"] == 0
    assert result["frequency_pct"] == 0.0
    assert result["last_appeared"] is None
    assert result["gap_since_last"] is None
    assert result["companion_top5"] == []
    assert result["recent_20_count"] == 0
    assert all(v == 0 for v in result["by_position"].values())


# ---------------------------------------------------------------------------
# 2. GET /api/numbers/{number}/stats
# ---------------------------------------------------------------------------


def test_api_number_stats_ok(client: TestClient) -> None:
    """정상 번호 조회 → 200 + 구조 검증."""
    resp = client.get("/api/numbers/7/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["number"] == 7
    assert body["total_count"] == 3
    assert body["total_draws"] == 5
    assert "by_position" in body
    assert "companion_top5" in body


def test_api_number_stats_min_boundary(client: TestClient) -> None:
    """번호 1 (하한) → 200."""
    resp = client.get("/api/numbers/1/stats")
    assert resp.status_code == 200
    assert resp.json()["number"] == 1


def test_api_number_stats_max_boundary(client: TestClient) -> None:
    """번호 45 (상한) → 200."""
    resp = client.get("/api/numbers/45/stats")
    assert resp.status_code == 200
    assert resp.json()["number"] == 45


def test_api_number_stats_over_range_422(client: TestClient) -> None:
    """46 (범위 초과) → 422."""
    resp = client.get("/api/numbers/46/stats")
    assert resp.status_code == 422


def test_api_number_stats_zero_422(client: TestClient) -> None:
    """0 (범위 미만) → 422."""
    resp = client.get("/api/numbers/0/stats")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 3. GET /numbers 목록 페이지
# ---------------------------------------------------------------------------


def test_numbers_page_ok(client: TestClient) -> None:
    """번호 목록 페이지 → 200 + 45개 번호 링크."""
    resp = client.get("/numbers")
    assert resp.status_code == 200
    html = resp.text
    assert "번호 통계" in html
    # 상세 페이지 링크 존재
    assert "/numbers/7" in html
    assert "/numbers/45" in html


def test_numbers_page_shows_counts(client: TestClient) -> None:
    """목록에 출현 횟수/출현율 표시."""
    resp = client.get("/numbers")
    assert resp.status_code == 200
    # 7번 출현 3회가 어딘가 렌더링
    assert "3" in resp.text


# ---------------------------------------------------------------------------
# 4. GET /numbers/{number} 상세 페이지
# ---------------------------------------------------------------------------


def test_number_detail_page_ok(client: TestClient) -> None:
    """번호 상세 페이지 → 200 + 동반 번호/위치 차트 렌더링."""
    resp = client.get("/numbers/7")
    assert resp.status_code == 200
    html = resp.text
    assert "7" in html
    assert "동반" in html  # 동반 번호 카드 제목


def test_number_detail_page_companion(client: TestClient) -> None:
    """상세 페이지에 동반 번호 14가 표시."""
    resp = client.get("/numbers/7")
    assert resp.status_code == 200
    assert "14" in resp.text


def test_number_detail_page_over_range_422(client: TestClient) -> None:
    """범위 초과 번호 상세 페이지 → 422."""
    resp = client.get("/numbers/99")
    assert resp.status_code == 422


def test_number_detail_page_position_chart(client: TestClient) -> None:
    """위치별 출현 빈도 바 차트 섹션 존재."""
    resp = client.get("/numbers/7")
    assert resp.status_code == 200
    assert "위치" in resp.text


# ---------------------------------------------------------------------------
# 5. 네비게이션 링크
# ---------------------------------------------------------------------------


def test_nav_has_numbers_link(client: TestClient) -> None:
    """홈 화면 네비게이션에 번호 통계 링크 존재."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "/numbers" in resp.text
