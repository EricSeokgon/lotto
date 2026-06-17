---
id: SPEC-LOTTO-059
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
priority: medium
---

# SPEC-LOTTO-059 인수 기준

## 픽스처 (예시)

다음 4개 회차를 기준 픽스처로 사용한다 (본번호만, 보너스 제외).
구간: "01-09"(1-9, size 9), "10-19"(10-19, size 10), "20-29"(20-29, size 10),
"30-39"(30-39, size 10), "40-45"(40-45, size 6).

- D1: [3, 5, 12, 18, 25, 33]   → 01-09:2, 10-19:2, 20-29:1, 30-39:1, 40-45:0
- D2: [1, 9, 11, 21, 41, 45]   → 01-09:2, 10-19:1, 20-29:1, 30-39:0, 40-45:2
- D3: [10, 19, 20, 29, 30, 39] → 01-09:0, 10-19:2, 20-29:2, 30-39:2, 40-45:0
- D4: [2, 4, 6, 8, 40, 42]     → 01-09:4, 10-19:0, 20-29:0, 30-39:0, 40-45:2

각 회차에서 다섯 구간 count의 합 == 6 임을 확인:
D1 2+2+1+1+0=6, D2 2+1+1+0+2=6, D3 0+2+2+2+0=6, D4 4+0+0+0+2=6.

구간별 count 모음 (4개씩):

| 구간   | size | counts        | 합 | avg_count |
|--------|------|---------------|----|-----------|
| 01-09  | 9    | [2, 2, 0, 4]  | 8  | 2.00      |
| 10-19  | 10   | [2, 1, 2, 0]  | 5  | 1.25      |
| 20-29  | 10   | [1, 1, 2, 0]  | 4  | 1.00      |
| 30-39  | 10   | [1, 0, 2, 0]  | 3  | 0.75      |
| 40-45  | 6    | [0, 2, 0, 2]  | 4  | 1.00      |

expected_avg = (size/45)*6: 01-09=1.20, 10-19=1.33, 20-29=1.33, 30-39=1.33, 40-45=0.80.
deviation = avg_count - expected_avg(미반올림 평균 기준, 2 decimals):
01-09=+0.80, 10-19=-0.08, 20-29=-0.33, 30-39=-0.58, 40-45=+0.20.

## 분류 — 단일 번호

- DC-01: 번호 1~9는 "01-09" 구간으로 분류된다. (REQ-DC-013)
- DC-02: 번호 10~19는 "10-19", 20~29는 "20-29", 30~39는 "30-39" 구간으로
  분류된다. (REQ-DC-013)
- DC-03: 번호 40~45는 "40-45" 구간으로 분류된다. (REQ-DC-013)
- DC-04: 임의 회차에서 다섯 구간 count의 합 == 6. (REQ-DC-002)
- DC-05: 구간 크기(size)는 고정 — 01-09:9, 10-19:10, 20-29:10, 30-39:10,
  40-45:6이고 합은 45. (REQ-DC-004)

## 데이터 계층 — get_decade_stats

- DC-06: 픽스처에서 total_draws == 4. (REQ-DC-001)
- DC-07: groups는 정확히 5개 항목이고, label 순서는 "01-09", "10-19",
  "20-29", "30-39", "40-45"로 고정된다. (REQ-DC-003)
- DC-08: 각 group dict는 label, size, avg_count, expected_avg, deviation,
  distribution 키를 모두 가진다. (REQ-DC-003)
- DC-09: expected_avg는 01-09=1.2, 10-19=1.33, 20-29=1.33, 30-39=1.33,
  40-45=0.8 (2 decimals). (REQ-DC-006)
- DC-10: avg_count는 01-09=2.0, 10-19=1.25, 20-29=1.0, 30-39=0.75,
  40-45=1.0 (2 decimals). (REQ-DC-005)
