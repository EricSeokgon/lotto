---
id: SPEC-LOTTO-101
version: 0.1.0
status: draft
created: 2026-06-18
updated: 2026-06-18
author: ircp
priority: medium
---

# SPEC-LOTTO-101: 적합도 기반 번호 추천

## 1. 개요

적합도 점수(Fitness Score) 함수를 활용하여 고득점 로또 번호 조합을 자동으로 생성하고 추천하는 기능을 구현한다. 무작위로 생성된 대규모 번호 풀에서 각 조합의 적합도를 계산하고, 임계값 이상의 조합을 점수 순으로 정렬하여 상위 조합을 반환한다.

사용자는 API 또는 웹 페이지를 통해 추천 개수, 최소 점수 기준, 풀 크기를 조정하여 원하는 조건의 번호 조합을 추천받을 수 있다.

## 2. 배경

SPEC-LOTTO-100에서 구현된 `get_fitness_score()` 함수는 로또 번호 조합의 역사적 데이터 기반 적합도를 0~100점으로 평가한다. 이 함수는 `lotto/web/data.py`에 구현되어 있으며, 과거 당첨 데이터(`DrawResult` 목록)를 입력받아 해당 번호 조합에 대한 다차원 분석 결과를 딕셔너리 형태로 반환한다.

SPEC-LOTTO-101은 이 함수를 활용하여 사용자가 직접 번호를 입력하지 않고도 시스템이 자동으로 고적합도 조합을 탐색·추천하는 기능을 추가한다. 기존 `/api/recommendations` 엔드포인트(LottoRecommender 기반)와 구별되며, 적합도 점수 분석에 특화된 새로운 추천 경로를 제공한다.

## 3. 요구사항

### 기능 요구사항

**REQ-FR-101-001: 무작위 번호 풀 생성 및 적합도 계산**

WHEN 추천 요청이 들어오면,
THE SYSTEM SHALL `pool_size`개의 무작위 6개 번호 조합(1~45, 중복 없음)을 생성하고,
각 조합에 대해 `get_fitness_score(numbers, draws)`를 호출하여 적합도 점수를 계산한다.

**REQ-FR-101-002: 점수 필터링 및 정렬 후 상위 반환**

WHEN 적합도 점수 계산이 완료되면,
THE SYSTEM SHALL `min_score` 이상인 조합만 선별하고,
점수 내림차순으로 정렬한 후 상위 `count`개를 반환한다.
반환 항목에는 번호 목록, 점수, 등급이 포함된다.

**REQ-FR-101-003: API 엔드포인트 제공**

THE SYSTEM SHALL `GET /api/stats/fitness-recommend` 엔드포인트를 제공해야 한다.

- 쿼리 파라미터:
  - `count` (기본값: 5, 범위: 1–20): 반환할 추천 개수
  - `min_score` (기본값: 60, 범위: 0–100): 최소 적합도 점수
  - `pool_size` (기본값: 1000, 범위: 1–5000): 생성할 무작위 조합 수
- 응답 형식 (JSON):
  ```json
  [
    {"numbers": [3, 12, 21, 30, 38, 45], "score": 78.5, "grade": "B"},
    ...
  ]
  ```
- `min_score` 이상의 조합이 `count`개 미만인 경우, 해당 조합만 반환한다(빈 배열도 유효).

**REQ-FR-101-004: 웹 페이지 제공**

THE SYSTEM SHALL `GET /stats/fitness-recommend` 웹 페이지를 제공해야 한다.

- 파라미터 설정 폼(count, min_score, pool_size)을 포함한다.
- 추천 번호 조합을 점수·등급과 함께 테이블로 표시한다.
- `base.html`의 내비게이션 탭에 "적합도 추천" 항목을 추가한다.

**REQ-FR-101-005: count 파라미터 범위 검증**

WHEN `count` 파라미터가 1 미만이거나 20 초과인 경우,
THE SYSTEM SHALL HTTP 422 오류를 반환해야 한다.

**REQ-FR-101-006: min_score 파라미터 범위 검증**

WHEN `min_score` 파라미터가 0 미만이거나 100 초과인 경우,
THE SYSTEM SHALL HTTP 422 오류를 반환해야 한다.

**REQ-FR-101-007: pool_size 파라미터 범위 검증**

WHEN `pool_size` 파라미터가 1 미만이거나 5000 초과인 경우,
THE SYSTEM SHALL HTTP 422 오류를 반환해야 한다.

