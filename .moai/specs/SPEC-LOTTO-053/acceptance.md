---
id: SPEC-LOTTO-053
version: 0.1.0
status: Planned
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-053 인수 기준

## Given-When-Then 시나리오

### AC-01: 동시 출현 행렬 정확성 (정상 케이스)

- **Given**: 본번호가 알려진 추첨 회차 데이터가 존재함.
- **When**: `get_cooccurrence_matrix(draws)`를 호출한다.
- **Then**: 각 키는 `(i, j)` (단 i < j) 형태의 쌍이고, 값은 두 번호가 같은 회차의
  본번호 6개에 함께 포함된 회차 수와 정확히 일치한다.
- 연관: REQ-CO-001

### AC-02: i < j 단일 집계 (이중 집계 금지)

- **Given**: 임의의 추첨 데이터.
- **When**: 동시 출현 행렬을 구성한다.
- **Then**: 모든 키는 `i < j`를 만족하며 `(j, i)` 키는 절대 존재하지 않고, 한
  회차 내에서 한 쌍이 두 번 집계되지 않는다.
- 연관: REQ-CO-002, REQ-CO-014

### AC-03: 보너스 번호 제외

- **Given**: 보너스 번호가 본번호와 구별되는 추첨 데이터.
- **When**: 동시 출현 행렬을 구성한다.
- **Then**: 보너스 번호는 어떤 쌍 카운트에도 기여하지 않으며, `DrawResult.numbers()`
  의 본번호 6개만 집계에 사용된다.
- 연관: REQ-CO-003, REQ-CO-015

### AC-04: 상위 쌍 목록 + 백분율

- **Given**: 충분한 추첨 데이터.
- **When**: `get_top_cooccurrences(draws, n=20)`를 호출한다.
- **Then**: count 내림차순 상위 20개 쌍 목록이 반환되고, 각 항목은
  `{pair: (i, j), count: int, pct: float}` 구조이며 `pct`는
  `count / total_draws × 100` (소수 2자리)이다.
- 연관: REQ-CO-004, REQ-CO-006

### AC-05: 특정 번호의 동반 파트너 목록

- **Given**: 충분한 추첨 데이터와 번호 N (1~45).
- **When**: `get_number_partners(draws, N, top_k=10)`를 호출한다.
- **Then**: N과 함께 출현한 다른 번호의 상위 10개 파트너가 count 내림차순으로
  반환되고, 각 항목은 `{number, count, pct}` 구조이며 N 자신은 제외된다.
- 연관: REQ-CO-005, REQ-CO-006

### AC-06: 페이지 기본 뷰 (상위 쌍)

- **Given**: 충분한 추첨 데이터.
- **When**: 사용자가 `GET /numbers/cooccurrence`를 (number 없이) 연다.
- **Then**: HTTP 200으로 상위 20개 동시 출현 쌍이 (쌍, count, 백분율) 표로
  렌더된다.
- 연관: REQ-CO-007

### AC-07: 페이지 파트너 뷰 (number 지정)

- **Given**: 충분한 추첨 데이터.
- **When**: 사용자가 `GET /numbers/cooccurrence?number=7`을 연다.
- **Then**: HTTP 200으로 번호 7의 상위 10개 파트너가 표로 렌더되며, 상위 쌍 뷰
  대신 파트너 뷰가 표시된다.
- 연관: REQ-CO-008, REQ-CO-012

### AC-08: API 파트너 응답 (number 지정)

- **Given**: 충분한 추첨 데이터.
- **When**: 클라이언트가 `GET /api/numbers/cooccurrence?number=7&top=20`을
  호출한다.
- **Then**: JSON 응답이 번호 7의 상위 20개 파트너를 포함한다.
- 연관: REQ-CO-009

### AC-09: API 상위 쌍 응답 (number 없음)

- **Given**: 충분한 추첨 데이터.
- **When**: 클라이언트가 `GET /api/numbers/cooccurrence?top=20`을 호출한다.
- **Then**: JSON 응답이 전체 상위 20개 쌍을 포함한다 (기본 top=20).
- 연관: REQ-CO-010

### AC-10: 데이터 부재 시 빈 결과 (에러 없음)

