---
id: SPEC-LOTTO-067
version: 0.1.0
status: Planned
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-067 인수 기준

## 인수 기준 목록

### AC-067-001: 빈 데이터 처리
**Given** draws 목록이 비어 있을 때  
**When** `get_total_sum_stats([])` 를 호출하면  
**Then** `total_draws=0`, `avg_total_sum=0.0`, `min_total_sum=0`, `max_total_sum=0`,
`low_count=0`, `mid_count=0`, `high_count=0`, `low_pct=0.0`, `mid_pct=0.0`,
`high_pct=0.0`, `most_common_bucket=""`, `total_sum_distribution` 키가
`["21-80","81-110","111-130","131-150","151-170","171-255"]` 모두 포함되며 값이 모두 0

### AC-067-002: 최솟값 회차 (sum=21)
**Given** 6개 번호가 [1,2,3,4,5,6]인 단일 회차  
**When** stats 산출  
**Then** `total_sum=21`, `low_count=1` (21 < 110이므로 low), `most_common_bucket="21-80"`

### AC-067-003: 최댓값 회차 (sum=255)
**Given** 6개 번호가 [40,41,42,43,44,45]인 단일 회차  
**When** stats 산출  
**Then** `total_sum=255`, `high_count=1` (255 > 170이므로 high), `most_common_bucket="171-255"`

### AC-067-004: 보너스 번호 제외
**Given** main numbers=[10,20,30,40,5,6], bonus=45  
**When** stats 산출  
**Then** `total_sum=111` (보너스 45는 제외), 45는 합산에 포함되지 않음

### AC-067-005: avg/min/max 정확성
**Given** total_sum 값이 [100, 138, 175]인 3개 회차  
**When** stats 산출  
**Then** `avg_total_sum=137.67` (±0.01), `min_total_sum=100`, `max_total_sum=175`

### AC-067-006: 6 버킷 항상 존재
**Given** 임의 비어 있지 않은 draws 목록  
**When** `get_total_sum_stats(draws)` 호출  
**Then** `total_sum_distribution` 에 "21-80","81-110","111-130","131-150","151-170","171-255"
6개 키가 항상 존재

### AC-067-007: 버킷 경계값 — 80/81
**Given** total_sum=80인 회차와 total_sum=81인 회차  
**When** stats 산출  
**Then** 80 → "21-80", 81 → "81-110"

### AC-067-008: 버킷 경계값 — 110/111
**Given** total_sum=110인 회차와 total_sum=111인 회차  
**When** stats 산출  
**Then** 110 → "81-110", 111 → "111-130"

### AC-067-009: 버킷 경계값 — 130/131
**Given** total_sum=130인 회차와 total_sum=131인 회차  
**When** stats 산출  
**Then** 130 → "111-130", 131 → "131-150"

### AC-067-010: 버킷 경계값 — 150/151
**Given** total_sum=150인 회차와 total_sum=151인 회차  
**When** stats 산출  
**Then** 150 → "131-150", 151 → "151-170"

### AC-067-011: 버킷 경계값 — 170/171
**Given** total_sum=170인 회차와 total_sum=171인 회차  
**When** stats 산출  
**Then** 170 → "151-170", 171 → "171-255"

### AC-067-012: 3-tier low 경계
**Given** total_sum=109인 회차와 total_sum=110인 회차  
**When** stats 산출  
**Then** 109 → low, 110 → mid

### AC-067-013: 3-tier high 경계
**Given** total_sum=170인 회차와 total_sum=171인 회차  
**When** stats 산출  
**Then** 170 → mid, 171 → high

### AC-067-014: 비율 합계
**Given** 임의 비어 있지 않은 draws  
**When** stats 산출  
**Then** `low_pct + mid_pct + high_pct ≈ 100.0` (abs=0.1)

### AC-067-015: most_common_bucket
**Given** "131-150" 버킷이 5회, "151-170"이 3회인 draws  
**When** stats 산출  
**Then** `most_common_bucket="131-150"`

### AC-067-016: most_common_bucket 동점 처리
**Given** "131-150"과 "151-170"이 동점  
**When** stats 산출  
**Then** 버킷 순서상 앞서는 "131-150" 반환 (또는 일관된 tie-break)

### AC-067-017: 캐시 히트
**Given** `get_total_sum_stats(draws)` 첫 호출 완료  
**When** 동일한 `len(draws)`로 두 번째 호출  
**Then** 동일한 객체(id) 반환

### AC-067-018: 캐시 미스
**Given** `get_total_sum_stats(draws_n)` 호출 완료  
**When** 다른 `len(draws_n+1)`으로 호출  
**Then** 새로 계산한 결과 반환

### AC-067-019: invalidate_cache
**Given** 캐시에 값이 채워진 상태  
**When** `invalidate_cache()` 호출  
**Then** `_total_sum_cache` 가 비워짐 (다음 호출이 새로 계산)

### AC-067-020: API 엔드포인트 — 구조 검증
**Given** TestClient 사용  
**When** `GET /api/stats/total_sum`  
**Then** HTTP 200, JSON에 `total_draws`, `avg_total_sum`, `total_sum_distribution`,
`most_common_bucket`, `low_count`, `mid_count`, `high_count` 키 존재

### AC-067-021: 페이지 엔드포인트
**Given** TestClient 사용  
**When** `GET /stats/total_sum`  
**Then** HTTP 200, Content-Type text/html, "총합" 텍스트 포함

### AC-067-022: 실 데이터 smoke test
**Given** 실제 DB draws 로드 (비어 있지 않음 가정)  
**When** `get_total_sum_stats(real_draws)`  
**Then** `total_draws > 0`, `avg_total_sum > 100.0`, no exception

## 완료 정의 (Definition of Done)

- [ ] AC-067-001 ~ AC-067-022 전체 pass
- [ ] `pytest tests/test_total_sum_analysis.py` 실행 시 20개 이상 PASS
- [ ] `mypy lotto/ tests/` 오류 0건 (기존 무시 목록 유지)
- [ ] `GET /stats/total_sum` 200 응답, HTML 정상 렌더링
- [ ] `GET /api/stats/total_sum` 200 응답, JSON 구조 정확
- [ ] `invalidate_cache()` 호출 시 캐시 초기화 확인
- [ ] base.html 네비게이션에 "총합" 링크 추가 확인
- [ ] 기존 1541개 테스트 전체 PASS (회귀 없음)
