---
id: SPEC-LOTTO-062
version: 0.1.0
status: completed
created: 2026-06-10
updated: 2026-06-10
author: ircp
priority: medium
---

# SPEC-LOTTO-062: 연속 번호 패턴 분석 (Consecutive Number Pattern Analysis)

## 개요

각 회차의 본번호 6개(보너스 제외)를 오름차순 정렬한 뒤, 인접한 두 번호의 차가
정확히 1인 "연속 쌍(consecutive pair)"의 개수를 회차별로 집계한다. 회차당 연속
쌍 개수(0~5)의 평균·분포·비율, 연속 쌍이 없는 회차 수, 그리고 연속 3개 이상이
한 줄로 이어지는 "연속 트리플(consecutive triple)"을 하나 이상 포함한 회차 수를
서버 렌더링 테이블과 JSON API로 제공한다.

회차당 산출값:

- consecutive_pairs: 정렬된 6개 본번호에서 인접 차가 1인 쌍의 개수 (0..5)
- has_triple: 길이 3 이상의 연속 런(예: [5,6,7])을 하나라도 포함하면 참

## 배경

기존 통계 기능은 끝자리 분포(SPEC-LOTTO-055), 번호 간격(SPEC-LOTTO-056),
AC값(SPEC-LOTTO-057), 소수/합성수(SPEC-LOTTO-058), 십의 자리 구간
(SPEC-LOTTO-059), 홀짝 비율(SPEC-LOTTO-060), 고저 비율(SPEC-LOTTO-061) 등을
다룬다. 본 SPEC은 이 "통계 분석(stats)" 계열의 일관된 패턴
(`get_<topic>_stats` 함수 + `str(len(draws))` 캐시 + 3계층 라우트)을 그대로
따른다.

### SPEC-LOTTO-043과의 관계 (중요 — 혼동 방지)

코드베이스에는 이미 SPEC-LOTTO-043에서 구현한 연속 번호 분석
`consecutive_pattern(draws, recent_n=...)` (data.py)이 존재하며 라우트
`/patterns/consecutive`, 템플릿 `patterns_consecutive.html`,
네비게이션 "연속 번호"를 사용한다. 본 SPEC-LOTTO-062는 SPEC-043과 **별개**이며
함께 공존한다:

| 항목 | SPEC-043 `consecutive_pattern` | SPEC-062 `get_consecutive_pattern_stats` (본 SPEC) |
|------|-------------------------------|---------------------------------------------------|
| 집계 단위 | 런(run) 길이 분포(2~6), 연속 쌍 라벨 빈도 | 회차별 연속 쌍 개수(0~5) 분포 |
| 주요 반환 | run_length_distribution, most_common_pairs, consecutive_ratio | pair_distribution, most_common_pair_count, has_triple_count |
| recent_n 윈도 | 지원 | 미지원 (전체 회차) |
| 캐시 | 없음 | `_consecutive_cache` (`str(len(draws))`) |
| 라우트 | `/patterns/consecutive` | `/stats/consecutive-pattern` |
| 템플릿 | `patterns_consecutive.html` | `consecutive_pattern.html` |
| 네비 | "연속 번호" | "연속 패턴" |

본 SPEC은 SPEC-043 코드를 수정·병합·리팩터링하지 않는다(Exclusions 참조).
기존 `lotto/*.py` 코어 모듈도 수정하지 않고 `lotto/web/data.py`에 신규 함수만
추가한다.

## 용어 정의

- 본번호: 회차당 보너스를 제외한 6개 메인 번호
- 정렬: 본번호 6개를 오름차순 정렬
- 연속 쌍(consecutive pair): 정렬된 인접 두 번호 (n, n+1) — 차가 정확히 1인 쌍.
  6개 번호에는 최대 5개의 인접 쌍이 존재하므로 회차당 연속 쌍 개수는 0..5
- 연속 트리플(consecutive triple): 정렬된 3개 번호가 각각 1씩 차이 나는 구간
  (예: [5,6,7]). 즉 길이 3 이상의 연속 런이 존재함을 의미
- consecutive_pairs: 한 회차의 연속 쌍 개수 (0..5)
- has_triple: 한 회차가 연속 트리플(길이 3+ 런)을 하나라도 포함하면 참(회차 단위 불리언)
- no_consecutive 회차: 연속 쌍이 0개인 회차

## 요구사항 (EARS)

### Ubiquitous Requirements

- REQ-CP-001: The system SHALL provide `get_consecutive_pattern_stats(draws)`
  returning total_draws, avg_consecutive_pairs(2 decimals), pair_distribution,
  pair_distribution_pct, most_common_pair_count, no_consecutive_count,
  no_consecutive_pct(2 decimals), has_triple_count, has_triple_pct(2 decimals),
  max_consecutive_count.
- REQ-CP-002: For each draw the system SHALL sort the 6 main numbers ascending
  and count the number of adjacent sorted pairs (n, n+1) whose difference is
  exactly 1, yielding a per-draw consecutive_pairs value in the range 0..5.
- REQ-CP-003: The avg_consecutive_pairs SHALL be the mean of every draw's
  consecutive_pairs across all aggregated draws, rounded to 2 decimals.
- REQ-CP-004: The pair_distribution SHALL be a mapping from each pair count
  value 0..5 to the count of draws having exactly that many consecutive pairs,
  with every key 0..5 present (zero counts included).
