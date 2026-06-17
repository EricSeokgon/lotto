---
id: SPEC-LOTTO-063
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
priority: medium
---

# SPEC-LOTTO-063 인수 기준

## 픽스처 (예시)

다음 4개 회차를 기준 픽스처로 사용한다 (본번호만, 보너스 제외). 각 회차는 본번호
6개의 끝자리(n % 10)를 모두 더해 last_digit_sum을 산출한다.

- D1: [3, 11, 18, 25, 33, 40]   → 끝자리 3,1,8,5,3,0 → 합 20 (중: 15≤20≤29)
- D2: [1, 2, 5, 6, 10, 20]      → 끝자리 1,2,5,6,0,0 → 합 14 (저: <15)
- D3: [9, 19, 29, 39, 40, 44]   → 끝자리 9,9,9,9,0,4 → 합 40 (고: ≥30)
- D4: [7, 8, 17, 18, 27, 28]    → 끝자리 7,8,7,8,7,8 → 합 45 (고: ≥30)

회차별 last_digit_sum 모음 (4개): [20, 14, 40, 45]
구간 분류: D1=중, D2=저, D3=고, D4=고

## 단일 회차 산출

- LDS-01: 끝자리 합계 산출 — D1 [3,11,18,25,33,40]의 끝자리 합은
  3+1+8+5+3+0 = 20. (REQ-LDS-002)
- LDS-02: 끝자리 0 처리 — 10,20,30,40 등 0으로 끝나는 번호는 끝자리 0을
  기여한다. D2 [1,2,5,6,10,20] → 1+2+5+6+0+0 = 14. (REQ-LDS-012)
- LDS-03: 동일 끝자리 반복 — D4 [7,8,17,18,27,28]는 7,8이 세 번씩 →
  (7+8)*3 = 45. (REQ-LDS-002)
- LDS-04: 정렬 비의존 — 입력 순서가 섞여 있어도 끝자리 합은 동일.
  예: [40,3,33,11,25,18]은 D1과 동일하게 합 20. (REQ-LDS-002)
- LDS-05: 최소 경계 — 끝자리가 모두 작은 회차 예 [1,2,3,10,20,30] →
  1+2+3+0+0+0 = 6 (저 구간). (REQ-LDS-002, REQ-LDS-007)
- LDS-06: 고 경계 — 끝자리가 큰 회차 예 [9,19,29,39,8,18] →
  9+9+9+9+8+8 = 52 (고 구간). (REQ-LDS-002, REQ-LDS-007)

## 데이터 계층 — get_last_digit_sum_stats

- LDS-07: 픽스처에서 total_draws == 4. (REQ-LDS-001)
- LDS-08: avg_sum == 29.75 — (20 + 14 + 40 + 45) / 4 = 119/4 = 29.75.
  (REQ-LDS-003)
- LDS-09: min_sum == 14 — 회차별 합 [20,14,40,45]의 최솟값. (REQ-LDS-004)
- LDS-10: max_sum == 45 — 회차별 합 [20,14,40,45]의 최댓값. (REQ-LDS-004)
- LDS-11: sum_distribution == {20:1, 14:1, 40:1, 45:1} — 출현한 합계값만 포함
  (0-채움 없음). (REQ-LDS-005)
- LDS-12: sum_distribution 값의 합 == total_draws == 4. (REQ-LDS-005)
- LDS-13: most_common_sum == 14 — 픽스처는 모든 합계값이 각 1회로 동률이므로
  더 작은 값 14를 채택. (REQ-LDS-006)
- LDS-14: low_sum_count == 1 — <15인 회차는 D2(14)뿐. (REQ-LDS-007)
- LDS-15: mid_sum_count == 1 — 15~29인 회차는 D1(20)뿐. (REQ-LDS-007)
- LDS-16: high_sum_count == 2 — ≥30인 회차는 D3(40), D4(45). (REQ-LDS-007)
- LDS-17: 구간 카운트 합 == total_draws — low+mid+high == 1+1+2 == 4.
  (REQ-LDS-007)
- LDS-18: low_sum_pct == 25.0, mid_sum_pct == 25.0, high_sum_pct == 50.0 —
  각각 1/4, 1/4, 2/4 * 100. (REQ-LDS-008)
- LDS-19: 빈 리스트 → total_draws=0, avg_sum=0, min_sum=0, max_sum=0,
  sum_distribution={}, most_common_sum=0, low_sum_count=0, mid_sum_count=0,
  high_sum_count=0, low_sum_pct=0, mid_sum_pct=0, high_sum_pct=0.
  (REQ-LDS-013)
- LDS-20: 보너스 번호는 분석에서 제외 — 회차에 bonus가 있어도 본번호 6개만
  사용. (REQ-LDS-011)
- LDS-21: 본번호가 6개 미만인 회차는 집계에서 제외되고 예외를 던지지 않는다.
  (REQ-LDS-015)
