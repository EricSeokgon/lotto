# SPEC-LOTTO-101 구현 계획

## 구현 전략

TDD(Test-Driven Development) 방식으로 구현한다. RED → GREEN → REFACTOR 사이클을 따른다.

## 구현 순서

### Phase 1: 테스트 작성 (RED)

`tests/test_fitness_recommend.py`에 다음 테스트를 먼저 작성한다 (모두 실패 상태).

1. `test_fitness_recommend_api_returns_list` — API가 JSON 배열을 반환
2. `test_fitness_recommend_api_items_have_required_keys` — 각 항목에 `numbers`, `score`, `grade` 포함
3. `test_fitness_recommend_api_min_score_filter` — `min_score` 이상 항목만 반환
4. `test_fitness_recommend_api_count_limit` — 최대 `count`개 반환
5. `test_fitness_recommend_api_sorted_descending` — 점수 내림차순 정렬
6. `test_fitness_recommend_api_count_validation` — count 범위 외 422 반환
7. `test_fitness_recommend_api_min_score_validation` — min_score 범위 외 422 반환
8. `test_fitness_recommend_api_pool_size_validation` — pool_size 범위 외 422 반환
9. `test_fitness_recommend_api_partial_result` — 조건 미달 시 부분 반환
10. `test_fitness_recommend_page_renders` — 웹 페이지 HTTP 200 반환
11. `test_fitness_recommend_nav_link_exists` — 내비게이션 탭 링크 포함

### Phase 2: 구현 (GREEN)

최소 코드로 모든 테스트를 통과시킨다.

**우선순위 High:**
1. `lotto/web/routes/api.py` — `GET /api/stats/fitness-recommend` 엔드포인트 구현
   - 파라미터 검증 (FastAPI Query + validator)
   - 무작위 조합 생성 (`random.sample(range(1, 46), 6)`)
   - `get_fitness_score()` 호출
   - 필터링 → 정렬 → 슬라이싱
   - Python 3.9 호환 타입 힌트 사용

2. `lotto/web/routes/pages.py` — `GET /stats/fitness-recommend` 라우트 추가
   - API 결과를 템플릿 컨텍스트로 전달

**우선순위 Medium:**
3. `lotto/web/templates/fitness_recommend.html` — 결과 테이블 템플릿 작성
4. `lotto/web/templates/base.html` — 내비게이션 탭에 "적합도 추천" 추가

### Phase 3: 리팩토링 (REFACTOR)

- 추천 로직을 별도 함수 또는 모듈로 분리 (필요 시)
- 코드 중복 제거
- mypy 타입 검사 통과 확인
- 테스트 커버리지 확인

## 기술 고려사항

### 성능

- `pool_size=1000`일 때 `get_fitness_score()`를 1000회 호출한다.
- 각 호출은 `draws` 데이터를 순회하므로 응답 시간이 증가할 수 있다.
- 현재 단계에서는 비동기 최적화 없이 동기 처리로 구현한다.

### 난수 생성

- `random.sample(range(1, 46), 6)`을 사용하여 중복 없는 6개 번호를 생성한다.
- 시드 고정은 요구사항에 없으므로 매 요청마다 다른 결과가 반환된다.

### 타입 힌트 (Python 3.9 호환)

```python
# 올바른 방식 (Python 3.9 호환)
from typing import Optional
count: Optional[int] = Query(default=5, ge=1, le=20)  # noqa: UP045

# 금지 방식 (Python 3.10+)
count: int | None = Query(default=5, ge=1, le=20)
```

## 파일별 변경 요약

| 파일 | 변경 유형 | 핵심 내용 |
|------|-----------|-----------|
| `tests/test_fitness_recommend.py` | 신규 생성 | 11개 이상 테스트 케이스 |
| `lotto/web/routes/api.py` | 수정 | fitness-recommend 엔드포인트 추가 |
| `lotto/web/routes/pages.py` | 수정 | fitness-recommend 페이지 라우트 추가 |
| `lotto/web/templates/fitness_recommend.html` | 신규 생성 | 결과 테이블 템플릿 |
| `lotto/web/templates/base.html` | 수정 | 내비게이션 탭 추가 |
