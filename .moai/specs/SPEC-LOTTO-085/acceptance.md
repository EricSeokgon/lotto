# SPEC-LOTTO-085 인수 기준 (Acceptance Criteria)

## 경계/예외
- AC-01: 빈 draws → total_draws=0, 예외 없음.
- AC-02: 빈 draws → has_pair_pct=0.0.
- AC-03: 빈 draws → most_common_pair_count=0.
- AC-04: 빈 draws → avg_pair_count=0.0.
- AC-05: 빈 draws → last_digit_pair_distribution 4개 키 모두 count=0, pct=0.0.
- AC-06: None 입력도 빈 zero 구조를 반환한다.

## 헬퍼 (_count_last_digit_pairs)
- AC-07: [1,2,3,4,5,6] → 0 (모두 다른 일의 자리).
- AC-08: [1,11,21,31,41,2] → 1 (일의 자리 1이 5개).
- AC-09: [5,15,25,6,16,26] → 2 (두 그룹 각 3개).
- AC-10: [1,11,2,12,3,13] → 3 (세 그룹 각 2개).
- AC-11: [1,11,2,22,3,4] → 2 (그룹 1·2).
- AC-12: 4그룹 발생 시 min(4,3)=3 으로 상한.
- AC-13: 단일 회차 [1,11,2,3,4,5] → 1 (일의 자리 1만 2개).

## 응답 구조
- AC-14: 반환 dict는 5개 최상위 키를 모두 포함한다.
- AC-15: last_digit_pair_distribution은 항상 4개 키("0"~"3")만 포함한다.
- AC-16: 각 분포 항목은 count·pct 두 키를 가진다.
- AC-17: 모든 분포 count 합은 total_draws와 같다.
- AC-18: pct는 소수 2자리로 반올림된다.

## 파생 지표 (4회차 픽스처: D1=3, D2=0, D3=2, D4=1)
- AC-19: 분포 count — "0"=1, "1"=1, "2"=1, "3"=1.
- AC-20: 분포 pct — 각 25.0.
- AC-21: avg_pair_count = (3+0+2+1)/4 = 1.5.
- AC-22: has_pair_pct = 3/4*100 = 75.0.
- AC-23: most_common_pair_count = 0 (1:1:1:1 동률 → 가장 작은 키 0).

## 캐시
- AC-24: 동일 입력 재호출 시 캐시된 동일 객체를 반환한다.
- AC-25: invalidate_cache 후에는 새 결과 객체를 생성한다.
- AC-26: invalidate_cache가 _last_digit_pair_cache를 비운다.

## 라우트
- AC-27: GET /api/stats/last_digit_pair → 200 + 키 구조.
- AC-28: GET /api/stats/last_digit_pair 은 데이터가 없어도 200.
- AC-29: GET /stats/last-digit-pair → 200(HTML).
- AC-30: GET /stats/last-digit-pair 은 데이터가 없어도 200(빈 상태).

## 실데이터 스모크
- AC-31: 실데이터 존재 시 total_draws>0, avg_pair_count 0~3 범위.
