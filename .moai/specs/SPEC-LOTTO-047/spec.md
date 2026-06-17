---
id: SPEC-LOTTO-047
version: 0.1.0
status: Planned
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-047: 번호별 당첨 주기 분석

## 1. 개요 (Overview)

번호 1~45 각각에 대해 전체 추첨 이력 기준 **평균 출현 주기(avg_cycle)** 와
**현재 간격(current_gap)** 을 산출하고, 두 값을 비교하여 각 번호를
`overdue`(지연) / `frequent`(활발) / `normal`(정상) / `never`(미출현) 상태로
분류한다. 가장 지연된 번호(most_overdue)와 상태별 요약 카운트를 함께 제공한다.

기존 `number_trend`(SPEC-LOTTO-042)의 간격/주기 개념을 재사용하되,
선택 번호 1~3개가 아닌 **전체 45개 번호를 한 번에** 분석한다는 점이 다르다.

## 2. 배경 (Background)

- 사용자는 "오랫동안 안 나온 번호"(지연)를 직관적으로 보고 싶어 한다.
- 기존 번호 통계(SPEC-LOTTO-030)는 단일 번호 상세에 집중되어,
  45개 전체를 주기 관점에서 한눈에 비교하는 화면이 없었다.
- 외부 의존성 추가 없이 기존 `DrawResult`/`_UNSET` 패턴으로 구현 가능하다.

## 3. 요구사항 (Requirements, EARS)

### REQ-CYCLE-001 (Ubiquitous)
The system shall, for all numbers 1 through 45, compute appearances,
avg_cycle, last_appeared_drwNo, current_gap, and status over the full draw
history in chronological order.

### REQ-CYCLE-002 (Ubiquitous)
The `numbers` list shall always contain exactly 45 entries sorted by number
ascending (1..45).

### REQ-CYCLE-003 (Ubiquitous)
The system shall define avg_cycle as `round(total_draws / appearances, 2)`
when appearances > 0, and 0.0 when appearances == 0.

### REQ-CYCLE-004 (Ubiquitous)
The system shall define current_gap as the number of draws after the last
appearance up to the latest draw (0 if appeared in the most recent draw;
total_draws if never appeared).

### REQ-CYCLE-005 (State-driven)
While appearances == 0, the system shall set status to `never`.
While `|current_gap - avg_cycle| <= 0.5`, the system shall set status to
`normal`. While current_gap > avg_cycle, the system shall set status to
`overdue`. Otherwise the system shall set status to `frequent`.

### REQ-CYCLE-006 (Ubiquitous)
The system shall return `most_overdue` as the top 5 overdue numbers ordered by
`(current_gap - avg_cycle)` descending (ties broken by lower number),
each as `{number, current_gap, avg_cycle}`.

### REQ-CYCLE-007 (Ubiquitous)
The system shall return `summary` as status counts
`{overdue, frequent, normal, never}` whose total equals 45.

### REQ-CYCLE-008 (Event-driven)
When draws is empty or None, the system shall return total_draws=0,
all 45 numbers as never (appearances=0, avg_cycle=0.0, last=None,
current_gap=0), most_overdue=[], and summary with never=45.

### REQ-CYCLE-009 (Ubiquitous)
The output shall be deterministic for identical input.

### REQ-CYCLE-010 (Event-driven)
When `GET /api/numbers/cycle` is requested, the system shall return 200 with
the cycle_analysis structure regardless of data availability (no query params).

### REQ-CYCLE-011 (Event-driven)
When `GET /numbers/cycle` is requested, the system shall render an HTML page
showing the 45-number table, most_overdue highlight, and summary counts, with
an empty-state message when total_draws == 0.

### REQ-CYCLE-012 (Ubiquitous)
The route `/numbers/cycle` shall be registered before `/numbers/{number}`
so that "cycle" is not captured as a numeric path parameter.

### REQ-CYCLE-013 (Ubiquitous)
The navigation menu shall include a "당첨 주기" link to `/numbers/cycle`
(desktop tabs, mobile active label, mobile dropdown).

## 4. 비범위 (Out of Scope)

- 보너스 번호는 출현 집계에서 제외한다 (본번호 6개 기준).
- 미래 회차 예측이나 확률 추정은 수행하지 않는다.
- 주기 기반 추천 조합 생성은 별도 SPEC으로 다룬다.
