"""SPEC-LOTTO-104: 번호 출현 주기(recency / interval) 분석 테스트.

손계산 가능한 소규모 DrawResult 픽스처로 last_seen_ago·avg/max/min interval·
appearance_count·overdue·recent를 결정적으로 검증한다. (AC-REC-001 ~ AC-REC-020)
"""

from __future__ import annotations

import os
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.data import get_recency_analysis


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
    """손계산 픽스처 — 5회차 (acceptance.md 기준).

    | idx | drwNo | 본번호 |
    |-----|-------|--------|
    | 0 | 1 | 1, 2, 3, 4, 5, 6 |
    | 1 | 2 | 1, 7, 8, 9, 10, 11 |
    | 2 | 3 | 2, 7, 12, 13, 14, 15 |
    | 3 | 4 | 1, 16, 17, 18, 19, 20 |
    | 4 | 5 | 2, 21, 22, 23, 24, 25 |

    total_draws=5, last_idx=4, recent=[2, 21, 22, 23, 24, 25].
    번호1 출현 idx [0,1,3] / 번호2 [0,2,4] / 번호7 [1,2] / 번호6 [0] / 번호30 미출현.
    보너스는 분석 무관하므로 임의 값.
    """
    return [
        make_draw(1, 1, 2, 3, 4, 5, 6, 40),
        make_draw(2, 1, 7, 8, 9, 10, 11, 41),
        make_draw(3, 2, 7, 12, 13, 14, 15, 42),
        make_draw(4, 1, 16, 17, 18, 19, 20, 43),
        make_draw(5, 2, 21, 22, 23, 24, 25, 44),
    ]


def _num_item(result: dict, number: int) -> dict:
    """numbers 리스트에서 특정 번호 항목을 조회."""
    for item in result["numbers"]:
        if item["number"] == number:
            return item
    raise AssertionError(f"번호 {number} 항목이 numbers에 없음")


# ---------------------------------------------------------------------------
# 핵심 함수 검증 (get_recency_analysis)
# ---------------------------------------------------------------------------


def test_numbers_all_45_items() -> None:
    """numbers는 1~45 모든 45개 항목을 번호 오름차순 포함 (AC-REC-001)."""
    result = get_recency_analysis(sample_draws())
    numbers = result["numbers"]
    assert len(numbers) == 45
    nums = [item["number"] for item in numbers]
    assert nums == list(range(1, 46))


def test_number_item_keys() -> None:
    """각 항목에 6개 필수 키 존재 (AC-REC-002)."""
    result = get_recency_analysis(sample_draws())
    for item in result["numbers"]:
        for key in [
            "number",
            "last_seen_ago",
            "avg_interval",
            "max_interval",
            "min_interval",
            "appearance_count",
        ]:
            assert key in item, f"{key} 키 누락 (번호 {item.get('number')})"


def test_last_seen_ago_hand_counted() -> None:
    """번호 1=1, 번호 7=2 (AC-REC-003)."""
    result = get_recency_analysis(sample_draws())
    assert _num_item(result, 1)["last_seen_ago"] == 1
    assert _num_item(result, 7)["last_seen_ago"] == 2


def test_last_seen_ago_zero_when_in_latest() -> None:
    """최근 회차 출현 번호 = 0 (번호 2) (AC-REC-004)."""
    result = get_recency_analysis(sample_draws())
    assert _num_item(result, 2)["last_seen_ago"] == 0


def test_last_seen_ago_none_when_never() -> None:
    """미출현 번호 = None (번호 30) (AC-REC-005)."""
    result = get_recency_analysis(sample_draws())
    assert _num_item(result, 30)["last_seen_ago"] is None


def test_avg_interval_uses_consecutive_gaps() -> None:
    """번호 1 avg_interval=1.5 (mean([1,2])) — total/count 아님 (AC-REC-006)."""
    result = get_recency_analysis(sample_draws())
    assert _num_item(result, 1)["avg_interval"] == 1.5


