---
id: SPEC-LOTTO-041
version: 0.1.0
status: Planned
created: 2026-06-01
updated: 2026-06-01
author: ircp
priority: medium
---

# SPEC-LOTTO-041: 회차 구간 통계 (Draw Range Statistics)

## 개요

사용자가 회차 구간(start_drw ~ end_drw)을 지정하면, 해당 구간에 속한
추첨 회차들만을 대상으로 번호 빈도·홀짝·번호대·1등 당첨금 통계를 산출한다.
기존 `dashboard_overview`(SPEC-LOTTO-038)가 전체 이력을 대상으로 하는 것과 달리,
이 기능은 사용자 지정 구간으로 분석 범위를 좁혀 비교 분석을 가능하게 한다.

## 요구사항 (EARS)

### Ubiquitous (상시)

- REQ-RANGE-001: 시스템은 `range_stats(start_drw, end_drw, draws)` 함수를 통해
  지정 구간의 통계를 단일 진입점으로 제공해야 한다(SHALL).
- REQ-RANGE-002: `range_stats`는 `drwNo >= start_drw AND drwNo <= end_drw`를
  만족하는 회차만 집계 대상으로 포함해야 한다(SHALL).
- REQ-RANGE-003: 반환 구조는 항상 동일한 키 집합을 가져야 한다(SHALL):
  `start_drw, end_drw, total_draws, number_frequency, odd_even,
  range_distribution, avg_prize1, highest_prize1_draw, lowest_prize1_draw`.
- REQ-RANGE-004: `number_frequency`는 번호 1~45 전체를 번호 오름차순으로
  포함해야 하며, 본번호만 집계하고 보너스 번호는 제외해야 한다(SHALL).
- REQ-RANGE-005: `avg_prize1`은 구간 내 `prize1Amount`가 None이 아닌 회차들의
  정수 평균이어야 하며, 해당 회차가 없으면 None이어야 한다(SHALL).

### Event-driven (이벤트 기반)

- REQ-RANGE-006: WHEN 클라이언트가 `GET /api/stats/range?start_drw=&end_drw=`를
  호출하면, 시스템은 `range_stats` 결과를 JSON으로 HTTP 200으로 반환해야 한다(SHALL).
- REQ-RANGE-007: WHEN 클라이언트가 `GET /stats/range`를 파라미터 없이 호출하면,
  시스템은 입력 폼만 포함한 HTML을 200으로 반환해야 한다(SHALL).
- REQ-RANGE-008: WHEN 클라이언트가 `GET /stats/range?start_drw=&end_drw=`를
  유효한 파라미터로 호출하면, 시스템은 폼과 함께 통계 결과를 HTML로 반환해야 한다(SHALL).

### Unwanted (비정상 입력)

- REQ-RANGE-009: IF `start_drw > end_drw`이면, `GET /api/stats/range`는
  HTTP 422를 반환해야 한다(SHALL).
- REQ-RANGE-010: IF `start_drw` 또는 `end_drw`가 누락되면, `GET /api/stats/range`는
  HTTP 422를 반환해야 한다(SHALL).
- REQ-RANGE-011: IF 구간에 해당하는 회차가 없거나(`start_drw > end_drw` 포함)
  `draws`가 None/빈 값이면, `range_stats`는 예외를 던지지 않고(SHALL NOT)
  일관된 빈 구조(total_draws=0, 모든 빈도 0, avg_prize1=None,
  highest/lowest=None)를 반환해야 한다(SHALL).

### State-driven (상태 기반)

- REQ-RANGE-012: WHILE `prize1Amount`가 모두 None인 구간에서는,
  `avg_prize1`/`highest_prize1_draw`/`lowest_prize1_draw`가 모두 None이어야 한다(SHALL).

## 가정 (Assumptions)

- 데이터 접근은 기존 `get_draws()` 게이트웨이를 재사용한다(읽기 전용).
- `range_stats`는 `_UNSET` 센티넬 패턴을 따른다: 인자 생략 시 `get_draws()`
  자동 호출, 명시적 None 전달 시 데이터 없음으로 처리.
- highest/lowest 동률 시 낮은 drwNo가 우선한다(SPEC-LOTTO-038 `_prize_beats` 재사용).
- `avg_prize1`은 정수 내림 나눗셈(`get_prize_stats`/`dashboard_overview`와 동일 정책).
- 번호대 구간은 SPEC-LOTTO-038과 동일: 1-9 / 10-19 / 20-29 / 30-39 / 40-45.

## 제외 (Exclusions)

- 차트/시각화 세부 디자인은 본 SPEC 범위 밖(템플릿은 최소 표시만 제공).
- 구간 비교(두 구간 동시 비교)는 본 SPEC 범위 밖.
- 데이터 수집/캐시 변경 없음(읽기 전용).
- 신규 외부 의존성 추가 없음.

## 추적성 (Traceability)

| 요구사항 | 구현 | 테스트 |
|---------|------|--------|
| REQ-RANGE-001~005, 011, 012 | `lotto/web/data.py::range_stats` | `tests/test_range_stats.py` |
| REQ-RANGE-006, 009, 010 | `lotto/web/routes/api.py::api_stats_range` | `tests/test_api_range_stats.py` |
| REQ-RANGE-007, 008 | `lotto/web/routes/pages.py::stats_range_page` | `tests/test_range_stats_page.py` |