- DC-11: deviation은 01-09=0.8, 10-19=-0.08, 20-29=-0.33, 30-39=-0.58,
  40-45=0.2 (2 decimals). (REQ-DC-007)
- DC-12: 각 group의 distribution은 키 0..6 모두 존재. 픽스처 기준
  01-09={0:1,2:2,4:1}, 10-19={0:1,1:1,2:2}, 20-29={0:1,1:2,2:1},
  30-39={0:2,1:1,2:1}, 40-45={0:2,2:2}이고 나머지 키는 모두 0. (REQ-DC-008)
- DC-13: 각 group의 distribution 값의 합 == total_draws == 4. (REQ-DC-008)
- DC-14: most_frequent_group == "01-09" — avg_count 최댓값(2.0). (REQ-DC-009)
- DC-15: least_frequent_group == "30-39" — avg_count 최솟값(0.75). (REQ-DC-009)
- DC-16: 빈 리스트 → total_draws=0, groups 5개 모두 avg_count=0,
  deviation은 (0 - expected_avg) 2 decimals(01-09=-1.2, 10-19=-1.33,
  20-29=-1.33, 30-39=-1.33, 40-45=-0.8), distribution 키 0..6 모두 0,
  most_frequent_group="01-09", least_frequent_group="01-09". (REQ-DC-014)
- DC-17: 보너스 번호는 분류에서 제외 — 회차에 bonus가 있어도 본번호 6개만
  사용. (REQ-DC-012)
- DC-18: 본번호가 6개 미만인 회차는 집계에서 제외되고 예외를 던지지 않는다.
  (REQ-DC-016)
- DC-19: 입력 draws 리스트는 변경되지 않으며 코어 모듈 호출/수정 없음.
  (REQ-DC-015)
- DC-20: 결정적 — 동일 입력 시 동일 출력. (REQ-DC-001)
- DC-21: 동률 처리 — avg_count가 동일한 구간이 여러 개일 때 most_frequent_group
  과 least_frequent_group은 고정 순서상 더 앞선 구간 label을 선택한다.
  (예: 20-29와 40-45가 모두 1.0이면 최솟값 후보 중에서는 30-39(0.75)가
  최소이므로 무관하나, 동률 최댓값/최솟값 발생 시 앞선 label 우선) (REQ-DC-009)

## API 계층

- DC-22: GET /api/stats/decade → 200 + 키 4개(total_draws, groups,
  most_frequent_group, least_frequent_group). (REQ-DC-010)
- DC-23: groups는 5개 항목이고 각 항목의 distribution은 7개 키(0..6)를 가진다.
  (REQ-DC-003, REQ-DC-008)
- DC-24: 데이터 부재 시(get_draws None/빈) → 200, total_draws=0,
  most_frequent_group="01-09", least_frequent_group="01-09". (REQ-DC-014)

## 페이지 계층

- DC-25: GET /stats/decade → 200 + text/html. (REQ-DC-011)
- DC-26: 페이지에 구간별 표(label, size, avg_count, expected_avg, deviation)와
  구간별 count 분포 표(값 0..6, 회차 수)가 렌더링된다. (REQ-DC-011)
- DC-27: 데이터 부재 시 빈 상태(empty state) 메시지가 렌더링되고 200을 반환한다.
  (REQ-DC-014)
- DC-28: 페이지에 JavaScript 동적 계산 로직이 포함되지 않는다(서버 렌더링 전용).
  (비기능 요구사항)

## 품질 게이트 (Definition of Done)

- DoD-01: `tests/test_decade_analysis.py` 신규 테스트 전부 통과.
- DoD-02: 신규 테스트가 mypy.ini override 목록에 등록되고 mypy 0건 유지.
- DoD-03: Python 3.9 호환(금지 구문 없음).
- DoD-04: 기존 전체 테스트 회귀 없음(전체 스위트 통과, 현재 1320 → 증가).
- DoD-05: 기존 `lotto/*.py` 코어 모듈 무수정 확인.