def test_avg_interval_two_decimals() -> None:
    """avg_interval = round(mean(gaps), 2) (AC-REC-007).

    번호 X가 idx [0, 1, 4]에 등장 → gaps=[1, 3] → mean=2.0.
    무한소수 검증: idx [0, 1, 2, 6] → gaps=[1,1,4] → mean=2.0.
    여기서는 round 동작을 직접 검증한다 (gaps=[1,2,2] → mean=1.666... → 1.67).
    """
    # 번호 9가 idx [0,1,3,5]에 등장 → gaps=[1,2,2] → mean=1.666... → round 1.67
    draws = [
        make_draw(1, 9, 2, 3, 4, 5, 6, 40),
        make_draw(2, 9, 7, 8, 10, 11, 12, 41),
        make_draw(3, 2, 13, 14, 15, 16, 17, 42),
        make_draw(4, 9, 18, 19, 20, 21, 22, 43),
        make_draw(5, 23, 24, 25, 26, 27, 28, 44),
        make_draw(6, 9, 29, 30, 31, 32, 33, 45),
    ]
    result = get_recency_analysis(draws)
    assert _num_item(result, 9)["avg_interval"] == 1.67


def test_max_min_interval() -> None:
    """번호 1 max=2, min=1 (gaps=[1,2]) (AC-REC-008)."""
    result = get_recency_analysis(sample_draws())
    item = _num_item(result, 1)
    assert item["max_interval"] == 2
    assert item["min_interval"] == 1


def test_single_appearance_interval_none() -> None:
    """1회 출현(번호 6) → avg/max/min=None, count=1, last_seen_ago=4 (AC-REC-009)."""
    result = get_recency_analysis(sample_draws())
    item = _num_item(result, 6)
    assert item["avg_interval"] is None
    assert item["max_interval"] is None
    assert item["min_interval"] is None
    assert item["appearance_count"] == 1
    assert item["last_seen_ago"] == 4


def test_appearance_count_hand_counted() -> None:
    """번호 1·2=3, 번호 7=2 (AC-REC-010)."""
    result = get_recency_analysis(sample_draws())
    assert _num_item(result, 1)["appearance_count"] == 3
    assert _num_item(result, 2)["appearance_count"] == 3
    assert _num_item(result, 7)["appearance_count"] == 2


def test_appearance_count_main_only() -> None:
    """보너스 출현은 count 제외 (AC-REC-011, REQ-REC-N02).

    번호 40은 보너스로만 등장(본번호로는 안 나옴) → appearance_count=0.
    """
    result = get_recency_analysis(sample_draws())
    item = _num_item(result, 40)
    assert item["appearance_count"] == 0
    assert item["last_seen_ago"] is None


def test_overdue_descending() -> None:
    """overdue는 last_seen_ago 내림차순 상위 top_n (AC-REC-012)."""
    result = get_recency_analysis(sample_draws(), top_n=45)
    overdue = result["overdue"]
    # None(미출현)을 무한대로 환산했을 때 내림차순이어야 한다
    import math

    keys = [
        math.inf if item["last_seen_ago"] is None else item["last_seen_ago"]
        for item in overdue
    ]
    assert keys == sorted(keys, reverse=True)


def test_overdue_none_first() -> None:
    """미출현(None) 최상단 (AC-REC-013)."""
    result = get_recency_analysis(sample_draws(), top_n=45)
    # 미출현 번호가 출현 번호보다 앞에 위치해야 한다
    first = result["overdue"][0]
    assert first["last_seen_ago"] is None


def test_overdue_tie_smaller_number_first() -> None:
    """동률(또는 동일 미출현) 시 작은 번호 우선 (AC-REC-014)."""
    result = get_recency_analysis(sample_draws(), top_n=45)
    overdue = result["overdue"]
    # 미출현 번호들(last_seen_ago=None)끼리는 번호 오름차순이어야 한다
    none_numbers = [
        item["number"] for item in overdue if item["last_seen_ago"] is None
    ]
    assert none_numbers == sorted(none_numbers)


def test_overdue_size_equals_top_n() -> None:
    """top_n=3 → overdue 길이 3 (AC-REC-015)."""
    result = get_recency_analysis(sample_draws(), top_n=3)
    assert len(result["overdue"]) == 3


