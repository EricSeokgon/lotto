# SPEC-LOTTO-090 인수 기준 (Acceptance Criteria)

## 빈 데이터
- AC-01: 빈 draws → total_draws=0, avg_sum=0.0, most_common_digit="0", even_digit_pct=0.0
- AC-02: None draws → 빈 구조, 10개 키 존재
- AC-03: 빈 draws → 10개 키 모두 count=0, pct=0.0, 키 순서 "0"~"9" 일치

## 끝자리 계산 (집계 경로)
- AC-04: [1,2,3,4,5,6] → sum=21 → "1" count=1
- AC-05: [40,41,42,43,44,45] → sum=255 → "5" count=1
- AC-06: [10,20,30,1,2,3] → sum=66 → "6" count=1
- AC-07: [5,10,15,20,25,30] → sum=105 → "5" count=1
- AC-08: [1,2,3,4,5,15] → sum=30 → "0" count=1 (끝자리 0)
- AC-09: [1,2,3,4,5,14] → sum=29 → "9" count=1 (끝자리 9)

## 구조 / 집계
- AC-10: 분포는 정확히 10개 키
- AC-11: 모든 count 합 == total_draws
- AC-12: pct는 소수 2자리 (1/3 → 33.33)
- AC-13: most_common_digit 동률 시 가장 작은 키
- AC-14: even_digit_pct = ("0","2","4","6","8") count 합 / total * 100, 소수 2자리
- AC-15: avg_sum 소수 2자리

## 4-draw 픽스처
- D1 [1,2,3,4,5,6] sum=21 "1" / D2 [40,41,42,43,44,45] sum=255 "5"
- D3 [10,20,30,1,2,3] sum=66 "6" / D4 [5,10,15,20,25,30] sum=105 "5"
- AC-16: avg_sum = 447/4 = 111.75
- AC-17: most_common_digit = "5" (count=2)
- AC-18: even_digit_pct = 1/4*100 = 25.0 ("6"만 짝수 끝자리)
- AC-19: 분포 "1"=1, "5"=2, "6"=1, 나머지 0
- AC-20: 분포 pct "1"=25.0, "5"=50.0, "6"=25.0

## 캐시
- AC-21: 동일 회차 수 재호출 시 캐시 결과 반환(동일 객체)
- AC-22: invalidate_cache()가 _sum_last_digit_cache를 비운다

## 라우트
- AC-23: GET /api/stats/sum_last_digit → 200 + 키 구조
- AC-24: GET /api/stats/sum_last_digit 데이터 없어도 200 (total_draws=0)
- AC-25: GET /stats/sum-last-digit → 200 (HTML)
- AC-26: GET /stats/sum-last-digit 데이터 없어도 200
