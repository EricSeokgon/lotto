---
id: SPEC-LOTTO-060
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
priority: medium
---

# SPEC-LOTTO-060 인수 기준

## 픽스처 (예시)

다음 4개 회차를 기준 픽스처로 사용한다 (본번호만, 보너스 제외).
홀수: {1,3,5,...,43,45}(23개), 짝수: {2,4,...,44}(22개).

- D1: [1, 3, 5, 7, 9, 11]   → 6개 모두 홀수.        odd=6, even=0
- D2: [2, 4, 6, 8, 10, 12]  → 6개 모두 짝수.        odd=0, even=6
- D3: [1, 2, 3, 4, 5, 6]    → 홀{1,3,5}, 짝{2,4,6}. odd=3, even=3 (균형)
- D4: [1, 3, 5, 2, 4, 7]    → 홀{1,3,5,7}, 짝{2,4}. odd=4, even=2

odd_count 모음 (4개): [6, 0, 3, 4]
even_count 모음 (4개): [0, 6, 3, 2]

각 회차에서 odd + even == 6 임을 확인:
D1 6+0=6, D2 0+6=6, D3 3+3=6, D4 4+2=6.

## 분류 — 단일 번호

- OE-01: 홀수 판정 — 1,3,5,...,43,45 (23개)는 odd로 분류된다. (REQ-OE-002)
- OE-02: 짝수 판정 — 2,4,6,...,44 (22개)는 even으로 분류된다. (REQ-OE-002)
- OE-03: 임의 회차에서 odd_count + even_count == 6 이고
  even_count == 6 - odd_count. (REQ-OE-002, REQ-OE-012)

## 데이터 계층 — get_odd_even_stats

- OE-04: 픽스처에서 total_draws == 4. (REQ-OE-001)
- OE-05: avg_odd == 3.25 — (6 + 0 + 3 + 4) / 4 = 3.25. (REQ-OE-003)
- OE-06: avg_even == 2.75 — (0 + 6 + 3 + 2) / 4 = 2.75. (REQ-OE-003)
- OE-07: odd_distribution은 정확히 키 0..6 모두 존재. 픽스처 기준
  {0:1, 3:1, 4:1, 6:1}이고 나머지 키(1,2,5)는 모두 0. (REQ-OE-004)
- OE-08: odd_distribution 값의 합 == total_draws == 4. (REQ-OE-004)
- OE-09: even_distribution은 정확히 키 0..6 모두 존재. 픽스처 기준
  {0:1, 2:1, 3:1, 6:1}이고 나머지 키(1,4,5)는 모두 0. 값의 합 == 4.
  (REQ-OE-005)
- OE-10: odd_distribution_pct는 키 0..6 모두 존재하며 각 값 ==
  count/4*100 (2 decimals). 픽스처 기준 {0:25.0, 3:25.0, 4:25.0, 6:25.0},
  나머지 0.0. (REQ-OE-006)
- OE-11: even_distribution_pct는 키 0..6 모두 존재하며 각 값 ==
  count/4*100 (2 decimals). 픽스처 기준 {0:25.0, 2:25.0, 3:25.0, 6:25.0},
  나머지 0.0. (REQ-OE-006)
- OE-12: most_common_odd_count == 0 — 픽스처는 odd_count 0,3,4,6이 각각 1회로
  동률이며 동률 시 가장 작은 값(0) 우선. (REQ-OE-007)
- OE-13: most_common_even_count == 0 — even_count 0,2,3,6이 각각 1회로 동률,
  가장 작은 값(0) 우선. (REQ-OE-007)
- OE-14: balanced_count == 1 — odd==even(3:3)인 회차는 D3뿐. (REQ-OE-008)
- OE-15: balanced_pct == 25.0 — 1/4*100. (REQ-OE-008)
- OE-16: 빈 리스트 → total_draws=0, avg_odd=0, avg_even=0,
  odd_distribution 키 0..6 모두 0, even_distribution 키 0..6 모두 0,
  odd_distribution_pct 키 0..6 모두 0, even_distribution_pct 키 0..6 모두 0,
  most_common_odd_count=0, most_common_even_count=0, balanced_count=0,
  balanced_pct=0. (REQ-OE-013)
- OE-17: 보너스 번호는 분류에서 제외 — 회차에 bonus가 있어도 본번호 6개만
  사용. (REQ-OE-011)
- OE-18: 본번호가 6개 미만인 회차는 집계에서 제외되고 예외를 던지지 않는다.
  (REQ-OE-015)
- OE-19: 입력 draws 리스트는 변경되지 않으며 코어 모듈 호출/수정 없음.
  (REQ-OE-014)
- OE-20: 결정적 — 동일 입력 시 동일 출력. (REQ-OE-001)

## 추가 경계 검증 (균형 회차)

- OE-21: 모든 회차가 3:3 균형인 입력에서 balanced_count == total_draws,
  balanced_pct == 100.0. 예: [[1,2,3,4,5,6],[7,8,9,10,11,12]] →
  각 회차 odd=3/even=3 (7,9,11 홀 + 8,10,12 짝), balanced_count=2,
  balanced_pct=100.0. (REQ-OE-008)
- OE-22: 균형 회차가 전혀 없는 입력에서 balanced_count == 0,
  balanced_pct == 0.0. 예: [[1,3,5,7,9,11]] → odd=6, balanced_count=0.
  (REQ-OE-008)

## API 계층

- OE-23: GET /api/stats/odd-even → 200 + 키 11개(total_draws, avg_odd,
  avg_even, odd_distribution, even_distribution, most_common_odd_count,
  most_common_even_count, balanced_count, balanced_pct, odd_distribution_pct,
  even_distribution_pct). (REQ-OE-009)
- OE-24: odd_distribution, even_distribution, odd_distribution_pct,
  even_distribution_pct는 각각 7개 키(0..6)를 가진다.
  (REQ-OE-004, REQ-OE-005, REQ-OE-006)
- OE-25: 데이터 부재 시(get_draws None/빈) → 200, total_draws=0,
  most_common_odd_count=0, balanced_count=0. (REQ-OE-013)

## 페이지 계층

- OE-26: GET /stats/odd-even → 200 + text/html. (REQ-OE-010)
- OE-27: 페이지에 요약 카드(평균 홀수 개수 / 평균 짝수 개수 / 균형 회차 비율)와
  홀수 개수 분포 표(값 0..6, 회차 수, 비율)가 렌더링되고, 균형 회차(3:3) 항목이
  강조 표시된다. (REQ-OE-010)
- OE-28: 데이터 부재 시 빈 상태(empty state) 메시지가 렌더링되고 200을 반환한다.
  (REQ-OE-013)
- OE-29: 페이지에 JavaScript 동적 계산 로직이 포함되지 않는다(서버 렌더링 전용).
  (비기능 요구사항)
- OE-30: `base.html` 네비게이션에 "홀짝 분석" 링크(`/stats/odd-even`)가 존재한다.
  (비기능 요구사항)

## 품질 게이트 (Definition of Done)

- DoD-01: `tests/test_odd_even_analysis.py` 신규 테스트 전부 통과(최소 20개).
- DoD-02: 신규 테스트가 mypy.ini override 목록에 등록되고 mypy 0건 유지.
- DoD-03: Python 3.9 호환(금지 구문 없음).
- DoD-04: 기존 전체 테스트 회귀 없음(전체 스위트 통과).
- DoD-05: 기존 `lotto/*.py` 코어 모듈 무수정 확인.
