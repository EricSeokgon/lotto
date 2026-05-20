# SPEC-LOTTO-001: Compact Spec (Run 단계용 압축본)

본 문서는 `/moai run SPEC-LOTTO-001` 실행 시 컨텍스트 효율을 위해 사용되는 압축 SPEC이다. 정상 동작에 필요한 핵심 요구사항, 인수 기준, 파일 목록, 제외 범위만 추출한다. 상세 배경/근거는 `spec.md`, `plan.md`, `acceptance.md`를 참조한다.

---

## 1. REQ-* 요구사항 (EARS Format)

### REQ-COLLECT — 데이터 수집

- **REQ-COLLECT-01 (Ubiquitous)**: The system SHALL maintain all collected draw results in `data/draws.csv` with columns `drwNo, date, n1..n6, bonus`.
- **REQ-COLLECT-02 (Event-driven)**: WHEN `python main.py collect`, THE system SHALL fetch from `https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={N}` for all new rounds and append to CSV.
- **REQ-COLLECT-03 (Event-driven)**: WHEN `collect --full`, THE system SHALL re-collect all rounds after user confirmation.
- **REQ-COLLECT-04 (Unwanted)**: IF HTTP status ≠ 200 OR `returnValue ≠ "success"`, THEN retry 3 times with exponential backoff (1s/2s/4s).
- **REQ-COLLECT-05 (Unwanted)**: IF 5+ consecutive rounds fail, THEN abort with exit code 2, preserving previous data.
- **REQ-COLLECT-06 (State-driven)**: WHILE collecting sequentially, the system SHALL delay ≥200ms between requests.

### REQ-ANALYZE — 통계 분석

- **REQ-ANALYZE-01 (Ubiquitous)**: The system SHALL persist results to `data/stats.json` with sections `frequency, recent_pattern, consecutive_pattern, pair_analysis`.
- **REQ-ANALYZE-02 (Event-driven)**: WHEN `analyze`, THE system SHALL compute absolute/relative frequency for numbers 1~45 across all rounds.
- **REQ-ANALYZE-03 (Event-driven)**: WHEN analysis runs, THE system SHALL compute recent appearance pattern over last N rounds (default N=20, configurable via `--recent-window`).
- **REQ-ANALYZE-04 (Event-driven)**: WHEN analysis runs, THE system SHALL compute consecutive appearance/exclusion streaks per number.
- **REQ-ANALYZE-05 (Event-driven)**: WHEN analysis runs, THE system SHALL compute pair co-occurrence and store top 20 pairs.
- **REQ-ANALYZE-06 (Unwanted)**: IF `data/draws.csv` missing/empty, THEN print `당첨 데이터가 없습니다. 먼저 'collect' 명령을 실행하세요.` and exit code 1.
- **REQ-ANALYZE-07 (Unwanted)**: IF rounds < `--recent-window`, THEN warn and compute over available rounds.

### REQ-RECOMMEND — 번호 추천

- **REQ-RECOMMEND-01 (Ubiquitous)**: The system SHALL generate sets of exactly 6 distinct integers in [1, 45]; no two sets in one run are identical.
- **REQ-RECOMMEND-02 (Event-driven)**: WHEN `recommend`, THE system SHALL load `data/stats.json`, compute `score(n) = w_freq×freq_norm(n) + w_recent×recent_norm(n) + w_pair×pair_norm(n) − w_consec×consec_penalty(n)`, and produce 5 sets by default.
- **REQ-RECOMMEND-03 (Event-driven)**: WHEN `--count N` (1 ≤ N ≤ 20), THE system SHALL produce exactly N sets.
- **REQ-RECOMMEND-04 (Optional)**: WHERE `--weights w_freq,w_recent,w_pair,w_consec` provided, THE system SHALL use them if all non-negative and sum > 0; defaults (0.4, 0.3, 0.2, 0.1).
- **REQ-RECOMMEND-05 (Ubiquitous)**: The system SHALL display each set in ascending order with one strategy label from {`고빈도, 저빈도, 균형, 최근편향, 동반패턴`}.
- **REQ-RECOMMEND-06 (Unwanted)**: IF `data/stats.json` missing/malformed, THEN print `통계 데이터가 없습니다. 먼저 'analyze' 명령을 실행하세요.` and exit code 1.
- **REQ-RECOMMEND-07 (Complex)**: WHILE recommending, WHEN non-zero scored numbers < 6, THE system SHALL fall back to uniform random selection with a warning.

### REQ-SIMULATE — 시뮬레이션

