---
id: SPEC-LOTTO-064
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
priority: medium
---

# SPEC-LOTTO-064 인수 기준

## 픽스처 (예시)

다음 4개 회차를 기준 픽스처로 사용한다 (본번호만, 보너스 제외). 각 회차에서
min_num(6개 중 최솟값), max_num(6개 중 최댓값), range_val(max - min)을 산출한다.

- D1: [3, 11, 18, 25, 33, 40]  → min=3,  max=40, range=37 (넓음: ≥30)
- D2: [1, 2, 5, 6, 10, 20]     → min=1,  max=20, range=19 (좁음: <30)
- D3: [9, 19, 29, 39, 40, 44]  → min=9,  max=44, range=35 (넓음: ≥30)
- D4: [7, 8, 17, 18, 27, 28]   → min=7,  max=28, range=21 (좁음: <30)

회차별 모음:
- min_num: [3, 1, 9, 7]
- max_num: [40, 20, 44, 28]
- range_val: [37, 19, 35, 21]
- 범위 구간: D1=넓음, D2=좁음, D3=넓음, D4=좁음

## 단일 회차 산출

- MM-01: 최솟값 산출 — D1 [3,11,18,25,33,40]의 최솟값은 3. (REQ-MM-002)
- MM-02: 최댓값 산출 — D1의 최댓값은 40. (REQ-MM-002)
- MM-03: 범위 산출 — D1의 range_val = 40 - 3 = 37. (REQ-MM-002)
- MM-04: 정렬 비의존 — 입력 순서가 섞여 있어도 결과 동일. 예
  [40,3,33,11,25,18]은 D1과 동일하게 min=3, max=40, range=37. (REQ-MM-002)
- MM-05: range == max - min 불변식 — 임의 회차에서 range_val은 항상
  max_num - min_num과 일치한다. D3 [9,19,29,39,40,44] → 44 - 9 = 35.
  (REQ-MM-015)
- MM-06: 최소 범위 근접 — 연속 6개 [1,2,3,4,5,6] → min=1, max=6, range=5
  (좁음). (REQ-MM-002, REQ-MM-010)
- MM-07: 최대 범위 근접 — [1,2,3,4,5,45] → min=1, max=45, range=44
  (넓음). (REQ-MM-002, REQ-MM-010)

## 데이터 계층 — get_min_max_stats

- MM-08: 픽스처에서 total_draws == 4. (REQ-MM-001)
- MM-09: avg_min == 5.0 — (3 + 1 + 9 + 7) / 4 = 20/4 = 5.0. (REQ-MM-003)
- MM-10: avg_max == 33.0 — (40 + 20 + 44 + 28) / 4 = 132/4 = 33.0.
  (REQ-MM-003)
- MM-11: avg_range == 28.0 — (37 + 19 + 35 + 21) / 4 = 112/4 = 28.0.
  (REQ-MM-003)
- MM-12: min_distribution == {3:1, 1:1, 9:1, 7:1} — 출현한 최솟값만 포함
  (0-채움 없음). (REQ-MM-004)
- MM-13: max_distribution == {40:1, 20:1, 44:1, 28:1} — 출현한 최댓값만 포함.
  (REQ-MM-005)
- MM-14: range_distribution == {37:1, 19:1, 35:1, 21:1} — 출현한 범위만 포함.
  (REQ-MM-006)
- MM-15: 각 분포 값의 합 == total_draws == 4 (세 분포 모두). (REQ-MM-004,
  REQ-MM-005, REQ-MM-006)
- MM-16: most_common_min == 1 — 픽스처는 모든 최솟값이 각 1회로 동률이므로
  더 작은 값 1을 채택. (REQ-MM-007)
- MM-17: most_common_max == 20 — 동률이므로 더 작은 값 20을 채택.
  (REQ-MM-008)
- MM-18: most_common_range == 19 — 동률이므로 더 작은 값 19를 채택.
  (REQ-MM-009)
- MM-19: small_range_count == 2 — range<30인 회차는 D2(19), D4(21).
  (REQ-MM-010)
- MM-20: large_range_count == 2 — range≥30인 회차는 D1(37), D3(35).
  (REQ-MM-010)
- MM-21: 구간 카운트 합 == total_draws — small+large == 2+2 == 4.
  (REQ-MM-010)
- MM-22: small_range_pct == 50.0, large_range_pct == 50.0 — 각각 2/4 * 100.
  (REQ-MM-011)
- MM-23: 빈 리스트 → total_draws=0, avg_min=0, avg_max=0, avg_range=0,
  min_distribution={}, max_distribution={}, range_distribution={},
  most_common_min=0, most_common_max=0, most_common_range=0,
  small_range_count=0, large_range_count=0, small_range_pct=0,
  large_range_pct=0. (REQ-MM-016)
