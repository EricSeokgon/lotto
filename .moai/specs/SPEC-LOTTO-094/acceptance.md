# SPEC-LOTTO-094 인수 기준 (Acceptance Criteria)

## 헬퍼 `_count_alternations`

- AC-01: [1,3,5,7,9,11] (전부 홀수) → 0
- AC-02: [2,4,6,8,10,12] (전부 짝수) → 0
- AC-03: [1,2,3,4,5,6] → 5 (완전 교차)
- AC-04: [2,1,4,3,6,5] (정렬되지 않은 입력) → 정렬 후 [1,2,3,4,5,6] → 5
- AC-05: [1,2,3,5,7,9] → 2
- AC-06: [2,4,6,7,9,11] → 1

## 집계 `get_alternation_stats`

- AC-07: 빈 draws → total_draws=0, avg_alternation=0.0,
  most_common_level="교차0", full_alternation_pct=0.0, 6개 키 전부 0
- AC-08: None draws → AC-07 과 동일한 빈 구조
- AC-09: alternation_distribution 은 정확히 6개 키를 가진다
- AC-10: 6개 키는 "교차0","교차1","교차2","교차3","교차4","교차5" 순서이다
- AC-11: 각 키 cell 은 "count" 와 "pct" 를 가진다
- AC-12: 분포 count 합계 == total_draws
- AC-13: 모든 pct 는 소수 2자리로 반올림된다
- AC-14: avg_alternation 은 소수 2자리로 반올림된다

## 5-회차 픽스처

D1 [1,2,3,4,5,6]=교차5, D2 [1,3,5,7,9,11]=교차0,
D3 [2,4,6,8,10,12]=교차0, D4 [1,2,3,5,7,9]=교차2, D5 [2,4,6,7,9,11]=교차1

- AC-15: total_draws == 5
- AC-16: avg_alternation == 1.6  ((5+0+0+2+1)/5)
- AC-17: most_common_level == "교차0" (count=2, 동률 아님)
- AC-18: full_alternation_pct == 20.0  (교차5 1건 / 5)
- AC-19: 교차0 count=2 pct=40.0
- AC-20: 교차1 count=1 pct=20.0
- AC-21: 교차2 count=1 pct=20.0
- AC-22: 교차3 count=0 pct=0.0
- AC-23: 교차4 count=0 pct=0.0
- AC-24: 교차5 count=1 pct=20.0

## 요약 지표 의미

- AC-25: most_common_level 동률 시 키 정의 순서상 앞선("교차0" 방향) 값을 선택한다
- AC-26: full_alternation_pct 는 "교차5" 단계만의 비율이다(교차4 미포함)

## 캐시 / 무효화

- AC-27: 동일 길이 재호출 시 동일 객체(캐시)를 반환한다
- AC-28: invalidate_cache() 호출 시 _alternation_cache 가 비워진다

## API / 페이지

- AC-29: GET /api/stats/alternation → 200, JSON 에 6개 키 포함
- AC-30: GET /stats/alternation → 200, text/html
