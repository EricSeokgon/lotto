---
id: SPEC-LOTTO-068
version: 1.0.0
status: Completed
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-068: 번호 구간별 분포 분석 (Number Range Distribution Analysis)

## HISTORY

- 2026-06-11 (v0.1.0 → v1.0.0): 구현 완료. +29 tests (1569→1598). GET /api/stats/range_dist, GET /stats/range_dist 구현. base.html 구간별 nav 추가.
- 2026-06-11 (v0.1.0): 최초 작성 (Planned). 당첨번호 6개(보너스 제외)가
  5개 고정 숫자 구간에 어떻게 분포되는지 회차별로 산출하고 분석하는
  읽기 전용 통계 기능으로 정의. 총합(total_sum)·소수합(prime_sum)과 달리
  하나의 회차가 여러 구간에 동시에 기여한다는 구조적 차이를 가진다.

## 개요

당첨번호 6개(보너스 제외)가 다음 5개 고정 숫자 구간에 분포되는 양상을 분석한다.

| 구간 키 (range key) | 포함 번호 | 1~45 중 개수 |
|---------------------|-----------|--------------|
| `"1-9"`             | 1–9       | 9개          |
| `"10-19"`           | 10–19     | 10개         |
| `"20-29"`           | 20–29     | 10개         |
| `"30-39"`           | 30–39     | 10개         |
| `"40-45"`           | 40–45     | 6개          |

### 다른 합산 기반 통계와의 핵심 차이

총합(SPEC-067)·소수합(SPEC-066) 등은 **회차당 하나의 버킷**에만 속한다.
반면 구간별 분포는 **한 회차가 여러 구간에 동시에 기여**한다. 예를 들어
`[5, 15, 25, 35, 42, 43]` 회차는 "1-9","10-19","20-29","30-39","40-45"
5개 구간 모두에 번호를 기여한다. 따라서 응답 구조도 평면 분포(flat dict)가
아니라 구간별 통계를 담는 **중첩 딕셔너리(`range_stats`)**로 다르다.

### 구간별 산출 통계

각 구간(5개)마다 다음 5개 지표를 계산한다.

1. `total_count`: 모든 회차 전체에서 이 구간에 속한 번호의 누적 개수
2. `draw_count`: 이 구간 번호를 최소 1개 이상 포함하는 회차의 수
3. `avg_per_draw`: 회차당 이 구간 번호 평균 개수 (= total_count / total_draws, 2자리 반올림)
4. `pct_of_numbers`: 전체 추첨 번호 중 이 구간 비율 (= total_count / (total_draws × 6) × 100, 2자리 반올림)
5. `draw_pct`: 이 구간을 포함하는 회차 비율 (= draw_count / total_draws × 100, 2자리 반올림)

본 기능은 **읽기 전용 분석 기능**이다. 추천 로직·통계 분석 로직을 변경하지 않고
`data.py`의 확장 패턴(SPEC-058·065·066·067)을 그대로 따른다. 결과는 메모리에
캐시하며 DB에 영속화하지 않는다.

## 요구사항 (EARS)

### 기능 요구사항

**REQ-068-F-001** [Ubiquitous]
The system SHALL compute the range distribution for each historical draw using all 6
main numbers, excluding the bonus number, classifying each number into exactly one of
the 5 fixed ranges (`"1-9"`, `"10-19"`, `"20-29"`, `"30-39"`, `"40-45"`).

**REQ-068-F-002** [Event-Driven]
WHEN the `/api/stats/range_dist` endpoint is called THEN the system SHALL return a
JSON response containing `total_draws`, `most_covered_range`, and `range_stats` —
where `range_stats` is a nested dict keyed by the 5 range keys, each mapping to
`total_count`, `draw_count`, `avg_per_draw`, `pct_of_numbers`, `draw_pct`.

**REQ-068-F-003** [Event-Driven]
WHEN the `/stats/range_dist` page is requested THEN the system SHALL render an
HTML page whose title and heading contain the text "구간", using the same stats dict.

**REQ-068-F-004** [Ubiquitous]
The system SHALL always include all 5 range keys in `range_stats` (zero-filled when
a range is absent from the data).

**REQ-068-F-005** [Event-Driven]
WHEN `invalidate_cache()` is called THEN `_range_dist_cache` SHALL be cleared.

**REQ-068-F-006** [Ubiquitous]
The system SHALL determine `most_covered_range` as the range with the highest
`draw_count`; on a tie, the range appearing earlier in `_RANGES` SHALL win.

### 비기능 요구사항

**REQ-068-NF-001** [State-Driven]
IF the draws list is empty THEN the system SHALL return all-zero stats with all 5
ranges present (each value 0) and `most_covered_range=""` without raising an exception.

**REQ-068-NF-002** [Unwanted]
The system SHALL NOT include the bonus number in range distribution computation.

**REQ-068-NF-003** [Unwanted]
The system SHALL NOT modify `analyzer.py`, `models.py`, or `recommender.py`.

**REQ-068-NF-004** [Ubiquitous]
Numeric ratio fields SHALL be rounded to 2 decimal places
(`avg_per_draw`, `pct_of_numbers`, `draw_pct`).

## 구현 범위

### 변경 파일

| 파일 | 변경 내용 | 델타 |
|------|-----------|------|
| `lotto/web/data.py` | `get_range_dist_stats()`, `_RANGES`, `_number_range()`, `_range_dist_cache`, `invalidate_cache()` 수정 추가 | NEW |
| `lotto/web/routes/pages.py` | `/stats/range_dist` 페이지 핸들러 추가 | NEW |
| `lotto/web/routes/api.py` | `/api/stats/range_dist` API 핸들러 추가 | NEW |
| `lotto/web/templates/range_dist.html` | 통계 페이지 템플릿 생성 | NEW |
| `lotto/web/templates/base.html` | 네비게이션 링크 추가 | MODIFY |
| `tests/test_range_dist_analysis.py` | 테스트 파일 생성 (20+ 케이스) | NEW |

### 불변 파일

`lotto/analyzer.py`, `lotto/models.py`, `lotto/recommender.py`, `lotto/simulator.py`

## 비목표 (Non-Goals)

- 추천 엔진 연동 (구간 분포 기반 가중치·필터 추가 금지)
- 구간 경계의 사용자 정의(커스텀 구간) 기능
- DB 영속화
- 구간 분포 예측 모델
- 구간 간 상관관계 분석

## 전제조건

- Python 3.9+ 환경 (walrus `:=`, `zip(strict=True)`, `match-case` 사용 금지)
- SPEC-058, SPEC-065, SPEC-066, SPEC-067 패턴이 `data.py`에 존재함
- 구간 분류에 `draw.numbers()` (6개 메인 번호) 사용
