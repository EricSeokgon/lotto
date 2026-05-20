# SPEC-LOTTO-001: 구현 계획 (Implementation Plan)

본 문서는 `SPEC-LOTTO-001` 한국 로또 번호 추천 시스템의 구현 계획을 정의한다. TDD(Test-Driven Development) 원칙에 따라 모든 단계는 **테스트 작성 → 실패 확인 → 최소 구현 → 테스트 통과 → 리팩토링** 순서로 진행한다.

---

## 1. 개발 방법론 (Methodology)

- **개발 모드**: TDD (Test-First)
- **개발 사이클**: RED → GREEN → REFACTOR
- **품질 기준**: TRUST 5 프레임워크 적용 (Tested 85%+, Readable, Unified, Secured, Trackable)
- **버전 관리**: 모든 단계는 별도 커밋으로 분리하며 Conventional Commits 규칙을 따른다 (`feat:`, `test:`, `refactor:` 등)
- **검증 도구**: `pytest` (단위/통합 테스트), `pytest-cov` (커버리지), `ruff` (린트/포맷), `mypy --strict` (타입 검증)

---

## 2. 단계별 구현 계획 (Implementation Phases)

전체 구현은 우선순위 기반 6단계로 구성된다. 시간 단위 예측은 사용하지 않으며, 각 단계는 다음 단계의 선행 조건이다.

### Phase 1: 프로젝트 스캐폴딩 및 데이터 모델 정의 (우선순위: High)

**목표**: 프로젝트 구조 확립, 데이터 모델 클래스 정의, 테스트 인프라 구축.

**작업 항목**:
- `pyproject.toml` 작성 (의존성 핀, ruff/mypy/pytest 설정)
- 디렉토리 구조 생성: `lotto/`, `tests/`, `data/`
- `lotto/__init__.py` 및 `lotto/models.py` 골격 작성
- 데이터 모델 정의: `DrawResult`, `Statistics`, `Recommendation` (Pydantic 또는 `@dataclass`)
- `tests/test_models.py` 작성 — 모델 직렬화/역직렬화, 유효성 검증 테스트
- 공통 픽스처 (`tests/conftest.py`) 정의 — 샘플 회차 데이터, 임시 데이터 디렉토리

**산출물**:
- `lotto/models.py`
- `tests/test_models.py` (전부 통과)
- `pyproject.toml`, `ruff.toml`, `mypy.ini`

**완료 조건**: `pytest tests/test_models.py` 전 케이스 통과, `ruff check`/`mypy --strict` 0 오류.

---

### Phase 2: 데이터 수집 모듈 (Collector) (우선순위: High)

**목표**: 동행복권 API에서 회차별 당첨 번호를 수집하고 CSV로 저장하는 기능 구현.

**작업 항목**:
- `tests/test_collector.py` 작성 (테스트 우선)
  - 정상 응답 파싱 테스트 (`requests-mock` 사용)
  - HTTP 실패 시 재시도 로직 테스트
  - `returnValue != "success"` 처리 테스트
  - 5회 연속 실패 시 abort 테스트
  - 요청 간 200ms 지연 검증 테스트 (`time.sleep` 모킹)
  - 신규 회차만 추가하는 증분 수집 테스트
  - `--full` 모드의 전체 재수집 테스트
- `lotto/collector.py` 구현
  - `LottoCollector` 클래스: `fetch_round(drwNo)`, `fetch_latest()`, `save_to_csv()`
  - 지수 백오프 재시도 (`backoff` 패턴, 1s/2s/4s)
  - 진행률 표시는 Phase 6에서 CLI 통합 시 추가

**산출물**:
- `lotto/collector.py`
- `tests/test_collector.py`
- 샘플 응답 픽스처 `tests/fixtures/api_response.json`

**완료 조건**: 수집 모듈 테스트 전 케이스 통과, 커버리지 85% 이상.

---

### Phase 3: 통계 분석 모듈 (Analyzer) (우선순위: High)

**목표**: 수집된 CSV 데이터를 분석하여 빈도/최근 패턴/연속 패턴/동반 출현을 산출하는 기능 구현.

**작업 항목**:
- `tests/test_analyzer.py` 작성
  - 출현 빈도 정확성 검증 (사전 정의된 mini-dataset 기준)
  - 최근 N회차 출현 패턴 정확성 검증
  - 연속 출현/배제 streak 계산 검증
  - 동반 출현 쌍 계산 검증 (조합 C(6,2) = 15쌍/회차)
  - 데이터 부재 시 에러 처리 검증
  - `--recent-window`가 전체 회차 수보다 클 때 경고 출력 검증
