---
id: SPEC-LOTTO-069
version: 0.1.0
status: Planned
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-069 인수 기준

본 SPEC의 데이터 계층 함수는 `get_consecutive_pairs_stats(draws)`,
헬퍼는 `count_consecutive_pairs(numbers)`,
캐시는 `_consecutive_pairs_cache`,
라우트는 `/api/stats/consecutive-pairs` · `/stats/consecutive-pairs`,
템플릿은 `consecutive_pairs.html` 이다 (SPEC-062와의 충돌 회피).

## 인수 기준 목록

### AC-069-001: 빈 데이터 처리
**Given** draws 목록이 비어 있을 때
**When** `get_consecutive_pairs_stats([])` 를 호출하면
**Then** `total_draws=0`, `avg_consecutive_pairs=0.0`, `most_common_bucket=""`,
`no_consecutive_pct=0.0`, `has_consecutive_pct=0.0`,
`consecutive_distribution` 에 `"0","1","2","3+"` 4개 버킷 키가 모두 존재하고
각 버킷 `count=0`, `pct=0.0`

### AC-069-002: 6연속 전체 회차 → 버킷 "3+"
**Given** 6개 번호가 [1,2,3,4,5,6]인 단일 회차
**When** stats 산출
**Then** 해당 회차 연속 쌍 개수 = 5 ((1,2),(2,3),(3,4),(4,5),(5,6)),
`consecutive_distribution["3+"]["count"]=1`, 다른 3개 버킷 `count=0`

### AC-069-003: 연속 쌍 없음 → 버킷 "0"
**Given** 6개 번호가 [1,3,5,7,9,11]인 단일 회차
**When** stats 산출
**Then** 연속 쌍 개수 = 0, `consecutive_distribution["0"]["count"]=1`,
다른 3개 버킷 `count=0`

### AC-069-004: 연속 쌍 1개 → 버킷 "1"
**Given** 6개 번호가 [1,2,10,20,30,40]인 단일 회차
**When** stats 산출
**Then** 연속 쌍 개수 = 1 ((1,2)), `consecutive_distribution["1"]["count"]=1`

### AC-069-005: 연속 쌍 2개 → 버킷 "2"
**Given** 6개 번호가 [1,2,10,11,20,30]인 단일 회차
**When** stats 산출
**Then** 연속 쌍 개수 = 2 ((1,2),(10,11)), `consecutive_distribution["2"]["count"]=1`

### AC-069-006: 보너스 번호 제외
**Given** main numbers=[1,2,3,4,5,6], bonus=7
**When** stats 산출
**Then** 연속 쌍 개수 = 5 (보너스 7은 제외되어 (6,7)이 추가되지 않음 → 6이 아님),
`consecutive_distribution["3+"]["count"]=1`

### AC-069-007: 4 버킷 항상 존재
**Given** 임의 비어 있지 않은 draws 목록
**When** `get_consecutive_pairs_stats(draws)` 호출
**Then** `consecutive_distribution` 에 "0","1","2","3+" 4개 키가 항상 존재

### AC-069-008: avg_consecutive_pairs 정확성
**Given** 10개 회차에서 연속 쌍 개수의 총합이 6
**When** stats 산출
**Then** `avg_consecutive_pairs=0.6` (6/10)

### AC-069-009: no_consecutive_pct 정확성
**Given** 3개 회차 중 1개 회차가 연속 쌍 0개
**When** stats 산출
**Then** `no_consecutive_pct=33.33` (1/3 × 100, 2자리 반올림)

### AC-069-010: has_consecutive_pct = 100 - no_consecutive_pct
**Given** 임의 비어 있지 않은 draws 목록
**When** stats 산출
**Then** `has_consecutive_pct` + `no_consecutive_pct` ≈ 100.0 (abs=0.01)

### AC-069-011: most_common_bucket
**Given** 버킷 "1" 이 다른 모든 버킷보다 높은 count 를 가지는 draws
**When** stats 산출
**Then** `most_common_bucket="1"`

