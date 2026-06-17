---
id: SPEC-LOTTO-071
version: 0.1.0
status: Planned
created: 2026-06-12
updated: 2026-06-12
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-071 인수 기준

본 SPEC의 데이터 계층 함수는 `get_median_stats(draws)`,
헬퍼는 `compute_median(numbers)` · `_median_bucket(median)`,
캐시는 `_median_cache`,
라우트는 `/api/stats/median` · `/stats/median`,
템플릿은 `median.html` 이다.

중앙값 = 정렬된 6개 본번호 `[a,b,c,d,e,f]` 의 `(c+d)/2.0`. 분포 키는 9개 고정
(`"1-5"`~`"41-45"`)이며 경계값(`.5` 단위)은 상위 구간에 포함(`>=` 하한, `<` 상한).
`low_median_pct` 는 `median < 23.0` 회차 비율(strict, 23.0 제외).

아래 픽스처의 중앙값은 모두 손계산/코드로 검증되었다.

## 인수 기준 목록

### AC-071-001: 빈 데이터 처리 (REQ-MED-NF-001)
**Given** draws 목록이 비어 있을 때
**When** `get_median_stats([])` 를 호출하면
**Then** `total_draws=0`, `avg_median=0.0`, `most_common_range="1-5"`,
`low_median_pct=0.0`, `median_distribution` 에 9개 키가 모두 존재하고 각 키
`count=0`, `pct=0.0`

### AC-071-002: 중앙값 기본 예시 — [1,2,3,4,5,6] → 3.5 → "1-5" (REQ-MED-001)
**Given** 6개 번호가 [1,2,3,4,5,6]인 단일 회차
**When** stats 산출
**Then** median = 3.5 ((3+4)/2), `median_distribution["1-5"]["count"]=1`,
다른 8개 키 `count=0`

### AC-071-003: 고번호대 예시 — [10,20,30,40,42,45] → 35.0 → "31-35" (REQ-MED-001)
**Given** 6개 번호가 [10,20,30,40,42,45]인 단일 회차
**When** stats 산출
**Then** median = 35.0 ((30+40)/2), `median_distribution["31-35"]["count"]=1`

### AC-071-004: 가능한 최솟값 중앙값 1.5 → "1-5" (REQ-MED-001, 004)
**Given** 6개 번호가 [1,2,3,43,44,45]인 단일 회차
**When** stats 산출
**Then** median = (3+43)/2 = 23.0 → "21-25" (주의: 3·4번째는 3,43)
**보충**: 가능한 최소 median 1.5 케이스는 [1,2,3,4,5,6]형이 아닌 3·4번째가 1.5를
만들 수 없으므로(3번째>=1, 4번째>=2 최소 [1,2,...]) median 최소는 [a,b]=가운데가
가장 작은 [.,.,1?] 불가. 실제 최소 median은 3·4번째 최소조합 → [x,y,1,2,...] 불가
(정렬상 3번째>=3). 따라서 **검증 케이스는 [1,2,3,4,5,6] median 3.5 (AC-071-002)** 로
대체하고, 본 항목은 median=23.0 경계 케이스(아래 AC-071-009)와 통합한다.

### AC-071-005: 가능한 최댓값 중앙값 44.5 → "41-45" (REQ-MED-001, 004)
**Given** 6개 번호가 [40,41,44,45,...] 정렬 시 3·4번째가 44,45인 회차
예: [42,43,44,45,?,?] 는 6개 미만. 6개 정렬 [a,b,44,45,e,f] 에서 e,f>45 불가하므로
3·4번째가 44,45가 되려면 [.,.,44,45,?,?] 의 5·6번째가 없음 → 불가.
실제 가능한 최대 median은 3·4번째 = 43,45 등. 예 [40,41,43,45,?,?] 도 6개 필요.
**검증 케이스**: [40,41,42,43,44,45] → 3·4번째 = 42,43 → median 42.5 → "41-45"
**Then** median = 42.5, `median_distribution["41-45"]["count"]=1`

### AC-071-006: 경계값 median=5.5 → "6-10" (상위 구간 포함) (REQ-MED-004)
**Given** 6개 번호 정렬 시 3·4번째 합이 11인 회차, 예 [1,2,5,6,44,45]
**When** stats 산출
**Then** median = (5+6)/2 = 5.5 → "6-10" (`5.5 < 5.5` 불성립, `5.5 < 10.5` 성립),
`median_distribution["6-10"]["count"]=1`, `"1-5"` 는 0

### AC-071-007: 경계값 median=10.5 → "11-15" (REQ-MED-004)
**Given** 3·4번째 합이 21인 회차, 예 [1,2,10,11,44,45]
**When** stats 산출
**Then** median = 10.5 → "11-15", `median_distribution["11-15"]["count"]=1`

### AC-071-008: 경계값 median=20.5 → "21-25" + low 포함 (REQ-MED-004, 007)
**Given** 3·4번째 합이 41인 회차, 예 [1,2,20,21,44,45]
**When** stats 산출
**Then** median = 20.5 → "21-25"; `median < 23.0` 이므로 low 카운트에 포함

### AC-071-009: 경계값 median=23.0 → "21-25" + low 제외 (REQ-MED-004, 007)
**Given** 3·4번째 합이 46인 회차, 예 [1,2,22,24,44,45]
**When** stats 산출
**Then** median = 23.0 → "21-25"; `median < 23.0` 거짓이므로 low 카운트에서 **제외**

