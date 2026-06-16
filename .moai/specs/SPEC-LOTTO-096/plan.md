# Implementation Plan: SPEC-LOTTO-096

## Overview

TDD 방법론(RED→GREEN→REFACTOR)으로 구현. 기존 `get_max_gap_dist_stats` (SPEC-080) 패턴을 참조하여 min_gap 버전을 구현한다.

## Phase 1: RED — 실패하는 테스트 작성

파일: `tests/test_min_gap_dist_stats.py`

테스트 항목 (41개 AC를 커버하는 35개 이상 테스트):
1. `test_none_input_returns_empty_structure` — AC-01
2. `test_empty_list_returns_empty_structure` — AC-02
3. `test_empty_returns_all_six_bucket_keys` — AC-03
4. `test_single_draw_min_gap_1_bucket_1` — AC-04
5. `test_single_draw_min_gap_2_bucket_2` — AC-05
6. `test_single_draw_min_gap_3_bucket_3` — AC-06
7. `test_single_draw_min_gap_4_bucket_4_5` — AC-07
8. `test_single_draw_min_gap_5_bucket_4_5` — AC-08
9. `test_single_draw_min_gap_6_bucket_6_10` — AC-09
10. `test_single_draw_min_gap_11plus_bucket` — AC-14
11. `test_multiple_draws_total_draws` — AC-15
12. `test_avg_min_gap_exact` — AC-16
13. `test_avg_min_gap_rounded_2dp` — AC-17
14. `test_pct_calculation_exact` — AC-18
15. `test_pct_rounded_2dp` — AC-19
16. `test_min1_pct_accuracy` — AC-20
17. `test_min1_pct_empty` — AC-21
18. `test_large_gap_pct_accuracy` — AC-22
19. `test_large_gap_pct_empty` — AC-23
20. `test_most_common_range_highest_count` — AC-24
21. `test_most_common_range_tie_prefers_first_bucket` — AC-25
22. `test_cache_hit_same_result` — AC-26
23. `test_invalidate_cache_clears` — AC-27
24. `test_api_endpoint_200` — AC-28
25. `test_api_response_bucket_keys` — AC-29
26. `test_api_bucket_value_structure` — AC-30
27. `test_page_endpoint_200` — AC-31
28. `test_page_contains_korean_title` — AC-32
29. `test_bonus_excluded_from_min_gap` — AC-33, AC-34
30. `test_pct_sum_near_100` — AC-35
31. `test_count_is_int_type` — AC-36
32. `test_pct_is_float_type` — AC-37
33. `test_total_draws_matches_list_length` — AC-38
34. `test_boundary_min_gap_5_bucket_4_5` — AC-39
35. `test_boundary_min_gap_6_bucket_6_10` — AC-40
36. `test_boundary_min_gap_10_bucket_6_10` — AC-41

## Phase 2: GREEN — 최소 구현

### Step 1: `lotto/web/data.py` 수정

추가 위치: `get_span_stats` 함수 바로 뒤 (파일 끝)

```python
# 버킷 상수
_MIN_GAP_KEYS = ("1", "2", "3", "4-5", "6-10", "11+")

# 캐시
_min_gap_dist_cache: dict[str, dict] = {}

def _min_gap_bucket(g: int) -> str:
    if g == 1:
        return "1"
    if g == 2:
        return "2"
    if g == 3:
        return "3"
    if g <= 5:
        return "4-5"
    if g <= 10:
        return "6-10"
    return "11+"

def get_min_gap_dist_stats(draws: list[DrawResult] | None) -> dict[str, Any]:
    ...
```

`invalidate_cache()` 함수에 `_min_gap_dist_cache.clear()` 추가.

### Step 2: `lotto/web/routes/api.py` 수정

추가 위치: `@router.get("/stats/span")` 엔드포인트 바로 뒤

```python
@router.get("/stats/min_gap_dist")
def stats_min_gap_dist():
    draws = get_draws()
    return get_min_gap_dist_stats(draws)
```

### Step 3: `lotto/web/routes/pages.py` 수정

기존 span 페이지 엔드포인트 뒤에 추가:

```python
@router.get("/stats/min_gap_dist")
def min_gap_dist_page(request: Request):
    draws = get_draws()
    stats = get_min_gap_dist_stats(draws)
    return templates.TemplateResponse(
        "min_gap_dist.html", {"request": request, "stats": stats}
    )
```

### Step 4: `lotto/web/templates/min_gap_dist.html` 신규 생성

기존 `span.html` 또는 `max_gap_dist.html` 템플릿 구조를 참고하여 작성. 한국어 레이블 사용.

### Step 5: `lotto/web/templates/base.html` 수정

내비게이션 탭에 "최소 간격 분포" 항목 추가 (`/stats/min_gap_dist` 링크).

## Phase 3: REFACTOR

- 불필요한 중복 제거
- 버킷 상수 네이밍 일관성 확인
- pct 계산 로직 단순화 확인
- 타입 힌트 완전성 확인 (Python 3.9 호환: `list[X]`, `dict[str, Any]`, `| None`)

## Key Constraints

- Python 3.9 호환: `zip(nums, nums[1:])` + `# noqa: B905` 사용
- `match/case` 미사용
- `zip(strict=True)` 미사용
- 캐시 키: `str(len(draws) if draws else 0)`
- 빈 데이터 most_common_range 기본값: `"1"`
- 모든 pct: `round(..., 2)`

## Dependency Map

```
tests/ → lotto/web/data.py (get_min_gap_dist_stats)
       → lotto/web/routes/api.py (/api/stats/min_gap_dist)
       → lotto/web/routes/pages.py (/stats/min_gap_dist)
       → lotto/web/templates/min_gap_dist.html
       → lotto/web/templates/base.html
```

## Definition of Done

- [ ] 35개 이상 테스트 모두 GREEN
- [ ] ruff check 오류 0건
- [ ] mypy 신규 오류 0건
- [ ] `/api/stats/min_gap_dist` HTTP 200 반환
- [ ] `/stats/min_gap_dist` HTML 페이지 렌더링
- [ ] invalidate_cache() 에 `_min_gap_dist_cache.clear()` 포함
- [ ] 기존 2453개 테스트 회귀 없음