- **REQ-SIMULATE-01 (Ubiquitous)**: The system SHALL evaluate recommendations against last K historical draws (default K=10) and output a summary report.
- **REQ-SIMULATE-02 (Event-driven)**: WHEN `simulate`, THE system SHALL generate per-round recommendations using only data available before that round (causal/look-ahead-safe).
- **REQ-SIMULATE-03 (Event-driven)**: WHEN `--rounds N`, THE system SHALL evaluate over last N rounds (1 ≤ N ≤ total).
- **REQ-SIMULATE-04 (Ubiquitous)**: The system SHALL report counts for 5등(3개)/4등(4개)/3등(5개)/2등(5+보너스)/1등(6개) and overall hit rate.
- **REQ-SIMULATE-05 (Unwanted)**: IF the algorithm uses round R data while predicting round R, THEN tests SHALL fail (look-ahead bias prevention).
- **REQ-SIMULATE-06 (Optional)**: WHERE `--output FILE` provided, THE system SHALL persist full report to JSON.

### REQ-CLI — CLI 인터페이스

- **REQ-CLI-01 (Ubiquitous)**: The system SHALL provide `typer`-based `main.py` with subcommands `collect, analyze, recommend, simulate`.
- **REQ-CLI-02 (Event-driven)**: WHEN `--help` invoked, THE system SHALL display Korean help text with usage/options/examples.
- **REQ-CLI-03 (Ubiquitous)**: The system SHALL render output via `rich` with Korean labels (tables, colors, progress bars).
- **REQ-CLI-04 (Unwanted)**: IF unknown subcommand or invalid option (e.g. `--count 0`, `--count 100`), THEN print Korean error and exit code 2.
- **REQ-CLI-05 (Event-driven)**: WHEN command completes, THE system SHALL exit 0 (success), 1 (validation error), or 2 (external/abort).
- **REQ-CLI-06 (State-driven)**: WHILE long-running operation in progress, THE system SHALL display `rich` progress bar with current/total/ETA.

---

## 2. Given-When-Then 인수 기준 (요약)

1. **수집 — 전체 히스토리**: GIVEN 첫 사용 / WHEN `collect --full` / THEN 1~1,200 모두 수집, CSV 생성, 200ms 간격 유지, exit 0.
2. **수집 — 일시 오류**: GIVEN 회차 503 HTTP 500 / WHEN `collect` / THEN 1s→2s→4s 3회 재시도, 실패 시 스킵하고 5회 연속 미만이므로 계속 진행.
3. **분석 — 빈도 정확성**: GIVEN mini-dataset 3회차 / WHEN `analyze` / THEN `stats.json` 생성, 번호 1 빈도=3, 번호 10=2, 번호 7=0, 상위 20 동반 쌍 기록.
4. **추천 — 형식/무결성**: GIVEN `stats.json` 존재 / WHEN `recommend` / THEN 5세트, 각 6개 정수 [1,45], 세트 내/세트 간 중복 없음, 오름차순, 전략 라벨, 면책 문구 출력.
5. **추천 — `--count` 검증**: WHEN `--count 0`/`--count 100` / THEN `1~20` 범위 에러, exit 2. WHEN `--count 10` / THEN 정확히 10세트.
6. **시뮬레이션 — 매칭 보고**: GIVEN 1,000회차 / WHEN `simulate --rounds 10` / THEN 회차 991~1000 각각에 대해 회차 이전 데이터만 사용해 추천 생성, 5등/4등/3등/2등/1등 카운트 및 hit rate 보고, exit 0.
7. **엣지 — 데이터 부재**: GIVEN `draws.csv` 없음 / WHEN `analyze` / THEN 한국어 안내 메시지, exit 1. GIVEN `stats.json` 없음 / WHEN `recommend` / THEN 한국어 안내, exit 1.
8. **엣지 — API 전체 장애**: GIVEN 모든 요청 HTTP 500 / WHEN `collect` / THEN 5회 연속 실패 시 abort, 기존 데이터 보존, exit 2.
9. **엣지 — recent-window 초과**: GIVEN 10회차만 존재, `--recent-window 50` / THEN 경고 후 가용 회차로 계산, exit 0.
10. **엣지 — look-ahead bias 방지**: 단위 테스트에서 회차 R 추천 생성 시 회차 R 데이터 누설이 발생하면 명시적으로 fail.
11. **엣지 — 커스텀 가중치**: 음수/합 0 가중치는 거부하고 exit 2. 정상 값은 사용해 5세트 출력.
12. **CLI — 한국어 도움말**: `--help`로 4개 명령 및 옵션이 한국어로 표시됨.

---

## 3. 파일 생성/수정 목록 (Files to Create/Modify)

### 신규 생성 (Create)

