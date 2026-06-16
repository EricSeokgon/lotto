---
id: SPEC-LOTTO-056
version: 0.1.0
status: Planned
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
---

# SPEC-LOTTO-056 인수 기준

## 픽스처 (예시)

다음 4개 회차를 기준 픽스처로 사용한다 (본번호만, 보너스 제외):

- D1: [1, 2, 3, 4, 5, 6]        → gaps [1, 1, 1, 1, 1]
- D2: [3, 12, 21, 33, 40, 45]   → gaps [9, 9, 12, 7, 5]
- D3: [5, 10, 15, 20, 25, 30]   → gaps [5, 5, 5, 5, 5]
- D4: [1, 9, 17, 25, 33, 41]    → gaps [8, 8, 8, 8, 8]

전체 간격 모음 (20개):
[1,1,1,1,1, 9,9,12,7,5, 5,5,5,5,5, 8,8,8,8,8]

## 데이터 계층 — get_gap_stats

- AC-01: 픽스처에서 total_draws=4. (REQ-GAP-001)
- AC-02: avg_gap == 5.55 — 전체 20개 간격 합 111 / 20 = 5.55. (REQ-GAP-002)
- AC-03: gap_size_distribution 정확 카운트 — small(1-5) count=11 (D1의 1×5,
  D2의 5×1, D3의 5×5), medium(6-10) count=8 (D2의 9,9,7 = 3 + D4의 8×5),
  large(11+) count=1 (D2의 12). ratio는 각각 count/20 (4 decimals):
  small 0.55, medium 0.4, large 0.05. (REQ-GAP-003)
- AC-04: 세 버킷 count 합 == 20 (전체 간격 수)이며 ratio 합 == 1.0 (부동소수 허용
  오차 내). (REQ-GAP-003)
- AC-05: most_common_gaps[0] == {gap:5, count:6} (D2 1개 + D3 5개). 동일 count
  동률 시 더 작은 gap 우선 — count=5 동률인 gap 1과 gap 8은 {gap:1}이 먼저,
  count=1 동률인 gap 7과 gap 12는 {gap:7}이 먼저. (REQ-GAP-004)
- AC-06: most_common_gaps는 최대 10개이며, 관측된 서로 다른 gap 값이 10 미만이면
  전부 반환(패딩 없음). 픽스처는 distinct gap {1,5,7,8,9,12} = 6개 → 6개 반환.
  (REQ-GAP-004, REQ-GAP-010)
- AC-07: avg_min_gap == 평균(각 회차 최소 간격) = (1+5+5+8)/4 = 4.75. (REQ-GAP-005)
- AC-08: avg_max_gap == 평균(각 회차 최대 간격) = (1+12+5+8)/4 = 6.5. (REQ-GAP-005)
- AC-09: position_avg_gaps는 5개 항목(위치 1→2 ... 5→6) 고정 순서. 위치 1→2 평균
  = (1+9+5+8)/4 = 5.75. (REQ-GAP-006)
- AC-10: position_avg_gaps 각 항목 키 == {position, label, avg_gap}. (REQ-GAP-006)
- AC-11: 빈 리스트 → total_draws=0, avg_gap=0, 세 버킷 {count:0, ratio:0},
  most_common_gaps=[], avg_min_gap=0, avg_max_gap=0, position_avg_gaps 5개 모두
  avg_gap=0. (REQ-GAP-011)
- AC-12: 보너스 번호는 간격 계산에서 제외 — 회차에 bonus가 있어도 본번호 6개만
  사용. (REQ-GAP-009)
- AC-13: 본번호가 6개 미만인 회차는 집계에서 제외되고 예외를 던지지 않는다.
  (REQ-GAP-013)
- AC-14: 입력 draws 리스트는 변경되지 않으며 코어 모듈 호출/수정 없음.
  (REQ-GAP-012)
- AC-15: 결정적 — 동일 입력 시 동일 출력. (REQ-GAP-001)

## API 계층

- AC-16: GET /api/stats/gap → 200 + 키 7개(total_draws, avg_gap,
  gap_size_distribution, most_common_gaps, avg_min_gap, avg_max_gap,
  position_avg_gaps). (REQ-GAP-007)
- AC-17: gap_size_distribution은 small/medium/large 세 키를 가지며 각각
  {count, ratio}. (REQ-GAP-003)
- AC-18: position_avg_gaps는 길이 5의 배열. (REQ-GAP-006)
- AC-19: 데이터 부재 시(get_draws None/빈) → 200, total_draws=0,
  most_common_gaps=[]. (REQ-GAP-011)

## 페이지 계층

- AC-20: GET /stats/gap → 200 + text/html. (REQ-GAP-008)
- AC-21: 페이지에 요약 카드(평균 간격/평균 최소/평균 최대), 간격 크기 분포 표,
  최빈 간격 표, 위치별 평균 간격 표가 렌더링된다. (REQ-GAP-008)
- AC-22: 데이터 부재 시 빈 상태(empty state) 메시지가 렌더링되고 200을 반환한다.
  (REQ-GAP-011)
- AC-23: 페이지에 JavaScript 동적 계산 로직이 포함되지 않는다(서버 렌더링 전용).
  (비기능 요구사항)

## 품질 게이트 (Definition of Done)

- DoD-01: `tests/test_gap_analysis.py` 신규 테스트 전부 통과.
- DoD-02: 신규 테스트가 mypy.ini override 목록에 등록되고 mypy 0건 유지.
- DoD-03: Python 3.9 호환(금지 구문 없음).
- DoD-04: 기존 1174개 테스트 회귀 없음(전체 스위트 통과).
- DoD-05: 기존 `lotto/*.py` 코어 모듈 무수정 확인.
