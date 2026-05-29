"""SPEC-LOTTO-028: 번호 조합 분석기 — API 통합 테스트.

REQ-COMB-001 (조합 분석 API), REQ-COMB-002 (검증), REQ-COMB-003 (verdict),
REQ-COMB-004 (historical_match), REQ-COMB-005 (페이지 섹션) 검증.
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
    """분석용 추첨 데이터 — 입력 [3,7,14,22,35,42]와 겹치도록 설계.

    - 121회: 3,7,14,22,35,42 (입력과 6개 모두 일치 → 1등급 매칭)
    - 122회: 3,7,14,22,35,9  (입력과 5개 일치)
    - 123회: 3,7,14,22,1,2   (입력과 4개 일치 → historical_match 제외)
    - 124회: 10,11,12,13,40,41 (입력과 0개 일치)
    """
    return [
        DrawResult(
            drwNo=121, date=date(2026, 1, 1),
            n1=3, n2=7, n3=14, n4=22, n5=35, n6=42, bonus=5,
        ),
        DrawResult(
            drwNo=122, date=date(2026, 1, 8),
            n1=3, n2=7, n3=14, n4=22, n5=35, n6=9, bonus=8,
        ),
        DrawResult(
            drwNo=123, date=date(2026, 1, 15),
            n1=3, n2=7, n3=14, n4=22, n5=1, n6=2, bonus=11,
        ),
        DrawResult(
            drwNo=124, date=date(2026, 1, 22),
            n1=10, n2=11, n3=12, n4=13, n5=40, n6=41, bonus=44,
        ),
    ]


@pytest.fixture(autouse=True)
def patch_draws(monkeypatch: pytest.MonkeyPatch, sample_draws: list[DrawResult]) -> None:
    """모든 테스트에서 get_draws()가 sample_draws를 반환하도록 패치."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: sample_draws)


# ─── REQ-COMB-001: POST /api/analyze-combination 기본 응답 ────────────────


class TestCombinationBasic:
    """기본 분석 결과 필드 검증."""

    def test_response_status_200(self, client: TestClient) -> None:
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        assert res.status_code == 200, res.text

    def test_response_has_all_keys(self, client: TestClient) -> None:
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        required = {
            "numbers", "sum", "odd_count", "even_count", "range_distribution",
            "consecutive_count", "frequency_score", "recent_score",
            "companion_score", "historical_match", "verdict",
        }
        assert required.issubset(body.keys())

    def test_numbers_returned_sorted(self, client: TestClient) -> None:
        """입력 순서와 무관하게 정렬된 번호를 반환한다."""
        res = client.post("/api/analyze-combination", json={
            "numbers": [42, 3, 35, 7, 22, 14],
        })
        body = res.json()
        assert body["numbers"] == [3, 7, 14, 22, 35, 42]

    def test_sum_correct(self, client: TestClient) -> None:
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        assert body["sum"] == 123  # 3+7+14+22+35+42

    def test_odd_even_count(self, client: TestClient) -> None:
        """3,7,35는 홀수(3개), 14,22,42는 짝수(3개)."""
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        assert body["odd_count"] == 3
        assert body["even_count"] == 3

    def test_range_distribution(self, client: TestClient) -> None:
        """1-10:2(3,7), 11-20:1(14), 21-30:1(22), 31-40:1(35), 41-45:1(42)."""
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        assert body["range_distribution"] == {
            "1-10": 2, "11-20": 1, "21-30": 1, "31-40": 1, "41-45": 1,
        }

    def test_consecutive_count_zero(self, client: TestClient) -> None:
        """3,7,14,22,35,42는 인접 연속이 없다."""
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        assert body["consecutive_count"] == 0

    def test_consecutive_count_counts_adjacent_pairs(self, client: TestClient) -> None:
        """1,2,3은 연속쌍 2개(1-2, 2-3), 10,11은 1개 → 총 3개."""
        res = client.post("/api/analyze-combination", json={
            "numbers": [1, 2, 3, 10, 11, 20],
        })
        body = res.json()
        assert body["consecutive_count"] == 3


# ─── REQ-COMB-004: historical_match ──────────────────────────────────────


