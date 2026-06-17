---
id: SPEC-LOTTO-052
version: 0.1.0
status: Planned
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-052 인수 기준

## Given-When-Then 시나리오

### AC-01: 백테스트 페이지 정상 렌더 (정상 케이스)

- **Given**: 추첨 데이터가 충분히(>= 20회) 존재함.
- **When**: 사용자가 `GET /backtest`로 백테스트 페이지를 연다.
- **Then**: 페이지가 HTTP 200으로 렌더되고, 11개 전략이 각각의 성능 지표
  (적중 분포, 평균 적중, 최고 회차, 종합 점수)와 함께 `score` 내림차순으로
  표시된다.
- 연관: REQ-BT-006

### AC-02: API가 전략별 BacktestResult JSON 반환

- **Given**: 추첨 데이터가 충분히 존재함.
- **When**: 클라이언트가 `GET /api/backtest?n=50`을 호출한다.
- **Then**: JSON 응답이 11개 전략 라벨 각각을 `BacktestResult` 직렬화 객체
  (`match_counts`, `avg_match`, `best_draw`, `score`)에 매핑한다.
- 연관: REQ-BT-007

### AC-03: look-ahead bias 제거 (핵심)

- **Given**: 회차 #k를 백테스트로 평가하는 중.
- **When**: 해당 회차의 추천을 위해 통계를 재구성한다.
- **Then**: 통계는 prior_draws(#1..#k-1)만으로 구성되며, 회차 #k 또는 그 이후
  회차의 어떤 데이터도 추천에 영향을 주지 않는다.
- 연관: REQ-BT-002, REQ-BT-012

### AC-04: 적중 개수 계산 (보너스 제외)

- **Given**: 한 전략이 회차 #k에 대해 6개 번호를 추천함.
- **When**: 적중 개수를 계산한다.
- **Then**: 적중 개수 = 추천 6개와 실제 당첨 6개(`DrawResult.numbers()`)의 교집합
  크기이며, 보너스 번호는 적중에서 제외된다(0~6 범위).
- 연관: REQ-BT-003, REQ-BT-015

### AC-05: 최소 회차 미달 시 에러 결과

- **Given**: 가용 추첨 데이터가 20회 미만임.
- **When**: 사용자가 `GET /backtest` 또는 `GET /api/backtest`를 호출한다.
- **Then**: 백테스트는 실행되지 않고 에러 결과가 반환된다. 페이지는 안내 메시지를
  렌더(HTTP 200 또는 명시된 에러 상태)하고, API는 에러 페이로드를 반환한다.
- 연관: REQ-BT-009

### AC-06: 메모리 캐시 재사용

- **Given**: `n_past=50`으로 백테스트가 한 번 계산되어 캐시됨.
- **When**: 동일 `n_past=50`으로 다시 요청한다.
- **Then**: 재계산 없이 메모리 캐시 결과가 반환된다.
- 연관: REQ-BT-008

### AC-07: 캐시 무효화 후 재계산

- **Given**: `n_past=50` 결과가 캐시되어 있고, 신규 추첨 데이터가 적재됨.
- **When**: 캐시 무효화 후 동일 `n_past`로 요청한다.
- **Then**: 다음 요청에서 백테스트가 재계산된다.
- 연관: REQ-BT-011

### AC-08: 성능 예산

- **Given**: 추첨 데이터가 충분히 존재함.
- **When**: 50회차 × 11전략 백테스트를 실행한다.
- **Then**: 30초 이내에 완료된다.
- 연관: REQ-BT-018

## 데이터 계층 단위 기준 — run_backtest

- AC-09: 반환 매핑은 `STRATEGY_LABELS`의 11개 라벨 전부를 키로 가진다.
  (REQ-BT-001)
- AC-10: 각 `BacktestResult.match_counts`는 0~6 키를 모두 포함하며, 값의 합은
  실제로 평가된 회차 수(평가 윈도 크기)와 같다. (REQ-BT-004, REQ-BT-005)
- AC-11: `avg_match`는 (적중 개수 합 / 평가 회차 수)와 일치하는 float다.
  (REQ-BT-004)
- AC-12: `best_draw`는 해당 전략의 최고 적중 회차에 대한
  `{round, matched, recommended, actual}` 레코드다. (REQ-BT-004)
- AC-13: `score`는 평균 적중과 고적중(3+ 매치) 빈도를 반영한 단조 종합 점수이며,
  페이지와 API가 동일 정의를 사용한다. (REQ-BT-004)
- AC-14: 회차당 통계 재구성/`LottoRecommender` 생성은 1회만 수행되고, 그
  recommender로 11개 전략을 추천한다(전략마다 재구성하지 않음). (REQ-BT-016)
- AC-15: `n_past`가 평가 가능한 최대 회차보다 크면 평가 윈도가 가능한 최대로
  클램프되며 match_counts 합이 클램프된 윈도 수와 일치한다. (REQ-BT-010)

## 제약 준수 기준

- AC-16: `recommender.py` 코어 로직(`STRATEGY_LABELS`, `_strategy_scores`,
  `_pick_set`)과 `analyzer.py`(`LottoAnalyzer.analyze`)가 변경되지 않는다.
  (REQ-BT-013, Exclusions 1)
- AC-17: 백테스트 결과가 DB나 파일에 저장되지 않는다(메모리 캐시 전용).
  (REQ-BT-014, Exclusions 2)
- AC-18: 전체 통계를 한 번만 만들어 모든 회차에 재사용하는 방식이 사용되지 않는다
  (회차별 prior_draws 재구성 확인). (Exclusions 3)
- AC-19: 신규 추천 전략이 추가되지 않는다(11개 그대로). (Exclusions 4)
- AC-20: 보너스 번호가 적중/등급으로 별도 집계되지 않는다. (REQ-BT-015,
  Exclusions 5)
- AC-21: UI에 예측 보장/투자 권유 문구가 없고 과거 성능 한계 안내가 포함된다.
  (Exclusions 6)
- AC-22: 신규 JavaScript 의존성 없이 서버사이드 렌더링으로 표가 표시된다.
  (Exclusions 7)

## 품질 기준

- AC-Q1: `~/.local/bin/pytest` 전체 스위트 통과(기존 1174 + 신규 테스트).
- AC-Q2: `run_backtest`/`BacktestResult` 커버리지 90%+.
- AC-Q3: mypy 통과, ruff clean, 신규 외부 의존성 없음.
- AC-Q4: 함수/변수명 영어, docstring/주석 한국어.

## Definition of Done

- [ ] REQ-BT-001 ~ REQ-BT-018 전부 구현 및 테스트로 검증.
- [ ] AC-01 ~ AC-22 및 AC-Q1 ~ AC-Q4 전부 충족.
- [ ] look-ahead bias 부재가 단위 테스트로 명시적으로 검증됨(AC-03/AC-18).
- [ ] 50회차 × 11전략 < 30초 성능 검증 통과(AC-08).
- [ ] `/backtest` 페이지, `/api/backtest` 엔드포인트 정상 동작.
- [ ] 코어 로직 무변경 및 DB 미영속화 확인(AC-16/AC-17).
