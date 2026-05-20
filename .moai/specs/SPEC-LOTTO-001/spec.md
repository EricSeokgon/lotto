---
id: SPEC-LOTTO-001
version: "1.0.0"
status: draft
created: "2026-05-20"
updated: "2026-05-20"
author: ircp
priority: high
issue_number: 0
---

# SPEC-LOTTO-001: 한국 로또 번호 추천 시스템

## HISTORY

| 버전 | 일자 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| 1.0.0 | 2026-05-20 | ircp | 초기 SPEC 작성 — 데이터 수집/분석/추천/시뮬레이션 4-모듈 파이프라인 정의 |

---

## Overview (개요)

### What (무엇을 만드는가)

본 시스템은 한국 동행복권(dhlottery.co.kr)에서 공식 제공하는 로또 6/45 회차별 당첨 번호를 수집하고, 통계적으로 분석하여 사용자에게 다중 가중치 기반 추천 번호 조합을 제시하는 **Python CLI 도구**이다. 또한 추천 알고리즘의 효용성을 과거 데이터에 대한 백테스팅으로 검증하는 시뮬레이션 기능을 제공한다.

### Why (왜 만드는가)

- 일반 사용자가 동행복권 API를 직접 다루지 않고도 회차별 당첨 번호를 손쉽게 확보할 수 있어야 한다.
- 단순 무작위 추천이 아니라 **출현 빈도, 최근 패턴, 연속/배제 패턴, 동반 출현 관계**를 통합한 객관적 분석 결과를 기반으로 후보 번호를 생성하여, 사용자가 자신만의 번호 선택 근거를 가질 수 있게 한다.
- 추천 결과의 유효성을 과거 회차에 대한 시뮬레이션으로 정량 평가하여 알고리즘 개선 사이클을 짧게 가져갈 수 있어야 한다.
- 외부 DB나 클라우드 의존 없이 **로컬 CSV/JSON 파일 기반**으로 동작하여, 개인 사용자가 별도 인프라 없이 즉시 활용 가능해야 한다.

### Scope (적용 범위)

- 한국 동행복권 6/45 로또 (1~45 범위의 6개 번호 + 보너스 번호)
- Python 3.11 이상 환경
- 단일 사용자 CLI 도구 (멀티 테넌시/웹 API 미지원)
- 로컬 파일 시스템 기반 저장 (외부 DB 미사용)

---

## Glossary (용어 정의)

| 용어 | 정의 |
|------|------|
| 회차(drwNo) | 동행복권 로또 6/45 추첨 회차 번호 (1부터 순차 증가) |
| 당첨 번호 | 한 회차에서 추첨된 6개의 본 번호 (1~45 범위) |
| 보너스 번호 | 본 번호 6개와 별도로 추첨되는 7번째 번호 |
| 출현 빈도 | 특정 번호가 전체 회차 중 본 번호로 추첨된 횟수 |
| 동반 출현 | 두 번호가 같은 회차에 동시에 본 번호로 추첨된 사례 |
| 추천 조합 | 시스템이 분석 결과를 기반으로 산출한 6개 번호 세트 |
| 백테스팅 | 추천 알고리즘을 과거 회차에 적용해 실제 당첨 결과와 비교 평가하는 행위 |
| 매칭 등급 | 추천 조합과 실제 당첨 번호의 일치 개수에 따른 등수 (3개=5등, 4개=4등, 5개=3등, 5개+보너스=2등, 6개=1등) |

---

## Functional Requirements (기능 요구사항 — EARS 형식)

### REQ-COLLECT: 당첨 번호 수집 모듈

#### REQ-COLLECT-01 (Ubiquitous)
The system SHALL maintain all collected lotto draw results in a local CSV file located at `data/draws.csv` with columns `drwNo, date, n1, n2, n3, n4, n5, n6, bonus`.

#### REQ-COLLECT-02 (Event-driven)
WHEN the user executes `python main.py collect`, THE system SHALL fetch the latest available draw number from `https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={N}` for all rounds from the last stored round + 1 up to the latest published round, AND append the new records to `data/draws.csv`.

#### REQ-COLLECT-03 (Event-driven)
WHEN `python main.py collect --full` is executed, THE system SHALL re-collect all draws from round 1 to the latest available round, overwriting the existing `data/draws.csv` file after a confirmation prompt.

#### REQ-COLLECT-04 (Unwanted behavior)
IF the API response status is not HTTP 200, OR the response JSON field `returnValue` is not `"success"`, THEN the system SHALL retry the request up to 3 times with exponential backoff (1s, 2s, 4s) before logging a failure entry and skipping that round.

#### REQ-COLLECT-05 (Unwanted behavior)
IF more than 5 consecutive rounds fail to collect, THEN the system SHALL abort the collection run, preserve all previously collected data, and exit with non-zero status code 2.

#### REQ-COLLECT-06 (State-driven)
WHILE collecting multiple rounds in sequence, the system SHALL insert a delay of at least 200ms between consecutive API requests to respect server rate limits.