### AC-069-012: most_common_bucket 동점 처리
**Given** 둘 이상의 버킷이 동일한 (최댓값) count 를 가짐
**When** stats 산출
**Then** `_CONSECUTIVE_BUCKETS` (`["0","1","2","3+"]`) 목록에서 앞서는 버킷이
`most_common_bucket` 으로 반환됨

### AC-069-013: pct 합계
**Given** 임의 비어 있지 않은 draws 목록
**When** stats 산출
**Then** 4개 버킷 `pct` 의 합 ≈ 100.0 (abs=0.1)

### AC-069-014: count 합계 = total_draws
**Given** 임의 비어 있지 않은 draws 목록
**When** stats 산출
**Then** 4개 버킷 `count` 의 합 = `total_draws`

### AC-069-015: 캐시 히트
**Given** `get_consecutive_pairs_stats(draws)` 첫 호출 완료
**When** 동일한 `len(draws)`로 두 번째 호출
**Then** 동일한 객체(id) 반환

### AC-069-016: 캐시 미스
**Given** `get_consecutive_pairs_stats(draws_n)` 호출 완료
**When** 다른 `len(draws_n+1)`으로 호출
**Then** 새로 계산한 결과 반환

### AC-069-017: invalidate_cache
**Given** 캐시에 값이 채워진 상태
**When** `invalidate_cache()` 호출
**Then** `_consecutive_pairs_cache` 가 비워짐 (다음 호출이 새로 계산)

### AC-069-018: API 엔드포인트 — 구조 검증
**Given** TestClient 사용
**When** `GET /api/stats/consecutive-pairs`
**Then** HTTP 200, JSON에 `total_draws`, `avg_consecutive_pairs`,
`most_common_bucket`, `no_consecutive_pct`, `has_consecutive_pct`,
`consecutive_distribution` 키가 모두 존재

### AC-069-019: 페이지 엔드포인트
**Given** TestClient 사용
**When** `GET /stats/consecutive-pairs`
**Then** HTTP 200, Content-Type text/html, "연속" 텍스트 포함

### AC-069-020: 실 데이터 smoke test
**Given** 실제 DB draws 로드 (비어 있지 않음 가정)
**When** `get_consecutive_pairs_stats(real_draws)`
**Then** `total_draws > 0`, `avg_consecutive_pairs > 0`, no exception

### AC-069-021: 실 데이터 — 다수 회차가 연속 쌍 보유
**Given** 실제 DB draws 로드 (비어 있지 않음 가정)
**When** stats 산출
**Then** `has_consecutive_pct > 50` (대다수 회차가 최소 1개 이상의 연속 쌍 보유)

### AC-069-022: 비정렬·다중 연속 회차 정확성
**Given** 6개 번호가 [44,45,1,2,3,30]인 단일 회차 (입력 비정렬)
**When** stats 산출
**Then** 연속 쌍 개수 = 3 ((1,2),(2,3),(44,45); 45→1 wrap-around 미포함),
`consecutive_distribution["3+"]["count"]=1`

## 완료 정의 (Definition of Done)

- [ ] AC-069-001 ~ AC-069-022 전체 pass
- [ ] `pytest tests/test_consecutive_pairs_analysis.py` 실행 시 22개 이상 PASS
- [ ] `GET /stats/consecutive-pairs` 200 응답, HTML 정상 렌더링 ("연속" 포함)
- [ ] `GET /api/stats/consecutive-pairs` 200 응답, JSON 구조 정확
- [ ] `invalidate_cache()` 호출 시 `_consecutive_pairs_cache` 초기화 확인
- [ ] base.html 네비게이션에 "연속 쌍" 링크 추가 확인
- [ ] SPEC-043 `consecutive_pattern` / SPEC-062 `get_consecutive_pattern_stats` 코드 무변경 확인
- [ ] 기존 1598개 테스트 전체 PASS (회귀 없음)
