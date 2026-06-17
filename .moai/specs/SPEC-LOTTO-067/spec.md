---
id: SPEC-LOTTO-067
version: 0.1.0
status: Completed
created: 2026-06-11
updated: 2026-06-11
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-067: 번호 총합 분포 분석 (Number Total Sum Distribution Analysis)

## HISTORY

- 2026-06-11 (v0.1.0): 최초 작성 (Planned). 당첨번호 6개의 총합(total sum) 분포를
  회차별로 산출하고, 그 분포를 분석하는 읽기 전용 통계 기능으로 정의.
  로또 통계 분석에서 가장 기본적인 지표 중 하나로, 아직 구현되지 않은 핵심 분석.

## 개요

당첨번호 6개(보너스 제외)를 합산한 총합(total sum)의 분포를 분석한다.

total sum의 이론적 범위:
- 최솟값: 21 (1+2+3+4+5+6)
- 최댓값: 255 (40+41+42+43+44+45)
- 기댓값(E): 6 × (1+45)/2 = 138
- 표준편차(SD): ≈ 30 (비복원 추출 기준)
- 실제 분포: 100~180 구간에 약 80% 집중

본 기능은 **읽기 전용 분석 기능**이다. 추천 로직·통계 분석 로직을 변경하지 않고
`data.py`의 확장 패턴(SPEC-058·065·066)을 그대로 따른다. 결과는 메모리에 캐시하며
DB에 영속화하지 않는다.

## 요구사항 (EARS)

### 기능 요구사항

**REQ-067-F-001** [Ubiquitous]  
The system SHALL compute the total sum for each historical draw by summing all 6
main numbers, excluding the bonus number.

**REQ-067-F-002** [Event-Driven]  
WHEN the `/api/stats/total_sum` endpoint is called THEN the system SHALL return a
JSON response containing: `total_draws`, `avg_total_sum`, `min_total_sum`,
`max_total_sum`, `most_common_bucket`, `total_sum_distribution`(6 fixed buckets),
`low_count`, `mid_count`, `high_count`, `low_pct`, `mid_pct`, `high_pct`.

**REQ-067-F-003** [Event-Driven]  
WHEN the `/stats/total_sum` page is requested THEN the system SHALL render an
HTML page with summary cards and a distribution table using the same stats dict.

**REQ-067-F-004** [Ubiquitous]  
The system SHALL classify the total sum into 6 fixed buckets:
`"21-80"`, `"81-110"`, `"111-130"`, `"131-150"`, `"151-170"`, `"171-255"`.
All 6 buckets SHALL always be present in the response (zero-filled if absent).

**REQ-067-F-005** [Ubiquitous]  
The system SHALL classify total sum into 3 tiers:
- Low: total_sum < 110
- Mid: 110 ≤ total_sum ≤ 170
- High: total_sum > 170

**REQ-067-F-006** [Event-Driven]  
WHEN `invalidate_cache()` is called THEN `_total_sum_cache` SHALL be cleared.

### 비기능 요구사항

**REQ-067-NF-001** [State-Driven]  
IF draws list is empty THEN the system SHALL return all-zero stats with empty
distribution (all 6 buckets present with count 0) without raising an exception.

**REQ-067-NF-002** [Unwanted]  
The system SHALL NOT include the bonus number in total sum computation.

**REQ-067-NF-003** [Unwanted]  
The system SHALL NOT modify `analyzer.py`, `models.py`, or `recommender.py`.

**REQ-067-NF-004** [Ubiquitous]  
Numeric fields SHALL be rounded to 2 decimal places (avg_total_sum,
low_pct, mid_pct, high_pct).

## 구현 범위

### 변경 파일

| 파일 | 변경 내용 | 델타 |
|------|-----------|------|
| `lotto/web/data.py` | `get_total_sum_stats()`, `_total_sum_cache`, `invalidate_cache()` 추가 | NEW |
| `lotto/web/routes/pages.py` | `/stats/total_sum` 페이지 핸들러 추가 | NEW |
| `lotto/web/routes/api.py` | `/api/stats/total_sum` API 핸들러 추가 | NEW |
| `lotto/web/templates/total_sum.html` | 통계 페이지 템플릿 생성 | NEW |
| `lotto/web/templates/base.html` | 네비게이션 링크 추가 | MODIFY |
| `tests/test_total_sum_analysis.py` | 테스트 파일 생성 (20+ 케이스) | NEW |

### 불변 파일

`lotto/analyzer.py`, `lotto/models.py`, `lotto/recommender.py`, `lotto/simulator.py`

## 비목표 (Non-Goals)

- 추천 엔진 연동 (total_sum 기반 가중치·필터 추가 금지)
- 번호별 기여도 세부 분석
- DB 영속화
- 총합 예측 모델

## 전제조건

- Python 3.9+ 환경
- SPEC-058, SPEC-065, SPEC-066 패턴이 `data.py`에 존재함
- total sum 계산에 `draw.numbers()` (6개 메인 번호) 사용
