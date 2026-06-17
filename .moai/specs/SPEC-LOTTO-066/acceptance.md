---
id: SPEC-LOTTO-066
version: 0.1.0
status: Planned
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-066 인수 기준

## 인수 기준 목록

### AC-066-001: 빈 데이터 처리
**Given** draws 목록이 비어 있을 때  
**When** `get_prime_sum_stats([])` 를 호출하면  
**Then** `total_draws=0`, `avg_prime_sum=0.0`, `min_prime_sum=0`, `max_prime_sum=0`,
`low_count=0`, `mid_count=0`, `high_count=0`, `low_pct=0.0`, `mid_pct=0.0`,
`high_pct=0.0`, `most_common_bucket=""`, `prime_sum_distribution` 키가
`["0-30","30-60","60-90","90-120","120-150","150+"]` 모두 포함되며 값이 모두 0

### AC-066-002: 소수 없는 회차
**Given** 6개 번호가 모두 합성수(1 포함)인 단일 회차 (예: [1,4,6,8,9,10])  
**When** stats 산출  
**Then** `prime_sum=0`, `low_count=1`, `most_common_bucket="0-30"`

### AC-066-003: 소수 1개 회차
**Given** 6개 번호 중 소수 1개 (예: [1,4,6,8,9,7])  
**When** stats 산출  
**Then** `prime_sum=7`, `low_count=1` (7 < 40이므로 low)

### AC-066-004: 소수만 있는 회차
**Given** 6개 번호가 모두 소수 (예: [2,3,5,7,11,13])  
**When** stats 산출  
**Then** `prime_sum=41`, `mid_count=1` (40 ≤ 41 ≤ 80이므로 mid)

### AC-066-005: 보너스 번호 제외
**Given** main numbers=[1,4,6,8,9,2], bonus=7  
**When** stats 산출  
**Then** `prime_sum=2` (보너스 7은 제외), 7은 합산에 포함되지 않음

### AC-066-006: avg/min/max 정확성
**Given** prime_sum 값이 [10, 40, 90]인 3개 회차  
**When** stats 산출  
**Then** `avg_prime_sum=46.67` (±0.01), `min_prime_sum=10`, `max_prime_sum=90`

### AC-066-007: 6 버킷 항상 존재
**Given** 임의 draws 목록 (비어 있지 않음)  
**When** `get_prime_sum_stats(draws)` 호출  
**Then** `prime_sum_distribution` 에 "0-30","30-60","60-90","90-120","120-150","150+"
6개 키가 항상 존재

### AC-066-008: 버킷 경계값 — 0-30 vs 30-60
**Given** prime_sum=29인 회차와 prime_sum=30인 회차  
**When** stats 산출  
**Then** 29 → "0-30", 30 → "30-60"

### AC-066-009: 버킷 경계값 — 150+
**Given** prime_sum=150인 회차와 prime_sum=151인 회차  
**When** stats 산출  
**Then** 150 → "120-150", 151 → "150+"

### AC-066-010: 3-tier low 경계
**Given** prime_sum=39인 회차와 prime_sum=40인 회차  
**When** stats 산출  
**Then** 39 → low, 40 → mid

### AC-066-011: 3-tier high 경계
**Given** prime_sum=80인 회차와 prime_sum=81인 회차  
**When** stats 산출  
**Then** 80 → mid, 81 → high

### AC-066-012: 비율 합계
**Given** 임의 비어 있지 않은 draws  
**When** stats 산출  
**Then** `low_pct + mid_pct + high_pct ≈ 100.0` (abs=0.1)

### AC-066-013: most_common_bucket
**Given** "30-60" 버킷이 5회, "60-90"이 3회인 draws  
**When** stats 산출  
**Then** `most_common_bucket="30-60"`

### AC-066-014: most_common_bucket 동점 처리
**Given** "30-60"과 "60-90"이 동점  
**When** stats 산출  
**Then** 버킷 순서상 앞서는 "30-60" 반환 (또는 일관된 tie-break)

### AC-066-015: 캐시 히트
**Given** `get_prime_sum_stats(draws)` 첫 호출 완료  
**When** 동일한 `len(draws)`로 두 번째 호출  
**Then** 동일한 객체(id) 반환

### AC-066-016: 캐시 미스
**Given** `get_prime_sum_stats(draws_n)` 호출 완료  
**When** 다른 `len(draws_n+1)`으로 호출  
**Then** 새로 계산한 결과 반환

### AC-066-017: invalidate_cache
**Given** 캐시에 값이 채워진 상태  
**When** `invalidate_cache()` 호출  
**Then** `_prime_sum_cache` 가 비워짐 (다음 호출이 새로 계산)

### AC-066-018: API 엔드포인트 — 구조 검증
**Given** TestClient 사용  
**When** `GET /api/stats/prime_sum`  
**Then** HTTP 200, JSON에 `total_draws`, `avg_prime_sum`, `prime_sum_distribution`,
`most_common_bucket`, `low_count`, `mid_count`, `high_count` 키 존재

### AC-066-019: 페이지 엔드포인트
**Given** TestClient 사용  
**When** `GET /stats/prime_sum`  
**Then** HTTP 200, Content-Type text/html, "소수합" 텍스트 포함

### AC-066-020: 실 데이터 smoke test
**Given** 실제 DB draws 로드 (비어 있지 않음 가정)  
**When** `get_prime_sum_stats(real_draws)`  
**Then** `total_draws > 0`, `avg_prime_sum > 0.0`, no exception

## 완료 정의 (Definition of Done)

- [ ] AC-066-001 ~ AC-066-020 전체 pass
- [ ] `pytest tests/test_prime_sum_analysis.py` 실행 시 20개 이상 PASS
- [ ] `mypy lotto/ tests/` 오류 0건 (기존 무시 목록 유지)
- [ ] `GET /stats/prime_sum` 200 응답, HTML 정상 렌더링
- [ ] `GET /api/stats/prime_sum` 200 응답, JSON 구조 정확
- [ ] `invalidate_cache()` 호출 시 캐시 초기화 확인
- [ ] base.html 네비게이션에 "소수합" 링크 추가 확인
- [ ] 기존 1515개 테스트 전체 PASS (회귀 없음)