---

### REQ-ANALYZE: 통계 분석 모듈

#### REQ-ANALYZE-01 (Ubiquitous)
The system SHALL compute statistical metrics from `data/draws.csv` and persist results to `data/stats.json` containing four sections: `frequency`, `recent_pattern`, `consecutive_pattern`, `pair_analysis`.

#### REQ-ANALYZE-02 (Event-driven)
WHEN the user executes `python main.py analyze`, THE system SHALL compute the absolute and relative frequency of each number (1~45) across all collected rounds and store the result under `frequency` in `data/stats.json`.

#### REQ-ANALYZE-03 (Event-driven)
WHEN analysis runs, THE system SHALL compute the recent appearance pattern for each number across the last N rounds (default N=20, configurable via `--recent-window`), recording the count and the most recent appearance round under `recent_pattern`.

#### REQ-ANALYZE-04 (Event-driven)
WHEN analysis runs, THE system SHALL compute consecutive appearance and exclusion streaks for each number (how many consecutive rounds it appeared, how many consecutive rounds it was absent) and store under `consecutive_pattern`.

#### REQ-ANALYZE-05 (Event-driven)
WHEN analysis runs, THE system SHALL compute pair co-occurrence counts (how often each number pair {i,j} appears together) and store the top 20 most frequent pairs under `pair_analysis`.

#### REQ-ANALYZE-06 (Unwanted behavior)
IF `data/draws.csv` does not exist or contains zero records, THEN the system SHALL print the error message `당첨 데이터가 없습니다. 먼저 'collect' 명령을 실행하세요.` and exit with status code 1.

#### REQ-ANALYZE-07 (Unwanted behavior)
IF `data/draws.csv` contains fewer rounds than the `--recent-window` value, THEN the system SHALL print a warning and compute recent_pattern over all available rounds without aborting.

---

### REQ-RECOMMEND: 번호 추천 모듈

#### REQ-RECOMMEND-01 (Ubiquitous)
The system SHALL generate recommended number sets where each set consists of exactly 6 distinct integers in the range [1, 45], and no two recommended sets within the same execution are identical.

#### REQ-RECOMMEND-02 (Event-driven)
WHEN the user executes `python main.py recommend`, THE system SHALL load `data/stats.json`, compute a weighted score for each number using the formula `score(n) = w_freq × freq_norm(n) + w_recent × recent_norm(n) + w_pair × pair_norm(n) - w_consec × consec_penalty(n)`, AND produce 5 recommended sets by default.

#### REQ-RECOMMEND-03 (Event-driven)
WHEN `--count N` is specified (1 ≤ N ≤ 20), THE system SHALL produce exactly N recommended sets.

#### REQ-RECOMMEND-04 (Optional)
WHERE the user provides custom weights via `--weights w_freq,w_recent,w_pair,w_consec`, THE system SHALL use the provided weights instead of the defaults (default: 0.4, 0.3, 0.2, 0.1) provided each weight is a non-negative float and the sum is positive.

#### REQ-RECOMMEND-05 (Ubiquitous)
The system SHALL present each recommended set in ascending numeric order and assign a strategy label among {`고빈도`, `저빈도`, `균형`, `최근편향`, `동반패턴`}.

#### REQ-RECOMMEND-06 (Unwanted behavior)
IF `data/stats.json` does not exist or is malformed, THEN the system SHALL print `통계 데이터가 없습니다. 먼저 'analyze' 명령을 실행하세요.` and exit with status code 1.

#### REQ-RECOMMEND-07 (Complex)
WHILE recommendation is in progress, WHEN the weighted scoring yields fewer than 6 numbers with non-zero score, the system SHALL fall back to uniform random selection from the remaining pool and log a warning indicating insufficient statistical signal.

---

### REQ-SIMULATE: 시뮬레이션 모듈

#### REQ-SIMULATE-01 (Ubiquitous)
The system SHALL evaluate recommended sets against the most recent K historical draw results (default K=10), computing per-set match counts and grade distribution, AND output a summary report.

#### REQ-SIMULATE-02 (Event-driven)
WHEN the user executes `python main.py simulate`, THE system SHALL generate recommendations for each of the last K rounds using only the data available before that round (causal/look-ahead-safe), THEN compare each recommendation against the actual draw of that round.

#### REQ-SIMULATE-03 (Event-driven)
WHEN `--rounds N` is specified, THE system SHALL evaluate the recommendation algorithm over the most recent N historical rounds (1 ≤ N ≤ total collected rounds).

#### REQ-SIMULATE-04 (Ubiquitous)
The system SHALL report the following aggregate metrics in the simulation output: total evaluated rounds, count of sets matching 3+ numbers (5등), 4 numbers (4등), 5 numbers (3등), 5 numbers + bonus (2등), 6 numbers (1등), AND the overall hit rate (rounds with at least one 5등 or better).

#### REQ-SIMULATE-05 (Unwanted behavior)
IF the simulation algorithm uses any draw data from round R while generating recommendations for round R (look-ahead bias), THEN the simulation SHALL be considered invalid AND the system SHALL fail the build during unit testing.

