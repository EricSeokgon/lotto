# SPEC-LOTTO-092 인수 기준

## 빈 데이터

- AC-01: `get_cluster_stats([])` → total_draws=0, avg_cluster_count=0.0,
  most_common_count="0", has_cluster_pct=0.0
- AC-02: `get_cluster_stats(None)` → 빈 구조, cluster_distribution 4개 키
- AC-03: 빈 draws → 4개 키 모두 count=0, pct=0.0, 키 순서 일치

## 군집 수 계산

- AC-04: [1,3,5,7,9,11] → 간격 전부 2, gap=1 없음 → clusters=0 → "0"
- AC-05: [1,2,3,4,5,6] → 한 묶음 → clusters=1 → "1"
- AC-06: [1,2,3,10,11,20] → (1,2,3)+(10,11) → clusters=2 → "2"
- AC-07: [1,2,10,11,20,21] → (1,2)+(10,11)+(20,21) → clusters=3 → "3"
- AC-08: [1,5,10,20,30,40] → 전부 고립 → clusters=0 → "0"
- AC-09: [1,2,10,20,30,40] → 쌍 1개 → clusters=1 → "1"
- AC-10: [1,2,10,11,20,30] → 쌍 2개 → clusters=2 → "2"
- AC-11: 단일 고립 번호는 군집으로 세지 않는다(길이 2 이상 필요)
- AC-12: cap 동작 — min(clusters, 3) 검증

## 헬퍼 직접 검증

- AC-13: `_count_clusters` 직접 호출 결과 검증

## 구조 / 집계

- AC-14: cluster_distribution은 정확히 4개 키
- AC-15: 모든 count 합 == total_draws
- AC-16: pct는 소수 2자리(1/3 → 33.33)
- AC-17: most_common_count 동률 시 가장 작은 키
- AC-18: has_cluster_pct = 군집 수 >= 1 회차 비율
- AC-19: avg_cluster_count 소수 2자리

## 4-draw 픽스처

- AC-20: total_draws=4, avg_cluster_count=1.5, most_common_count="0",
  has_cluster_pct=75.0
- AC-21: 분포 — "0":1, "1":1, "2":1, "3":1 각 pct=25.0

## 캐시

- AC-22: 동일 회차 수 재호출 시 캐시 결과(동일 객체) 반환
- AC-23: `invalidate_cache()`가 `_cluster_cache`를 비운다

## 라우트

- AC-24: GET /api/stats/cluster_count → 200 + 키 구조
- AC-25: GET /api/stats/cluster_count 데이터 없어도 200 (total_draws=0)
- AC-26: GET /stats/cluster-count → 200 (HTML)
- AC-27: GET /stats/cluster-count 데이터 없어도 200
