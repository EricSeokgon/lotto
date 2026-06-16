---
id: SPEC-LOTTO-070
version: 0.1.0
status: Planned
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-070 인수 기준

본 SPEC의 데이터 계층 함수는 `get_ac_value_stats(draws)`,
헬퍼는 `compute_ac_value(numbers)`,
캐시는 `_ac_value_cache`,
라우트는 `/api/stats/ac_value` · `/stats/ac-value`,
템플릿은 `ac_value.html` 이다.

AC값 = 한 회차 6개 본번호의 C(6,2)=15개 쌍에 대한 절대 차이 중 **distinct 개수**.
분포 키는 `"0".."14"` 15개 고정이며, AC>=14 회차는 `"14"` 오버플로 버킷에 합산한다
(`min(ac, 14)`). `avg_ac_value`·`high_diversity_pct` 는 clamp 이전 원본 AC값으로 계산.

아래 픽스처의 AC값은 모두 손계산/코드로 검증되었다.

## 인수 기준 목록

### AC-070-001: 빈 데이터 처리 (REQ-AC-NF-001)
**Given** draws 목록이 비어 있을 때
**When** `get_ac_value_stats([])` 를 호출하면
**Then** `total_draws=0`, `avg_ac_value=0.0`, `most_common_ac=0`,
`high_diversity_pct=0.0`, `ac_distribution` 에 `"0".."14"` 15개 키가 모두 존재하고
각 키 `count=0`, `pct=0.0`

### AC-070-002: AC값 기본 예시 — [1,2,3,10,11,12] → 7 (REQ-AC-001)
**Given** 6개 번호가 [1,2,3,10,11,12]인 단일 회차
**When** stats 산출
**Then** AC값 = 7 (distinct 차이 {1,2,7,8,9,10,11}),
`ac_distribution["7"]["count"]=1`, 다른 14개 키 `count=0`

### AC-070-003: 6연속 등차 → AC=5 (REQ-AC-001)
**Given** 6개 번호가 [1,2,3,4,5,6]인 단일 회차
**When** stats 산출
**Then** AC값 = 5 (distinct 차이 {1,2,3,4,5}), `ac_distribution["5"]["count"]=1`

### AC-070-004: 균등 간격 등차 → AC=5 (REQ-AC-001)
**Given** 6개 번호가 [2,4,6,8,10,12]인 단일 회차
**When** stats 산출
**Then** AC값 = 5 (distinct 차이 {2,4,6,8,10}), `ac_distribution["5"]["count"]=1`

### AC-070-005: 넓은 간격 등차 → AC=5 (REQ-AC-001)
**Given** 6개 번호가 [5,10,15,20,25,30]인 단일 회차
**When** stats 산출
**Then** AC값 = 5 (distinct 차이 {5,10,15,20,25}), `ac_distribution["5"]["count"]=1`

### AC-070-006: 고다양성 조합 — AC=11 (REQ-AC-001)
**Given** 6개 번호가 [3,9,17,28,36,44]인 단일 회차
**When** stats 산출
**Then** AC값 = 11, `ac_distribution["11"]["count"]=1`

### AC-070-007: 오버플로 버킷 — AC=15 → 키 "14" (REQ-AC-004)
**Given** 6개 번호가 [1,2,4,8,16,32]인 단일 회차 (원본 AC=15)
**When** stats 산출
**Then** `ac_distribution["14"]["count"]=1` (오버플로 합산),
키 `"15"` 는 존재하지 않음 (KeyError 미발생)

### AC-070-008: 오버플로 버킷 — 다른 AC=15 조합 (REQ-AC-004)
**Given** 6개 번호가 [5,8,9,17,32,37]인 단일 회차 (원본 AC=15)
**When** stats 산출
**Then** `ac_distribution["14"]["count"]=1`

### AC-070-009: 보너스 번호 제외 (REQ-AC-NF-002)
**Given** main numbers=[1,2,3,4,5,6], bonus=7
**When** stats 산출
**Then** AC값 = 5 (보너스 7은 제외, distinct 차이 {1,2,3,4,5}),
`ac_distribution["5"]["count"]=1`

### AC-070-010: 15 키 항상 존재 (REQ-AC-004)
**Given** 임의 비어 있지 않은 draws 목록
**When** `get_ac_value_stats(draws)` 호출
**Then** `ac_distribution` 에 `"0".."14"` 15개 키가 항상 존재

### AC-070-011: avg_ac_value 정확성 (REQ-AC-008)
**Given** 2개 회차 — [1,2,3,4,5,6](AC=5), [1,2,3,10,11,12](AC=7)
**When** stats 산출
**Then** `avg_ac_value=6.0` ((5+7)/2)

