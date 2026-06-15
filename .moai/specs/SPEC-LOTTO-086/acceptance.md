# SPEC-LOTTO-086 인수 기준

## 함수 동작 (get_sum_range_stats)

- AC-01: 빈 draws → total_draws=0, avg_sum=0.0, most_common_range="21-60", middle_range_pct=0.0
- AC-02: 빈 draws → 6개 키 모두 count=0, pct=0.0
- AC-03: [1,2,3,4,5,6] (sum=21) → "21-60" count=1
- AC-04: [40,41,42,43,44,45] (sum=255) → "201-255" count=1
- AC-05: [10,20,30,22,23,24] (sum=129) → "101-130" count=1
- AC-06: [15,20,25,30,35,37] (sum=162) → "161-200" count=1
- AC-07: [20,21,22,23,24,25] (sum=135) → "131-160" count=1
- AC-08: [10,11,12,13,14,15] (sum=75) → "61-100" count=1

## 버킷 경계

- AC-09: sum=60 → "21-60"
- AC-10: sum=61 → "61-100"
- AC-11: sum=100 → "61-100"
- AC-12: sum=101 → "101-130"
- AC-13: sum=130 → "101-130"
- AC-14: sum=131 → "131-160"
- AC-15: sum=160 → "131-160"
- AC-16: sum=161 → "161-200"
- AC-17: sum=200 → "161-200"
- AC-18: sum=201 → "201-255"

## 구조/집계

- AC-19: sum_range_distribution은 정확히 6개 키를 가진다
- AC-20: 모든 count의 합 == total_draws
- AC-21: pct는 소수 2자리로 반올림된다
- AC-22: most_common_range 동률 시 키 정의 순서상 앞선(=가장 작은) 구간이 이긴다
- AC-23: middle_range_pct = ("101-130" + "131-160") count 합 / total * 100
- AC-24: avg_sum은 소수 2자리로 반올림된다

## 4-draw 픽스처 (D1~D4)

- AC-25: avg_sum == 141.75, most_common_range == "21-60", middle_range_pct == 25.0
- AC-26: 분포가 21-60=1, 61-100=0, 101-130=1, 131-160=0, 161-200=1, 201-255=1

## 캐시

- AC-27: 동일 회차 수 재호출 시 캐시 결과 반환
- AC-28: invalidate_cache()가 _sum_range_cache를 비운다

## 라우트

- AC-29: GET /api/stats/sum_range → 200 JSON (키 구조 포함)
- AC-30: GET /api/stats/sum_range → 데이터 없어도 200 (total_draws=0)
- AC-31: GET /stats/sum-range-detailed → 200 HTML
- AC-32: GET /stats/sum-range-detailed → 데이터 없어도 200