- **Given**: 추첨 데이터가 없음(빈 리스트 또는 None).
- **When**: 데이터 함수/페이지/API를 호출한다.
- **Then**: 예외 없이 빈 행렬/빈 목록을 반환하고, 페이지는 안내 메시지와 함께
  HTTP 200으로 렌더되며, pct는 0.0이다.
- 연관: REQ-CO-011, REQ-CO-006

### AC-11: 캐시 무효화 후 재계산

- **Given**: 동시 출현 행렬이 메모리에 캐시되어 있고, 신규 데이터가 적재됨.
- **When**: `invalidate_cache()` 호출 후 다시 요청한다.
- **Then**: 다음 요청에서 행렬이 재계산된다.
- 연관: REQ-CO-013, REQ-CO-020

### AC-12: 성능 예산

- **Given**: 전체 추첨 이력이 존재함.
- **When**: 동시 출현 행렬을 구성한다.
- **Then**: 5초 이내에 완료된다 (각 회차당 C(6,2)=15 쌍).
- 연관: REQ-CO-021

## 데이터 계층 단위 기준

- AC-13: `get_cooccurrence_matrix`는 빈/None 입력에 대해 빈 dict를 반환한다.
  (REQ-CO-011)
- AC-14: 모든 쌍 키는 `i < j`이며, 동일 쌍이 회차마다 정확히 1씩 누적된다.
  (REQ-CO-002)
- AC-15: `get_top_cooccurrences`와 `get_number_partners`의 정렬은 count
  내림차순이고, 동률은 쌍/번호 오름차순으로 결정론적이다. (REQ-CO-004, REQ-CO-005)
- AC-16: `pct`는 `count / total_draws × 100`의 소수 2자리이며 total_draws=0일 때
  0.0이다. (REQ-CO-006)
- AC-17: 행렬은 요청당 1회만 구성되고 top/partner는 그 행렬에서 파생된다(쿼리마다
  draws를 재스캔하지 않음). (REQ-CO-019)

## 제약 준수 기준

- AC-18: 신규 추천 전략이 추가되지 않는다(원시 동시 출현 데이터만 제공).
  (REQ-CO-017, Exclusions 1)
- AC-19: 동시 출현 결과가 DB나 파일에 저장되지 않는다(메모리 캐시 전용).
  (REQ-CO-016, Exclusions 2)
- AC-20: 보너스 번호가 동시 출현 카운트에 포함되지 않는다. (REQ-CO-003,
  Exclusions 3)
- AC-21: 쌍이 (i, j)/(j, i)로 이중 집계되지 않는다. (REQ-CO-014, Exclusions 4)
- AC-22: 신규 JavaScript 의존성 없이 서버사이드 렌더링으로 표가 표시되고, UI에
  예측 보장/투자 권유 문구가 없다. (REQ-CO-018, Exclusions 5, 7)
- AC-23: `recommender.py`/`analyzer.py` 코어 로직이 변경되지 않는다(신규 함수는
  `lotto/web/data.py`에만 추가). (Exclusions 6)

## 품질 기준

- AC-Q1: `~/.local/bin/pytest` 전체 스위트 통과(기존 + 신규 테스트).
- AC-Q2: `get_cooccurrence_matrix`/`get_top_cooccurrences`/`get_number_partners`
  커버리지 90%+.
- AC-Q3: mypy 통과, ruff clean, 신규 외부 의존성 없음.
- AC-Q4: 함수/변수명 영어, docstring/주석 한국어.

## Definition of Done

- [ ] REQ-CO-001 ~ REQ-CO-021 전부 구현 및 테스트로 검증.
- [ ] AC-01 ~ AC-23 및 AC-Q1 ~ AC-Q4 전부 충족.
- [ ] i<j 단일 집계 및 보너스 제외가 단위 테스트로 명시적으로 검증됨(AC-02/AC-03).
- [ ] `/numbers/cooccurrence` 페이지, `/api/numbers/cooccurrence` 엔드포인트 정상
  동작 (number 유/무 분기 포함).
- [ ] 라우트가 `/numbers/{number}` 동적 라우트보다 먼저 등록되어 캡처 충돌 없음.
- [ ] 코어 로직 무변경 및 DB 미영속화 확인(AC-19/AC-23).
