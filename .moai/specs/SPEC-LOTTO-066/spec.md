---
id: SPEC-LOTTO-066
version: 0.1.0
status: Planned
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-066: 소수합 분포 분석 (Prime Sum Distribution Analysis)

## HISTORY

- 2026-06-11 (v0.1.0): 최초 작성 (Planned). 당첨번호 6개 중 소수(prime)에 해당하는
  번호들의 합계(prime sum)를 회차별로 산출하고, 그 분포를 분석하는 읽기 전용
  통계 기능으로 정의. SPEC-058(소수 개수 분포)과 보완 관계를 가짐.

## 개요

당첨번호 6개 중 소수(2·3·5·7·11·13·17·19·23·29·31·37·41·43) 번호들만 선별하여
합산한 값(prime sum)의 분포를 분석한다. SPEC-058이 회차별 소수 **개수** 분포를
다룬다면, 본 SPEC은 소수 번호들의 **합계** 분포를 다룬다.

prime sum의 이론적 범위:
- 최솟값: 0 (당첨번호 6개 중 소수 없음)
- 최댓값: 204 (소수 6개 선택: 43+41+37+31+29+23)

본 기능은 **읽기 전용 분석 기능**이다. 추천 로직·통계 분석 로직을 변경하지 않고
`data.py`의 확장 패턴(SPEC-058·065)을 그대로 따른다. 결과는 메모리에 캐시하며
DB에 영속화하지 않는다.

## 요구사항 (EARS)

### 기능 요구사항

**REQ-066-F-001** [Ubiquitous]  
The system SHALL compute the prime sum for each historical draw by summing only
the prime numbers (from `_PRIMES_1_45`) present in the 6 main numbers, excluding
the bonus number.

**REQ-066-F-002** [Event-Driven]  
WHEN the `/api/stats/prime_sum` endpoint is called THEN the system SHALL return a
JSON response containing: `total_draws`, `avg_prime_sum`, `min_prime_sum`,
`max_prime_sum`, `most_common_bucket`, `prime_sum_distribution`(6 fixed buckets),
`low_count`, `mid_count`, `high_count`, `low_pct`, `mid_pct`, `high_pct`.

**REQ-066-F-003** [Event-Driven]  
WHEN the `/stats/prime_sum` page is requested THEN the system SHALL render an
HTML page with summary cards and a distribution table using the same stats dict.

**REQ-066-F-004** [Ubiquitous]  
The system SHALL classify the prime sum into 6 fixed buckets:
`"0-30"`, `"30-60"`, `"60-90"`, `"90-120"`, `"120-150"`, `"150+"`.
All 6 buckets SHALL always be present in the response (zero-filled if absent).

**REQ-066-F-005** [Ubiquitous]  
The system SHALL classify prime sum into 3 tiers:
- Low: prime_sum < 40
- Mid: 40 ≤ prime_sum ≤ 80
- High: prime_sum > 80

**REQ-066-F-006** [Event-Driven]  
WHEN `invalidate_cache()` is called THEN `_prime_sum_cache` SHALL be cleared.

### 비기능 요구사항

**REQ-066-NF-001** [State-Driven]  
IF draws list is empty THEN the system SHALL return all-zero stats with empty
distribution (all 6 buckets present with count 0) without raising an exception.

**REQ-066-NF-002** [Unwanted]  
The system SHALL NOT include the bonus number in prime sum computation.

**REQ-066-NF-003** [Unwanted]  
The system SHALL NOT modify `analyzer.py`, `models.py`, or `recommender.py`.

**REQ-066-NF-004** [Ubiquitous]  
Numeric fields SHALL be rounded to 2 decimal places (avg_prime_sum,
low_pct, mid_pct, high_pct).

## 구현 범위

### 변경 파일

| 파일 | 변경 내용 | 델타 |
|------|-----------|------|
| `lotto/web/data.py` | `get_prime_sum_stats()`, `_prime_sum_cache`, `invalidate_cache()` 추가 | NEW |
| `lotto/web/routes/pages.py` | `/stats/prime_sum` 페이지 핸들러 추가 | NEW |
| `lotto/web/routes/api.py` | `/api/stats/prime_sum` API 핸들러 추가 | NEW |
| `lotto/web/templates/prime_sum.html` | 통계 페이지 템플릿 생성 | NEW |
| `lotto/web/templates/base.html` | 네비게이션 링크 추가 | MODIFY |
| `tests/test_prime_sum_analysis.py` | 테스트 파일 생성 (20+ 케이스) | NEW |

### 불변 파일

`lotto/analyzer.py`, `lotto/models.py`, `lotto/recommender.py`, `lotto/simulator.py`

## 비목표 (Non-Goals)

- 추천 엔진 연동 (prime_sum 기반 가중치·필터 추가 금지)
- 소수합의 번호별 기여도 세부 분석
- DB 영속화
- 소수합 예측 모델

## 전제조건

- Python 3.9+ 환경
- `_PRIMES_1_45` 상수를 `data.py` 내 기존 정의에서 재사용 가능
- SPEC-058, SPEC-065 패턴이 병합되어 `data.py`에 존재함
