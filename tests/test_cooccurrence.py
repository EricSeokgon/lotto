"""SPEC-LOTTO-053: 번호 동시 출현 분석기 테스트.

데이터 계층(get_cooccurrence_matrix / get_top_cooccurrences / get_number_partners),
캐시, 페이지/API 라우트를 RED-GREEN-REFACTOR로 검증한다.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from lotto.models import DrawResult


def _mk(no: int, d: date, nums: list[int], bonus: int) -> DrawResult:
    """본번호 6개와 보너스로 DrawResult를 생성하는 헬퍼."""
    return DrawResult(
        drwNo=no, date=d,
        n1=nums[0], n2=nums[1], n3=nums[2], n4=nums[3], n5=nums[4], n6=nums[5],
        bonus=bonus,
    )


@pytest.fixture
def api_client() -> TestClient:
    """매 테스트 새 TestClient — 라우터는 모듈 공유."""
    from lotto.web.app import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# 데이터 계층: get_cooccurrence_matrix
# ---------------------------------------------------------------------------


def test_cooccurrence_matrix_basic() -> None:
    """AC-01: 알려진 2회차에서 쌍별 동시 출현 횟수가 정확히 집계된다."""
    from lotto.web import data as wd

    # 회차 1: 1,2,3,4,5,6 / 회차 2: 1,2,3,40,41,42
    # 공통 쌍 (1,2),(1,3),(2,3)은 두 회차 모두 등장 → count 2
    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 10),
        _mk(2, date(2023, 1, 14), [1, 2, 3, 40, 41, 42], 11),
    ]
    matrix = wd.get_cooccurrence_matrix(draws)

    assert matrix[(1, 2)] == 2
    assert matrix[(1, 3)] == 2
    assert matrix[(2, 3)] == 2
    # 회차 1에만 등장하는 쌍은 1
    assert matrix[(4, 5)] == 1
    # 회차 2에만 등장하는 쌍은 1
    assert matrix[(40, 41)] == 1
    # 서로 다른 회차의 번호 쌍은 함께 나온 적 없음 → 키 부재
    assert (4, 40) not in matrix


def test_cooccurrence_no_double_count() -> None:
    """AC-02: 한 쌍은 i<j 키로만 존재하며 회차마다 정확히 1씩 누적된다."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [3, 1, 2, 4, 5, 6], 10),  # 입력 순서 비정렬
    ]
    matrix = wd.get_cooccurrence_matrix(draws)

    # 모든 키는 i < j
    assert all(i < j for (i, j) in matrix)
    # (j, i) 역순 키는 절대 존재하지 않음
    assert (2, 1) not in matrix
    assert (1, 2) in matrix
    # 한 회차에서 한 쌍은 1만 누적
    assert matrix[(1, 2)] == 1


def test_cooccurrence_excludes_bonus() -> None:
    """AC-03: 보너스 번호는 어떤 쌍 카운트에도 기여하지 않는다."""
    from lotto.web import data as wd

    # 본번호 1~6, 보너스 7
    draws = [_mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 7)]
    matrix = wd.get_cooccurrence_matrix(draws)

    # 보너스 7이 들어간 쌍은 어디에도 없음
    assert all(7 not in pair for pair in matrix)
    assert (6, 7) not in matrix
    assert (1, 7) not in matrix


def test_cooccurrence_matrix_empty() -> None:
    """AC-13: 빈/None 입력은 빈 dict를 반환한다 (에러 없음)."""
    from lotto.web import data as wd

    assert wd.get_cooccurrence_matrix([]) == {}
    assert wd.get_cooccurrence_matrix(None) == {}


# ---------------------------------------------------------------------------
# 데이터 계층: get_top_cooccurrences
# ---------------------------------------------------------------------------


def test_top_cooccurrences_sorted() -> None:
    """AC-04: 결과는 count 내림차순으로 정렬된다."""
    from lotto.web import data as wd

    # (1,2)는 두 회차 모두 → count 2, 나머지 쌍은 1
    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 10),
        _mk(2, date(2023, 1, 14), [1, 2, 30, 40, 41, 42], 11),
    ]
    top = wd.get_top_cooccurrences(draws, n=5)

    counts = [item["count"] for item in top]
    assert counts == sorted(counts, reverse=True)
    # 최상위는 (1,2) count 2
    assert top[0]["pair"] == [1, 2]
    assert top[0]["count"] == 2


