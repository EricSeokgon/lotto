---
id: SPEC-LOTTO-043
version: 0.1.0
status: Planned
created: 2026-06-02
updated: 2026-06-02
author: ircp
priority: medium
---

# SPEC-LOTTO-043: 연속 번호 패턴 분석 (Consecutive Number Pattern Analysis)

## 1. 개요

역대 당첨번호에서 연속된 번호(예: 1-2, 14-15, 22-23-24)가 얼마나 자주 등장하는지
집계·분석하는 기능. 한 회차의 정렬된 본번호 6개에서 인접한 번호들이 이루는
"연속 런(run)"의 길이 분포, 연속 번호를 포함한 회차 비율, 가장 자주 등장한
연속 쌍(pair) 등을 제공한다.

기존 `pattern_analysis`(SPEC-LOTTO-019)가 연속 포함 회차 비율(consecutive) 하나만
부수적으로 제공하는 것과 달리, 본 기능은 연속 패턴 자체를 1급 분석 대상으로 삼아
런 길이 분포·최장 런·연속 쌍 빈도까지 전용으로 산출한다.

## 2. 용어 정의

- **연속 런(consecutive run)**: 한 회차의 정렬된 본번호 6개 중 인접 차이가 1인
  2개 이상의 연속된 번호 묶음. 예) `[3,4,5,18,33,40]` → 길이 3 런 `3-4-5` 1개.
  예) `[7,8,19,20,41,45]` → 길이 2 런 2개 (`7-8`, `19-20`).
- **런 길이(run length, L)**: 한 런에 포함된 연속 번호 개수 (2~6).
- **연속 쌍(consecutive pair)**: 런 내부의 인접 번호 쌍. 길이 L 런은 (L-1)개의 쌍을 포함한다.
  예) 런 `3-4-5` → 쌍 `3-4`, `4-5`. 쌍 라벨 형식은 `"{낮은수}-{높은수}"`.
- **윈도(window) / recent_n**: 분석 대상 최신 회차 수. None이면 전체, 지정 시 최신 N회차.
  recent_n이 가용 회차보다 크면 가용 전체를 사용한다.

## 3. 요구사항 (EARS)

### Ubiquitous (항상 적용)

- REQ-CONSEC-001: 시스템은 `consecutive_pattern(draws, recent_n)` 함수를 통해
  연속 번호 패턴 통계를 단일 진입점으로 제공해야 한다(SHALL).
- REQ-CONSEC-002: 응답은 항상 `total_draws`, `draws_with_consecutive`,
  `consecutive_ratio`, `run_length_distribution`, `max_run_length`,
  `most_common_pairs`, `draws_without_consecutive` 7개 최상위 키를 포함해야 한다(SHALL).
- REQ-CONSEC-003: `run_length_distribution`은 항상 `"2"`~`"6"` 5개 키를 포함해야 한다(SHALL).
- REQ-CONSEC-004: 연속 판정은 정렬된 본번호 6개만 기준으로 하며 보너스 번호를
  포함하지 않아야 한다(SHALL NOT).

### Event-driven (WHEN)

- REQ-CONSEC-010: WHEN 한 회차에 길이 L의 런이 존재하면, 시스템은
  `run_length_distribution["{L}"]`를 1 증가시켜야 한다(SHALL).
- REQ-CONSEC-011: WHEN 한 회차에 길이 L의 런이 존재하면, 시스템은 그 런 내부의
  (L-1)개 인접 쌍 전부를 `most_common_pairs` 집계에 반영해야 한다(SHALL).
- REQ-CONSEC-012: WHEN 한 회차가 길이 2 이상의 런을 하나라도 포함하면, 시스템은
  `draws_with_consecutive`를 1 증가시켜야 한다(SHALL).
- REQ-CONSEC-013: WHEN 한 회차가 연속 런을 전혀 포함하지 않으면, 시스템은
  `draws_without_consecutive`를 1 증가시켜야 한다(SHALL).
- REQ-CONSEC-014: WHEN `GET /api/patterns/consecutive` 요청이 유효하면
  (recent_n 미지정 또는 1~2000), 시스템은 HTTP 200으로 `consecutive_pattern`
  결과를 반환해야 한다(SHALL).

### State-driven (WHILE / IF)

