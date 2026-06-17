---
id: SPEC-LOTTO-054
version: 0.1.0
status: Planned
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-054 인수 기준

## Given-When-Then 시나리오

### AC-01: 윈도우 빈도 정확성 (정상 케이스)

- **Given**: 본번호가 알려진 충분한 추첨 회차 데이터가 존재함.
- **When**: `get_rolling_frequency(draws, windows=(10, 20, 50, 100))`를 호출한다.
- **Then**: 각 윈도우 W의 `freq[n]`은 최근 W회차 중 번호 n을 본번호로 포함한 회차
  수와 정확히 일치한다.
- 연관: REQ-RW-001, REQ-RW-002

### AC-02: 추세 델타 정규화 계산

- **Given**: 충분한 추첨 데이터.
- **When**: 윈도우 W의 델타를 산출한다.
- **Then**: 각 번호 n의 `delta[n]`은 `freq_window[n]/W - freq_total[n]/total_draws`
  와 일치한다.
- 연관: REQ-RW-004, REQ-RW-022

### AC-03: 추세 분류 임계값 (상승/하락/보합)

- **Given**: 델타가 알려진 번호들.
- **When**: 추세를 분류한다.
- **Then**: 델타 > +0.02 → "상승", 델타 < -0.02 → "하락", 그 외(경계값 ±0.02
  포함) → "보합"으로 분류된다.
- 연관: REQ-RW-005

### AC-04: 최고 상승/하락 상위 5개

- **Given**: 충분한 추첨 데이터.
- **When**: 윈도우 W의 `rising`/`falling`을 산출한다.
- **Then**: `rising`은 델타 내림차순 상위 5개 번호, `falling`은 델타 오름차순
  하위 5개 번호이며, 동률은 번호 오름차순으로 결정론적이다.
- 연관: REQ-RW-006

### AC-05: 1~45 전 번호 커버

- **Given**: 충분한 추첨 데이터.
- **When**: 윈도우 W의 RollingResult를 산출한다.
- **Then**: `freq`/`delta`/`trend` 맵은 1~45 전 번호를 포함하며, 윈도우에 없는
  번호는 freq 0과 음수/0 델타를 갖는다.
- 연관: REQ-RW-007

### AC-06: 보너스 번호 제외

- **Given**: 보너스 번호가 본번호와 구별되는 추첨 데이터.
- **When**: 빈도/델타/추세를 산출한다.
- **Then**: 보너스 번호는 어떤 빈도/델타/추세 값에도 기여하지 않으며,
  `DrawResult.numbers()`의 본번호 6개만 집계에 사용된다.
- 연관: REQ-RW-003, REQ-RW-016

### AC-07: 부족 윈도우 스킵 (에러 없음)

- **Given**: 가용 회차가 30회뿐인 데이터, 요청 윈도우 (10, 20, 50, 100).
- **When**: `get_rolling_frequency`를 호출한다.
- **Then**: W=10, W=20만 결과에 포함되고 W=50, W=100은 예외 없이 생략된다.
- 연관: REQ-RW-012, REQ-RW-021

### AC-08: 페이지 기본 뷰 (전체 윈도우)

- **Given**: 충분한 추첨 데이터.
- **When**: 사용자가 `GET /stats/rolling`을 (w 없이) 연다.
- **Then**: HTTP 200으로 기본 윈도우 (10, 20, 50, 100)의 번호별 빈도/델타/추세가
  표로 렌더된다.
- 연관: REQ-RW-008

### AC-09: 페이지 단일 윈도우 뷰 (w 지정)

- **Given**: 충분한 추첨 데이터.
- **When**: 사용자가 `GET /stats/rolling?w=20`을 연다.
- **Then**: HTTP 200으로 윈도우 20만 포커스 표로 렌더되며, 전체 윈도우 뷰 대신
  단일 윈도우 뷰가 표시된다.
- 연관: REQ-RW-009, REQ-RW-014

### AC-10: API 다중 윈도우 응답

- **Given**: 충분한 추첨 데이터.
- **When**: 클라이언트가 `GET /api/stats/rolling?windows=10,20,50,100`을 호출한다.
- **Then**: JSON 응답이 적용 가능한 각 윈도우의 RollingResult를 포함한다.
- 연관: REQ-RW-010

### AC-11: API 기본 윈도우 (windows 없음)