- `lotto/analyzer.py` 구현
  - `LottoAnalyzer` 클래스: `load_draws()`, `compute_frequency()`, `compute_recent_pattern(window)`, `compute_consecutive_pattern()`, `compute_pair_analysis(top_n)`, `to_json()`
  - `pandas`/`numpy` 활용으로 벡터화 연산
  - 결과는 `data/stats.json`으로 직렬화

**산출물**:
- `lotto/analyzer.py`
- `tests/test_analyzer.py`
- `tests/fixtures/mini_draws.csv` (검증용 소규모 데이터)

**완료 조건**: 분석 모듈 테스트 전 케이스 통과, 1,200회차 기준 5초 이내 처리 (성능 벤치마크 테스트 포함).

---

### Phase 4: 번호 추천 모듈 (Recommender) (우선순위: High)

**목표**: 통계 결과를 기반으로 가중치 점수 모델을 적용해 N개의 추천 조합을 생성.

**작업 항목**:
- `tests/test_recommender.py` 작성
  - 추천 결과가 항상 6개의 서로 다른 1~45 정수임을 검증
  - 같은 실행 내 추천 세트 간 중복 없음 검증
  - 기본 5세트 생성 검증
  - `--count N` 옵션 검증 (경계값: 1, 20)
  - 커스텀 가중치 검증 (음수/합계 0 거부)
  - 통계 데이터 부재 시 에러 처리
  - 비제로 점수 번호가 6개 미만일 때 fallback 동작 검증
  - 5가지 전략 라벨(`고빈도`, `저빈도`, `균형`, `최근편향`, `동반패턴`) 모두 사용되는지 검증
- `lotto/recommender.py` 구현
  - `LottoRecommender` 클래스: `compute_scores()`, `generate(count, strategy)`, `generate_all(count)`
  - 점수 계산식: `score(n) = w_freq × freq_norm(n) + w_recent × recent_norm(n) + w_pair × pair_norm(n) - w_consec × consec_penalty(n)`
  - 정규화: min-max scaling (각 지표를 [0, 1]로)
  - 전략별 가중치 프리셋 + 사용자 오버라이드 지원
  - 결정론적 테스트를 위한 시드 주입 가능 (`random.Random(seed)`)

**산출물**:
- `lotto/recommender.py`
- `tests/test_recommender.py`

**완료 조건**: 추천 모듈 테스트 전 케이스 통과, 5세트 생성 2초 이내, 커버리지 85% 이상.

---

### Phase 5: 시뮬레이션 모듈 (Simulator) (우선순위: Medium)

**목표**: 추천 알고리즘을 과거 회차에 적용해 매칭 등급 분포와 hit rate를 산출하는 백테스팅 기능 구현.

**작업 항목**:
- `tests/test_simulator.py` 작성
  - 회차 R 추천 생성 시 회차 R 데이터를 사용하지 않음을 검증 (look-ahead bias 방지 테스트)
  - 매칭 등급 카운트 정확성 검증 (5등, 4등, 3등, 2등, 1등)
  - hit rate 계산 정확성 검증
  - `--rounds N` 옵션 검증
  - `--output FILE` 결과 직렬화 검증
- `lotto/simulator.py` 구현
  - `LottoSimulator` 클래스: `evaluate_round(round_no)`, `run(rounds, count_per_round)`, `summarize()`, `save_report(path)`
  - 회차별로 `Analyzer`를 재호출하여 해당 회차 이전 데이터만 사용 (causal slicing)
  - 매칭 등급 산정: 6=1등, 5+bonus=2등, 5=3등, 4=4등, 3=5등
  - 결과 리포트는 `rich.Table`로 콘솔 출력 + JSON 저장 옵션

**산출물**:
- `lotto/simulator.py`
- `tests/test_simulator.py`

**완료 조건**: 시뮬레이션 모듈 테스트 전 케이스 통과, look-ahead bias 방지 검증 통과.

---

### Phase 6: CLI 통합 및 통합 테스트 (우선순위: High)

**목표**: 4개 서브커맨드를 `typer` 기반 단일 진입점으로 통합하고 종단 간 통합 테스트 수행.

**작업 항목**:
- `tests/test_cli.py` 작성
  - `typer.testing.CliRunner`로 각 서브커맨드 호출 검증
  - 한국어 도움말 출력 검증
  - 유효하지 않은 옵션 값 처리 검증 (`--count 0`, `--count 100`)
  - 종료 코드 검증 (0/1/2)
  - 진행률 표시 동작 검증 (모킹)
