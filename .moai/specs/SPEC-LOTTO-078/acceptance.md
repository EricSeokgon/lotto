# SPEC-LOTTO-078 인수 기준 (Acceptance Criteria)

## 데이터 계층: `get_triple_run_stats`

### 빈 입력 처리
- AC-01: `get_triple_run_stats([])`는 `total_draws == 0`을 반환한다.
- AC-02: 빈 입력 시 `has_triple_pct == 0.0`, `most_common_group_count == 0`, `avg_max_run == 0.0`이다.
- AC-03: 빈 입력 시 `triple_distribution`은 "0","1","2" 3개 키를 모두 포함하고 각 count=0, pct=0.0이다.
- AC-04: `get_triple_run_stats(None)`도 예외 없이 빈 구조를 반환한다.

### 단일 회차 묶음 수 계산
- AC-05: [1,2,3,4,5,6] 회차는 묶음 수 1로 분류된다(전체 6연속).
- AC-06: [1,2,5,6,7,10] 회차는 묶음 수 1로 분류된다({5,6,7}).
- AC-07: [1,5,10,20,30,40] 회차는 묶음 수 0으로 분류된다(모두 고립).
- AC-08: [1,2,3,7,8,9] 회차는 묶음 수 2로 분류된다({1,2,3},{7,8,9}).
- AC-09: [3,4,10,20,30,40] 회차는 묶음 수 0으로 분류된다({3,4}는 2연속이므로 미포함).
- AC-10: 정확히 3개 연속(경계값)은 triple run 1개로 인정된다.

### 분포 구조
- AC-11: `triple_distribution`은 정확히 "0","1","2" 3개 키만 가진다.
- AC-12: 모든 분포 count의 합은 `total_draws`와 같다.
- AC-13: 각 분포 pct는 소수 2자리로 반올림된다.

### 집계 지표 (4-draw 픽스처: D1[1,2,3,4,5,6], D2[1,2,5,6,7,10], D3[1,5,10,20,30,40], D4[1,2,3,7,8,9])
- AC-14: 분포는 "0":count=1, "1":count=2, "2":count=1 이다.
- AC-15: "0" pct=25.0, "1" pct=50.0, "2" pct=25.0 이다.
- AC-16: `has_triple_pct == 75.0` 이다(D1,D2,D4가 >=1 묶음).
- AC-17: `most_common_group_count == 1` 이다(count=2로 최다).
- AC-18: `avg_max_run == 3.25` 이다((6+3+1+3)/4).

### 최빈값 동률 처리
- AC-19: 묶음 수 빈도가 동률일 때 더 작은 묶음 수가 `most_common_group_count`로 선택된다.

### 캐시
- AC-20: 동일 draws로 두 번 호출 시 동일 결과를 반환한다.
- AC-21: `invalidate_cache()` 호출 시 `_triple_run_cache`가 비워진다.

## API / 페이지 계층
- AC-22: `GET /api/stats/triple_run`은 200과 JSON(`triple_distribution` 포함)을 반환한다.
- AC-23: `GET /stats/triple-run`은 200과 HTML을 반환한다.

## 헬퍼 함수
- AC-24: `_count_triple_runs([1,2,3,7,8,9])`는 2를 반환한다.
- AC-25: `_max_run_length([1,2,3,4,5,6])`는 6을 반환한다.
- AC-26: `_max_run_length([1,5,10,20,30,40])`는 1을 반환한다.
- AC-27: `_count_triple_runs([3,4,10,20,30,40])`는 0을 반환한다.
