---
id: SPEC-LOTTO-062
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
priority: medium
---

# SPEC-LOTTO-062 인수 기준

## 픽스처 (예시)

다음 4개 회차를 기준 픽스처로 사용한다 (본번호만, 보너스 제외). 각 회차는
오름차순 정렬 후 인접 차가 1인 연속 쌍 개수와 트리플(길이 3+ 런) 포함 여부를
산출한다.

- D1: [3, 11, 18, 25, 33, 40]   → 인접차 8,7,7,8,7. 연속 쌍 0개. 트리플 없음
- D2: [1, 2, 5, 6, 10, 20]      → 인접차 1,3,1,4,10. 연속 쌍 2개([1,2],[5,6]).
                                  런 길이 모두 2 → 트리플 없음
- D3: [4, 5, 6, 7, 30, 44]      → 인접차 1,1,1,23,14. 연속 쌍 3개. 런 [4,5,6,7]
                                  길이 4 → 트리플 있음
- D4: [10, 11, 12, 20, 21, 35]  → 인접차 1,1,8,1,15. 연속 쌍 3개. 런 [10,11,12]
                                  길이 3 → 트리플 있음; 런 [20,21] 길이 2

회차별 consecutive_pairs 모음 (4개): [0, 2, 3, 3]
회차별 has_triple 모음 (4개): [False, False, True, True]

## 단일 회차 산출

- CP-01: 연속 쌍 판정 — 정렬 후 인접 차가 정확히 1인 쌍만 카운트한다.
  D2 [1,2,5,6,10,20] → 2개. (REQ-CP-002)
- CP-02: 정렬 비의존 — 입력 순서가 섞여 있어도 정렬 후 동일 결과.
  예: [6,2,20,1,10,5]는 D2와 동일하게 연속 쌍 2개. (REQ-CP-002)
- CP-03: 트리플 판정 — 길이 3 이상의 연속 런이 있으면 has_triple=True.
  [4,5,6,7,30,44] → True. (REQ-CP-008)
- CP-04: 트리플 미포함 + 연속 쌍 존재 — [1,2,4,5,7,8]은 연속 쌍 3개지만 모든
  런이 길이 2이므로 has_triple=False. (연속 쌍 개수 != 트리플) (REQ-CP-008)
- CP-05: 6개 연속 [1,2,3,4,5,6] → 연속 쌍 5개, 트리플 True (런 길이 6).
  (REQ-CP-002, REQ-CP-008)
- CP-06: 경계 연속 [40,41,42,43,44,45] → 연속 쌍 5개, 트리플 True.
  (REQ-CP-002, REQ-CP-008)

## 데이터 계층 — get_consecutive_pattern_stats

- CP-07: 픽스처에서 total_draws == 4. (REQ-CP-001)
- CP-08: avg_consecutive_pairs == 2.0 — (0 + 2 + 3 + 3) / 4 = 2.0. (REQ-CP-003)
- CP-09: pair_distribution은 정확히 키 0..5 모두 존재. 픽스처 기준
  {0:1, 1:0, 2:1, 3:2, 4:0, 5:0}. (REQ-CP-004)
- CP-10: pair_distribution 값의 합 == total_draws == 4. (REQ-CP-004)
- CP-11: pair_distribution_pct는 키 0..5 모두 존재하며 각 값 ==
  count/4*100 (2 decimals). 픽스처 기준 {0:25.0, 1:0.0, 2:25.0, 3:50.0,
  4:0.0, 5:0.0}. (REQ-CP-005)
- CP-12: most_common_pair_count == 3 — 픽스처는 키 3이 2회로 최다(나머지 0,2는
  각 1회, 1·4·5는 0회). (REQ-CP-006)
- CP-13: no_consecutive_count == 1 — 연속 쌍 0개 회차는 D1뿐. (REQ-CP-007)
- CP-14: no_consecutive_pct == 25.0 — 1/4*100. (REQ-CP-007)
- CP-15: has_triple_count == 2 — 트리플 포함 회차는 D3, D4. (REQ-CP-008)
- CP-16: has_triple_pct == 50.0 — 2/4*100. (REQ-CP-008)
- CP-17: max_consecutive_count == 3 — 회차별 연속 쌍 [0,2,3,3]의 최댓값.
  (REQ-CP-009)
- CP-18: 빈 리스트 → total_draws=0, avg_consecutive_pairs=0,
  pair_distribution 키 0..5 모두 0, pair_distribution_pct 키 0..5 모두 0,
  most_common_pair_count=0, no_consecutive_count=0, no_consecutive_pct=0,
  has_triple_count=0, has_triple_pct=0, max_consecutive_count=0. (REQ-CP-014)