class TestHistoricalMatch:
    """과거 회차 중 5개 이상 일치하는 회차 반환."""

    def test_returns_only_5plus_matches(self, client: TestClient) -> None:
        """121회(6개), 122회(5개)만 포함, 123회(4개)는 제외."""
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        matched_rounds = {m["drwNo"] for m in body["historical_match"]}
        assert matched_rounds == {121, 122}

    def test_newest_first(self, client: TestClient) -> None:
        """최신 회차(122)가 먼저 온다."""
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        rounds = [m["drwNo"] for m in body["historical_match"]]
        assert rounds == [122, 121]

    def test_match_entry_fields(self, client: TestClient) -> None:
        """각 항목은 drwNo, matched, numbers, bonus를 포함한다."""
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        entry = next(m for m in body["historical_match"] if m["drwNo"] == 121)
        assert entry["matched"] == 6
        assert entry["numbers"] == [3, 7, 14, 22, 35, 42]
        assert entry["bonus"] == 5

    def test_matched_count_for_partial(self, client: TestClient) -> None:
        """122회는 5개 일치."""
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        entry = next(m for m in body["historical_match"] if m["drwNo"] == 122)
        assert entry["matched"] == 5

    def test_max_five_results(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """6개 이상 일치 회차가 있어도 최대 5개만 반환한다."""
        many = [
            DrawResult(
                drwNo=200 + i, date=date(2026, 2, 1),
                n1=3, n2=7, n3=14, n4=22, n5=35, n6=42, bonus=1,
            )
            for i in range(7)
        ]
        from lotto.web import data as wd

        monkeypatch.setattr(wd, "get_draws", lambda: many)
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        assert len(body["historical_match"]) == 5


# ─── REQ-COMB-003: verdict 로직 ──────────────────────────────────────────


class TestVerdict:
    """frequency_score 기반 hot/cold/balanced 판정."""

    def test_verdict_is_valid_value(self, client: TestClient) -> None:
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        assert body["verdict"] in {"hot", "cold", "balanced"}

    def test_hot_verdict_for_frequent_numbers(self, client: TestClient) -> None:
        """입력 번호가 매우 자주 나온 경우 hot."""
        # 3,7,14,22,35는 121~123회에 반복 출현 → 고빈도
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        assert body["verdict"] == "hot"

    def test_cold_verdict_for_rare_numbers(self, client: TestClient) -> None:
        """거의 안 나온 번호 조합은 cold."""
        # 4,5,6,8,16,18은 sample_draws에 0~1회 출현
        res = client.post("/api/analyze-combination", json={
            "numbers": [4, 5, 6, 8, 16, 18],
        })
        body = res.json()
        assert body["verdict"] == "cold"


# ─── REQ-COMB-002: 빈 데이터 처리 ────────────────────────────────────────


class TestEmptyDraws:
    """draws 데이터 없을 때 점수=0, historical_match=[], verdict=balanced."""

    @pytest.fixture(autouse=True)
    def patch_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from lotto.web import data as wd

        monkeypatch.setattr(wd, "get_draws", lambda: [])

    def test_scores_zero(self, client: TestClient) -> None:
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        assert body["frequency_score"] == 0.0
        assert body["recent_score"] == 0.0
        assert body["companion_score"] == 0.0

    def test_historical_match_empty(self, client: TestClient) -> None:
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        assert body["historical_match"] == []

    def test_verdict_balanced(self, client: TestClient) -> None:
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        assert body["verdict"] == "balanced"

    def test_basic_stats_still_computed(self, client: TestClient) -> None:
        """빈 데이터여도 sum/odd/even 등 순수 통계는 계산된다."""
        res = client.post("/api/analyze-combination", json={
            "numbers": [3, 7, 14, 22, 35, 42],
        })
        body = res.json()
        assert body["sum"] == 123
        assert body["odd_count"] == 3


# ─── REQ-COMB-002: 입력 검증 (422) ───────────────────────────────────────


class TestCombinationValidation:
    """6개 / 1~45 / 중복 없음 검증."""

    def test_too_few_numbers_422(self, client: TestClient) -> None:
        res = client.post("/api/analyze-combination", json={
            "numbers": [1, 2, 3, 4, 5],
        })
        assert res.status_code == 422

    def test_too_many_numbers_422(self, client: TestClient) -> None:
        res = client.post("/api/analyze-combination", json={
            "numbers": [1, 2, 3, 4, 5, 6, 7],
        })
        assert res.status_code == 422

    def test_out_of_range_high_422(self, client: TestClient) -> None:
        res = client.post("/api/analyze-combination", json={
            "numbers": [1, 2, 3, 4, 5, 46],
        })
        assert res.status_code == 422

    def test_out_of_range_low_422(self, client: TestClient) -> None:
        res = client.post("/api/analyze-combination", json={
            "numbers": [0, 2, 3, 4, 5, 6],
        })
        assert res.status_code == 422

    def test_duplicate_numbers_422(self, client: TestClient) -> None:
        res = client.post("/api/analyze-combination", json={
            "numbers": [1, 1, 2, 3, 4, 5],
        })
        assert res.status_code == 422

    def test_missing_numbers_field_422(self, client: TestClient) -> None:
        res = client.post("/api/analyze-combination", json={})
        assert res.status_code == 422

    def test_non_integer_numbers_422(self, client: TestClient) -> None:
        res = client.post("/api/analyze-combination", json={
            "numbers": [1, 2, 3, 4, 5, "x"],
        })
        assert res.status_code == 422


# ─── REQ-COMB-005: /recommend 페이지 조합 분석 섹션 ──────────────────────


class TestRecommendPageSection:
    """조합 분석 UI 섹션 렌더링."""

    def test_page_loads_200(self, client: TestClient) -> None:
        res = client.get("/recommend")
        assert res.status_code == 200

    def test_section_present(self, client: TestClient) -> None:
        """조합 분석 섹션 컨테이너가 존재한다."""
        res = client.get("/recommend")
        assert 'id="combination-analyzer"' in res.text

    def test_section_title(self, client: TestClient) -> None:
        res = client.get("/recommend")
        assert "조합 분석" in res.text

    def test_has_six_inputs(self, client: TestClient) -> None:
        """6개 번호 입력 폼이 존재한다."""
        res = client.get("/recommend")
        assert 'name="comb-num-0"' in res.text
        assert 'name="comb-num-5"' in res.text

    def test_has_analyze_button(self, client: TestClient) -> None:
        res = client.get("/recommend")
        assert 'id="combination-form"' in res.text

    def test_has_result_container(self, client: TestClient) -> None:
        res = client.get("/recommend")
        assert 'id="combination-result"' in res.text

    def test_dark_mode_classes(self, client: TestClient) -> None:
        res = client.get("/recommend")
        assert "dark:" in res.text
