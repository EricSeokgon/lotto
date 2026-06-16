# SPEC-LOTTO-095 인수 기준 (Acceptance Criteria)

## 헬퍼 `_span_bucket` (스팬 값 → 버킷 키)

- AC-01: span=5 → "10 이하" (U2)
- AC-02: span=10 → "10 이하" (경계 상한, N1)
- AC-03: span=11 → "11-20" (경계 하한, N1)
- AC-04: span=20 → "11-20" (경계 상한, N1)
- AC-05: span=21 → "21-25" (N1)
- AC-06: span=25 → "21-25" (경계 상한, N1)
- AC-07: span=26 → "26-30" (N1)
- AC-08: span=30 → "26-30" (N1)
- AC-09: span=31 → "31-35" (N1)
- AC-10: span=35 → "31-35" (N1)
- AC-11: span=36 → "36-40" (N1)
- AC-12: span=40 → "36-40" (경계 상한, N1)
- AC-13: span=41 → "41 이상" (경계 하한, N1)
- AC-14: span=44 → "41 이상" (최대값, N1)

## 스팬 계산 (max - min)

- AC-15: [1,2,3,4,5,6] → span=5 ("10 이하")
- AC-16: [1,2,3,4,5,45] → span=44 ("41 이상")
- AC-17: [3,11,22,30,38,44] → span=41 ("41 이상")
- AC-18: 정렬되지 않은 입력 [44,3,22,11,38,30] → max-min=41 (입력 순서 무관)

## 집계 `compute_span_distribution`

- AC-19: 빈 draws → total_draws=0, avg_span=0.0,
  most_common_range="10 이하", narrow_pct=0.0, wide_pct=0.0, 7개 키 전부 0 (S1)
- AC-20: None draws → AC-19 와 동일한 빈 구조 (S1)
- AC-21: span_distribution 은 정확히 7개 키를 가진다 (U1)
- AC-22: 7개 키는 "10 이하","11-20","21-25","26-30","31-35","36-40","41 이상"
  순서이다 (U1)
- AC-23: 각 키 cell 은 "count" 와 "pct" 를 가진다 (U1)
- AC-24: 분포 count 합계 == total_draws (U2)
- AC-25: 모든 pct 는 소수 2자리로 반올림된다
- AC-26: avg_span 은 소수 2자리로 반올림된다

## 단일 회차 픽스처

D1 = [1,2,3,4,5,6] (span=5)

- AC-27: total_draws == 1
- AC-28: avg_span == 5.0
- AC-29: most_common_range == "10 이하" (count=1)
- AC-30: narrow_pct == 100.0 (span ≤ 20)
- AC-31: wide_pct == 0.0
- AC-32: "10 이하" count=1 pct=100.0, 나머지 6개 키 count=0 pct=0.0

## 5-회차 픽스처

D1 [1,2,3,4,5,6]=span5("10 이하"),
D2 [1,5,10,15,18,20]=span19("11-20"),
D3 [1,8,15,20,24,24→대체]=span 사용 시 손계산 명시,
D4 [2,12,22,30,38,44]=span42("41 이상"),
D5 [1,10,20,30,37,40]=span39("36-40")

검증을 위해 손계산 가능한 5개 회차로 고정한다:
D1 [1,2,3,4,5,6] → span=5 → "10 이하"
D2 [1,5,10,15,18,20] → span=19 → "11-20"
D3 [1,8,15,20,23,26] → span=25 → "21-25"
D4 [2,12,22,30,38,44] → span=42 → "41 이상"
D5 [1,10,20,30,37,40] → span=39 → "36-40"

- AC-33: total_draws == 5
- AC-34: avg_span == 26.0  ((5+19+25+42+39)/5 = 130/5)
- AC-35: most_common_range == "10 이하" (모든 버킷 count=1 동률 → 키 정의
  순서상 앞선 "10 이하" 선택)
- AC-36: narrow_pct == 40.0  (span ≤ 20: D1,D2 = 2건 / 5)
- AC-37: wide_pct == 40.0  (span ≥ 36: D4,D5 = 2건 / 5)
- AC-38: "10 이하" count=1 pct=20.0
- AC-39: "11-20" count=1 pct=20.0
- AC-40: "21-25" count=1 pct=20.0
- AC-41: "26-30" count=0 pct=0.0
- AC-42: "31-35" count=0 pct=0.0
- AC-43: "36-40" count=1 pct=20.0
- AC-44: "41 이상" count=1 pct=20.0

## 요약 지표 의미

- AC-45: most_common_range 동률 시 키 정의 순서상 앞선("10 이하" 방향) 값을
  선택한다
- AC-46: narrow_pct 는 "10 이하" + "11-20" 버킷 합산 비율이다(span ≤ 20)
- AC-47: wide_pct 는 "36-40" + "41 이상" 버킷 합산 비율이다(span ≥ 36)

## 캐시 / 무효화

- AC-48: 동일 길이 재호출 시 동일 객체(캐시)를 반환한다 (O1)
- AC-49: invalidate_cache() 호출 시 _span_cache 가 비워진다

## API / 페이지

- AC-50: GET /api/stats/span → 200, JSON 에 7개 키 포함 (E1)
- AC-51: GET /stats/span → 200, text/html (E2)