#### REQ-SIMULATE-06 (Optional)
WHERE the `--output FILE` flag is provided, THE system SHALL persist the full simulation report (including per-round details) to the specified JSON file in addition to console output.

---

### REQ-CLI: CLI 인터페이스 모듈

#### REQ-CLI-01 (Ubiquitous)
The system SHALL provide a `typer`-based CLI entry point at `main.py` exposing exactly four subcommands: `collect`, `analyze`, `recommend`, `simulate`.

#### REQ-CLI-02 (Event-driven)
WHEN the user invokes `python main.py --help` or `python main.py <subcommand> --help`, THE system SHALL display Korean-language help text describing usage, options, and examples for each subcommand.

#### REQ-CLI-03 (Ubiquitous)
The system SHALL render all user-facing output (progress, results, errors) using the `rich` library for tabular and color-coded display, with Korean labels.

#### REQ-CLI-04 (Unwanted behavior)
IF the user provides an unknown subcommand or an invalid option value (e.g., `--count 0`, `--count 100`), THEN the system SHALL print a Korean error message indicating the valid range and exit with status code 2.

#### REQ-CLI-05 (Event-driven)
WHEN any subcommand completes successfully, THE system SHALL exit with status code 0; WHEN it fails due to validation error, status code 1; WHEN it aborts due to external service failure, status code 2.

#### REQ-CLI-06 (State-driven)
WHILE a long-running operation is in progress (collection of many rounds, simulation of many rounds), the system SHALL display a `rich` progress bar showing current/total and ETA.

---

## Non-Functional Requirements (비기능 요구사항)

| 항목 | 요구사항 |
|------|----------|
| 성능 | `analyze` 명령은 1,200회차 데이터 기준 5초 이내 완료 |
| 성능 | `recommend` 명령은 5세트 생성 기준 2초 이내 완료 |
| 안정성 | API 일시 장애 시 3회 재시도 후에도 실패하면 사용자에게 명확한 에러 메시지 출력 |
| 호환성 | Python 3.11, 3.12 지원 |
| 코드 품질 | `ruff` 린팅 오류 0건, `mypy --strict` 타입 오류 0건 |
| 테스트 | 단위 테스트 커버리지 85% 이상 |
| 보안 | 사용자 입력값(`--count`, `--rounds`, `--weights`)에 대한 범위 검증 필수 |

---

## Exclusions (What NOT to Build) — 제외 범위

본 SPEC은 다음 항목을 **명시적으로 제외**한다:

1. **당첨 보장 불가 (No Winning Guarantee)**: 본 시스템의 추천은 통계적 분석 결과일 뿐이며, 어떠한 형태로도 당첨을 보장하지 않는다. 사용자에게 표시되는 모든 추천에는 "참고용이며 당첨을 보장하지 않습니다"라는 면책 문구를 함께 출력한다.

2. **자동 구매 미지원 (No Auto-Purchase)**: 동행복권 또는 그 외 어떠한 외부 결제/구매 시스템과도 연동하지 않으며, 추천된 번호의 실제 구매는 사용자가 직접 수행한다.

3. **GUI 미제공 (No GUI)**: 본 시스템은 순수 CLI 도구로만 제공하며, 웹 인터페이스, 데스크톱 GUI, 모바일 앱은 본 SPEC 범위에 포함하지 않는다.

4. **실시간 데이터 스트리밍 미지원 (No Real-time Streaming)**: 본 시스템은 사용자가 명시적으로 `collect` 명령을 실행할 때에만 API를 호출한다. 백그라운드 폴링, 푸시 알림, 실시간 추첨 중계는 제공하지 않는다.

5. **외부 DB 미사용 (No External Database)**: PostgreSQL, MySQL, MongoDB, Redis 등 어떠한 외부 데이터베이스도 사용하지 않는다. 모든 영속 데이터는 로컬 CSV/JSON 파일로 관리한다.

6. **머신러닝 모델 학습 제외 (No ML Training in v1.0.0)**: 본 SPEC의 추천 알고리즘은 통계 기반 가중치 점수 모델로 한정한다. 신경망/딥러닝 기반 추천은 향후 별도 SPEC(SPEC-LOTTO-002 이후)에서 다룬다.

7. **다국어 UI 미지원**: 본 버전의 CLI 출력 및 도움말은 한국어로만 제공한다.

---

## Dependencies (의존성)

- **선행 조건**: 없음 (신규 SPEC)
- **후속 SPEC**: SPEC-LOTTO-002 (ML 기반 추천 — 향후 작성 예정)

---

## References (참조)

- 동행복권 공식 사이트: https://www.dhlottery.co.kr/lt645/result
- 통계 페이지: https://www.dhlottery.co.kr/lt645/stats
- 회차별 당첨 API: `https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={N}`
- EARS 형식 가이드: `.claude/skills/moai-workflow-spec/SKILL.md`
