---
id: SPEC-LOTTO-039
version: 0.1.0
status: completed
created: 2026-06-01
updated: 2026-06-01
author: ircp
priority: medium
---

# SPEC-LOTTO-039: 당첨번호 예측 리포트

## HISTORY

- 2026-06-01 (v0.1.0): 최초 작성. 최근 N회차 패턴 기반 복합 스코어링 예측 리포트 정의.

---

## 1. 개요 (Overview)

최근 N회차의 출현 패턴을 복합 스코어링하여 다음 회차의 유력 번호 목록과
근거를 리포트 형태로 제공한다. 빈도(frequency), 간격(interval), 홀짝
균형(odd/even balance), 번호대 분포(range distribution) 네 가지 통계
휴리스틱을 가중 합산한 종합 점수(composite score)로 상위 후보 번호를
산출하고, 후보 번호로부터 추천 조합 3세트를 구성한다.

본 기능은 순수 통계 휴리스틱이며, 머신러닝이나 외부 의존성을 도입하지 않는다.
로또는 독립 시행이므로 예측이 당첨을 보장하지 않으며, 리포트는 과거 패턴의
요약·시각화 도구로서 제공된다.

### 배경 (Context)

- 기존 `weekly_report`(SPEC-LOTTO-034)는 최근 N주 출현 경향을 요약하지만
  "다음 회차 유력 번호"를 점수로 제시하지 않는다.
- 기존 `hot_cold_analysis`(SPEC-LOTTO-026)는 핫/콜드를 단일 차원(diff)으로만
  판정한다.
- 본 SPEC은 네 가지 차원을 가중 합산한 단일 종합 점수와 그 근거 분해
  (score breakdown)를 제공하여, 사용자가 "왜 이 번호가 유력한가"를 이해할 수
  있게 한다.

---

## 2. 용어 정의 (Glossary)

- **recent_n**: 분석 대상 최근 회차 수 (기본 50, 최대 200).
- **composite score**: 4개 부분 점수를 가중 합산한 0.0~1.0 정규화 종합 점수.
- **frequency score**: 최근 N회차 내 출현 빈도를 0~1로 정규화한 점수.
- **interval score**: 마지막 출현 이후 경과 회차(gap)를 정규화한 점수
  (오래 안 나온 번호일수록 높음 — "나올 때가 됐다" 휴리스틱).
- **odd/even balance score**: 후보 번호 선정 시 홀짝 균형 기여도.
- **range distribution score**: 번호대(1-9/10-19/20-29/30-39/40-45) 분포
  균형 기여도.
- **candidate**: 종합 점수 상위 후보 번호.
- **combination**: 후보 번호에서 추출한 6개 번호 1세트.

---

## 3. 요구사항 (Requirements — EARS)

### 3.1 집계 함수 (prediction_report)

- **REQ-PRED-001** (Ubiquitous): 시스템은 `lotto/web/data.py`에
  `prediction_report(draws=None, recent_n=50)` 함수를 제공해야 한다(SHALL).

- **REQ-PRED-002** (Event-Driven): `prediction_report`가 호출되면(WHEN), 시스템은
  최근 `recent_n` 회차(drwNo 오름차순 정렬 후 마지막 N개)를 분석 표본으로
  사용해야 한다(SHALL).

- **REQ-PRED-003** (State-Driven): `recent_n`이 가용 회차 수보다 큰 경우(WHILE),
  시스템은 가용한 전체 회차를 표본으로 사용하고 실제 사용 회차 수를
  `draws_analyzed` 필드로 반환해야 한다(SHALL).

- **REQ-PRED-004** (Ubiquitous): 시스템은 1~45 각 번호에 대해 frequency score,
  interval score, odd/even balance score, range distribution score 네 가지
  부분 점수를 계산해야 한다(SHALL).

- **REQ-PRED-005** (Ubiquitous): 시스템은 네 부분 점수를 가중 합산한 composite
  score를 0.0~1.0 범위로 정규화하여 계산해야 한다(SHALL). 가중치는 코드 내
  명명 상수로 정의하고 합이 1.0이 되어야 한다(SHALL).

- **REQ-PRED-006** (Ubiquitous): 시스템은 composite score 내림차순(동률 시 번호
  오름차순)으로 상위 10개 후보 번호를 `top_candidates` 리스트로 반환해야
  한다(SHALL). 각 항목은 `{number, composite_score, breakdown}` 구조이며,
  `breakdown`은 `{frequency, interval, odd_even, range}` 네 부분 점수를 담아야
  한다(SHALL).

- **REQ-PRED-007** (Ubiquitous): 시스템은 상위 후보 번호로부터 6개씩 추출한
  추천 조합 3세트를 `recommended_combinations` 리스트로 반환해야 한다(SHALL).
  각 조합은 6개의 서로 다른 번호를 오름차순 정렬하여 담아야 한다(SHALL).

- **REQ-PRED-008** (State-Driven): 추천 조합을 구성할 때(WHILE), 시스템은
  composite score 상위 후보를 우선 사용하되 세 조합이 완전히 동일하지 않도록
  변형(rotation/오프셋)해야 한다(SHALL).

- **REQ-PRED-009** (Unwanted): draws가 None이거나 빈 리스트인 경우(IF), 시스템은
  예외를 발생시키지 않아야 한다(SHALL NOT). 대신 `draws_analyzed=0`,
  `top_candidates=[]`, `recommended_combinations=[]`의 일관된 빈 구조를
  반환해야 한다(SHALL).

- **REQ-PRED-010** (Event-Driven): 결과를 반환할 때(WHEN), 시스템은 요청한
  `recent_n`을 (가용 회차로 잘리더라도) 그대로 `recent_n` 필드에 노출해야
  한다(SHALL).