### 비기능 요구사항

**REQ-NFR-101-001: 처리 성능**

WHILE `pool_size=1000`으로 추천 요청이 처리되는 동안,
THE SYSTEM SHALL 합리적인 응답 시간(단일 요청 기준) 내에 응답을 완료해야 한다.

## 4. 인수 조건

### AC-101-001: 기본 추천 동작

- GIVEN: 과거 당첨 데이터가 존재하고 `GET /api/stats/fitness-recommend`를 기본 파라미터로 요청한다.
- WHEN: API가 응답한다.
- THEN: 응답은 JSON 배열이며, 각 항목에 `numbers`(6개 정수 목록), `score`(0~100 실수), `grade`(문자열)가 포함된다.

### AC-101-002: min_score 필터링

- GIVEN: `min_score=80`으로 요청한다.
- WHEN: API가 응답한다.
- THEN: 응답의 모든 항목의 `score`가 80 이상이다.

### AC-101-003: count 제한

- GIVEN: `count=3`, `pool_size=1000`, `min_score=0`으로 요청한다.
- WHEN: API가 응답한다.
- THEN: 응답 항목 수는 최대 3개이다.

### AC-101-004: 점수 내림차순 정렬

- GIVEN: 추천 결과가 2개 이상인 경우.
- THEN: 결과는 `score` 기준 내림차순으로 정렬되어 있다.

### AC-101-005: 파라미터 범위 검증

- GIVEN: `count=0`, `count=21`, `min_score=-1`, `min_score=101`, `pool_size=0`, `pool_size=5001` 중 하나로 요청한다.
- THEN: HTTP 422 응답이 반환된다.

### AC-101-006: 결과 미달 시 부분 반환

- GIVEN: `min_score=99`, `pool_size=100`으로 요청한다.
- WHEN: 조건을 만족하는 조합이 `count`개 미만일 때.
- THEN: 조건을 만족하는 조합만 반환하며, 빈 배열도 유효한 응답이다.

### AC-101-007: 웹 페이지 렌더링

- GIVEN: `GET /stats/fitness-recommend`를 요청한다.
- THEN: HTTP 200 응답과 함께 HTML 페이지가 반환되며, 파라미터 설정 폼과 결과 테이블 영역이 포함된다.

### AC-101-008: 내비게이션 탭

- GIVEN: 어떤 페이지에서든 `base.html`을 사용하는 페이지를 방문한다.
- THEN: 내비게이션 탭에 "적합도 추천" 또는 이에 준하는 링크가 존재한다.

## 5. 구현 범위

### 신규 생성 파일

| 파일 | 설명 |
|------|------|
| `tests/test_fitness_recommend.py` | TDD 테스트 파일 (RED → GREEN → REFACTOR 순서로 작성) |
| `lotto/web/templates/fitness_recommend.html` | 적합도 추천 웹 페이지 템플릿 |

### 수정 파일

| 파일 | 수정 내용 |
|------|-----------|
| `lotto/web/routes/api.py` | `GET /api/stats/fitness-recommend` 엔드포인트 추가 |
| `lotto/web/routes/pages.py` | `GET /stats/fitness-recommend` 페이지 라우트 추가 |
| `lotto/web/templates/base.html` | 내비게이션 탭에 "적합도 추천" 항목 추가 |

### 참조 파일 (수정 없음)

| 파일 | 역할 |
|------|------|
| `lotto/web/data.py` | `get_fitness_score()` 함수 참조 (SPEC-LOTTO-100 구현체) |

### Python 3.9 호환성 주의사항

`api.py` 및 `pages.py`에 `from __future__ import annotations`가 없는 경우,
FastAPI Query 파라미터 타입 힌트에 `Optional[int] = None  # noqa: UP045` 형식을 사용해야 한다.
`int | None` 형식은 Python 3.10+ 전용이므로 사용을 금지한다.

## 6. 의존성

| 의존 SPEC | 관계 | 비고 |
|-----------|------|------|
| SPEC-LOTTO-100 | 필수 선행 | `get_fitness_score()` 함수 구현 |

SPEC-LOTTO-100의 `get_fitness_score(numbers: list[int], draws: list[DrawResult] | None) -> dict[str, Any]`가 정상 동작하는 환경이 전제된다. 해당 함수의 반환값 중 `score`(숫자)와 `grade`(문자열) 키를 사용한다.
