# SPEC-LOTTO-084 인수 기준 (Acceptance Criteria)

## 경계/예외
- AC-01: 빈 draws → total_draws=0
- AC-02: 빈 draws → avg_transitions=0.0
- AC-03: 빈 draws → most_common_transitions=0
- AC-04: 빈 draws → high_alternation_pct=0.0
- AC-05: 빈 draws → 6개 키 전부 존재, count/pct=0
- AC-06: None 입력 → 예외 없이 빈 구조 반환

## 헬퍼 _count_parity_transitions
- AC-07: [1,2,3,4,5,6] → 5 (완전 교차 OEOEOE)
- AC-08: [1,3,5,7,9,11] → 0 (전부 홀수)
- AC-09: [2,4,6,8,10,12] → 0 (전부 짝수)
- AC-10: [1,3,5,7,9,10] → 1 (OOOOO|E)
- AC-11: [2,3,4,5,6,7] → 5 (EOEOE|O)
- AC-12: [1,2,4,6,8,10] → 1 (O|EEEEE)
- AC-13: [1,2,3,5,6,8] → 3
- AC-14: 정렬되지 않은 입력도 내부 정렬로 올바르게 집계

## 응답 구조
- AC-15: 반환 dict는 5개 최상위 키를 모두 포함
- AC-16: parity_transition_distribution은 6개 고정 키만 포함("0"~"5")
- AC-17: 각 분포 항목은 count·pct 키를 가진다
- AC-18: 모든 분포 count 합 == total_draws
- AC-19: pct는 소수 2자리로 반올림

## 파생 지표 (4회차 픽스처)
- AC-20: 분포 count — "0"=1, "1"=1, "5"=2, 나머지 0
- AC-21: 분포 pct — "0"=25.0, "1"=25.0, "5"=50.0
- AC-22: avg_transitions = 2.75
- AC-23: most_common_transitions = 5
- AC-24: high_alternation_pct = 50.0
- AC-25: most_common_transitions 동률 시 더 작은 키 선택

## 캐시
- AC-26: 동일 입력 재호출 시 동일 객체 반환(캐시 hit)
- AC-27: invalidate_cache 후 새 객체 생성
- AC-28: invalidate_cache가 _parity_trans_cache를 비운다

## 라우트
- AC-29: GET /api/stats/parity_transition → 200 + 키 구조
- AC-30: GET /api/stats/parity_transition 은 데이터 없어도 200
- AC-31: GET /stats/parity-transition → 200 (HTML)
- AC-32: GET /stats/parity-transition 은 데이터 없어도 200

## 실데이터 스모크
- AC-33: 실데이터가 있으면 total_draws>0, avg_transitions 0~5 범위