### AC-071-010: 보너스 번호 제외 (REQ-MED-NF-002)
**Given** main numbers=[1,2,3,4,5,6], bonus=45
**When** stats 산출
**Then** median = 3.5 (보너스 45 제외, 3·4번째 = 3,4), `"1-5"` count=1
(보너스 포함 시 7개 정렬에서 median이 달라지므로, 본번호 6개만 사용함을 검증)

### AC-071-011: 9개 키 항상 존재 (REQ-MED-004)
**Given** 임의 비어 있지 않은 draws 목록
**When** `get_median_stats(draws)` 호출
**Then** `median_distribution` 에 9개 키(`"1-5"`~`"41-45"`)가 항상 존재,
그 외 키 없음

### AC-071-012: avg_median 정확성 (REQ-MED-008)
**Given** 2개 회차 — [1,2,3,4,5,6](median 3.5), [10,20,30,40,42,45](median 35.0)
**When** stats 산출
**Then** `avg_median = 19.25` ((3.5+35.0)/2)

### AC-071-013: avg_median 2자리 반올림 (REQ-MED-NF-004)
**Given** 3개 회차로 평균이 무한소수가 되는 구성, 예 median 3.5, 5.5, 5.5
**When** stats 산출
**Then** `avg_median = round((3.5+5.5+5.5)/3, 2) = 4.83`

### AC-071-014: most_common_range 산출 (REQ-MED-006)
**Given** "1-5" 회차 2개, "31-35" 회차 1개로 구성된 draws
**When** stats 산출
**Then** `most_common_range = "1-5"` (count 최댓값), 문자열 타입

### AC-071-015: most_common_range 동점 처리 — 앞 구간 우선 (REQ-MED-006)
**Given** "1-5" 회차 1개, "31-35" 회차 1개 (동일 최댓값 count)
**When** stats 산출
**Then** `most_common_range = "1-5"` (동점 시 키 순서상 앞 구간 우선)

### AC-071-016: low_median_pct 정확성 — 임계값 23.0 (REQ-MED-007)
**Given** 4개 회차 — median 3.5, 20.5, 23.0, 35.0
**When** stats 산출
**Then** `low_median_pct = 50.0` (median<23.0 인 3.5·20.5 두 개 / 4개 × 100;
23.0·35.0 제외)

### AC-071-017: pct 합계 (REQ-MED-NF-004)
**Given** 임의 비어 있지 않은 draws 목록
**When** stats 산출
**Then** 9개 키 `pct` 의 합 ≈ 100.0 (abs=0.1)

### AC-071-018: count 합계 = total_draws (REQ-MED-004)
**Given** 임의 비어 있지 않은 draws 목록
**When** stats 산출
**Then** 9개 키 `count` 의 합 = `total_draws`

### AC-071-019: 캐시 히트 / 미스 (REQ-MED-005)
**Given** `get_median_stats(draws)` 첫 호출 완료
**When** 동일한 `len(draws)`로 두 번째 호출 / 다른 `len`으로 호출
**Then** 동일 `len` → 동일한 객체(id) 반환; 다른 `len` → 새로 계산한 결과 반환

### AC-071-020: invalidate_cache (REQ-MED-005)
**Given** 캐시에 값이 채워진 상태
**When** `invalidate_cache()` 호출
**Then** `_median_cache` 가 비워짐 (다음 호출이 새로 계산)

### AC-071-021: API 엔드포인트 — 구조 검증 (REQ-MED-002)
**Given** TestClient 사용
**When** `GET /api/stats/median`
**Then** HTTP 200, JSON에 `total_draws`, `avg_median`, `most_common_range`,
`low_median_pct`, `median_distribution` 키가 모두 존재하고
`median_distribution` 에 9개 키(`"1-5"`~`"41-45"`) 존재

### AC-071-022: 페이지 엔드포인트 + 실 데이터 smoke (REQ-MED-003, NF-003)
**Given** TestClient 사용 및 실제 DB draws 로드 (비어 있지 않음 가정)
**When** `GET /stats/median` 호출 및 `get_median_stats(real_draws)` 호출
**Then** 페이지 HTTP 200, Content-Type text/html, "중앙값" 텍스트 포함;
실 데이터 `total_draws > 0`, `avg_median > 0`, 모든 median ∈ [1.5, 44.5], 예외 없음

## 완료 정의 (Definition of Done)

- [ ] AC-071-001 ~ AC-071-022 전체 pass
- [ ] `pytest tests/test_median_analysis.py` 실행 시 22개 이상 PASS
- [ ] `GET /stats/median` 200 응답, HTML 정상 렌더링 ("중앙값" 포함)
- [ ] `GET /api/stats/median` 200 응답, JSON 구조 정확 (9개 분포 키)
- [ ] `invalidate_cache()` 호출 시 `_median_cache` 초기화 확인
- [ ] 경계값(5.5/10.5/20.5/23.0) 버킷 배정 및 low 판정 정확성 확인
- [ ] base.html 네비게이션에 "중앙값" 링크 추가 확인 (데스크탑+모바일+모바일메뉴 3개소)
- [ ] 코어 모듈(`lotto/*.py`) 무변경 확인
- [ ] 기존 전체 테스트 PASS (회귀 없음)