### 3.2 API 엔드포인트

- **REQ-PRED-011** (Ubiquitous): 시스템은 `GET /api/prediction/report` 엔드포인트를
  제공해야 한다(SHALL).

- **REQ-PRED-012** (Ubiquitous): 엔드포인트는 쿼리 파라미터 `recent_n`(정수,
  기본 50, 최소 1, 최대 200)을 받아야 한다(SHALL).

- **REQ-PRED-013** (Unwanted): `recent_n`이 1 미만이거나 200 초과인 경우(IF),
  시스템은 FastAPI Query 검증으로 HTTP 422를 반환해야 한다(SHALL).

- **REQ-PRED-014** (State-Driven): draws 데이터가 부재한 경우에도(WHILE),
  엔드포인트는 HTTP 200으로 빈 리포트 구조를 반환해야 한다(SHALL).

### 3.3 페이지

- **REQ-PRED-015** (Ubiquitous): 시스템은 `GET /prediction` 페이지를 제공해야
  한다(SHALL).

- **REQ-PRED-016** (Event-Driven): `/prediction` 페이지가 렌더링되면(WHEN),
  시스템은 상위 후보 번호 목록(번호·종합 점수·점수 분해)과 추천 조합 3세트를
  표/카드 형태로 표시해야 한다(SHALL).

- **REQ-PRED-017** (State-Driven): draws 데이터가 부재한 경우(WHILE), 페이지는
  500 오류 없이 빈 상태 안내 메시지를 표시해야 한다(SHALL).

### 3.4 결정성 / 안정성

- **REQ-PRED-018** (Ubiquitous): 동일한 입력(draws, recent_n)에 대해 시스템은
  항상 동일한 결과를 반환해야 한다(SHALL) — 난수 미사용, 결정적 스코어링.

---

## 4. 비기능 요구사항 (Non-Functional)

- **NFR-PRED-001**: 신규 외부 의존성을 추가하지 않는다 (scikit-learn, numpy 등
  ML/수치 라이브러리 도입 금지). 표준 라이브러리 + 기존 모델만 사용한다.
  (참고: 기존 `analyzer.py`는 numpy를 사용하나, 본 SPEC의 집계 로직은 순수
  파이썬으로 작성한다.)
- **NFR-PRED-002**: Python 3.9 런타임 호환. `from __future__ import annotations`
  사용, `zip(strict=)` 사용 금지, 3.9에서 평가되는 위치에서는 `X | Y` 대신
  `Optional[X]`/`Union` 사용. (기존 `data.py`는 `from __future__ import
  annotations`로 함수 시그니처의 `| None`을 안전하게 사용 중이므로 동일 패턴을
  따른다.)
- **NFR-PRED-003**: 신규 코드 테스트 커버리지 85% 이상, 최소 12개 신규 테스트.
- **NFR-PRED-004**: 기존 961개 테스트가 모두 통과(회귀 없음)해야 한다.
- **NFR-PRED-005**: 집계 함수는 표본 회차에 대해 단일 패스(O(N·6)) 수준으로
  동작하여 recent_n=200에서도 즉시 응답해야 한다.

---

## 5. Exclusions (What NOT to Build)

- **EXC-001**: 머신러닝/통계 모델 학습 미포함. 회귀, 분류, 신경망, 시계열 모델
  등 어떠한 학습 기반 예측도 구현하지 않는다. 순수 통계 휴리스틱만 사용한다.
- **EXC-002**: 예측 정확도 보장·백테스트 검증 미포함. 본 리포트는 과거 패턴
  요약이며 당첨률/적중률 검증은 기존 `strategy_compare`(SPEC-LOTTO-032)의
  책임이다.
- **EXC-003**: 예측 결과 영속화(저장) 미포함. 리포트는 요청 시마다 계산되며
  파일 저장(JSON 등)이나 이력 관리는 하지 않는다.
- **EXC-004**: 사용자별 가중치 커스터마이징 UI 미포함. 가중치는 코드 내 고정
  상수로 한다.
- **EXC-005**: 추천 조합 구매/저장 연동 미포함. 기존 즐겨찾기/예약/구매 기능과의
  연계는 본 SPEC 범위 밖이다.
- **EXC-006**: 보너스 번호 예측 미포함. 본 추첨 6개 번호(1~45)만 대상으로 한다.
- **EXC-007**: 신규 의존성 추가 미포함 (NFR-PRED-001 참조).

---

## 6. 의존성 및 영향 범위

- 신규/수정 파일:
  - `lotto/web/data.py` — `prediction_report` 함수 추가
  - `lotto/web/routes/api.py` — `GET /api/prediction/report` 추가
  - `lotto/web/routes/pages.py` — `GET /prediction` 추가
  - `lotto/web/templates/prediction.html` — 신규 페이지 템플릿
  - `tests/` — 신규 테스트 파일
- 재사용: `get_draws()`, `_UNSET` 센티넬 패턴, `DrawResult.numbers()`,
  FastAPI `Query` 검증, `wd.` 동적 디스패치(테스트 patch 호환).
- 영향 없음: 기존 집계 함수(weekly_report, dashboard_overview 등) 미변경.

---

## 7. 참고 (References)

- SPEC-LOTTO-026: hot/cold 분석 (단일 차원 diff)
- SPEC-LOTTO-034: 주간 통계 리포트 (출현 경향 요약)
- SPEC-LOTTO-032: 전략 백테스트 비교 (적중률 검증)
- SPEC-LOTTO-030: 번호별 상세 통계 (간격/gap 계산 패턴)
