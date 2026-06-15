---
id: SPEC-LOTTO-091
title: 소수 이웃 번호 포함 분포 분석 — 인수 기준
status: Planned
version: 0.1.0
created: 2026-06-16
---

# 인수 기준 (Acceptance Criteria)

## 빈 데이터

- AC-01: 빈 draws → total_draws=0, avg_neighbor_count=0.0, most_common_count="0",
  high_neighbor_pct=0.0.
- AC-02: None draws → 빈 구조, 7개 키 포함.
- AC-03: 빈 draws → 7개 키 모두 count=0, pct=0.0, 키 순서 일치.

## 개수 계산

- AC-04: [9,15,21,25,33,35] → 전부 비이웃 → count=0 → "0".
- AC-05: [2,3,5,7,11,13] → 전부 소수(이웃) → count=6 → "6".
- AC-06: [2,3,5,9,15,21] → 2,3,5 이웃, 9,15,21 비이웃 → count=3 → "3".
- AC-07: [1,4,6,8,10,12] → 전부 이웃 → count=6 → "6".
- AC-08: [1,9,15,21,25,26] → 1만 이웃 → count=1 → "1".

## 집합 검증

- AC-09: 비이웃 번호 9,15,21,25,26,27,33,34,35,39,45 는 집합에 없다.
- AC-10: 이웃 번호 1,2,3,4,5,6,7,8 는 집합에 있다.
- AC-11: 44 는 집합에 있고 45 는 집합에 없다.

## 구조 / 집계

- AC-12: 분포는 정확히 7개 키.
- AC-13: 모든 count 합 == total_draws.
- AC-14: pct는 소수 2자리.
- AC-15: most_common_count 동률 시 가장 작은 키.
- AC-16: avg_neighbor_count는 소수 2자리.
- AC-17: high_neighbor_pct = count>=5(5,6) 회차 비율.

## 4-draw 픽스처

- AC-18: total_draws=4, avg_neighbor_count=3.75.
- AC-19: most_common_count="6", high_neighbor_pct=50.0.
- AC-20: 분포 — "0":1, "3":1, "6":2, 나머지 0.
- AC-21: 분포 pct — "0":25.0, "3":25.0, "6":50.0.

## 캐시

- AC-22: 동일 회차 수 재호출 시 캐시 결과 반환(동일 객체).
- AC-23: invalidate_cache()가 _prime_neighbor_cache를 비운다.

## 라우트

- AC-24: GET /api/stats/prime_neighbor → 200 + 키 구조.
- AC-25: GET /api/stats/prime_neighbor 은 데이터 없어도 200.
- AC-26: GET /stats/prime-neighbor → 200(HTML).
- AC-27: GET /stats/prime-neighbor 은 데이터 없어도 200.