- CP-19: 보너스 번호는 분석에서 제외 — 회차에 bonus가 있어도 본번호 6개만
  사용. (REQ-CP-012)
- CP-20: 본번호가 6개 미만인 회차는 집계에서 제외되고 예외를 던지지 않는다.
  (REQ-CP-016)
- CP-21: 입력 draws 리스트는 변경되지 않으며 코어 모듈/SPEC-043 함수 호출·수정
  없음. (REQ-CP-015)
- CP-22: 결정적 — 동일 입력 시 동일 출력. (REQ-CP-001)
- CP-23: 트리플 회차 단위 카운트 — 한 회차에 트리플이 여러 개 있어도
  has_triple_count에는 1만 더해진다. 예: [1,2,3,10,11,12]는 트리플 2개 보유
  ([1,2,3],[10,11,12])이나 해당 회차는 has_triple_count에 1만 기여.
  (REQ-CP-013)

## 추가 경계 검증

- CP-24: 동률 최빈값(작은 값 우선) — 연속 쌍 개수가 동률일 때 더 작은 값을
  most_common_pair_count로 채택. 예:
  [[1,2,3,10,20,30](2쌍), [5,6,11,12,30,40](2쌍), [1,2,10,20,30,40](1쌍),
  [3,4,15,25,35,44](1쌍)] → pair_distribution {1:2, 2:2, 나머지 0},
  most_common_pair_count == 1. (REQ-CP-006)
- CP-25: 전 회차 연속 쌍 0개 입력 → no_consecutive_count == total_draws,
  no_consecutive_pct == 100.0, has_triple_count == 0. 예:
  [[2,5,9,14,22,40],[3,8,13,19,28,41]] → 두 회차 모두 0쌍. (REQ-CP-007, REQ-CP-008)
- CP-26: 최대치 분포 — 모든 회차가 6연속인 입력 → pair_distribution 키 5에
  모든 회차가 집계되고 max_consecutive_count == 5, has_triple_count ==
  total_draws. 예: [[1,2,3,4,5,6],[10,11,12,13,14,15]]. (REQ-CP-004, REQ-CP-009, REQ-CP-008)

## API 계층

- CP-27: GET /api/stats/consecutive-pattern → 200 + 키 10개
  (total_draws, avg_consecutive_pairs, pair_distribution,
  pair_distribution_pct, most_common_pair_count, no_consecutive_count,
  no_consecutive_pct, has_triple_count, has_triple_pct,
  max_consecutive_count). (REQ-CP-010)
- CP-28: pair_distribution, pair_distribution_pct는 각각 6개 키(0..5)를 가진다.
  (REQ-CP-004, REQ-CP-005)
- CP-29: 데이터 부재 시(get_draws None/빈) → 200, total_draws=0,
  most_common_pair_count=0, has_triple_count=0, max_consecutive_count=0.
  (REQ-CP-014)

## 페이지 계층

- CP-30: GET /stats/consecutive-pattern → 200 + text/html. (REQ-CP-011)
- CP-31: 페이지에 요약 카드(평균 연속 쌍 개수 / 연속 쌍 없는 회차 비율 /
  트리플 포함 회차 비율)와 연속 쌍 개수 분포 표(값 0..5, 회차 수, 비율)가
  렌더링된다. (REQ-CP-011)
- CP-32: 데이터 부재 시 빈 상태(empty state) 메시지가 렌더링되고 200을 반환한다.
  (REQ-CP-014)
- CP-33: 페이지에 JavaScript 동적 계산 로직이 포함되지 않는다(서버 렌더링 전용).
  (비기능 요구사항)
- CP-34: `base.html` 네비게이션(데스크톱·모바일 양쪽)에 "연속 패턴"
  링크(`/stats/consecutive-pattern`)가 존재한다. 기존 "연속 번호"
  (`/patterns/consecutive`, SPEC-043) 링크와 별개로 공존한다. (비기능 요구사항)

## 품질 게이트 (Definition of Done)

- DoD-01: `tests/test_consecutive_pattern_analysis.py` 신규 테스트 전부
  통과(최소 20개).
- DoD-02: 신규 테스트가 mypy.ini override 목록에 `test_consecutive_pattern_analysis`로
  등록되고 mypy 0건 유지.
- DoD-03: Python 3.9 호환(금지 구문 없음).
- DoD-04: 기존 전체 테스트 회귀 없음(전체 스위트 통과). 특히 SPEC-043
  관련 테스트(test_consecutive_pattern, test_api_consecutive,
  test_consecutive_page) 무변경·무회귀.
- DoD-05: 기존 `lotto/*.py` 코어 모듈 및 SPEC-043 `consecutive_pattern`
  함수/라우트/템플릿 무수정 확인.
