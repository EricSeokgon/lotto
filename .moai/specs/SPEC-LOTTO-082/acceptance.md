---
id: SPEC-LOTTO-082
title: 10단위 다양성 분포 분석 - 인수 기준
version: 0.1.0
created: 2026-06-15
---

# 인수 기준 (Acceptance Criteria)

## 헬퍼 `_decade_of`

- AC-01: `_decade_of(1)` == 1, `_decade_of(9)` == 1.
- AC-02: `_decade_of(10)` == 2, `_decade_of(19)` == 2.
- AC-03: `_decade_of(20)` == 3, `_decade_of(29)` == 3.
- AC-04: `_decade_of(30)` == 4, `_decade_of(39)` == 4.
- AC-05: `_decade_of(40)` == 5, `_decade_of(45)` == 5.

## 커버 구간 수 계산

- AC-06: [1,11,21,31,41,42] → decade_count 5.
- AC-07: [1,2,3,4,5,6] → decade_count 1.
- AC-08: [1,2,10,11,20,21] → decade_count 3.
- AC-09: [10,11,20,21,30,31] → decade_count 3.
- AC-10: [10,11,12,13,14,15] → decade_count 1.
- AC-11: [1,10,20,30,40,45] → decade_count 5.

## 빈 입력

- AC-12: 빈 입력 → total_draws 0, avg_decade_count 0.0.
- AC-13: 빈 입력 → most_common_count 1.
- AC-14: 빈 입력 → full_coverage_pct 0.0.
- AC-15: 빈 입력 → distribution 5개 키 모두 count 0, pct 0.0.

## 분포 구조 / 집계

- AC-16: distribution 키는 정확히 {"1","2","3","4","5"}.
- AC-17: distribution count 합 == total_draws.
- AC-18: 모든 pct 소수 2자리.
- AC-19: avg_decade_count 소수 2자리.
- AC-20: most_common_count 동률 시 작은 키 우선.
- AC-21: full_coverage_pct == count==5 비율.

## 손계산 4-회차 픽스처

- AC-22: avg_decade_count == 3.0.
- AC-23: most_common_count == 3.
- AC-24: full_coverage_pct == 25.0.
- AC-25: distribution["3"].count == 2, pct == 50.0.

## 캐시

- AC-26: 동일 길이 반복 호출 시 캐시된 동일 객체 재사용.
- AC-27: invalidate_cache()가 _decade_div_cache를 비운다.

## 라우트

- AC-28: GET /api/stats/decade_diversity → 200 + 키 구조.
- AC-29: GET /api/stats/decade_diversity (빈 데이터) → 200, total_draws 0.
- AC-30: GET /stats/decade-diversity → 200 HTML.
- AC-31: GET /stats/decade-diversity (빈 데이터) → 200.
