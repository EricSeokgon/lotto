---
id: SPEC-LOTTO-044
version: 0.1.0
status: completed
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-044: 번호 궁합 추천기 (Number Affinity Recommender)

## 1. 개요 (Overview)

특정 번호(1~45)에 대해, 역대 추첨에서 같은 회차에 함께 출현한 빈도가 높은
다른 번호("궁합" = co-occurrence affinity)를 분석한다. 가장 궁합이 좋은 파트너
번호들을 기반으로 추천 조합을 생성한다.

기존 번호 통계(SPEC-LOTTO-030)가 단일 번호의 출현 이력에 초점을 맞춘 것과 달리,
본 기능은 번호 간 **동반 출현 관계**에 초점을 맞춘다.

## 2. 목표 (Goals)

- 대상 번호와 가장 자주 함께 나온 파트너 번호 상위 N개를 식별한다.
- 파트너별 동반 횟수(count)와 동반율(rate)을 제공한다.
- 대상 번호 + 상위 5개 파트너로 6개 추천 조합을 생성한다.
- 데이터 부재/대상 번호 미출현 시에도 일관된 빈 구조를 반환한다.

## 3. 요구사항 (EARS Requirements)

### REQ-AFFINITY-001 (Ubiquitous)
The system SHALL provide a `number_affinity(target, draws, top_k)` function in
`lotto/web/data.py` that computes co-occurrence statistics for a given number.

### REQ-AFFINITY-002 (Event-driven)
WHEN `number_affinity` is called with a target that appears in the main 6 numbers
(bonus excluded) of one or more draws, the system SHALL count, for each OTHER
number, how many of those draws also contained that number.

### REQ-AFFINITY-003 (Ubiquitous)
The system SHALL return partners sorted by co-occurrence count descending, then by
number ascending, limited to `top_k` entries, with the target excluded from its own
partner list.

### REQ-AFFINITY-004 (Ubiquitous)
The system SHALL compute each partner's `rate` as `count / target_appearances`
rounded to 4 decimal places (0.0 when `target_appearances == 0`).

### REQ-AFFINITY-005 (Ubiquitous)
The system SHALL produce `recommended_combination` as the sorted ascending list of
`[target] + (top 5 partner numbers)`; when fewer than 5 partners exist, only the
available partners are included.

### REQ-AFFINITY-006 (Unwanted)
IF `draws` is empty/None OR the target never appeared, THEN the system SHALL return
a consistent structure with `target_appearances=0`, `partners=[]`, and
`recommended_combination=[target]`, without raising an exception.

### REQ-AFFINITY-010 (Event-driven)
WHEN a client requests `GET /api/numbers/affinity?target=<n>&top_k=<k>`, the system
SHALL return the `number_affinity` result with HTTP 200, including empty-ish data
when no draws exist.

### REQ-AFFINITY-011 (Unwanted)
IF `target` is missing or outside 1~45, OR `top_k` is outside 1~44, THEN the system
SHALL return HTTP 422.

### REQ-AFFINITY-020 (Event-driven)
WHEN a client requests `GET /numbers/affinity` without a target, the system SHALL
render the input form only (HTTP 200).

### REQ-AFFINITY-021 (Event-driven)
WHEN a client requests `GET /numbers/affinity?target=<n>`, the system SHALL render
the affinity results (partners table + recommended combination) alongside the form.

### REQ-AFFINITY-022 (Ubiquitous)
The system SHALL expose a "번호 궁합" navigation link to `/numbers/affinity` in the
global navigation (desktop list, active-label, mobile list).

## 4. 범위 외 (Out of Scope)

- 보너스 번호 동반 분석 (본번호 6개만 사용)
- 3개 이상 번호 조합의 동시 동반 분석
- 외부 의존성 추가

## 5. 결정론 (Determinism)

동일 입력에 대해 항상 동일한 출력을 보장한다 (정렬 기준 고정).