| 경로 | 목적 | 담당 Phase |
|------|------|-----------|
| `pyproject.toml` | 프로젝트 메타데이터, 의존성 핀, 도구 설정 | Phase 1 |
| `ruff.toml` | ruff 린트/포맷 설정 | Phase 1 |
| `mypy.ini` | mypy 엄격 모드 설정 | Phase 1 |
| `lotto/__init__.py` | 패키지 마커 | Phase 1 |
| `lotto/models.py` | `DrawResult`, `Statistics`, `Recommendation` 데이터 모델 | Phase 1 |
| `lotto/collector.py` | `LottoCollector` — API 수집 | Phase 2 |
| `lotto/analyzer.py` | `LottoAnalyzer` — 통계 분석 (frequency/recent/consecutive/pair) | Phase 3 |
| `lotto/recommender.py` | `LottoRecommender` — 가중치 점수 기반 추천 + 5가지 전략 | Phase 4 |
| `lotto/simulator.py` | `LottoSimulator` — causal-safe 백테스팅 | Phase 5 |
| `main.py` | `typer` 기반 CLI 진입점, 4개 서브커맨드 | Phase 6 |
| `tests/conftest.py` | 공통 픽스처 (mini-dataset, 임시 디렉토리) | Phase 1 |
| `tests/fixtures/api_response.json` | 동행복권 API 응답 샘플 | Phase 2 |
| `tests/fixtures/mini_draws.csv` | 검증용 3회차 mini-dataset | Phase 3 |
| `tests/test_models.py` | 모델 직렬화/검증 테스트 | Phase 1 |
| `tests/test_collector.py` | 수집/재시도/지연 테스트 | Phase 2 |
| `tests/test_analyzer.py` | 4종 통계 정확성 + 성능 벤치마크 | Phase 3 |
| `tests/test_recommender.py` | 추천 무결성, count 옵션, 가중치, fallback | Phase 4 |
| `tests/test_simulator.py` | 매칭 등급, look-ahead bias 방지 | Phase 5 |
| `tests/test_cli.py` | typer CliRunner 기반 CLI 테스트 | Phase 6 |
| `tests/test_integration.py` | collect→analyze→recommend→simulate 종단 간 | Phase 6 |
| `README.md` | 설치/사용법/면책 사항 (한국어) | Phase 6 |
| `.gitignore` | `data/`, `__pycache__/`, `.coverage`, `.mypy_cache/` 등 제외 | Phase 1 |

### 수정 대상

해당 없음 (전체 신규 프로젝트).

### 런타임 생성 (사용자 환경에서만 생성, Git 비추적)

- `data/draws.csv` — `collect` 산출물
- `data/stats.json` — `analyze` 산출물
- `data/report.json` — `simulate --output` 산출물 (선택)

---

## 4. Exclusions (제외 범위)

본 SPEC 범위에서 **명시적으로 제외**되는 항목 (구현 금지):

1. **당첨 보장 (No Winning Guarantee)** — 모든 추천 출력에 면책 문구 필수 표시.
2. **자동 구매 (No Auto-Purchase)** — 외부 결제/구매 시스템 연동 금지.
3. **GUI (No GUI)** — 웹/데스크톱/모바일 UI 구현 금지. CLI 전용.
4. **실시간 스트리밍 (No Real-time Streaming)** — 백그라운드 폴링, 푸시 알림 금지. `collect` 명령 시점에만 API 호출.
5. **외부 DB (No External Database)** — PostgreSQL/MySQL/MongoDB/Redis 등 사용 금지. 로컬 CSV/JSON 전용.
6. **ML 모델 학습 (No ML Training in v1.0.0)** — 신경망/딥러닝 추천은 별도 SPEC(SPEC-LOTTO-002 이후) 범위.
7. **다국어 UI (No i18n)** — CLI 출력 및 도움말은 한국어 전용.

---

## 5. 핵심 의존성 (Pinned)

```
requests   >=2.31,<3.0
pandas     >=2.1,<3.0
numpy      >=1.26,<2.0
typer      >=0.12,<1.0
rich       >=13.7,<14.0
pytest     >=8.0,<9.0   (dev)
pytest-cov >=4.1,<5.0   (dev)
requests-mock >=1.11,<2.0  (dev)
ruff       >=0.4,<1.0   (dev)
mypy       >=1.10,<2.0  (dev)
```

Python: `>=3.11,<3.13`

---

## 6. Quality Gate (요약)

- `pytest tests/ -v` 100% 통과
- 커버리지 ≥ 85%
- `ruff check .` 0 오류, `ruff format --check .` 통과
- `mypy --strict lotto/ main.py` 0 오류
- 성능: `analyze` 1,200회차 ≤ 5s, `recommend` 5세트 ≤ 2s
- 모든 신규 공개 함수에 docstring + 타입 힌트
- 모든 커밋이 Conventional Commits 준수, `SPEC-LOTTO-001` 참조

---

상세 내용 참조: `spec.md`, `plan.md`, `acceptance.md`
