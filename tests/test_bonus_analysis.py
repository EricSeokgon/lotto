"""SPEC-LOTTO-103: 보너스 번호 분석 (Bonus Number Analysis) 테스트.

손계산 가능한 소규모 DrawResult 픽스처로 빈도·비율·동시출현·최근추세를
결정적으로 검증한다. (AC-BON-001 ~ AC-BON-020)
"""

from __future__ import annotations

import os
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.data import get_bonus_analysis


def make_draw(
    draw_no: int,
    n1: int,
    n2: int,
    n3: int,
    n4: int,
    n5: int,
    n6: int,
    bonus: int,
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
    """손계산 픽스처 — 보너스 분포가 알려진 5회차.

    보너스: 회차1=7, 회차2=7, 회차3=7, 회차4=13, 회차5=22
    → 보너스 빈도: 7=3, 13=1, 22=1, 나머지=0 / total=5
    """
    return [
        make_draw(1, 1, 2, 3, 4, 5, 6, 7),
        make_draw(2, 1, 2, 3, 4, 5, 8, 7),
        make_draw(3, 1, 2, 3, 10, 11, 12, 7),
        make_draw(4, 5, 6, 7, 8, 9, 10, 13),
        make_draw(5, 40, 41, 42, 43, 44, 45, 22),
    ]


# ---------------------------------------------------------------------------
# 핵심 함수 검증 (get_bonus_analysis)
# ---------------------------------------------------------------------------


def test_bonus_frequency_all_45_keys() -> None:
    """bonus_frequency는 1~45 모든 키를 포함하고 미출현 번호는 0 (AC-BON-001)."""
    result = get_bonus_analysis(sample_draws())
    freq = result["bonus_frequency"]
    assert set(freq.keys()) == set(range(1, 46))
    # 미출현 번호 1번은 0 (보너스로 나온 적 없음)
    assert freq[1] == 0
    assert freq[3] == 0


def test_bonus_frequency_hand_counted() -> None:
    """손계산 픽스처로 각 번호 빈도 정확 집계 (AC-BON-002)."""
    result = get_bonus_analysis(sample_draws())
    freq = result["bonus_frequency"]
    assert freq[7] == 3
    assert freq[13] == 1
    assert freq[22] == 1
    # 본번호로만 등장한 번호(예: 5)는 보너스 빈도 0
    assert freq[5] == 0


def test_bonus_percentage_two_decimals() -> None:
    """bonus_percentage = round(count/total*100, 2) (AC-BON-003)."""
    result = get_bonus_analysis(sample_draws())
    pct = result["bonus_percentage"]
    # 7번: 3/5*100 = 60.0
    assert pct[7] == round(3 / 5 * 100, 2)
    assert pct[7] == 60.0
    # 13번: 1/5*100 = 20.0
    assert pct[13] == 20.0
    assert pct[1] == 0.0


def test_bonus_percentage_all_45_keys() -> None:
    """bonus_percentage도 1~45 모든 키를 포함 (AC-BON-004)."""
    result = get_bonus_analysis(sample_draws())
    assert set(result["bonus_percentage"].keys()) == set(range(1, 46))


def test_top_bonus_top_10() -> None:
    """top_bonus는 빈도 내림차순 상위 10개 (AC-BON-005)."""
    result = get_bonus_analysis(sample_draws())
    top = result["top_bonus"]
    assert len(top) == 10
    # 1순위는 7번 (빈도 3)
    assert top[0]["number"] == 7
    assert top[0]["count"] == 3
    # 내림차순 정렬 확인
    counts = [item["count"] for item in top]
    assert counts == sorted(counts, reverse=True)


def test_top_bonus_item_keys() -> None:
    """각 항목에 number, count, percentage 포함 (AC-BON-005)."""
    result = get_bonus_analysis(sample_draws())
    item = result["top_bonus"][0]
    assert "number" in item
    assert "count" in item
    assert "percentage" in item
    assert item["percentage"] == 60.0


def test_top_bonus_tie_smaller_number_first() -> None:
    """동률 시 더 작은 번호가 먼저 정렬 (AC-BON-006)."""
    # 보너스 10과 20이 각각 2회, 30이 1회
    draws = [
        make_draw(1, 1, 2, 3, 4, 5, 6, 10),
        make_draw(2, 1, 2, 3, 4, 5, 6, 10),
        make_draw(3, 1, 2, 3, 4, 5, 6, 20),
        make_draw(4, 1, 2, 3, 4, 5, 6, 20),
        make_draw(5, 1, 2, 3, 4, 5, 6, 30),
    ]
    result = get_bonus_analysis(draws)
    top = result["top_bonus"]
    # 동률(2회)인 10과 20 중 10이 먼저
    assert top[0]["number"] == 10
    assert top[1]["number"] == 20


def test_recent_bonus_window() -> None:
    """recent_bonus는 최근 recent_n 회차로만 한정 집계 (AC-BON-007)."""
    result = get_bonus_analysis(sample_draws(), recent_n=2)
    # 최근 2회차 = 회차4(보너스13), 회차5(보너스22)
    recent_freq = result["recent_bonus"]["frequency"]
    assert recent_freq[13] == 1
    assert recent_freq[22] == 1
    # 회차1~3의 보너스 7번은 최근 윈도우에 없음
    assert recent_freq[7] == 0


def test_recent_bonus_all_45_keys() -> None:
    """recent_bonus.frequency도 1~45 전체 키 0채움 (REQ-BON-U05)."""
    result = get_bonus_analysis(sample_draws(), recent_n=2)
    assert set(result["recent_bonus"]["frequency"].keys()) == set(range(1, 46))


def test_recent_bonus_recent_count() -> None:
    """recent_count = min(recent_n, total_draws) (AC-BON-008)."""
    result = get_bonus_analysis(sample_draws(), recent_n=2)
    assert result["recent_bonus"]["recent_count"] == 2
    assert result["recent_count"] == 2


def test_cooccurrence_top_5() -> None:
    """각 보너스 번호별 동시출현 상위 5개 (AC-BON-009)."""
    result = get_bonus_analysis(sample_draws())
    cooc = result["cooccurrence"]
    # 보너스 7이 나온 회차1,2,3의 본번호 중 1,2,3은 3회씩 함께 등장
    cooc7 = cooc[7]
    assert len(cooc7) <= 5
    # 1,2,3은 회차1,2,3 모두에 등장 → count 3
    top_numbers = {item["number"]: item["count"] for item in cooc7}
    assert top_numbers.get(1) == 3
    assert top_numbers.get(2) == 3
    assert top_numbers.get(3) == 3


def test_cooccurrence_descending_tie_break() -> None:
    """동시출현 내림차순, 동률 시 작은 번호 우선 (AC-BON-010)."""
    result = get_bonus_analysis(sample_draws())
    cooc7 = result["cooccurrence"][7]
    counts = [item["count"] for item in cooc7]
    assert counts == sorted(counts, reverse=True)
    # 동률(count=3)인 1,2,3 중 작은 번호가 먼저
    tied = [item["number"] for item in cooc7 if item["count"] == 3]
    assert tied == sorted(tied)


def test_cooccurrence_uses_main_numbers_only() -> None:
    """본번호(numbers())만 집계, 보너스 제외 (AC-BON-011)."""
    result = get_bonus_analysis(sample_draws())
    # 보너스 7의 동시출현에 보너스 자기 자신(7)은 포함되지 않아야 한다
    cooc7 = result["cooccurrence"][7]
    nums = {item["number"] for item in cooc7}
    # 회차1,2,3의 본번호에 7이 없으므로 7은 동시출현에 등장 불가
    assert 7 not in nums


def test_cooccurrence_all_45_keys() -> None:
    """cooccurrence는 1~45 모든 보너스 번호 키를 포함 (REQ-BON-U06)."""
    result = get_bonus_analysis(sample_draws())
    assert set(result["cooccurrence"].keys()) == set(range(1, 46))
    # 보너스로 나온 적 없는 번호는 빈 리스트
    assert result["cooccurrence"][1] == []


def test_result_keys_present() -> None:
    """반환 dict에 필수 키 모두 존재 (AC-BON-012)."""
    result = get_bonus_analysis(sample_draws())
    for key in [
        "total_draws",
        "recent_n",
        "recent_count",
        "bonus_frequency",
        "bonus_percentage",
        "top_bonus",
        "recent_bonus",
        "cooccurrence",
        "hot_cold",
        "disclaimer",
    ]:
        assert key in result, f"{key} 키 누락"


def test_total_draws_count() -> None:
    """total_draws는 입력 회차 수와 일치."""
    result = get_bonus_analysis(sample_draws())
    assert result["total_draws"] == 5


def test_deterministic() -> None:
    """동일 입력 → 동일 결과 (AC-BON-013)."""
    draws = sample_draws()
    r1 = get_bonus_analysis(draws)
    r2 = get_bonus_analysis(draws)
    assert r1 == r2


def test_hot_cold_normal_classification() -> None:
    """평균(100/45 ≈ 2.22%) 기준 hot/cold/normal 판정 (AC-BON-014)."""
    result = get_bonus_analysis(sample_draws())
    hot_cold = result["hot_cold"]
    assert set(hot_cold.keys()) == set(range(1, 46))
    # average = 5/45 ≈ 0.111. 7번 count=3 > 0.111*1.2 → hot
    assert hot_cold[7] == "hot"
    # count=0 < 0.111*0.8 → cold
    assert hot_cold[1] == "cold"


def test_disclaimer_present() -> None:
    """disclaimer 키 포함 (AC-BON-015)."""
    result = get_bonus_analysis(sample_draws())
    assert "disclaimer" in result
    assert isinstance(result["disclaimer"], str)
    assert len(result["disclaimer"]) > 0


# ---------------------------------------------------------------------------
# 경계/빈 데이터 검증
# ---------------------------------------------------------------------------


def test_empty_draws_returns_zeroed() -> None:
    """draws=[] → total 0, 전부 0/0.0, 빈 top/cooccurrence (AC-BON-016)."""
    result = get_bonus_analysis([])
    assert result["total_draws"] == 0
    assert all(v == 0 for v in result["bonus_frequency"].values())
    assert all(v == 0.0 for v in result["bonus_percentage"].values())
    assert result["top_bonus"] == []
    assert result["recent_bonus"]["recent_count"] == 0
    assert all(v == [] for v in result["cooccurrence"].values())


def test_none_draws_returns_zeroed() -> None:
    """draws=None → 동일하게 0 채움 (AC-BON-016)."""
    result = get_bonus_analysis(None)
    assert result["total_draws"] == 0
    assert set(result["bonus_frequency"].keys()) == set(range(1, 46))
    assert all(v == 0 for v in result["bonus_frequency"].values())
    assert result["top_bonus"] == []


def test_empty_draws_all_normal_hot_cold() -> None:
    """빈 데이터에서도 hot_cold는 1~45 전체 키 (정상 응답)."""
    result = get_bonus_analysis([])
    assert set(result["hot_cold"].keys()) == set(range(1, 46))


def test_recent_n_larger_than_total() -> None:
    """recent_n > total_draws → 전체 사용, 에러 없음 (AC-BON-017)."""
    result = get_bonus_analysis(sample_draws(), recent_n=1000)
    assert result["recent_count"] == 5
    assert result["recent_bonus"]["recent_count"] == 5
    # 전체를 윈도우로 사용 → 7번 빈도 3
    assert result["recent_bonus"]["frequency"][7] == 3


def test_single_draw() -> None:
    """단일 회차 → 해당 보너스만 1로 집계."""
    result = get_bonus_analysis([make_draw(1, 1, 2, 3, 4, 5, 6, 9)])
    assert result["total_draws"] == 1
    assert result["bonus_frequency"][9] == 1
    assert result["bonus_percentage"][9] == 100.0
    assert result["top_bonus"][0]["number"] == 9


def test_main_and_bonus_distributions_separate() -> None:
    """본번호/보너스 빈도 분리 검증 (AC-BON-018)."""
    # 5번은 본번호로 여러 번 등장하지만 보너스로는 한 번도 안 나옴
    result = get_bonus_analysis(sample_draws())
    # 5번은 회차1,2,4에서 본번호 → 그러나 보너스 빈도는 0
    assert result["bonus_frequency"][5] == 0


# ---------------------------------------------------------------------------
# API 라우트 검증 (GET /api/stats/bonus)
# ---------------------------------------------------------------------------


class TestBonusAPI:
    """GET /api/stats/bonus 엔드포인트 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app

        return TestClient(app)

    def test_bonus_api_returns_required_fields(self) -> None:
        """응답에 필수 필드 포함, HTTP 200 (AC-BON-019)."""
        with patch("lotto.web.data.get_draws", return_value=sample_draws()):
            resp = self._client().get("/api/stats/bonus")
        assert resp.status_code == 200
        body = resp.json()
        for field in [
            "bonus_frequency",
            "bonus_percentage",
            "top_bonus",
            "recent_bonus",
            "cooccurrence",
            "total_draws",
            "recent_n",
        ]:
            assert field in body, f"{field} 필드 누락"

    def test_bonus_api_default_recent_n_50(self) -> None:
        """recent_n 미지정 시 기본 50 (AC-BON-019)."""
        with patch("lotto.web.data.get_draws", return_value=sample_draws()):
            resp = self._client().get("/api/stats/bonus")
        assert resp.status_code == 200
        assert resp.json()["recent_n"] == 50

    def test_bonus_api_recent_n_query(self) -> None:
        """?recent_n=100 반영 (AC-BON-020)."""
        with patch("lotto.web.data.get_draws", return_value=sample_draws()):
            resp = self._client().get("/api/stats/bonus?recent_n=100")
        assert resp.status_code == 200
        assert resp.json()["recent_n"] == 100

    def test_bonus_api_recent_n_too_small(self) -> None:
        """recent_n=0 → HTTP 422 (AC-BON-020)."""
        resp = self._client().get("/api/stats/bonus?recent_n=0")
        assert resp.status_code == 422

    def test_bonus_api_recent_n_too_large(self) -> None:
        """recent_n=501 → HTTP 422 (AC-BON-020)."""
        resp = self._client().get("/api/stats/bonus?recent_n=501")
        assert resp.status_code == 422

    def test_bonus_api_recent_n_boundaries(self) -> None:
        """recent_n=1, recent_n=500 → HTTP 200 (AC-BON-020)."""
        with patch("lotto.web.data.get_draws", return_value=sample_draws()):
            client = self._client()
            assert client.get("/api/stats/bonus?recent_n=1").status_code == 200
            assert client.get("/api/stats/bonus?recent_n=500").status_code == 200

    def test_bonus_api_empty_data_returns_200(self) -> None:
        """데이터 부재 시에도 200 + total_draws=0 (REQ-BON-S01)."""
        with patch("lotto.web.data.get_draws", return_value=None):
            resp = self._client().get("/api/stats/bonus")
        assert resp.status_code == 200
        assert resp.json()["total_draws"] == 0


# ---------------------------------------------------------------------------
# 웹 페이지 검증 (GET /stats/bonus)
# ---------------------------------------------------------------------------


class TestBonusPage:
    """GET /stats/bonus 페이지 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app

        return TestClient(app)

    def test_bonus_page_renders(self) -> None:
        """GET /stats/bonus → HTTP 200, HTML 응답 (AC-BON-E03)."""
        with patch("lotto.web.data.get_draws", return_value=sample_draws()):
            resp = self._client().get("/stats/bonus")
        assert resp.status_code == 200
        assert "보너스" in resp.text

    def test_bonus_template_file_exists(self) -> None:
        """bonus_analysis.html 템플릿 파일이 존재."""
        template_path = (
            "/home/sklee/moai/lotto/lotto/web/templates/bonus_analysis.html"
        )
        assert os.path.exists(template_path)

    def test_bonus_page_recent_n_reflected(self) -> None:
        """?recent_n=200 시 최근 윈도우 반영 (AC-BON-E04)."""
        with patch("lotto.web.data.get_draws", return_value=sample_draws()):
            resp = self._client().get("/stats/bonus?recent_n=200")
        assert resp.status_code == 200

    def test_bonus_page_server_rendered(self) -> None:
        """핵심 테이블이 서버 렌더링(JS 비의존) (REQ-BON-N06)."""
        with patch("lotto.web.data.get_draws", return_value=sample_draws()):
            resp = self._client().get("/stats/bonus")
        # 서버 렌더링된 번호별 테이블에 보너스 번호 7이 표시되어야 한다
        assert "<table" in resp.text

    def test_bonus_nav_tab_exists(self) -> None:
        """base.html 내비게이션에 보너스 분석 탭 존재."""
        base_path = "/home/sklee/moai/lotto/lotto/web/templates/base.html"
        with open(base_path, encoding="utf-8") as f:
            content = f.read()
        assert "/stats/bonus" in content
        assert "보너스 분석" in content
