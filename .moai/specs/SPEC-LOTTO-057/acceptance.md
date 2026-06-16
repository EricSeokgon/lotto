---
id: SPEC-LOTTO-057
version: 0.1.0
status: Planned
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
---

# SPEC-LOTTO-057 인수 기준

## 픽스처 (예시)

다음 4개 회차를 기준 픽스처로 사용한다 (본번호만, 보너스 제외):

- D1: [1, 2, 3, 4, 5, 6]         → 등차(간격 1), unique diffs {1,2,3,4,5}, U=5,  AC=0
- D2: [2, 6, 13, 16, 32, 38]     → 모두 다른 차이, U=15, AC=10
- D3: [1, 2, 3, 4, 5, 10]        → unique diffs {1..9}, U=9,  AC=4
- D4: [3, 12, 21, 33, 40, 45]    → unique diffs 13개, U=13, AC=8

AC 값 모음 (4개): [0, 10, 4, 8]

## 알고리즘 — 단일 회차 AC 계산

- AC-01: 단일 회차 AC == (서로 다른 쌍 차이 개수 U) - 5. 본번호 6개 정렬 후
  C(6,2)=15개 차이를 만든 뒤 unique 개수에서 5를 뺀다. (REQ-AC-002)
- AC-02: [1,2,3,4,5,6]의 AC == 0 (최솟값 경계). unique diffs {1,2,3,4,5}, U=5.
  (REQ-AC-002)
- AC-03: [2,6,13,16,32,38]의 AC == 10 (최댓값 경계). 15개 차이가 모두 서로 달라
  U=15. (REQ-AC-002, REQ-AC-012)
- AC-04: [1,2,3,4,5,10]의 AC == 4. unique diffs {1,2,3,4,5,6,7,8,9}, U=9.
  (REQ-AC-002)
- AC-05: [3,12,21,33,40,45]의 AC == 8. unique diffs 13개, U=13. (REQ-AC-002)

## 데이터 계층 — get_ac_stats

- AC-06: 픽스처에서 total_draws == 4. (REQ-AC-001)
- AC-07: avg_ac == 5.5 — (0 + 10 + 4 + 8) / 4 = 5.5. (REQ-AC-003)
- AC-08: ac_distribution은 키 0..11이 아닌 정확히 0..10 모두 존재. 픽스처 기준
  {0:1, 4:1, 8:1, 10:1}이고 나머지 키는 모두 0. (REQ-AC-004)
- AC-09: ac_distribution 값의 합 == total_draws == 4. (REQ-AC-004)
- AC-10: ac_distribution_pct는 키 0..10 모두 존재하며 각 값 == count/4*100
  (2 decimals). 픽스처 기준 {0:25.0, 4:25.0, 8:25.0, 10:25.0}, 나머지 0.0.
  (REQ-AC-005)
- AC-11: most_common_ac == 0 — 픽스처는 0/4/8/10이 각 1회로 동률이며, 동률 시
  더 작은 AC 값 우선이므로 0. (REQ-AC-006)
- AC-12: high_ac_count == 2 (AC 10, 8 — 둘 다 >= 7), high_ac_pct == 50.0
  (2/4*100). (REQ-AC-007)
- AC-13: low_ac_count == 1 (AC 0만 <= 3; AC 4는 제외), low_ac_pct == 25.0
  (1/4*100). (REQ-AC-008)
- AC-14: 빈 리스트 → total_draws=0, avg_ac=0, ac_distribution 키 0..10 모두 0,
  ac_distribution_pct 키 0..10 모두 0, most_common_ac=0, high_ac_count=0,
  high_ac_pct=0, low_ac_count=0, low_ac_pct=0. (REQ-AC-013)
- AC-15: 보너스 번호는 AC 계산에서 제외 — 회차에 bonus가 있어도 본번호 6개만
  사용. (REQ-AC-011)
- AC-16: 본번호가 6개 미만인 회차는 집계에서 제외되고 예외를 던지지 않는다.
  (REQ-AC-015)
- AC-17: 입력 draws 리스트는 변경되지 않으며 코어 모듈 호출/수정 없음.
  (REQ-AC-014)
- AC-18: 결정적 — 동일 입력 시 동일 출력. (REQ-AC-001)

## API 계층

- AC-19: GET /api/stats/ac → 200 + 키 9개(total_draws, avg_ac,
  ac_distribution, ac_distribution_pct, most_common_ac, high_ac_count,
  high_ac_pct, low_ac_count, low_ac_pct). (REQ-AC-009)
- AC-20: ac_distribution과 ac_distribution_pct는 각각 11개 키(0..10)를 가진다.
  (REQ-AC-004, REQ-AC-005)
- AC-21: 데이터 부재 시(get_draws None/빈) → 200, total_draws=0,
  most_common_ac=0. (REQ-AC-013)

## 페이지 계층

- AC-22: GET /stats/ac → 200 + text/html. (REQ-AC-010)
- AC-23: 페이지에 요약 카드(평균 AC / 고AC 비율 / 저AC 비율)와 AC값 분포 표
  (AC 값, 회차 수, 비율)가 렌더링된다. (REQ-AC-010)
- AC-24: 데이터 부재 시 빈 상태(empty state) 메시지가 렌더링되고 200을 반환한다.
  (REQ-AC-013)
- AC-25: 페이지에 JavaScript 동적 계산 로직이 포함되지 않는다(서버 렌더링 전용).
  (비기능 요구사항)

## 품질 게이트 (Definition of Done)

- DoD-01: `tests/test_ac_analysis.py` 신규 테스트 전부 통과.
- DoD-02: 신규 테스트가 mypy.ini override 목록에 등록되고 mypy 0건 유지.
- DoD-03: Python 3.9 호환(금지 구문 없음).
- DoD-04: 기존 1174개 테스트 회귀 없음(전체 스위트 통과).
- DoD-05: 기존 `lotto/*.py` 코어 모듈 무수정 확인.