- REQ-CONSEC-020: IF `recent_n`이 주어지면, 시스템은 최신 recent_n 회차만 분석해야 한다(SHALL).
  IF `recent_n`이 None이면 전체 회차를 분석해야 한다.
- REQ-CONSEC-021: IF `recent_n`이 가용 회차 수보다 크면, 시스템은 가용 전체를
  사용해야 한다(SHALL).
- REQ-CONSEC-022: `consecutive_ratio`는 `draws_with_consecutive / total_draws`를
  소수 4자리로 반올림한 값이어야 하며, 회차가 없으면 0.0이어야 한다(SHALL).
- REQ-CONSEC-023: `most_common_pairs`는 빈도 내림차순, 동률은 쌍 라벨 오름차순으로
  정렬한 상위 10개여야 한다(SHALL).
- REQ-CONSEC-024: `max_run_length`는 관측된 가장 긴 연속 런의 길이여야 하며,
  연속 런이 없으면 0이어야 한다(SHALL).

### Unwanted (SHALL NOT)

- REQ-CONSEC-030: 시스템은 draws가 None이거나 비었을 때 예외를 발생시키지
  않아야 하며(SHALL NOT), 일관된 빈 구조(`total_draws=0`, 모든 분포 0,
  `consecutive_ratio=0.0`, `max_run_length=0`, `most_common_pairs=[]`)를 반환해야 한다.

### Optional (WHERE possible)

- REQ-CONSEC-040: WHERE 페이지(`GET /patterns/consecutive`)가 렌더링되면, 시스템은
  연속 비율(headline %), 런 길이 분포, 연속 쌍 표, 최장 런을 표시할 수 있다.
  recent_n 쿼리 파라미터로 분석 윈도를 좁힐 수 있다.
- REQ-CONSEC-041: WHERE 네비게이션이 렌더링되면, 시스템은 `/patterns/consecutive`로의
  링크를 노출할 수 있다.

## 4. 인터페이스

### 4.1 데이터 함수

```
consecutive_pattern(draws=_UNSET, recent_n: Optional[int] = None) -> dict
```

반환 구조:

```json
{
  "total_draws": int,
  "draws_with_consecutive": int,
  "consecutive_ratio": float,
  "run_length_distribution": {"2": int, "3": int, "4": int, "5": int, "6": int},
  "max_run_length": int,
  "most_common_pairs": [{"pair": "1-2", "count": int}],
  "draws_without_consecutive": int
}
```

### 4.2 API

- `GET /api/patterns/consecutive?recent_n=<int|생략>` → 200, `consecutive_pattern` 결과 JSON
  - `recent_n`: Optional[int], 기본 None, ge=1, le=2000. 범위 위반 시 422.
  - 데이터 부재 시에도 200 (빈 구조).

### 4.3 페이지

- `GET /patterns/consecutive?recent_n=<int|생략>` → 200 HTML (`patterns_consecutive.html`)
  - active_tab = `patterns_consecutive`
  - 데이터 부재(total_draws==0) 시 빈 상태 메시지.

## 5. 가정 (Assumptions)

- 주 1회 추첨, 한 회차는 본번호 6개 + 보너스 1개로 구성된다.
- 본번호는 `DrawResult.numbers()`로 항상 정렬된 6개로 제공된다.
- 단일 ASGI 워커 환경 기준 (기존 모듈 캐시 정책과 동일).

## 6. 제외 (Exclusions)

- 보너스 번호를 포함한 연속 패턴은 분석하지 않는다(본번호 6개만 대상).
- 연속 쌍의 통계적 유의성/확률 검정은 범위 밖이다.
- 연속 패턴 기반 번호 추천/예측은 본 SPEC 범위 밖이다(SPEC-LOTTO-039 참조).

## 7. 추적성 (Traceability)

- 데이터 함수: `lotto/web/data.py::consecutive_pattern`
- API: `lotto/web/routes/api.py::GET /api/patterns/consecutive`
- 페이지: `lotto/web/routes/pages.py::GET /patterns/consecutive`
- 템플릿: `lotto/web/templates/patterns_consecutive.html`
- 네비게이션: `lotto/web/templates/base.html`
- 테스트:
  - `tests/test_consecutive_pattern.py` (REQ-CONSEC-001~003, 010~013, 020~024, 030)
  - `tests/test_api_consecutive.py` (REQ-CONSEC-014, 020, 030)
  - `tests/test_consecutive_page.py` (REQ-CONSEC-040, 041)
