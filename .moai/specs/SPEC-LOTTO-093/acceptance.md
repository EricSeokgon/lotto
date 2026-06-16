# SPEC-LOTTO-093 인수 기준 (Acceptance Criteria)

## 빈 데이터

- AC-01: 빈 draws → total_draws=0, avg_span=0.0, most_common_combo="AA", wide_span_pct=0.0
- AC-02: None draws → 빈 구조, 6개 키 포함
- AC-03: 빈 draws → 6개 키 모두 count=0, pct=0.0, 키 순서 일치

## 구간 판정 / 조합 분류

- AC-04: [1,2,3,4,5,6] → "AA" (min=1 A, max=6 A), span=5
- AC-05: [1,10,20,30,40,45] → "AC" (min=1 A, max=45 C), span=44
- AC-06: [16,17,18,19,20,30] → "BB" (min=16 B, max=30 B), span=14
- AC-07: [16,20,25,30,35,40] → "BC" (min=16 B, max=40 C), span=24
- AC-08: [31,35,38,40,42,45] → "CC" (min=31 C, max=45 C), span=14
- AC-09: [1,5,10,15,20,25] → "AB" (min=1 A, max=25 B)

## 경계값

- AC-10: 최솟값 15→A, 16→B, 30→B, 31→C 경계 판정
- AC-11: 최댓값 15→A, 16→B, 30→B, 31→C 경계 판정

## 불가능 조합

- AC-12: min ≤ max 이므로 BA/CA/CB 조합은 절대 나타나지 않는다

## 구조 / 집계

- AC-13: first_last_zone_distribution은 정확히 6개 키
- AC-14: 모든 count 합 == total_draws
- AC-15: pct는 소수 2자리 (1/3 → 33.33)
- AC-16: 헬퍼 _first_last_zone 직접 검증 (A/B/C)

## 요약 통계

- AC-17: most_common_combo 동률 시 키 순서상 앞선 것
- AC-18: wide_span_pct = "AC" 조합 비율만
- AC-19: avg_span = (max-min) 평균, 소수 2자리

## 4-draw 픽스처

- AC-20: avg_span=21.75, most_common_combo="AA", wide_span_pct=25.0, total_draws=4
- AC-21: 분포 AA=1, AB=0, AC=1, BB=1, BC=1, CC=0
- AC-22: 분포 pct AA=25.0, AC=25.0, BB=25.0, BC=25.0

## 캐시

- AC-23: 동일 회차 수 재호출 시 캐시 결과 반환 (동일 객체)
- AC-24: invalidate_cache()가 _first_last_zone_cache를 비운다

## 라우트

- AC-25: GET /api/stats/first_last_zone → 200 + 키 구조
- AC-26: GET /api/stats/first_last_zone 데이터 없어도 200
- AC-27: GET /stats/first-last-zone → 200 (HTML)
- AC-28: GET /stats/first-last-zone 데이터 없어도 200
