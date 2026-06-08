---
id: SPEC-LOTTO-051
version: 0.1.0
status: draft
created: 2026-06-05
updated: 2026-06-05
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-051 인수 기준

## Given-When-Then 시나리오

### AC-01: 추천 페이지에 합의도 배지 표시 (정상 케이스)

- **Given**: 통계 데이터(`stats.json`)가 존재하고 추천 결과가 생성됨.
- **When**: 사용자가 `GET /recommend?count=5`로 추천 페이지를 연다.
- **Then**: 페이지가 HTTP 200으로 렌더되고, 추천된 각 번호 옆에 해당 번호의
  전략 합의도(`N/11`)가 표시된다.
- 연관: REQ-CONS-003, REQ-CONS-004

### AC-02: API 응답에 consensus 필드 포함

- **Given**: 통계 데이터가 존재함.
- **When**: 클라이언트가 `GET /api/recommendations?count=5`를 호출한다.
- **Then**: JSON 응답의 각 추천 객체에 `consensus` 필드가 포함되며, 해당 추천의
  각 번호를 0~11 범위의 합의도 카운트에 매핑한다.
- 연관: REQ-CONS-005

### AC-03: 임계값(4개 이상) 도달 시 주의 배지

- **Given**: 특정 추천 번호가 11개 전략 중 4개 이상에 포함됨.
- **When**: 추천 페이지가 해당 번호를 렌더한다.
- **Then**: 그 번호에 주의 배지/하이라이트가 표시된다. 합의도 3 이하인 번호에는
  주의 배지가 표시되지 않는다(카운트만 표시).
- 연관: REQ-CONS-006

### AC-04: 성능 — 합의도 계산 포함 페이지 로드

- **Given**: 통계 데이터가 존재함.
- **When**: 추천 페이지가 합의도 계산(11개 전략 스캔)을 수행하며 로드된다.
- **Then**: 페이지 로드가 타임아웃 없이 정상 완료된다. 합의도 스캔은 요청당
  1회만 수행되어 추천 카드 수와 무관하게 11회 전략 호출을 넘지 않는다.
- 연관: REQ-CONS-011

### AC-05: 계층 경계 — recommender만 사용

- **Given**: `get_cross_strategy_consensus(recommender, target_numbers)` 호출.
- **When**: 함수가 합의도를 계산한다.
- **Then**: 함수는 `recommender.recommend_by_strategy(label)`만 호출하며 raw
  draws나 `_strategy_scores`/`_pick_set`에 접근하지 않는다.
- 연관: REQ-CONS-002, REQ-CONS-008, REQ-CONS-009

## 데이터 계층 단위 기준 — get_cross_strategy_consensus

- AC-06: 반환 매핑은 `target_numbers`에 포함된 모든 번호를 키로 가지며 각 값은
  0~11 범위 정수다. (REQ-CONS-001)
- AC-07: 11개 전략 각각에 대해 `recommend_by_strategy`가 정확히 1회 호출된다
  (총 11회). (REQ-CONS-002)
- AC-08: 동일 번호가 여러 전략에 등장하면 등장한 전략 수만큼 정확히 카운트된다.
  (REQ-CONS-001)
- AC-09: `target_numbers`에 없는 번호는 반환 매핑에 포함되지 않는다.
  (REQ-CONS-001)

## 빈 데이터 / 엣지 기준

- AC-10: 추천이 None(통계 부재)이면 페이지는 합의도 계산을 건너뛰고 HTTP 200으로
  렌더되며 합의도 패널이 없다. (REQ-CONS-007)
- AC-11: `target_numbers`가 빈 리스트면 빈 매핑(`{}`)을 반환한다. (REQ-CONS-001)

## 제약 준수 기준

- AC-12: `Recommendation` 데이터클래스가 수정/확장되지 않는다. (REQ-CONS-010)
- AC-13: `recommender.py` 코어 로직(`STRATEGY_LABELS`, `_strategy_scores`,
  `_pick_set`)이 변경되지 않는다. (Exclusions 1)
- AC-14: 신규 JavaScript 추가 없이 서버사이드 렌더링으로 배지가 표시된다.
  (Exclusions 4)

## 품질 기준

- AC-Q1: `~/.local/bin/pytest` 전체 스위트 통과(기존 1174 + 신규 테스트).
- AC-Q2: `get_cross_strategy_consensus` 커버리지 90%+.
- AC-Q3: mypy 통과, ruff clean, 신규 외부 의존성 없음.
- AC-Q4: 함수/변수명 영어, docstring/주석 한국어.
