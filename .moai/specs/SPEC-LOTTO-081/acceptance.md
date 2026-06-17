# SPEC-LOTTO-081 인수 기준

## 경계/예외
- AC-01: 빈 draws → total_draws=0
- AC-02: 빈 draws → has_even_run_pct=0.0
- AC-03: 빈 draws → most_common_group_count=0
- AC-04: 빈 draws → avg_even_run_count=0.0
- AC-05: 빈 draws → 4개 키 전부 count=0, pct=0.0
- AC-06: None 입력도 동일한 zero 구조 반환

## 헬퍼 _count_even_runs
- AC-07: [2,4,6,10,20,30] → 1 (묶음 {2,4,6})
- AC-08: [2,4,10,12,20,30] → 2 (묶음 {2,4},{10,12})
- AC-09: [1,3,5,7,9,11] → 0 (짝수 없음)
- AC-10: [2,6,10,14,18,22] → 0 (간격 4, 연속 짝수 아님)
- AC-11: [2,4,6,8,10,12] → 1 (전부 연속, 1개 묶음)
- AC-12: [1,2,4,6,11,13] → 1 (묶음 {2,4,6})
- AC-13: [3,4,5,6,7,8] 짝수=[4,6,8] → 1 묶음
- AC-14: 단일 짝수 묶음(길이1)은 0

## 응답 구조/분포
- AC-15: 반환 dict는 5개 최상위 키를 모두 포함
- AC-16: even_run_distribution은 정확히 4개 키("0","1","2","3")
- AC-17: 각 분포 항목은 count·pct 두 키
- AC-18: 모든 count 합 == total_draws
- AC-19: pct는 소수 2자리로 반올림

## 파생 지표 (4-회차 픽스처: D1=1,D2=2,D3=0,D4=0)
- AC-20: 분포 "0"=2, "1"=1, "2"=1, "3"=0
- AC-21: pct "0"=50.0, "1"=25.0, "2"=25.0, "3"=0.0
- AC-22: has_even_run_pct = 50.0
- AC-23: most_common_group_count = 0
- AC-24: avg_even_run_count = 0.75
- AC-25: most_common_group_count 동률 시 작은 키 선택

## 캐시
- AC-26: 동일 입력 재호출 시 캐시된 동일 객체 반환
- AC-27: invalidate_cache 후 새 객체 생성
- AC-28: invalidate_cache가 _even_run_cache를 비움

## 라우트
- AC-29: GET /api/stats/even_run → 200 + 키 구조
- AC-30: GET /api/stats/even_run 데이터 없어도 200
- AC-31: GET /stats/even-run → 200 (HTML)
- AC-32: GET /stats/even-run 데이터 없어도 200