def test_top_cooccurrences_pct() -> None:
    """AC-04/AC-16: pct = count / total_draws * 100 (소수 2자리)."""
    from lotto.web import data as wd

    # 4회차 중 (1,2)는 3회 동시 출현 → 3/4*100 = 75.0
    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 10),
        _mk(2, date(2023, 1, 14), [1, 2, 10, 11, 12, 13], 11),
        _mk(3, date(2023, 1, 21), [1, 2, 20, 21, 22, 23], 12),
        _mk(4, date(2023, 1, 28), [30, 31, 32, 33, 34, 35], 13),
    ]
    top = wd.get_top_cooccurrences(draws, n=1)

    assert top[0]["pair"] == [1, 2]
    assert top[0]["count"] == 3
    assert top[0]["pct"] == 75.0


def test_top_cooccurrences_limit() -> None:
    """AC-04: n 인자가 반환 개수를 제한한다."""
    from lotto.web import data as wd

    draws = [_mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 10)]
    # C(6,2) = 15 쌍이 존재하지만 n=3으로 제한
    top = wd.get_top_cooccurrences(draws, n=3)
    assert len(top) == 3


def test_cooccurrence_pct_zero_total() -> None:
    """AC-16/REQ-CO-006: total_draws가 0이면 pct는 0.0이다."""
    from lotto.web import data as wd

    assert wd._cooccurrence_pct(5, 0) == 0.0
    assert wd._cooccurrence_pct(0, 0) == 0.0
    # 정상 케이스: 3/4*100 = 75.0
    assert wd._cooccurrence_pct(3, 4) == 75.0


def test_top_cooccurrences_empty() -> None:
    """AC-10: 데이터 부재 시 빈 목록을 반환한다."""
    from lotto.web import data as wd

    assert wd.get_top_cooccurrences([], n=20) == []
    assert wd.get_top_cooccurrences(None, n=20) == []


# ---------------------------------------------------------------------------
# 데이터 계층: get_number_partners
# ---------------------------------------------------------------------------


def test_number_partners_basic() -> None:
    """AC-05: 특정 번호의 동반 파트너가 count 내림차순으로 반환된다."""
    from lotto.web import data as wd

    # 번호 1과 함께: 회차1에서 2,3,4,5,6 / 회차2에서 2,3,40,41,42
    # → 2,3은 2회, 4,5,6,40,41,42는 1회
    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 10),
        _mk(2, date(2023, 1, 14), [1, 2, 3, 40, 41, 42], 11),
    ]
    partners = wd.get_number_partners(draws, 1, top_k=10)

    counts = [p["count"] for p in partners]
    assert counts == sorted(counts, reverse=True)
    # 상위 2개는 count 2의 번호 2, 3 (동률은 번호 오름차순)
    assert partners[0] == {"number": 2, "count": 2, "pct": 100.0}
    assert partners[1] == {"number": 3, "count": 2, "pct": 100.0}
    # 자기 자신은 파트너에 포함되지 않음
    assert all(p["number"] != 1 for p in partners)


def test_number_partners_includes_pairs_where_number_is_larger() -> None:
    """REQ-CO-005: 대상이 쌍의 큰 쪽(j)인 경우도 파트너로 집계된다."""
    from lotto.web import data as wd

    # 번호 45는 모든 쌍에서 큰 쪽(j) — (1,45),(2,45),...의 j 위치
    draws = [_mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 45], 10)]
    partners = wd.get_number_partners(draws, 45, top_k=10)

    partner_numbers = {p["number"] for p in partners}
    assert partner_numbers == {1, 2, 3, 4, 5}
    assert all(p["number"] != 45 for p in partners)


def test_number_partners_top_k() -> None:
    """AC-05: top_k가 반환 파트너 수를 제한한다."""
    from lotto.web import data as wd

    # 번호 1은 5개의 파트너를 가짐 (2,3,4,5,6)
    draws = [_mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 10)]
    partners = wd.get_number_partners(draws, 1, top_k=2)
    assert len(partners) == 2


def test_number_partners_empty() -> None:
    """AC-10: 데이터 부재 시 빈 목록을 반환한다."""
    from lotto.web import data as wd

    assert wd.get_number_partners([], 7, top_k=10) == []
    assert wd.get_number_partners(None, 7, top_k=10) == []


# ---------------------------------------------------------------------------
# 캐시
# ---------------------------------------------------------------------------


