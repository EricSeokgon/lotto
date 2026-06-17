---
id: SPEC-LOTTO-042
version: 0.1.0
status: completed
created: 2026-06-01
updated: 2026-06-01
author: ircp
priority: medium
---

# SPEC-LOTTO-042: 번호 추이 트래커 (Number Trend Tracker)

## 1. 개요

사용자가 선택한 1~3개 번호의 최근 N회차 출현 타임라인과 간격(gap) 분석을
한눈에 보여주는 기능. 특정 번호가 "최근에 얼마나 자주/뜸하게 나왔는지"를
시각적·수치적으로 추적할 수 있게 한다.

기존 `number_stats`(SPEC-LOTTO-030)가 단일 번호의 전체 이력 요약을 제공하는 것과 달리,
본 기능은 다중 번호(최대 3개)를 최근 윈도(recent_n) 안에서 회차별 타임라인으로 비교한다.

## 2. 용어 정의

- **타임라인(timeline)**: 분석 윈도 내 각 회차에 대한 `{drwNo, date, appeared}` 항목의
  시간 오름차순(오래된 → 최신) 리스트.
- **윈도(window) / draws_analyzed**: 최근 `recent_n` 회차. 가용 회차가 부족하면 가용 전체.
- **gap(간격)**: 윈도 내 위치(0-기반 인덱스) 기준 연속 출현 사이의 거리.
- **current_gap**: 윈도의 마지막 회차 기준, 마지막 출현 이후 경과 회차 수.

## 3. 요구사항 (EARS)

### Ubiquitous (항상 적용)

- REQ-TREND-T-001: 시스템은 `number_trend(numbers, recent_n, draws)` 함수를 통해
  선택 번호별 출현 타임라인과 간격 통계를 단일 진입점으로 제공해야 한다(SHALL).
- REQ-TREND-T-002: 응답은 항상 `recent_n`, `draws_analyzed`, `numbers` 세 최상위 키를
  포함해야 한다(SHALL).
- REQ-TREND-T-003: 각 번호 항목은 `number`, `total_appearances`, `avg_gap`,
  `last_appeared_drwNo`, `current_gap`, `timeline` 키를 포함해야 한다(SHALL).

### Event-driven (WHEN)

- REQ-TREND-T-010: WHEN 유효한 1~3개 번호와 draws가 주어지면, 시스템은 각 번호에 대해
  윈도 내 회차마다 `appeared` 여부를 시간 오름차순 타임라인으로 산출해야 한다(SHALL).
- REQ-TREND-T-011: WHEN 번호가 윈도 내 2회 이상 출현하면, 시스템은 연속 출현 위치
  간격의 평균을 `avg_gap`(소수 1자리)로 산출해야 한다(SHALL).
- REQ-TREND-T-012: WHEN 번호가 윈도 최신 회차에 출현하면, 시스템은 `current_gap`을
  0으로 산출해야 한다(SHALL).
- REQ-TREND-T-013: WHEN `GET /api/numbers/trend` 요청이 유효하면(번호 1~3개, 각 1~45,
  중복 없음, recent_n 10~500), 시스템은 HTTP 200으로 `number_trend` 결과를
  반환해야 한다(SHALL).

### State-driven (WHILE / IF)

- REQ-TREND-T-020: IF `recent_n`이 가용 회차 수보다 크면, 시스템은 `draws_analyzed`를
  가용 회차 수로 산출해야 한다(SHALL). 요청 `recent_n`은 응답에 그대로 노출한다.
- REQ-TREND-T-021: IF 번호가 윈도 내 한 번도 출현하지 않으면, 시스템은
  `last_appeared_drwNo`를 null, `avg_gap`을 null로 산출해야 한다(SHALL).

### Unwanted (SHALL NOT)

- REQ-TREND-T-030: 시스템은 draws가 None이거나 비었을 때 예외를 발생시키지 않아야 하며
  (SHALL NOT), `{"recent_n": recent_n, "draws_analyzed": 0, "numbers": []}`를 반환해야 한다.
- REQ-TREND-T-031: 데이터 레이어(`number_trend`)는 잘못된 번호 입력(빈 리스트, 범위 외)에 대해
  예외를 발생시키지 않아야 한다(SHALL NOT) — 빈 구조를 반환한다(검증은 API 레이어 책임).
- REQ-TREND-T-032: 보너스 번호는 타임라인 출현 판정에 포함되지 않아야 한다(SHALL NOT) —
  본번호 6개만 기준으로 한다.

### Optional (WHERE possible)

- REQ-TREND-T-040: WHERE 페이지(`GET /numbers/trend`)에 유효 파라미터가 있으면, 시스템은
  결과(타임라인/간격)를 함께 렌더링할 수 있다. 파라미터가 없으면 폼만 표시한다.
- REQ-TREND-T-041: WHERE 네비게이션이 렌더링되면, 시스템은 `/numbers/trend`로의 링크를
  노출할 수 있다.

## 4. 인터페이스

### 4.1 데이터 함수

```
number_trend(numbers: List[int], recent_n: int = 100, draws=_UNSET) -> dict
```

반환 구조:

```json
{
  "recent_n": 100,
  "draws_analyzed": 100,
  "numbers": [
    {
      "number": 7,
      "total_appearances": 18,
      "avg_gap": 5.6,
      "last_appeared_drwNo": 1153,
      "current_gap": 3,
      "timeline": [
        {"drwNo": 1054, "date": "2023-01-07", "appeared": false},
        {"drwNo": 1055, "date": "2023-01-14", "appeared": true}
      ]
    }
  ]
}
```

### 4.2 API

`GET /api/numbers/trend`

- Query: `n` (repeatable, 1~3개, 각 1~45, 중복 없음), `recent_n` (int, default=100, ge=10, le=500)
- 검증 실패 → 422
- 항상 HTTP 200으로 `number_trend` 결과 반환(데이터 부재 포함)

### 4.3 페이지

`GET /numbers/trend`

- 최대 3개 번호 입력 + recent_n 입력 폼
- 파라미터 없음 → 폼만, 유효 파라미터 → 폼 + 결과
- `active_tab="numbers_trend"`

## 5. 가정 (Assumptions)

- 주 1회 추첨 가정으로 "회차"가 곧 시간 단위이다.
- 단일 ASGI 워커 환경 — 기존 모듈 캐시 패턴을 그대로 따른다.
- 추가 외부 의존성 없음(표준 라이브러리 + 기존 스택).
- 런타임은 Python 3.9.25 — `Optional[X]`/`List[X]` 런타임 타입 사용.

## 6. 제외 범위 (Exclusions)

- 4개 이상 번호 동시 추적(최대 3개로 제한).
- 미래 출현 예측(본 기능은 과거 추이 추적만 — 예측은 SPEC-LOTTO-039 담당).
- 보너스 번호 추이(본번호만 대상).
- 타임라인 데이터의 영속 저장(읽기 전용 분석).

## 7. 추적성 (Traceability)

| 요구사항 | 구현 | 테스트 |
|----------|------|--------|
| REQ-TREND-T-001~003, 010~012, 020, 021, 030~032 | `lotto/web/data.py: number_trend` | `tests/test_number_trend.py` |
| REQ-TREND-T-013, 031 | `lotto/web/routes/api.py: GET /api/numbers/trend` | `tests/test_api_number_trend.py` |
| REQ-TREND-T-040, 041 | `lotto/web/routes/pages.py: GET /numbers/trend`, `numbers_trend.html`, `base.html` | `tests/test_numbers_trend_page.py` |