- LDS-22: 입력 draws 리스트는 변경되지 않으며 코어 모듈/SPEC-055 함수 호출·
  수정 없음. (REQ-LDS-014)
- LDS-23: 결정적 — 동일 입력 시 동일 출력. (REQ-LDS-001)

## 추가 경계 검증

- LDS-24: 구간 경계 정확성 — last_digit_sum == 15는 mid(≥15)이고 14는 low,
  29는 mid이며 30은 high. 예: 합 15 회차 [5,10,20,30,40,1]→5+0+0+0+0+1=6은
  저… (정확한 경계 픽스처는 별도 구성) 합이 정확히 15가 되는 회차
  [5,1,2,3,4,10]→5+1+2+3+4+0=15는 mid. 합이 정확히 30이 되는 회차
  [9,1,2,8,10,20]→9+1+2+8+0+0=20… 경계 검증은 합=15(mid), 합=29(mid),
  합=30(high) 회차를 직접 구성하여 확인한다. (REQ-LDS-007)
- LDS-25: 동률 최빈값(작은 값 우선) — 합계값이 동률일 때 더 작은 값을
  most_common_sum으로 채택. 예: [[1,2,3,10,20,30](합6), [4,5,6,10,20,30](합15),
  [3,2,1,10,20,30](합6), [5,4,6,10,20,30](합15)] → sum_distribution {6:2, 15:2},
  most_common_sum == 6. (REQ-LDS-006)
- LDS-26: 단일 구간 집중 — 모든 회차가 고 구간이면 high_sum_count ==
  total_draws, high_sum_pct == 100.0, low/mid 카운트 0. 예:
  [[9,19,29,39,8,18](합52), [7,8,17,18,27,28](합45)] → 두 회차 모두 ≥30.
  (REQ-LDS-007, REQ-LDS-008)
- LDS-27: 최소 합 — 끝자리가 모두 0인 6개 번호는 1~45 범위에서 불가능하나
  (0으로 끝나는 번호는 10,20,30,40 4개뿐), 가능한 최소 근접 케이스
  [10,20,30,40,1,2]→0+0+0+0+1+2=3은 저 구간. (REQ-LDS-002, REQ-LDS-007)

## API 계층

- LDS-28: GET /api/stats/last-digit-sum → 200 + 키 12개
  (total_draws, avg_sum, min_sum, max_sum, sum_distribution, most_common_sum,
  low_sum_count, mid_sum_count, high_sum_count, low_sum_pct, mid_sum_pct,
  high_sum_pct). (REQ-LDS-009)
- LDS-29: sum_distribution은 출현한 합계값만 키로 가진다(전 구간 0-채움 없음).
  (REQ-LDS-005)
- LDS-30: 데이터 부재 시(get_draws None/빈) → 200, total_draws=0,
  sum_distribution={}, most_common_sum=0, low/mid/high 카운트 0.
  (REQ-LDS-013)

## 페이지 계층

- LDS-31: GET /stats/last-digit-sum → 200 + text/html. (REQ-LDS-010)
- LDS-32: 페이지에 요약 카드(평균/최소/최대 합계, 저·중·고 구간 회차 수와
  비율)와 분포 표(최빈 상위 20개 합계값: 합계값, 회차 수, 비율)가
  렌더링된다. (REQ-LDS-010)
- LDS-33: 분포 표는 빈도 내림차순(동률 시 합계값 오름차순)으로 최대 20개
  행만 표시한다. (REQ-LDS-010)
- LDS-34: 데이터 부재 시 빈 상태(empty state) 메시지가 렌더링되고 200을
  반환한다. (REQ-LDS-013)
- LDS-35: 페이지에 JavaScript 동적 계산 로직이 포함되지 않는다(서버 렌더링
  전용). (비기능 요구사항)
- LDS-36: `base.html` 네비게이션(데스크톱·모바일 양쪽)에 "끝합 분석"
  링크(`/stats/last-digit-sum`)가 존재한다. 기존 "끝자리 분포"
  (`/stats/last-digit`, SPEC-055) 링크와 별개로 공존한다. (비기능 요구사항)

## 품질 게이트 (Definition of Done)

- DoD-01: `tests/test_last_digit_sum_analysis.py` 신규 테스트 전부
  통과(최소 20개).
- DoD-02: 신규 테스트가 mypy.ini override 목록에
  `test_last_digit_sum_analysis`로 등록되고 mypy 0건 유지.
- DoD-03: Python 3.9 호환(금지 구문 없음).
- DoD-04: 기존 전체 테스트 회귀 없음(전체 스위트 통과). 특히 SPEC-055
  관련 끝자리 분포 테스트 무변경·무회귀.
- DoD-05: 기존 `lotto/*.py` 코어 모듈 및 SPEC-055 끝자리 분포
  함수/라우트/템플릿 무수정 확인.
