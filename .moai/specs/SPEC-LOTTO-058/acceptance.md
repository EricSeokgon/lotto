---
id: SPEC-LOTTO-058
version: 0.1.0
status: Planned
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
---

# SPEC-LOTTO-058 인수 기준

## 픽스처 (예시)

다음 4개 회차를 기준 픽스처로 사용한다 (본번호만, 보너스 제외).
소수: {2,3,5,7,11,13,17,19,23,29,31,37,41,43}, 합성수: 그 외 1보다 큰 수,
1은 어느 쪽도 아님.

- D1: [2, 3, 5, 7, 11, 13]    → 6개 모두 소수.      prime=6, comp=0, one=0
- D2: [1, 4, 6, 8, 9, 10]     → 1 + 합성수 5개.     prime=0, comp=5, one=1
- D3: [1, 2, 4, 6, 8, 9]      → 1 + 소수 1(2) + 합성수 4(4,6,8,9). prime=1, comp=4, one=1
- D4: [4, 6, 8, 9, 10, 12]    → 6개 모두 합성수.    prime=0, comp=6, one=0

prime_count 모음 (4개): [6, 0, 1, 0]
composite_count 모음 (4개): [0, 5, 4, 6]
one_count 모음 (4개): [0, 1, 1, 0]

각 회차에서 prime + comp + one == 6 임을 확인:
D1 6+0+0=6, D2 0+5+1=6, D3 1+4+1=6, D4 0+6+0=6.

## 분류 — 단일 번호

- PR-01: 소수 판정 — 2,3,5,7,11,13,17,19,23,29,31,37,41,43은 prime로 분류된다.
  (REQ-PR-002)
- PR-02: 합성수 판정 — 4,6,8,9,10,12,...,44,45(소수가 아닌 1 초과 정수)는
  composite로 분류된다. (REQ-PR-002)
- PR-03: 숫자 1은 prime도 composite도 아닌 one으로 분류된다. (REQ-PR-002)
- PR-04: 임의 회차에서 prime_count + composite_count + one_count == 6.
  (REQ-PR-002)

## 데이터 계층 — get_prime_stats

- PR-05: 픽스처에서 total_draws == 4. (REQ-PR-001)
- PR-06: avg_prime == 1.75 — (6 + 0 + 1 + 0) / 4 = 1.75. (REQ-PR-003)
- PR-07: avg_composite == 3.75 — (0 + 5 + 4 + 6) / 4 = 3.75. (REQ-PR-003)
- PR-08: prime_distribution은 정확히 키 0..6 모두 존재. 픽스처 기준
  {0:2, 1:1, 6:1}이고 나머지 키(2,3,4,5)는 모두 0. (REQ-PR-004)
- PR-09: prime_distribution 값의 합 == total_draws == 4. (REQ-PR-004)
- PR-10: prime_distribution_pct는 키 0..6 모두 존재하며 각 값 ==
  count/4*100 (2 decimals). 픽스처 기준 {0:50.0, 1:25.0, 6:25.0}, 나머지 0.0.
  (REQ-PR-005)
- PR-11: most_common_prime_count == 0 — 픽스처는 prime_count 0이 2회로 최다.
  (REQ-PR-006)
- PR-12: composite_distribution은 키 0..6 모두 존재. 픽스처 기준
  {0:1, 4:1, 5:1, 6:1}이고 나머지 키(1,2,3)는 모두 0. 값의 합 == 4.
  (REQ-PR-007)
- PR-13: one_appeared_count == 2 — 숫자 1을 포함한 회차는 D2, D3.
  (REQ-PR-008)
- PR-14: one_appeared_pct == 50.0 — 2/4*100. (REQ-PR-008)
- PR-15: 빈 리스트 → total_draws=0, avg_prime=0, avg_composite=0,
  prime_distribution 키 0..6 모두 0, prime_distribution_pct 키 0..6 모두 0,
  most_common_prime_count=0, composite_distribution 키 0..6 모두 0,
  one_appeared_count=0, one_appeared_pct=0. (REQ-PR-013)
- PR-16: 보너스 번호는 분류에서 제외 — 회차에 bonus가 있어도 본번호 6개만
  사용. (REQ-PR-011)
- PR-17: 숫자 1이 회차에 있어도 one_count는 1을 초과하지 않는다(본번호는
  중복 없음). (REQ-PR-012)
- PR-18: 본번호가 6개 미만인 회차는 집계에서 제외되고 예외를 던지지 않는다.
  (REQ-PR-015)
- PR-19: 입력 draws 리스트는 변경되지 않으며 코어 모듈 호출/수정 없음.
  (REQ-PR-014)
- PR-20: 결정적 — 동일 입력 시 동일 출력. (REQ-PR-001)

## API 계층

- PR-21: GET /api/stats/prime → 200 + 키 9개(total_draws, avg_prime,
  avg_composite, prime_distribution, prime_distribution_pct,
  most_common_prime_count, composite_distribution, one_appeared_count,
  one_appeared_pct). (REQ-PR-009)
- PR-22: prime_distribution, prime_distribution_pct, composite_distribution은
  각각 7개 키(0..6)를 가진다. (REQ-PR-004, REQ-PR-005, REQ-PR-007)
- PR-23: 데이터 부재 시(get_draws None/빈) → 200, total_draws=0,
  most_common_prime_count=0, one_appeared_count=0. (REQ-PR-013)

## 페이지 계층

- PR-24: GET /stats/prime → 200 + text/html. (REQ-PR-010)
- PR-25: 페이지에 요약 카드(평균 소수 개수 / 평균 합성수 개수 / 1 등장 비율)와
  소수 개수 분포 표 및 합성수 개수 분포 표(값 0..6, 회차 수, 비율)가
  렌더링된다. (REQ-PR-010)
- PR-26: 데이터 부재 시 빈 상태(empty state) 메시지가 렌더링되고 200을 반환한다.
  (REQ-PR-013)
- PR-27: 페이지에 JavaScript 동적 계산 로직이 포함되지 않는다(서버 렌더링 전용).
  (비기능 요구사항)

## 품질 게이트 (Definition of Done)

- DoD-01: `tests/test_prime_analysis.py` 신규 테스트 전부 통과.
- DoD-02: 신규 테스트가 mypy.ini override 목록에 등록되고 mypy 0건 유지.
- DoD-03: Python 3.9 호환(금지 구문 없음).
- DoD-04: 기존 전체 테스트 회귀 없음(전체 스위트 통과).
- DoD-05: 기존 `lotto/*.py` 코어 모듈 무수정 확인.