### AC-070-012: avg_ac_value — 오버플로는 원본값으로 평균 (REQ-AC-008)
**Given** 2개 회차 — [1,2,3,4,5,6](AC=5), [1,2,4,8,16,32](원본 AC=15)
**When** stats 산출
**Then** `avg_ac_value=10.0` ((5+15)/2, clamp 이전 원본 15 사용)

### AC-070-013: most_common_ac 산출 (REQ-AC-006)
**Given** AC=5 회차 2개, AC=7 회차 1개로 구성된 draws
**When** stats 산출
**Then** `most_common_ac=5` (count 최댓값), 정수 타입으로 반환

### AC-070-014: most_common_ac 동점 처리 — 더 작은 AC 우선 (REQ-AC-006)
**Given** AC=5 회차 1개, AC=7 회차 1개 (동일 최댓값 count)
**When** stats 산출
**Then** `most_common_ac=5` (동점 시 더 작은 AC값 우선)

### AC-070-015: high_diversity_pct 정확성 — 임계값 9 (REQ-AC-007)
**Given** 4개 회차 — AC=5, AC=8, AC=9, AC=12 각 1개
**When** stats 산출
**Then** `high_diversity_pct=50.0` (AC>=9 인 2개 / 4개 × 100)

### AC-070-016: high_diversity_pct 경계 — AC=9는 포함, AC=8은 제외 (REQ-AC-007)
**Given** 2개 회차 — [3,4,15,26,37,38](AC=8), [12,16,20,24,30,38](AC=9)
**When** stats 산출
**Then** `high_diversity_pct=50.0` (AC=9 포함, AC=8 제외)

### AC-070-017: AC값 0~14 범위 보장 (REQ-AC-004)
**Given** 임의 비어 있지 않은 draws 목록
**When** stats 산출
**Then** `ac_distribution` 의 모든 키는 `"0".."14"` 범위 내, 그 외 키 없음

### AC-070-018: pct 합계 (REQ-AC-NF-004)
**Given** 임의 비어 있지 않은 draws 목록
**When** stats 산출
**Then** 15개 키 `pct` 의 합 ≈ 100.0 (abs=0.1)

### AC-070-019: count 합계 = total_draws (REQ-AC-004)
**Given** 임의 비어 있지 않은 draws 목록
**When** stats 산출
**Then** 15개 키 `count` 의 합 = `total_draws`

### AC-070-020: 캐시 히트 (REQ-AC-005)
**Given** `get_ac_value_stats(draws)` 첫 호출 완료
**When** 동일한 `len(draws)`로 두 번째 호출
**Then** 동일한 객체(id) 반환

### AC-070-021: 캐시 미스 (REQ-AC-005)
**Given** `get_ac_value_stats(draws_n)` 호출 완료
**When** 다른 `len(draws_n+1)`으로 호출
**Then** 새로 계산한 결과 반환

### AC-070-022: invalidate_cache (REQ-AC-005)
**Given** 캐시에 값이 채워진 상태
**When** `invalidate_cache()` 호출
**Then** `_ac_value_cache` 가 비워짐 (다음 호출이 새로 계산)

### AC-070-023: API 엔드포인트 — 구조 검증 (REQ-AC-002)
**Given** TestClient 사용
**When** `GET /api/stats/ac_value`
**Then** HTTP 200, JSON에 `total_draws`, `avg_ac_value`, `most_common_ac`,
`high_diversity_pct`, `ac_distribution` 키가 모두 존재하고
`ac_distribution` 에 15개 키(`"0".."14"`) 존재

### AC-070-024: 페이지 엔드포인트 + 실 데이터 smoke (REQ-AC-003, NF-003)
**Given** TestClient 사용 및 실제 DB draws 로드 (비어 있지 않음 가정)
**When** `GET /stats/ac-value` 호출 및 `get_ac_value_stats(real_draws)` 호출
**Then** 페이지 HTTP 200, Content-Type text/html, "AC" 텍스트 포함;
실 데이터 `total_draws > 0`, `avg_ac_value > 0`, 예외 없음

## 완료 정의 (Definition of Done)

- [ ] AC-070-001 ~ AC-070-024 전체 pass
- [ ] `pytest tests/test_ac_value_analysis.py` 실행 시 24개 이상 PASS
- [ ] `GET /stats/ac-value` 200 응답, HTML 정상 렌더링 ("AC" 포함)
- [ ] `GET /api/stats/ac_value` 200 응답, JSON 구조 정확 (15개 분포 키)
- [ ] `invalidate_cache()` 호출 시 `_ac_value_cache` 초기화 확인
- [ ] AC>=15 오버플로가 `"14"` 버킷에 합산되고 KeyError 미발생 확인
- [ ] base.html 네비게이션에 "AC값" 링크 추가 확인 (데스크탑+모바일+모바일메뉴 3개소)
- [ ] 코어 모듈(`lotto/*.py`) 무변경 확인
- [ ] 기존 1629개 테스트 전체 PASS (회귀 없음)