- `main.py` 구현
  - `typer.Typer()` 앱 정의, 4개 명령 등록
  - `rich.console.Console`/`rich.progress.Progress` 통합
  - 각 명령은 해당 도메인 모듈을 호출하는 얇은 래퍼 (Thin Command Pattern)
- 통합 테스트 `tests/test_integration.py`
  - 종단 간 시나리오: collect → analyze → recommend → simulate (소규모 mock 데이터)
  - 데이터 디렉토리 격리 (`tmp_path` 픽스처)

**산출물**:
- `main.py`
- `tests/test_cli.py`
- `tests/test_integration.py`

**완료 조건**: 모든 CLI 시나리오 통과, 전체 커버리지 85% 이상, `acceptance.md`의 모든 Given/When/Then 시나리오 통과.

---

## 3. 기술적 접근 (Technical Approach)

### 3.1 아키텍처 패턴

- **선형 파이프라인 (Linear Pipeline)**: Collect → Analyze → Recommend → Simulate. 각 단계의 출력이 다음 단계의 입력 파일로 명확히 분리되어 있어 단계별 독립 실행 및 재현성을 보장한다.
- **얇은 명령 패턴 (Thin Command Pattern)**: `main.py`는 인수 파싱과 도메인 모듈 호출만 담당하며 비즈니스 로직을 포함하지 않는다.
- **도메인 모듈 분리**: 각 도메인(`collector`, `analyzer`, `recommender`, `simulator`)은 독립 단위 테스트가 가능하며 상호 직접 의존하지 않고 파일 시스템을 통해서만 데이터를 주고받는다.

### 3.2 데이터 흐름

```
[dhlottery API] --(collector)--> data/draws.csv
                                       |
                                       v
                                 (analyzer)
                                       |
                                       v
                                 data/stats.json
                                       |
                                       v
                                 (recommender)
                                       |
                                       v
                                 콘솔 출력 (rich.Table)
                                       |
                                       v
                                 (simulator)
                                       |
                                       v
                                 콘솔 + data/report.json
```

### 3.3 핵심 기술 선택 (Technology Choices with Rationale)

| 항목 | 선택 | 근거 |
|------|------|------|
| 언어 | Python 3.11+ | 표준 라이브러리 풍부, 데이터 분석 생태계 성숙, 사용자 학습 곡선 낮음 |
| HTTP 클라이언트 | `requests` | 동기 호출 단순성, 표준 채택, 모킹 도구 풍부 (`requests-mock`) |
| CLI 프레임워크 | `typer` | 타입 힌트 기반 자동 문서화, `rich`와 자연 통합, 한국어 도움말 지원 우수 |
| 콘솔 출력 | `rich` | 테이블/진행률/색상 표현이 한 번에 가능, MoAI 표준 |
| 데이터 처리 | `pandas`, `numpy` | 1,200+ 회차 데이터의 벡터화 연산으로 성능 목표 달성 |
| 데이터 모델 | `dataclasses` + `pydantic`(선택) | 표준 라이브러리 우선, 검증이 필요한 경계에서만 pydantic |
| 테스트 | `pytest`, `pytest-cov`, `requests-mock` | 사실상 표준, 픽스처/파라미터화 강력 |
| 린트/포맷 | `ruff` | 빠른 속도, 통합 린터+포매터, MoAI 표준 |
| 타입 검증 | `mypy --strict` | 정적 타입 안전성, TRUST 5의 Readable 충족 |

### 3.4 저장소 구조 (계획)

```
lotto/
├── main.py                      # CLI 진입점 (typer)
├── lotto/
│   ├── __init__.py
│   ├── models.py                # DrawResult, Statistics, Recommendation
│   ├── collector.py             # API 수집
│   ├── analyzer.py              # 통계 분석
│   ├── recommender.py           # 추천 생성
│   └── simulator.py             # 백테스팅
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── api_response.json
│   │   └── mini_draws.csv
│   ├── test_models.py
│   ├── test_collector.py
│   ├── test_analyzer.py
│   ├── test_recommender.py
│   ├── test_simulator.py
│   ├── test_cli.py
│   └── test_integration.py
├── data/
│   ├── draws.csv                # collect 산출물
│   ├── stats.json               # analyze 산출물
│   └── report.json              # simulate 산출물(옵션)
├── pyproject.toml
├── ruff.toml
├── mypy.ini
└── README.md
```