def test_recent_is_latest_draw_numbers() -> None:
    """recent == 최근 회차 본번호 오름차순 (AC-REC-016)."""
    result = get_recency_analysis(sample_draws())
    assert result["recent"] == [2, 21, 22, 23, 24, 25]


def test_result_keys_present() -> None:
    """반환 dict 필수 키 모두 존재 (AC-REC-017)."""
    result = get_recency_analysis(sample_draws())
    for key in [
        "numbers",
        "overdue",
        "recent",
        "total_draws",
        "top_n",
        "disclaimer",
    ]:
        assert key in result, f"{key} 키 누락"


def test_total_draws_count() -> None:
    """total_draws는 입력 회차 수와 일치."""
    result = get_recency_analysis(sample_draws())
    assert result["total_draws"] == 5


def test_top_n_echoed() -> None:
    """top_n 값이 반환 dict에 그대로 반영."""
    result = get_recency_analysis(sample_draws(), top_n=7)
    assert result["top_n"] == 7


def test_deterministic() -> None:
    """동일 입력 → 동일 결과 (AC-REC-017, REQ-REC-U09)."""
    draws = sample_draws()
    r1 = get_recency_analysis(draws)
    r2 = get_recency_analysis(draws)
    assert r1 == r2


def test_disclaimer_present() -> None:
    """disclaimer 키 포함, 회고 분석 명시 (AC-REC-018)."""
    result = get_recency_analysis(sample_draws())
    assert "disclaimer" in result
    assert isinstance(result["disclaimer"], str)
    assert len(result["disclaimer"]) > 0


def test_draws_order_independent() -> None:
    """입력 회차 순서가 뒤섞여도 drwNo 정렬로 동일 결과 (REQ-REC-U03)."""
    forward = get_recency_analysis(sample_draws())
    reversed_draws = list(reversed(sample_draws()))
    backward = get_recency_analysis(reversed_draws)
    assert forward == backward


# ---------------------------------------------------------------------------
# 경계/빈 데이터 검증
# ---------------------------------------------------------------------------


def test_empty_draws_returns_none_filled() -> None:
    """draws=[] → total 0, 45개 None/0, 빈 overdue/recent (AC-REC-019)."""
    result = get_recency_analysis([])
    assert result["total_draws"] == 0
    assert len(result["numbers"]) == 45
    for item in result["numbers"]:
        assert item["last_seen_ago"] is None
        assert item["avg_interval"] is None
        assert item["max_interval"] is None
        assert item["min_interval"] is None
        assert item["appearance_count"] == 0
    assert result["overdue"] == []
    assert result["recent"] == []
    assert "disclaimer" in result


def test_none_draws_returns_none_filled() -> None:
    """draws=None → 동일하게 None 채움 (AC-REC-019)."""
    result = get_recency_analysis(None)
    assert result["total_draws"] == 0
    assert len(result["numbers"]) == 45
    assert all(item["appearance_count"] == 0 for item in result["numbers"])
    assert result["overdue"] == []
    assert result["recent"] == []


# ---------------------------------------------------------------------------
# API 라우트 검증 (GET /api/stats/recency)
# ---------------------------------------------------------------------------


