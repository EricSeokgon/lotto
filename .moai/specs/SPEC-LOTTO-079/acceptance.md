---
id: SPEC-LOTTO-079
title: 끝자리 합계 분포 분석 — 인수 기준
version: 0.1.0
created: 2026-06-15
---

# SPEC-LOTTO-079 인수 기준 (Acceptance Criteria)

## 빈 입력 / 경계

- AC-01: 빈 draws → `total_draws == 0`.
- AC-02: 빈 draws → `avg_digit_sum == 0.0`, `high_digit_sum_pct == 0.0`.
- AC-03: 빈 draws → `most_common_range == "0-9"`.
- AC-04: None 입력도 예외 없이 빈 구조를 반환한다.
- AC-05: 빈 draws → `digit_sum_distribution`의 6개 키 모두 count=0, pct=0.0.

## 끝자리 합 / 버킷 계산

- AC-06: [1,2,3,4,5,6] → 끝자리 합 21 → 버킷 "20-24".
- AC-07: [10,20,30,40,41,42] → 끝자리 합 3 → 버킷 "0-9".
- AC-08: [5,15,25,35,6,7] → 끝자리 합 33 → 버킷 "30+".
- AC-09: [3,13,23,33,4,14] → 끝자리 합 20 → 버킷 "20-24".
- AC-10: 번호 45의 끝자리는 5 (`45 % 10 == 5`).
- AC-11: 보너스 번호는 끝자리 합 계산에 포함되지 않는다.
- AC-12: `_digit_sum_bucket` 경계값 — 9→"0-9", 10→"10-14", 14→"10-14",
  15→"15-19", 19→"15-19", 24→"20-24", 29→"25-29", 30→"30+".

## 응답 구조 / 분포

- AC-13: 반환 dict는 5개 최상위 키를 모두 포함한다.
- AC-14: `digit_sum_distribution`은 정확히 6개 키만 포함한다.
- AC-15: 각 분포 항목은 count·pct 두 키를 가진다.
- AC-16: 모든 버킷 count 합은 `total_draws`와 같다.
- AC-17: pct는 소수 2자리로 반올림된다(예: 3회차 → 33.33).

## 파생 지표 (4 회차 픽스처)

- AC-18: 분포 count — "0-9"=1, "20-24"=2, "30+"=1, 나머지 0.
- AC-19: 분포 pct — "0-9"=25.0, "20-24"=50.0, "30+"=25.0.
- AC-20: `avg_digit_sum == 19.25`.
- AC-21: `most_common_range == "20-24"`.
- AC-22: `high_digit_sum_pct == 25.0` (합>=25 인 D3 1건/4건).
- AC-23: most_common_range 동률 시 더 작은(앞선) 구간이 선택된다.

## 캐시

- AC-24: 동일 입력 재호출 시 캐시된 동일 객체를 반환한다.
- AC-25: `invalidate_cache()` 후에는 새 결과 객체를 생성한다.
- AC-26: `invalidate_cache()`가 `_digit_sum_dist_cache`를 비운다.

## 라우트

- AC-27: GET `/api/stats/digit_sum_dist` → 200 + JSON 키 구조.
- AC-28: GET `/api/stats/digit_sum_dist` 은 데이터 부재 시에도 200.
- AC-29: GET `/stats/digit-sum-dist` → 200 (HTML).
- AC-30: GET `/stats/digit-sum-dist` 은 데이터 부재 시에도 200.