- MM-24: 보너스 번호는 분석에서 제외 — 회차에 bonus가 있어도 본번호 6개만
  사용. (REQ-MM-014)
- MM-25: 본번호가 6개 미만인 회차는 집계에서 제외되고 예외를 던지지 않는다.
  (REQ-MM-018)
- MM-26: 입력 draws 리스트는 변경되지 않으며 코어 모듈/기존 stats 함수 호출·
  수정 없음. (REQ-MM-017)
- MM-27: 결정적 — 동일 입력 시 동일 출력. (REQ-MM-001)

## 추가 경계 검증

- MM-28: 범위 구간 경계 정확성 — range_val == 29는 좁음(<30), 30은 넓음(≥30).
  경계 픽스처 직접 구성: 범위 29 회차 [1,2,3,4,5,30]→30-1=29(좁음),
  범위 30 회차 [1,2,3,4,5,31]→31-1=30(넓음). (REQ-MM-010)
- MM-29: 동률 최빈값(작은 값 우선) — 동일 최솟값이 빈도 동률일 때 더 작은
  값을 채택한다. 예: [[1,10,20,30,40,45](min1), [2,10,20,30,40,45](min2),
  [1,11,21,31,41,45](min1), [2,11,21,31,41,45](min2)] →
  min_distribution {1:2, 2:2}, most_common_min == 1. (REQ-MM-007)
- MM-30: 동일 최빈값 빈도 우세 — 한 값의 빈도가 더 높으면 그 값이 최빈값.
  예: 세 회차 min이 [5,5,9]이면 most_common_min == 5 (빈도 2 > 1).
  (REQ-MM-007)
- MM-31: 단일 구간 집중 — 모든 회차가 넓은 범위면 large_range_count ==
  total_draws, large_range_pct == 100.0, small_range_count == 0. 예:
  [[1,2,3,4,5,45](range44), [3,11,18,25,33,40](range37)] → 두 회차 모두 ≥30.
  (REQ-MM-010, REQ-MM-011)
- MM-32: 동일 회차 min/max/range 동시 검증 — [10,11,12,13,14,15] →
  min=10, max=15, range=5 (좁음). 세 분포에 각각 10/15/5가 1회씩 기록된다.
  (REQ-MM-002, REQ-MM-004, REQ-MM-005, REQ-MM-006)

## API 계층

- MM-33: GET /api/stats/min-max → 200 + 키 15개
  (total_draws, avg_min, avg_max, avg_range, min_distribution, max_distribution,
  range_distribution, most_common_min, most_common_max, most_common_range,
  small_range_count, large_range_count, small_range_pct, large_range_pct).
  (REQ-MM-012)
- MM-34: 세 분포(min/max/range_distribution)는 출현한 값만 키로 가진다(전 구간
  0-채움 없음). (REQ-MM-004, REQ-MM-005, REQ-MM-006)
- MM-35: 데이터 부재 시(get_draws None/빈) → 200, total_draws=0, 세 분포 {},
  most_common_* = 0, small/large 카운트 0. (REQ-MM-016)

## 페이지 계층

- MM-36: GET /stats/min-max → 200 + text/html. (REQ-MM-013)
- MM-37: 페이지에 요약 카드(평균 최솟값/최댓값/범위, 좁음·넓음 구간 회차 수와
  비율)와 두 개의 표(최빈 상위 15개 최솟값 표, 최빈 상위 15개 최댓값 표)가
  렌더링된다. (REQ-MM-013)
- MM-38: 각 top-15 표는 빈도 내림차순(동률 시 번호 오름차순)으로 최대 15개
  행만 표시한다. (REQ-MM-013)
- MM-39: 데이터 부재 시 빈 상태(empty state) 메시지가 렌더링되고 200을
  반환한다. (REQ-MM-016)
- MM-40: 페이지에 JavaScript 동적 계산 로직이 포함되지 않는다(서버 렌더링
  전용). (비기능 요구사항)
- MM-41: `base.html` 네비게이션(데스크톱·모바일 양쪽)에 "최대최소"
  링크(`/stats/min-max`)가 존재한다. (비기능 요구사항)

## 품질 게이트 (Definition of Done)

- DoD-01: `tests/test_min_max_analysis.py` 신규 테스트 전부 통과(최소 20개).
- DoD-02: 신규 테스트가 mypy.ini override 목록에 `test_min_max_analysis`로
  등록되고 mypy 0건 유지.
- DoD-03: Python 3.9 호환(금지 구문 없음).
- DoD-04: 기존 전체 테스트 회귀 없음(전체 스위트 통과).
- DoD-05: 기존 `lotto/*.py` 코어 모듈 및 기존 stats 함수/라우트/템플릿
  무수정 확인.
