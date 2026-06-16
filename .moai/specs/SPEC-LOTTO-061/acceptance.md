---
id: SPEC-LOTTO-061
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
priority: medium
---

# SPEC-LOTTO-061 인수 기준

## 픽스처 (예시)

다음 4개 회차를 기준 픽스처로 사용한다 (본번호만, 보너스 제외).
저번호: {1,2,...,22}(22개), 고번호: {23,24,...,45}(23개).

- D1: [1, 3, 5, 7, 9, 11]      → 6개 모두 저번호.        low=6, high=0
- D2: [23, 25, 27, 29, 31, 33] → 6개 모두 고번호.        low=0, high=6
- D3: [1, 2, 3, 40, 42, 44]    → 저{1,2,3}, 고{40,42,44}. low=3, high=3 (균형)
- D4: [1, 3, 5, 7, 40, 42]     → 저{1,3,5,7}, 고{40,42}.  low=4, high=2

low_count 모음 (4개): [6, 0, 3, 4]
high_count 모음 (4개): [0, 6, 3, 2]

각 회차에서 low + high == 6 임을 확인:
D1 6+0=6, D2 0+6=6, D3 3+3=6, D4 4+2=6.

## 분류 — 단일 번호

- HL-01: 저번호 판정 — 1,2,3,...,22 (22개)는 low로 분류된다. (REQ-HL-002)
- HL-02: 고번호 판정 — 23,24,...,45 (23개)는 high로 분류된다. (REQ-HL-002)
- HL-03: 경계값 판정 — 22는 low, 23은 high로 분류된다. (REQ-HL-002)
- HL-04: 임의 회차에서 low_count + high_count == 6 이고
  high_count == 6 - low_count. (REQ-HL-002, REQ-HL-012)

## 데이터 계층 — get_high_low_stats

- HL-05: 픽스처에서 total_draws == 4. (REQ-HL-001)
- HL-06: avg_low == 3.25 — (6 + 0 + 3 + 4) / 4 = 3.25. (REQ-HL-003)
- HL-07: avg_high == 2.75 — (0 + 6 + 3 + 2) / 4 = 2.75. (REQ-HL-003)
- HL-08: low_distribution은 정확히 키 0..6 모두 존재. 픽스처 기준
  {0:1, 3:1, 4:1, 6:1}이고 나머지 키(1,2,5)는 모두 0. (REQ-HL-004)
- HL-09: low_distribution 값의 합 == total_draws == 4. (REQ-HL-004)
- HL-10: high_distribution은 정확히 키 0..6 모두 존재. 픽스처 기준
  {0:1, 2:1, 3:1, 6:1}이고 나머지 키(1,4,5)는 모두 0. 값의 합 == 4.
  (REQ-HL-005)
- HL-11: low_distribution_pct는 키 0..6 모두 존재하며 각 값 ==
  count/4*100 (2 decimals). 픽스처 기준 {0:25.0, 3:25.0, 4:25.0, 6:25.0},
  나머지 0.0. (REQ-HL-006)
- HL-12: high_distribution_pct는 키 0..6 모두 존재하며 각 값 ==
  count/4*100 (2 decimals). 픽스처 기준 {0:25.0, 2:25.0, 3:25.0, 6:25.0},
  나머지 0.0. (REQ-HL-006)
- HL-13: most_common_low_count == 0 — 픽스처는 low_count 0,3,4,6이 각각 1회로
  동률이며 동률 시 가장 작은 값(0) 우선. (REQ-HL-007)
- HL-14: most_common_high_count == 0 — high_count 0,2,3,6이 각각 1회로 동률,
  가장 작은 값(0) 우선. (REQ-HL-007)
- HL-15: balanced_count == 1 — low==high(3:3)인 회차는 D3뿐. (REQ-HL-008)
- HL-16: balanced_pct == 25.0 — 1/4*100. (REQ-HL-008)
- HL-17: 빈 리스트 → total_draws=0, avg_low=0, avg_high=0,
  low_distribution 키 0..6 모두 0, high_distribution 키 0..6 모두 0,
  low_distribution_pct 키 0..6 모두 0, high_distribution_pct 키 0..6 모두 0,
  most_common_low_count=0, most_common_high_count=0, balanced_count=0,
  balanced_pct=0. (REQ-HL-013)
- HL-18: 보너스 번호는 분류에서 제외 — 회차에 bonus가 있어도 본번호 6개만
  사용. (REQ-HL-011)
- HL-19: 본번호가 6개 미만인 회차는 집계에서 제외되고 예외를 던지지 않는다.
  (REQ-HL-015)
- HL-20: 입력 draws 리스트는 변경되지 않으며 코어 모듈 호출/수정 없음.
  (REQ-HL-014)
- HL-21: 결정적 — 동일 입력 시 동일 출력. (REQ-HL-001)

## 추가 경계 검증 (균형 회차)

- HL-22: 모든 회차가 3:3 균형인 입력에서 balanced_count == total_draws,
  balanced_pct == 100.0. 예: [[1,2,3,23,24,25],[10,11,12,40,41,42]] →
  각 회차 low=3/high=3, balanced_count=2, balanced_pct=100.0. (REQ-HL-008)
- HL-23: 균형 회차가 전혀 없는 입력에서 balanced_count == 0,
  balanced_pct == 0.0. 예: [[1,3,5,7,9,11]] → low=6, balanced_count=0.
  (REQ-HL-008)

## API 계층

- HL-24: GET /api/stats/high-low → 200 + 키 11개(total_draws, avg_low,
  avg_high, low_distribution, high_distribution, most_common_low_count,
  most_common_high_count, balanced_count, balanced_pct, low_distribution_pct,
  high_distribution_pct). (REQ-HL-009)
- HL-25: low_distribution, high_distribution, low_distribution_pct,
  high_distribution_pct는 각각 7개 키(0..6)를 가진다.
  (REQ-HL-004, REQ-HL-005, REQ-HL-006)
- HL-26: 데이터 부재 시(get_draws None/빈) → 200, total_draws=0,
  most_common_low_count=0, balanced_count=0. (REQ-HL-013)

## 페이지 계층

- HL-27: GET /stats/high-low → 200 + text/html. (REQ-HL-010)
- HL-28: 페이지에 요약 카드(평균 저번호 개수 / 평균 고번호 개수 / 균형 회차 비율)와
  저번호 개수 분포 표(값 0..6, 회차 수, 비율)가 렌더링되고, 균형 회차(3:3) 항목이
  강조 표시된다. (REQ-HL-010)
- HL-29: 데이터 부재 시 빈 상태(empty state) 메시지가 렌더링되고 200을 반환한다.
  (REQ-HL-013)
- HL-30: 페이지에 JavaScript 동적 계산 로직이 포함되지 않는다(서버 렌더링 전용).
  (비기능 요구사항)
- HL-31: `base.html` 네비게이션(데스크톱·모바일 양쪽)에 "고저 분석"
  링크(`/stats/high-low`)가 존재한다. (비기능 요구사항)

## 품질 게이트 (Definition of Done)

- DoD-01: `tests/test_high_low_analysis.py` 신규 테스트 전부 통과(최소 20개).
- DoD-02: 신규 테스트가 mypy.ini override 목록에 등록되고 mypy 0건 유지.
- DoD-03: Python 3.9 호환(금지 구문 없음).
- DoD-04: 기존 전체 테스트 회귀 없음(전체 스위트 통과).
- DoD-05: 기존 `lotto/*.py` 코어 모듈 무수정 확인.
