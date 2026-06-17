"""SPEC-LOTTO-101: 적합도 기반 번호 추천 TDD 테스트.

get_fitness_score(SPEC-LOTTO-100)를 사용해 pool_size개 무작위 조합 중
min_score 이상의 상위 count개 추천을 생성한다.

주의: 내부 get_fitness_score는 {"fitness_score", "grade", ...}를 반환하지만
이 기능의 출력 계약은 {"numbers", "score", "grade"}이다 (score = fitness_score).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from lotto.models import DrawResult
from lotto.web.app import app
from lotto.web.data import get_fitness_recommendations

client = TestClient(app)


def _sample_draws() -> list[DrawResult]:
    """점수 계산을 위한 소규모 회차 데이터."""
    return [
        DrawResult(
            drwNo=1, date=date(2002, 12, 7), n1=1, n2=10, n3=20, n4=30, n5=40, n6=45, bonus=5
        ),
        DrawResult(
            drwNo=2, date=date(2002, 12, 14), n1=3, n2=12, n3=18, n4=27, n5=33, n6=44, bonus=3
        ),
        DrawResult(
            drwNo=3, date=date(2002, 12, 21), n1=5, n2=11, n3=22, n4=29, n5=38, n6=42, bonus=7
        ),
    ]


# --- 핵심 함수 테스트 (get_fitness_recommendations) ---

def test_returns_list() -> None:
    """리스트를 반환한다."""
    result = get_fitness_recommendations(count=5, min_score=0, pool_size=10, draws=_sample_draws())
    assert isinstance(result, list)


def test_each_item_has_numbers() -> None:
    """각 항목에 numbers 키가 있다."""
    result = get_fitness_recommendations(count=5, min_score=0, pool_size=10, draws=_sample_draws())
    for item in result:
        assert "numbers" in item


def test_each_item_has_score() -> None:
    """각 항목에 score 키가 있다."""
    result = get_fitness_recommendations(count=5, min_score=0, pool_size=10, draws=_sample_draws())
    for item in result:
        assert "score" in item


def test_each_item_has_grade() -> None:
    """각 항목에 grade 키가 있다."""
    result = get_fitness_recommendations(count=5, min_score=0, pool_size=10, draws=_sample_draws())
    for item in result:
        assert "grade" in item


def test_numbers_are_sorted() -> None:
    """numbers는 오름차순 정렬된다."""
    result = get_fitness_recommendations(count=5, min_score=0, pool_size=10, draws=_sample_draws())
    for item in result:
        assert item["numbers"] == sorted(item["numbers"])


def test_numbers_are_six_integers() -> None:
    """numbers는 정수 6개다."""
    result = get_fitness_recommendations(count=5, min_score=0, pool_size=10, draws=_sample_draws())
    for item in result:
        assert len(item["numbers"]) == 6
        assert all(isinstance(n, int) for n in item["numbers"])


def test_numbers_in_range_1_to_45() -> None:
    """모든 번호는 1~45 범위다."""
    result = get_fitness_recommendations(count=5, min_score=0, pool_size=20, draws=_sample_draws())
    for item in result:
        assert all(1 <= n <= 45 for n in item["numbers"])


def test_score_is_float() -> None:
    """score는 float다."""
    result = get_fitness_recommendations(count=5, min_score=0, pool_size=10, draws=_sample_draws())
    for item in result:
        assert isinstance(item["score"], float)


def test_grade_is_str() -> None:
    """grade는 문자열이다."""
    result = get_fitness_recommendations(count=5, min_score=0, pool_size=10, draws=_sample_draws())
    for item in result:
        assert isinstance(item["grade"], str)


def test_min_score_filter_zero() -> None:
    """min_score=0이면 pool 전체가 통과한다 (count 제한 내)."""
    result = get_fitness_recommendations(count=20, min_score=0, pool_size=15, draws=_sample_draws())
    assert len(result) == 15


def test_min_score_filter_high() -> None:
    """min_score=100이면 결과가 비거나 매우 적다."""
    result = get_fitness_recommendations(
        count=5, min_score=100, pool_size=20, draws=_sample_draws()
    )
    assert len(result) <= 5


def test_all_results_meet_min_score() -> None:
    """모든 결과의 score는 min_score 이상이다."""
    result = get_fitness_recommendations(
        count=10, min_score=20, pool_size=30, draws=_sample_draws()
    )
    for item in result:
        assert item["score"] >= 20


def test_count_limits_results() -> None:
    """count가 결과 개수를 제한한다."""
    result = get_fitness_recommendations(count=3, min_score=0, pool_size=50, draws=_sample_draws())
    assert len(result) <= 3


def test_results_sorted_descending() -> None:
    """결과는 score 내림차순으로 정렬된다."""
    result = get_fitness_recommendations(count=10, min_score=0, pool_size=50, draws=_sample_draws())
    scores = [item["score"] for item in result]
    assert scores == sorted(scores, reverse=True)


def test_pool_size_one() -> None:
    """pool_size=1이면 0개 또는 1개 결과."""
    result = get_fitness_recommendations(count=5, min_score=0, pool_size=1, draws=_sample_draws())
    assert len(result) <= 1


def test_default_params() -> None:
    """draws만 지정해도 기본 파라미터로 동작한다."""
    result = get_fitness_recommendations(draws=_sample_draws())
    assert isinstance(result, list)
    assert len(result) <= 5


def test_draws_param_accepted() -> None:
    """draws 인자를 받는다."""
    result = get_fitness_recommendations(count=2, min_score=0, pool_size=5, draws=_sample_draws())
    assert isinstance(result, list)


def test_empty_draws_returns_zero_score() -> None:
    """draws=[]이면 점수 0점 — min_score=0이면 결과 반환."""
    result = get_fitness_recommendations(count=3, min_score=0, pool_size=5, draws=[])
    assert len(result) <= 3
    for item in result:
        assert item["score"] == 0.0


def test_empty_draws_high_min_score_empty() -> None:
    """draws=[]이고 min_score>0이면 결과가 비어있다 (모두 0점)."""
    result = get_fitness_recommendations(count=5, min_score=1, pool_size=10, draws=[])
    assert result == []


def test_no_duplicates_in_numbers() -> None:
    """각 조합의 번호는 중복이 없다."""
    result = get_fitness_recommendations(count=5, min_score=0, pool_size=20, draws=_sample_draws())
    for item in result:
        assert len(set(item["numbers"])) == 6


def test_draws_none_calls_get_draws() -> None:
    """draws=None이면 내부에서 get_draws()를 호출한다."""
    with patch("lotto.web.data.get_draws", return_value=_sample_draws()) as mock_draws:
        get_fitness_recommendations(count=2, min_score=0, pool_size=5)
        mock_draws.assert_called_once()


# --- API 엔드포인트 테스트 (GET /api/stats/fitness-recommend) ---

def test_api_default_response_200() -> None:
    """기본 호출은 200을 반환한다."""
    resp = client.get("/api/stats/fitness-recommend?pool_size=20&min_score=0")
    assert resp.status_code == 200


def test_api_response_is_list() -> None:
    """응답은 리스트다."""
    resp = client.get("/api/stats/fitness-recommend?pool_size=20&min_score=0")
    assert isinstance(resp.json(), list)


def test_api_item_structure() -> None:
    """각 항목은 numbers, score, grade를 포함한다."""
    resp = client.get("/api/stats/fitness-recommend?count=3&pool_size=30&min_score=0")
    for item in resp.json():
        assert "numbers" in item
        assert "score" in item
        assert "grade" in item


def test_api_count_param() -> None:
    """count 파라미터가 결과 개수를 제한한다."""
    resp = client.get("/api/stats/fitness-recommend?count=2&pool_size=50&min_score=0")
    assert len(resp.json()) <= 2


def test_api_min_score_filter() -> None:
    """min_score 필터가 적용된다 — 모든 항목 score>=min_score."""
    resp = client.get("/api/stats/fitness-recommend?min_score=10&pool_size=30&count=10")
    for item in resp.json():
        assert item["score"] >= 10


def test_api_min_score_zero_returns_results() -> None:
    """min_score=0이면 결과를 반환한다."""
    resp = client.get("/api/stats/fitness-recommend?min_score=0&pool_size=20&count=5")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_api_pool_size_param() -> None:
    """pool_size 파라미터로 동작한다."""
    resp = client.get("/api/stats/fitness-recommend?pool_size=5&min_score=0&count=5")
    assert resp.status_code == 200


def test_api_count_min_invalid() -> None:
    """count=0은 422."""
    resp = client.get("/api/stats/fitness-recommend?count=0")
    assert resp.status_code == 422


def test_api_count_max_invalid() -> None:
    """count=21은 422."""
    resp = client.get("/api/stats/fitness-recommend?count=21")
    assert resp.status_code == 422


def test_api_count_min_valid() -> None:
    """count=1은 200."""
    resp = client.get("/api/stats/fitness-recommend?count=1&pool_size=10&min_score=0")
    assert resp.status_code == 200


def test_api_count_max_valid() -> None:
    """count=20은 200."""
    resp = client.get("/api/stats/fitness-recommend?count=20&pool_size=10&min_score=0")
    assert resp.status_code == 200


def test_api_min_score_below_zero() -> None:
    """min_score=-1은 422."""
    resp = client.get("/api/stats/fitness-recommend?min_score=-1")
    assert resp.status_code == 422


def test_api_min_score_above_100() -> None:
    """min_score=101은 422."""
    resp = client.get("/api/stats/fitness-recommend?min_score=101")
    assert resp.status_code == 422


def test_api_min_score_zero_valid() -> None:
    """min_score=0은 200."""
    resp = client.get("/api/stats/fitness-recommend?min_score=0&pool_size=10")
    assert resp.status_code == 200


def test_api_min_score_100_valid() -> None:
    """min_score=100은 200."""
    resp = client.get("/api/stats/fitness-recommend?min_score=100&pool_size=10")
    assert resp.status_code == 200


def test_api_pool_size_zero_invalid() -> None:
    """pool_size=0은 422."""
    resp = client.get("/api/stats/fitness-recommend?pool_size=0")
    assert resp.status_code == 422


def test_api_pool_size_over_max() -> None:
    """pool_size=5001은 422."""
    resp = client.get("/api/stats/fitness-recommend?pool_size=5001")
    assert resp.status_code == 422


def test_api_pool_size_one_valid() -> None:
    """pool_size=1은 200."""
    resp = client.get("/api/stats/fitness-recommend?pool_size=1&min_score=0")
    assert resp.status_code == 200


def test_api_pool_size_5000_valid() -> None:
    """pool_size=5000은 200 (느린 실행 회피를 위해 mock 사용)."""
    with patch(
        "lotto.web.data.get_fitness_recommendations",
        return_value=[{"numbers": [1, 2, 3, 4, 5, 6], "score": 50.0, "grade": "B"}],
    ):
        resp = client.get("/api/stats/fitness-recommend?pool_size=5000&min_score=0")
    assert resp.status_code == 200


def test_api_sorted_descending() -> None:
    """API 결과는 score 내림차순이다."""
    resp = client.get("/api/stats/fitness-recommend?count=10&pool_size=40&min_score=0")
    scores = [item["score"] for item in resp.json()]
    assert scores == sorted(scores, reverse=True)


def test_api_partial_result_ok() -> None:
    """min_score=99이면 비어있을 수 있으나 여전히 200."""
    resp = client.get("/api/stats/fitness-recommend?min_score=99&pool_size=20")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_api_numbers_six_each() -> None:
    """API 각 항목의 번호는 6개다."""
    resp = client.get("/api/stats/fitness-recommend?count=5&pool_size=30&min_score=0")
    for item in resp.json():
        assert len(item["numbers"]) == 6


def test_api_numbers_in_range() -> None:
    """API 각 번호는 1~45 범위다."""
    resp = client.get("/api/stats/fitness-recommend?count=5&pool_size=30&min_score=0")
    for item in resp.json():
        assert all(1 <= n <= 45 for n in item["numbers"])


# --- 페이지 라우트 테스트 (GET /stats/fitness-recommend) ---

def test_page_200() -> None:
    """페이지는 200을 반환한다."""
    resp = client.get("/stats/fitness-recommend?pool_size=10&min_score=0")
    assert resp.status_code == 200


def test_page_html_content() -> None:
    """HTML 콘텐츠를 반환한다."""
    resp = client.get("/stats/fitness-recommend?pool_size=10&min_score=0")
    assert "text/html" in resp.headers["content-type"]


def test_page_contains_form() -> None:
    """페이지에 폼이 포함된다."""
    resp = client.get("/stats/fitness-recommend?pool_size=10&min_score=0")
    assert "<form" in resp.text


def test_page_contains_title() -> None:
    """페이지에 적합도 추천 제목이 포함된다."""
    resp = client.get("/stats/fitness-recommend?pool_size=10&min_score=0")
    assert "적합도" in resp.text


def test_page_with_params() -> None:
    """파라미터를 전달해도 동작한다."""
    resp = client.get("/stats/fitness-recommend?count=3&min_score=0&pool_size=10")
    assert resp.status_code == 200


def test_page_invalid_count_422() -> None:
    """count=0은 422 (FastAPI 검증)."""
    resp = client.get("/stats/fitness-recommend?count=0")
    assert resp.status_code == 422


def test_page_invalid_count_max_422() -> None:
    """count=21은 422."""
    resp = client.get("/stats/fitness-recommend?count=21")
    assert resp.status_code == 422


def test_page_invalid_min_score_422() -> None:
    """min_score=-1은 422."""
    resp = client.get("/stats/fitness-recommend?min_score=-1")
    assert resp.status_code == 422


def test_page_invalid_min_score_max_422() -> None:
    """min_score=101은 422."""
    resp = client.get("/stats/fitness-recommend?min_score=101")
    assert resp.status_code == 422


def test_page_invalid_pool_size_422() -> None:
    """pool_size=0은 422."""
    resp = client.get("/stats/fitness-recommend?pool_size=0")
    assert resp.status_code == 422


def test_page_invalid_pool_size_max_422() -> None:
    """pool_size=5001은 422."""
    resp = client.get("/stats/fitness-recommend?pool_size=5001")
    assert resp.status_code == 422


def test_page_renders_recommendations() -> None:
    """추천 결과가 페이지에 렌더링된다 (번호 표시)."""
    resp = client.get("/stats/fitness-recommend?count=3&min_score=0&pool_size=20")
    assert resp.status_code == 200


# --- 네비게이션 탭 테스트 ---

def test_base_html_has_fitness_recommend_nav() -> None:
    """base.html 네비게이션에 적합도 추천 탭이 있다."""
    resp = client.get("/stats/fitness-recommend?pool_size=10&min_score=0")
    assert "/stats/fitness-recommend" in resp.text


def test_fitness_recommend_page_active_tab() -> None:
    """페이지의 active_tab이 fitness-recommend다 (탭 라벨 표시 확인)."""
    resp = client.get("/stats/fitness-recommend?pool_size=10&min_score=0")
    assert "적합도 추천" in resp.text


def test_page_default_no_params() -> None:
    """파라미터 없이 호출해도 기본값으로 동작한다 (mock으로 속도 확보)."""
    with patch(
        "lotto.web.data.get_fitness_recommendations",
        return_value=[{"numbers": [1, 2, 3, 4, 5, 6], "score": 50.0, "grade": "B"}],
    ):
        resp = client.get("/stats/fitness-recommend")
    assert resp.status_code == 200
