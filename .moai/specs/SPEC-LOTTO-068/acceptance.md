---
id: SPEC-LOTTO-068
version: 0.1.0
status: Planned
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-068 인수 기준

## 인수 기준 목록

### AC-068-001: 빈 데이터 처리
**Given** draws 목록이 비어 있을 때
**When** `get_range_dist_stats([])` 를 호출하면
**Then** `total_draws=0`, `most_covered_range=""`, `range_stats` 에
`"1-9","10-19","20-29","30-39","40-45"` 5개 구간 키가 모두 존재하고,
각 구간의 `total_count=0`, `draw_count=0`, `avg_per_draw=0.0`,
`pct_of_numbers=0.0`, `draw_pct=0.0`

### AC-068-002: 단일 구간 "1-9" 전체 회차
**Given** 6개 번호가 [1,2,3,4,5,6]인 단일 회차
**When** stats 산출
**Then** `range_stats["1-9"]["total_count"]=6`,
다른 4개 구간의 `total_count=0`

### AC-068-003: 단일 구간 "40-45" 전체 회차
**Given** 6개 번호가 [40,41,42,43,44,45]인 단일 회차
**When** stats 산출
**Then** `range_stats["40-45"]["total_count"]=6`,
다른 4개 구간의 `total_count=0`

### AC-068-004: 3개 구간 이상 분산 회차
**Given** 6개 번호가 [5, 15, 25, 35, 42, 43]인 단일 회차
**When** stats 산출
**Then** `range_stats["1-9"]["total_count"]=1`,
`range_stats["10-19"]["total_count"]=1`,
`range_stats["20-29"]["total_count"]=1`,
`range_stats["30-39"]["total_count"]=1`,
`range_stats["40-45"]["total_count"]=2`

### AC-068-005: 보너스 번호 제외
**Given** main numbers=[5,15,25,35,42,43], bonus=1
**When** stats 산출
**Then** `range_stats["1-9"]["total_count"]=1` (보너스 1은 제외되어 2가 아님)

### AC-068-006: 5 구간 항상 존재
**Given** 임의 비어 있지 않은 draws 목록
**When** `get_range_dist_stats(draws)` 호출
**Then** `range_stats` 에 "1-9","10-19","20-29","30-39","40-45"
5개 키가 항상 존재

### AC-068-007: avg_per_draw 정확성
**Given** 10개 회차에서 "1-9" 구간 번호의 누적 개수가 15개
**When** stats 산출
**Then** `range_stats["1-9"]["avg_per_draw"]=1.5` (15/10)

### AC-068-008: pct_of_numbers 정확성
**Given** 10개 회차에서 "1-9" 구간 번호의 누적 개수가 15개
**When** stats 산출
**Then** `range_stats["1-9"]["pct_of_numbers"]=25.0` (15 / (10×6) × 100)

### AC-068-009: draw_count 정확성
**Given** 3개 회차 중 2개 회차가 "40-45" 구간 번호를 포함
**When** stats 산출
**Then** `range_stats["40-45"]["draw_count"]=2`

### AC-068-010: draw_pct 정확성
**Given** 3개 회차 중 2개 회차가 특정 구간을 포함 (draw_count=2)
**When** stats 산출
**Then** 해당 구간 `draw_pct=66.67` (2/3 × 100, 2자리 반올림)

### AC-068-011: most_covered_range
**Given** "10-19" 구간이 다른 모든 구간보다 높은 draw_count를 가지는 draws
**When** stats 산출
**Then** `most_covered_range="10-19"`

### AC-068-012: most_covered_range 동점 처리
**Given** 둘 이상의 구간이 동일한 (최댓값) draw_count를 가짐
**When** stats 산출
**Then** `_RANGES` 목록에서 앞서는 구간이 `most_covered_range`로 반환됨

### AC-068-013: draw_count <= total_draws 불변식
**Given** 임의 비어 있지 않은 draws 목록
**When** stats 산출
**Then** 모든 구간에 대해 `range_stats[r]["draw_count"] <= total_draws`

### AC-068-014: pct_of_numbers 합계
**Given** 임의 비어 있지 않은 draws (모든 번호가 정확히 한 구간에 속함)
**When** stats 산출
**Then** 5개 구간 `pct_of_numbers` 의 합 ≈ 100.0 (abs=0.1)

### AC-068-015: 캐시 히트
**Given** `get_range_dist_stats(draws)` 첫 호출 완료
**When** 동일한 `len(draws)`로 두 번째 호출
**Then** 동일한 객체(id) 반환

### AC-068-016: 캐시 미스
**Given** `get_range_dist_stats(draws_n)` 호출 완료
**When** 다른 `len(draws_n+1)`으로 호출
**Then** 새로 계산한 결과 반환

### AC-068-017: invalidate_cache
**Given** 캐시에 값이 채워진 상태
**When** `invalidate_cache()` 호출
**Then** `_range_dist_cache` 가 비워짐 (다음 호출이 새로 계산)

### AC-068-018: API 엔드포인트 — 구조 검증
**Given** TestClient 사용
**When** `GET /api/stats/range_dist`
**Then** HTTP 200, JSON에 `total_draws`, `most_covered_range`, `range_stats` 키 존재

### AC-068-019: 페이지 엔드포인트
**Given** TestClient 사용
**When** `GET /stats/range_dist`
**Then** HTTP 200, Content-Type text/html, "구간" 텍스트 포함

### AC-068-020: 실 데이터 smoke test
**Given** 실제 DB draws 로드 (비어 있지 않음 가정)
**When** `get_range_dist_stats(real_draws)`
**Then** `total_draws > 0`, `range_stats["10-19"]["avg_per_draw"] > 0.5`, no exception

### AC-068-021: 폭이 넓은 구간 우위
**Given** 실제 DB draws 로드 (비어 있지 않음 가정)
**When** stats 산출
**Then** `range_stats["10-19"]["total_count"] + range_stats["20-29"]["total_count"]
> range_stats["1-9"]["total_count"]`
(10개 폭 구간이 9개 폭 구간보다 누적 개수가 큼)

### AC-068-022: 구간 경계값 분류
**Given** 번호 9를 포함하는 회차와 번호 10을 포함하는 회차
**When** stats 산출
**Then** 9 → "1-9" 구간으로 분류, 10 → "10-19" 구간으로 분류

## 완료 정의 (Definition of Done)

- [ ] AC-068-001 ~ AC-068-022 전체 pass
- [ ] `pytest tests/test_range_dist_analysis.py` 실행 시 20개 이상 PASS
- [ ] `mypy lotto/ tests/` 오류 0건 (기존 무시 목록 유지)
- [ ] `GET /stats/range_dist` 200 응답, HTML 정상 렌더링
- [ ] `GET /api/stats/range_dist` 200 응답, JSON 구조 정확
- [ ] `invalidate_cache()` 호출 시 캐시 초기화 확인
- [ ] base.html 네비게이션에 "구간" 링크 추가 확인
- [ ] 기존 1569개 테스트 전체 PASS (회귀 없음)