- REQ-CP-005: The pair_distribution_pct SHALL be a mapping from each pair count
  value 0..5 to (count / total_draws * 100) rounded to 2 decimals, with every
  key 0..5 present (zero values included).
- REQ-CP-006: The most_common_pair_count SHALL be the pair count value 0..5
  with the highest draw count, breaking ties by the smaller pair count value
  first.
- REQ-CP-007: The no_consecutive_count SHALL be the number of draws with exactly
  0 consecutive pairs, and no_consecutive_pct SHALL be
  no_consecutive_count / total_draws * 100 rounded to 2 decimals.
- REQ-CP-008: A consecutive triple SHALL be defined as three sorted numbers each
  differing by 1 (a run of length 3 or more). The has_triple_count SHALL be the
  number of draws containing at least one consecutive triple, and has_triple_pct
  SHALL be has_triple_count / total_draws * 100 rounded to 2 decimals.
- REQ-CP-009: The max_consecutive_count SHALL be the maximum per-draw
  consecutive_pairs value observed across all aggregated draws (0 when no draws
  are aggregated).
- REQ-CP-010: The system SHALL expose `GET /api/stats/consecutive-pattern`
  returning the consecutive pattern analysis as JSON (always 200).
- REQ-CP-011: The system SHALL expose `GET /stats/consecutive-pattern`
  rendering a server-side page with summary cards (average consecutive pairs,
  no-consecutive ratio, has-triple ratio) and a pair-count distribution table
  (pair count 0..5 with draw count and percentage).

### Event-driven Requirements

- REQ-CP-012: WHEN analyzing a draw, the system SHALL use only the 6 main
  numbers and exclude the bonus number entirely.
- REQ-CP-013: WHEN counting triples, the system SHALL count each draw at most
  once toward has_triple_count regardless of how many distinct triples it
  contains (a per-draw boolean, not a count of triple occurrences).

### State-driven Requirements

- REQ-CP-014: WHILE no draw data is available, `get_consecutive_pattern_stats`
  SHALL return total_draws=0, avg_consecutive_pairs=0, pair_distribution with
  all keys 0..5 mapped to 0, pair_distribution_pct with all keys 0..5 mapped to
  0, most_common_pair_count=0, no_consecutive_count=0, no_consecutive_pct=0,
  has_triple_count=0, has_triple_pct=0, max_consecutive_count=0; both endpoints
  SHALL still return 200 and the page SHALL render an empty state.

### Unwanted Behavior Requirements

- REQ-CP-015: The data layer SHALL NOT mutate the input draws list, SHALL NOT
  modify any existing `lotto/*.py` core module, and SHALL NOT modify, merge with,
  or refactor the existing SPEC-LOTTO-043 `consecutive_pattern` function or its
  helpers.
- REQ-CP-016: IF a draw exposes fewer than 6 main numbers, THEN the system SHALL
  skip that draw from aggregation rather than raising.

### Optional Requirements

- REQ-CP-017: Where a memory cache is used, the system SHALL store the computed
  result in `_consecutive_cache: dict[str, Any]` keyed by `str(len(draws))` and
  clear it in `invalidate_cache()`, consistent with existing cache patterns in
  `data.py` (e.g. `_odd_even_cache`, `_high_low_cache`).

## 비기능 요구사항

- Python 3.9 호환 (match/case 금지, `zip(strict=...)` 금지 — 필요 시 `# noqa: B905`)
- 서버 사이드 렌더링 전용 (JavaScript 사용 금지)
- 결정적 — 동일 입력에 동일 출력
- 테스트는 `tests/test_consecutive_pattern_analysis.py`에 작성하고 최소 20개
- `mypy.ini` override 목록에 `test_consecutive_pattern_analysis` 등록
- 네비게이션: `base.html`에 "연속 패턴" → `/stats/consecutive-pattern` 링크를
  데스크톱과 모바일 네비게이션 양쪽에 추가
- 템플릿 파일명: `consecutive_pattern.html` (기존 `patterns_consecutive.html`과
  구별)

## 인수 기준

acceptance.md 참조.

## Exclusions (What NOT to Build)

- SPEC-LOTTO-043 `consecutive_pattern` 함수/라우트/템플릿/테스트의 수정·병합·
  리팩터링 (두 기능은 독립적으로 공존; 본 SPEC은 신규 함수만 추가)
- recent_n 최신 N회차 윈도잉 (본 SPEC은 전체 회차만 대상 — 윈도잉은 SPEC-043에서 제공)
- 연속 쌍 라벨별 빈도(most_common_pairs, "3-4" 같은 라벨 순위) — SPEC-043에서 다룸
- 런 길이 분포(2~6) — SPEC-043에서 다룸
- 트리플 발생 횟수(회차 내 여러 트리플 누적 카운트) — 본 SPEC은 회차 단위 불리언만
- 번호별 연속 출현 빈도 또는 특정 연속 쌍(예: 27-28) 핫/콜드 분석
- 회차 시계열에 따른 연속 패턴 추세(연도별/구간별 변화)
- 사용자 입력 조합의 연속 패턴 평가 체커
- 추천 엔진과의 자동 연동(연속 패턴 필터/가중치)
- 연속 패턴 분포 시각화 차트(막대/그래프) — 표 형태만 제공
- 연속 패턴과 다른 지표(합계, 간격, AC, 홀짝, 고저)의 상관관계 교차 분석
- JavaScript 기반 인터랙션 또는 클라이언트 측 계산