def test_cooccurrence_cache() -> None:
    """AC-11: 동일 draws에 대한 두 번째 호출은 캐시된 결과를 반환한다."""
    from lotto.web import data as wd

    wd.invalidate_cache()
    draws = [_mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 10)]

    first = wd.get_cooccurrence_matrix(draws)
    second = wd.get_cooccurrence_matrix(draws)
    # 동일 객체(캐시 적중)를 반환한다
    assert first is second

    # 무효화 후에는 재계산되어 새 객체를 반환한다
    wd.invalidate_cache()
    third = wd.get_cooccurrence_matrix(draws)
    assert third is not first
    assert third == first


# ---------------------------------------------------------------------------
# API 라우트
# ---------------------------------------------------------------------------


def test_api_cooccurrence_default(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-09: GET /api/numbers/cooccurrence (number 없음) → 상위 쌍 목록."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 10),
        _mk(2, date(2023, 1, 14), [1, 2, 30, 40, 41, 42], 11),
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    response = api_client.get("/api/numbers/cooccurrence")
    assert response.status_code == 200, response.text
    body = response.json()
    assert "pairs" in body
    assert body["pairs"][0]["pair"] == [1, 2]
    assert body["pairs"][0]["count"] == 2


def test_api_cooccurrence_number(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-08: GET /api/numbers/cooccurrence?number=7 → 파트너 목록."""
    from lotto.web import data as wd

    draws = [
        _mk(1, date(2023, 1, 7), [7, 13, 27, 30, 40, 45], 1),
        _mk(2, date(2023, 1, 14), [7, 13, 27, 33, 41, 44], 2),
    ]
    monkeypatch.setattr(wd, "get_draws", lambda: draws)

    response = api_client.get("/api/numbers/cooccurrence?number=7")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["number"] == 7
    assert "partners" in body
    # 13, 27은 두 회차 모두 함께 → count 2
    assert body["partners"][0]["count"] == 2


def test_api_cooccurrence_no_data(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AC-10: 데이터 부재 시에도 200 + 빈 구조를 반환한다."""
    from lotto.web import data as wd

    monkeypatch.setattr(wd, "get_draws", lambda: None)

    response = api_client.get("/api/numbers/cooccurrence")
    assert response.status_code == 200, response.text
    assert response.json()["pairs"] == []


# ---------------------------------------------------------------------------
# 페이지 라우트
# ---------------------------------------------------------------------------


def test_cooccurrence_page_default() -> None:
    """AC-06: GET /numbers/cooccurrence → 200 HTML (상위 쌍 뷰)."""
    from lotto.web import data as wd
    from lotto.web.app import app

    draws = [
        _mk(1, date(2023, 1, 7), [1, 2, 3, 4, 5, 6], 10),
        _mk(2, date(2023, 1, 14), [1, 2, 30, 40, 41, 42], 11),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/numbers/cooccurrence")

    assert response.status_code == 200, response.text
    assert "동시 출현" in response.text


def test_cooccurrence_page_number() -> None:
    """AC-07: GET /numbers/cooccurrence?number=7 → 200 HTML (파트너 뷰)."""
    from lotto.web import data as wd
    from lotto.web.app import app

    draws = [
        _mk(1, date(2023, 1, 7), [7, 13, 27, 30, 40, 45], 1),
        _mk(2, date(2023, 1, 14), [7, 13, 27, 33, 41, 44], 2),
    ]
    with patch.object(wd, "get_draws", return_value=draws):
        c = TestClient(app)
        response = c.get("/numbers/cooccurrence?number=7")

    assert response.status_code == 200, response.text


def test_cooccurrence_page_no_data_returns_200() -> None:
    """AC-10: 데이터 부재에도 /numbers/cooccurrence는 200을 반환한다."""
    from lotto.web import data as wd
    from lotto.web.app import app

    with patch.object(wd, "get_draws", return_value=None):
        c = TestClient(app)
        response = c.get("/numbers/cooccurrence")

    assert response.status_code == 200, response.text


def test_index_has_cooccurrence_nav_link() -> None:
    """GET / 응답 HTML에 /numbers/cooccurrence 네비게이션 링크가 포함된다."""
    from lotto.web.app import app

    c = TestClient(app)
    response = c.get("/")
    assert response.status_code == 200
    assert 'href="/numbers/cooccurrence"' in response.text