- **Given**: 충분한 추첨 데이터.
- **When**: 클라이언트가 `GET /api/stats/rolling`을 (windows 없이) 호출한다.
- **Then**: JSON 응답이 기본 윈도우 (10, 20, 50, 100) 결과를 포함한다.
- 연관: REQ-RW-011

### AC-12: 데이터 부재 시 빈 결과 (에러 없음)

- **Given**: 추첨 데이터가 없음(빈 리스트 또는 None).
- **When**: 데이터 함수/페이지/API를 호출한다.
- **Then**: 예외 없이 빈 매핑을 반환하고(모든 윈도우 스킵), 페이지는 안내 메시지와
  함께 HTTP 200으로 렌더된다.
- 연관: REQ-RW-013

### AC-13: 캐시 무효화 후 재계산

- **Given**: 롤링 결과가 메모리에 캐시되어 있고, 신규 데이터가 적재됨.
- **When**: `invalidate_cache()` 호출 후 다시 요청한다.
- **Then**: 다음 요청에서 결과가 재계산된다.
- 연관: REQ-RW-015, REQ-RW-023

### AC-14: 성능 예산

- **Given**: 전체 추첨 이력이 존재함.
- **When**: 기본 윈도우의 롤링 빈도를 산출한다.
- **Then**: 5초 이내에 완료된다.
- 연관: REQ-RW-024

## 데이터 계층 단위 기준

- AC-15: `get_rolling_frequency`는 빈/None 입력에 대해 빈 dict를 반환한다.
  (REQ-RW-013)
- AC-16: 전체 빈도(freq_total)는 요청당 1회만 계산되고 모든 윈도우가 재사용한다.
  (REQ-RW-022)
- AC-17: `rising`/`falling` 정렬은 델타 기준이며 동률은 번호 오름차순으로
  결정론적이다. (REQ-RW-006)
- AC-18: 추세 분류 경계값 ±0.02는 "보합"으로 처리된다(엄격 부등호). (REQ-RW-005)
- AC-19: 결과는 windows 튜플 키로 캐시되며 동일 windows 재요청 시 재계산하지
  않는다. (REQ-RW-023)

## 제약 준수 기준

- AC-20: 보너스 번호가 빈도/델타/추세에 포함되지 않는다. (REQ-RW-003, Exclusions 1)
- AC-21: 추세 임계값 ±0.02가 설정/쿼리로 노출되지 않고 하드코딩 상수다.
  (REQ-RW-017, Exclusions 2)
- AC-22: 롤링 결과가 DB나 파일에 저장되지 않는다(메모리 캐시 전용).
  (REQ-RW-018, Exclusions 3)
- AC-23: 신규 추천 전략이 추가되지 않는다(빈도/추세 분석 데이터만 제공).
  (REQ-RW-019, Exclusions 4)
- AC-24: 신규 JavaScript 의존성 없이 서버사이드 렌더링으로 표가 표시되고, UI에
  예측 보장/투자 권유 문구가 없다. (REQ-RW-020, Exclusions 5, 8)
- AC-25: `recommender.py`/`analyzer.py` 코어 로직이 변경되지 않는다(신규 함수는
  `lotto/web/data.py`에만 추가). (Exclusions 6)
- AC-26: 가용 회차보다 큰 윈도우는 에러 없이 조용히 건너뛴다.
  (REQ-RW-021, Exclusions 7)

## 품질 기준

- AC-Q1: `~/.local/bin/pytest` 전체 스위트 통과(기존 + 신규 테스트).
- AC-Q2: `get_rolling_frequency` 커버리지 90%+.
- AC-Q3: mypy 통과, ruff clean, 신규 외부 의존성 없음.
- AC-Q4: 함수/변수명 영어, docstring/주석 한국어.

## Definition of Done

- [ ] REQ-RW-001 ~ REQ-RW-024 전부 구현 및 테스트로 검증.
- [ ] AC-01 ~ AC-26 및 AC-Q1 ~ AC-Q4 전부 충족.
- [ ] 추세 임계값 경계(±0.02)와 부족 윈도우 스킵이 단위 테스트로 명시적으로
  검증됨(AC-03/AC-07).
- [ ] `/stats/rolling` 페이지, `/api/stats/rolling` 엔드포인트 정상 동작
  (w 단일 윈도우 / windows 다중 윈도우 분기 포함).
- [ ] 보너스 제외 및 1~45 전 번호 커버가 단위 테스트로 검증됨(AC-05/AC-06).
- [ ] 코어 로직 무변경 및 DB 미영속화 확인(AC-22/AC-25).