---

## 4. 의존성 명세 (Dependencies with Pinned Versions)

```toml
# pyproject.toml [project.dependencies]
"requests>=2.31,<3.0"
"pandas>=2.1,<3.0"
"numpy>=1.26,<2.0"
"typer>=0.12,<1.0"
"rich>=13.7,<14.0"

# pyproject.toml [project.optional-dependencies.dev]
"pytest>=8.0,<9.0"
"pytest-cov>=4.1,<5.0"
"requests-mock>=1.11,<2.0"
"ruff>=0.4,<1.0"
"mypy>=1.10,<2.0"
```

핀 정책: 메이저 버전 상한을 고정하여 breaking change로부터 보호하되, 마이너/패치는 자유 업데이트 허용.

---

## 5. 리스크 분석 (Risk Analysis)

| 리스크 ID | 설명 | 영향 | 발생 가능성 | 대응 방안 |
|-----------|------|------|-------------|-----------|
| R-01 | 동행복권 API 요청 빈도 제한(rate limit) | 수집 중단 | Medium | 200ms 간격 강제 (REQ-COLLECT-06), 3회 재시도 + 지수 백오프 |
| R-02 | API 응답 JSON 스키마 변경 | 수집 모두 실패 | Low | `returnValue` 필드 검증, 알 수 없는 필드는 무시, 변경 감지 테스트 추가 |
| R-03 | 시뮬레이션의 look-ahead bias | 평가 결과 부풀려짐 | Medium | 회차별 causal slicing 강제, 전용 단위 테스트로 회귀 방지 (REQ-SIMULATE-05) |
| R-04 | 1,200+ 회차 처리 시 메모리/시간 초과 | UX 저하 | Low | pandas 벡터화 연산, 성능 벤치마크 테스트로 회귀 감지 |
| R-05 | 가중치 점수 계산 시 0-나눗셈 또는 NaN 전파 | 추천 실패 | Low | `compute_scores`에서 분모 0 가드, NaN→0 변환, fallback 경로 (REQ-RECOMMEND-07) |
| R-06 | 사용자가 잘못된 가중치 입력 (음수, 합 0) | 추천 무의미 | Medium | CLI 단계에서 입력 검증 후 종료 코드 2로 거부 (REQ-CLI-04) |
| R-07 | 사용자가 추천 결과를 실제 당첨 보장으로 오해 | 사용자 클레임 | Medium | 모든 추천 출력에 면책 문구 명시 (Exclusion 1) |
| R-08 | Python 버전 호환성 (3.11 미만 환경) | 실행 불가 | Low | `pyproject.toml`에 `python_requires=">=3.11"` 명시, CLI 시작 시 버전 체크 |

---

## 6. 마일스톤 (Milestones, 우선순위 기반)

- **M1 (Priority High)**: Phase 1 + Phase 2 완료 — 데이터 수집 가능 상태
- **M2 (Priority High)**: Phase 3 + Phase 4 완료 — 추천까지 동작하는 최소 가치 제품(MVP)
- **M3 (Priority High)**: Phase 6 완료 — CLI 통합으로 사용자 인수 가능 상태
- **M4 (Priority Medium)**: Phase 5 완료 — 시뮬레이션으로 추천 알고리즘 검증 가능

> 시간 단위 예측(예: "1주", "3일")은 본 계획에 사용하지 않는다. 마일스톤은 완료 우선순위로만 정렬한다.

---

## 7. 품질 게이트 (Quality Gates)

각 Phase 종료 시 다음 게이트를 통과해야 다음 Phase로 진행한다.

- [ ] `pytest` 해당 단계 테스트 100% 통과
- [ ] `pytest --cov` 커버리지 85% 이상
- [ ] `ruff check .` 0 오류
- [ ] `mypy --strict lotto/ main.py` 0 오류
- [ ] 모든 신규 공개 함수에 docstring 및 타입 힌트 작성
- [ ] Conventional Commits 규칙 준수

---

## 8. 향후 확장 (Future Extensions, 본 SPEC 범위 밖)

- SPEC-LOTTO-002: 머신러닝 기반 추천 (LSTM, Transformer 시도)
- SPEC-LOTTO-003: 웹 UI 추가 (FastAPI + 단순 프론트엔드)
- SPEC-LOTTO-004: 다국어 출력 지원 (i18n)

---

## References

- 상세 요구사항: `spec.md`
- 인수 기준: `acceptance.md`
- 압축 SPEC (run 단계용): `spec-compact.md`