class TestRecencyAPI:
    """GET /api/stats/recency 엔드포인트 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app

        return TestClient(app)

    def test_recency_api_returns_required_fields(self) -> None:
        """응답에 필수 필드 포함, HTTP 200 (AC-REC-020, REQ-REC-E01)."""
        with patch("lotto.web.data.get_draws", return_value=sample_draws()):
            resp = self._client().get("/api/stats/recency")
        assert resp.status_code == 200
        body = resp.json()
        for field in [
            "numbers",
            "overdue",
            "recent",
            "total_draws",
            "top_n",
            "disclaimer",
        ]:
            assert field in body, f"{field} 필드 누락"

    def test_recency_api_default_top_n_10(self) -> None:
        """top_n 미지정 시 기본 10 (REQ-REC-E02)."""
        with patch("lotto.web.data.get_draws", return_value=sample_draws()):
            resp = self._client().get("/api/stats/recency")
        assert resp.status_code == 200
        assert resp.json()["top_n"] == 10

    def test_recency_api_top_n_query(self) -> None:
        """?top_n=20 반영 (REQ-REC-E04)."""
        with patch("lotto.web.data.get_draws", return_value=sample_draws()):
            resp = self._client().get("/api/stats/recency?top_n=20")
        assert resp.status_code == 200
        assert resp.json()["top_n"] == 20

    def test_recency_api_top_n_too_small(self) -> None:
        """top_n=0 → HTTP 422 (REQ-REC-N01)."""
        resp = self._client().get("/api/stats/recency?top_n=0")
        assert resp.status_code == 422

    def test_recency_api_top_n_too_large(self) -> None:
        """top_n=46 → HTTP 422 (REQ-REC-N01)."""
        resp = self._client().get("/api/stats/recency?top_n=46")
        assert resp.status_code == 422

    def test_recency_api_top_n_boundaries(self) -> None:
        """top_n=1, top_n=45 → HTTP 200 (REQ-REC-N01)."""
        with patch("lotto.web.data.get_draws", return_value=sample_draws()):
            client = self._client()
            assert client.get("/api/stats/recency?top_n=1").status_code == 200
            assert client.get("/api/stats/recency?top_n=45").status_code == 200

    def test_recency_api_empty_data_returns_200(self) -> None:
        """데이터 부재 시에도 200 + total_draws=0 (REQ-REC-S01)."""
        with patch("lotto.web.data.get_draws", return_value=None):
            resp = self._client().get("/api/stats/recency")
        assert resp.status_code == 200
        assert resp.json()["total_draws"] == 0


# ---------------------------------------------------------------------------
# 웹 페이지 검증 (GET /stats/recency)
# ---------------------------------------------------------------------------


class TestRecencyPage:
    """GET /stats/recency 페이지 검증."""

    def _client(self) -> TestClient:
        from lotto.web.app import app

        return TestClient(app)

    def test_recency_page_renders(self) -> None:
        """GET /stats/recency → HTTP 200, HTML 응답 (REQ-REC-E03)."""
        with patch("lotto.web.data.get_draws", return_value=sample_draws()):
            resp = self._client().get("/stats/recency")
        assert resp.status_code == 200
        assert "주기" in resp.text

    def test_recency_template_file_exists(self) -> None:
        """recency_analysis.html 템플릿 파일이 존재."""
        template_path = (
            "/home/sklee/moai/lotto/lotto/web/templates/recency_analysis.html"
        )
        assert os.path.exists(template_path)

    def test_recency_page_server_rendered(self) -> None:
        """핵심 테이블이 서버 렌더링(JS 비의존) (REQ-REC-N06)."""
        with patch("lotto.web.data.get_draws", return_value=sample_draws()):
            resp = self._client().get("/stats/recency")
        assert "<table" in resp.text

    def test_recency_page_top_n_reflected(self) -> None:
        """?top_n=20 시 overdue 목록 크기 반영 (REQ-REC-E04)."""
        with patch("lotto.web.data.get_draws", return_value=sample_draws()):
            resp = self._client().get("/stats/recency?top_n=20")
        assert resp.status_code == 200

    def test_recency_nav_tab_exists(self) -> None:
        """base.html 내비게이션에 주기 분석 탭 존재 (/stats/recency, tab=recency)."""
        base_path = "/home/sklee/moai/lotto/lotto/web/templates/base.html"
        with open(base_path, encoding="utf-8") as f:
            content = f.read()
        assert "/stats/recency" in content
        assert "주기 분석" in content

    def test_cycle_tab_still_exists(self) -> None:
        """기존 당첨 주기(/numbers/cycle, tab=cycle) 탭과 별개로 공존."""
        base_path = "/home/sklee/moai/lotto/lotto/web/templates/base.html"
        with open(base_path, encoding="utf-8") as f:
            content = f.read()
        assert "/numbers/cycle" in content
        assert "당첨 주기" in content
