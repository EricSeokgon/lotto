---
id: SPEC-WEB-001
version: "1.0.0"
status: planned
created: "2026-05-20"
updated: "2026-05-20"
author: ircp
---

# SPEC-WEB-001: 구현 계획 (Implementation Plan)

본 문서는 SPEC-WEB-001(로또 통계 웹 대시보드)을 구현하기 위한 단계별 계획이다. TDD 방법론에 따라 각 단계에서 테스트를 먼저 작성하고 구현을 진행한다(`.moai/config/sections/quality.yaml`의 기본 `development_mode: tdd` 가정).

상세 요구사항은 `spec.md`, 인수 기준은 `acceptance.md`를 참조한다.

---

## Implementation Strategy (구현 전략)

### Core Approach

- **Add-only, no-modify**: 기존 `lotto/{collector,analyzer,recommender,simulator,models}.py`는 한 줄도 수정하지 않는다. 모든 신규 코드는 `lotto/web/` 디렉토리와 `tests/test_web_*.py`에 집중한다.
- **Thin web layer**: 라우트는 데이터 변환·전달만 수행하고 비즈니스 로직은 `lotto/web/data.py`를 거쳐 기존 모듈에 위임한다.
- **Async-safe by default**: 모든 라우트를 `async def`로 정의하고, 블로킹 호출은 `BackgroundTasks` 또는 `asyncio.to_thread()`로 격리한다.
- **CDN-only frontend**: Tailwind CSS, Chart.js, Noto Sans KR 모두 CDN으로 로드한다. Node.js/npm 빌드 환경을 도입하지 않는다.
- **Server-side rendering first**: 모든 차트 데이터는 Jinja2가 `<script>` 안에 인라인 JSON으로 주입한다. 별도 fetch 호출 최소화로 초기 렌더 단순화.

### Technical Approach (How We Build It)

1. **Dependency layer**: `requirements.txt`에 4개 의존성(`fastapi`, `uvicorn`, `jinja2`, `aiofiles`) 추가. `pyproject.toml`도 동기화.
2. **App skeleton**: `lotto/web/app.py`에 FastAPI 인스턴스, `lifespan`, 라우터 등록, Jinja2 환경 구성.
3. **Data layer**: `lotto/web/data.py`에 5개 read 함수 + 1개 percentile 계산 함수 정의. 기존 모듈만 호출.
4. **Routes**: `lotto/web/routes/pages.py`(5개 HTML 라우트), `lotto/web/routes/api.py`(6개 JSON 라우트 + `/health`).
5. **Templates**: `base.html`(공통 레이아웃 + CDN + Chart.js defaults) + 5개 페이지 템플릿.
6. **CLI integration**: `lotto/cli.py`(또는 `main.py`)에 `web` 서브커맨드 추가.
7. **Tests**: 라우트 통합 테스트 + 데이터 레이어 단위 테스트 + 템플릿 렌더링 검증.

---

## Milestones (우선순위 기반, 시간 추정 없음)

각 마일스톤은 의존 관계 순서대로 실행하며, 동일 마일스톤 내 작업은 병렬 가능 여부를 명시한다.

### Milestone 1 — Foundation (Priority: High)

**목표**: 의존성 추가 및 빈 FastAPI 앱이 기동되는 최소 골격 확보.

작업:
- M1.1 `requirements.txt` 및 `pyproject.toml`에 `fastapi>=0.115`, `uvicorn>=0.29`, `jinja2>=3.1`, `aiofiles>=23.2` 추가
- M1.2 `lotto/web/__init__.py` 생성(빈 패키지 마커)
- M1.3 `lotto/web/app.py` 작성 — `FastAPI()` 인스턴스, `lifespan`, Jinja2 `Jinja2Templates` 설정, 라우터 자리만 마련
- M1.4 `lotto/web/routes/__init__.py`, `pages.py`(빈 라우터), `api.py`(빈 라우터)
- M1.5 `tests/test_web_app.py` — `TestClient(app)`로 `GET /health`가 200 반환하는지 검증(M2까지 미구현이므로 일단 skip 또는 stub)

완료 조건:
- `pip install -r requirements.txt`가 깨지지 않고 성공
- `python -c "from lotto.web.app import app; print(app)"`가 에러 없이 출력
- `uvicorn lotto.web.app:app --port 8000`으로 빈 서버가 기동(404만 반환해도 OK)

### Milestone 2 — Data Access Layer (Priority: High)

**목표**: 기존 `lotto/` 모듈을 호출하는 데이터 레이어 완성. 라우트와 무관하게 단독 테스트 가능.

작업:
- M2.1 `lotto/web/data.py` 작성:
  - `get_draws() -> list[DrawResult]` → `collector.LottoCollector().load_existing()`
  - `get_stats() -> Statistics` → `analyzer.LottoAnalyzer().load_stats()`
  - `get_recommendations(count: int) -> list[Recommendation]` → `recommender.LottoRecommender().recommend(count)`
  - `get_simulation(rounds: int) -> SimulationResult` → `simulator.LottoSimulator().simulate(rounds)`
  - `get_data_status() -> DataStatus` (Pydantic) — `data/draws.csv`, `data/stats.json` 존재 여부 + mtime
  - `compute_frequency_percentiles(stats: Statistics) -> dict[int, float]` — 빈도 percentile 계산(tie-break: 번호 오름차순)
  - `interpolate_color(percentile: float) -> str` — `#E2E8F0`(0.0) ↔ `#3B82F6`(1.0) 선형 보간, hex 문자열 반환
- M2.2 `tests/test_web_data.py` — 6개 함수 각각의 단위 테스트
  - `compute_frequency_percentiles`: 단조성, 경계값(min/max), 동률 처리
  - `interpolate_color`: `0.0 → #E2E8F0`, `1.0 → #3B82F6`, `0.5`의 중간 색상 검증
  - `get_*` 함수들은 픽스처 데이터(`tests/fixtures/mini_draws.csv`, `mini_stats.json`)로 검증
- M2.3 `tests/fixtures/web_mini_stats.json` 픽스처 추가(45개 번호 빈도 포함)

완료 조건:
- `pytest tests/test_web_data.py` 전부 PASS
- `compute_frequency_percentiles`와 `interpolate_color`가 결정적(determinism) 동작

### Milestone 3 — Page Routes and Templates (Priority: High)

**목표**: 5개 페이지 라우트와 base.html 골격을 완성하여 브라우저에서 시각적으로 확인 가능.

작업:
- M3.1 `lotto/web/templates/base.html`:
  - `<head>`: Tailwind CDN, Chart.js v4 CDN, Noto Sans KR Google Fonts, Tailwind `tailwind.config` 인라인 디자인 토큰, Chart.js 전역 defaults
  - `<body>`: 헤더(로고 텍스트 + 마지막 수집 일자), 4개 탭 nav, `{% block content %}{% endblock %}`, 면책 푸터
- M3.2 `lotto/web/templates/index.html` — 대시보드 홈(마지막 회차 요약, 4개 탭 진입 카드)
- M3.3 `lotto/web/templates/collect.html` — 수집 상태(회차 범위, 파일 크기, mtime)
- M3.4 `lotto/web/templates/analyze.html` — **시그니처 빈도 그라데이션 배지(6×8 격자) + Chart.js horizontal bar + 페어 테이블 + 최근 히트맵**
- M3.5 `lotto/web/templates/recommend.html` — N개 추천 카드(원형 번호 배지 + 전략 라벨 + 신뢰도)
- M3.6 `lotto/web/templates/simulate.html` — 도넛 차트 + 등급 테이블 + 면책 카드
- M3.7 `lotto/web/routes/pages.py` — 5개 `async def` 라우트, `data.py` 호출 후 컨텍스트 전달
- M3.8 `tests/test_web_pages.py`:
  - 5개 페이지가 HTTP 200 반환
  - HTML 응답에 핵심 마커 문자열 존재 검증(면책 문구, 탭 링크, 시그니처 배지 격자, Chart.js CDN URL, Tailwind CDN URL)
  - 데이터 누락 시 안내 메시지 노출, 크래시 없음

완료 조건:
- `uvicorn lotto.web.app:app --reload`로 기동 후 브라우저에서 5개 페이지가 모두 시각적으로 렌더링됨
- `pytest tests/test_web_pages.py` 전부 PASS
- `analyze.html`에서 빈도 그라데이션 배지가 6열 × 8행 격자로 표시되며 색상이 시각적으로 단조 증가하는 것이 확인됨

### Milestone 4 — JSON API Routes (Priority: Medium)

**목표**: 6개 API 엔드포인트 + `/health` 완성. 페이지와 독립적으로 호출 가능.

작업:
- M4.1 `lotto/web/routes/api.py`:
  - `GET /health` → 데이터 파일 존재 상태 JSON
  - `GET /api/draws` → DrawResult 리스트
  - `GET /api/stats` → Statistics
  - `GET /api/recommendations?count={N}` (Query 검증: `1 ≤ N ≤ 20`)
  - `GET /api/simulation?rounds={K}` (Query 검증: `1 ≤ K ≤ 100`)
  - `POST /api/collect` → `BackgroundTasks.add_task(LottoCollector().collect_new)` + `{"status": "started"}`
  - `POST /api/analyze` → `BackgroundTasks.add_task(LottoAnalyzer().analyze)` + `{"status": "started"}`
- M4.2 데이터 누락 시 `HTTPException(503, "data_unavailable")` 처리(`Depends`로 공통화 가능)
- M4.3 `tests/test_web_api.py`:
  - 정상 JSON 응답 구조 검증
  - 경계값 검증(`count=0`, `count=21`, `rounds=0`, `rounds=101` → 422)
  - 데이터 누락 시 503
  - `POST /api/collect` 호출 시 즉시 응답 + BackgroundTasks 등록 검증(monkeypatch로 `collect_new` mock)

완료 조건:
- `curl localhost:8000/api/stats` 등 모든 엔드포인트가 정상 JSON 반환
- `pytest tests/test_web_api.py` 전부 PASS
- BackgroundTasks 등록이 mock으로 검증됨(실제 API 호출 방지)

### Milestone 5 — CLI `web` Subcommand (Priority: Medium)

**목표**: `python main.py web [--host] [--port] [--reload]` 명령 제공.

작업:
- M5.1 `lotto/cli.py`(또는 `main.py` Typer 앱)에 `web` 서브커맨드 추가:
  - `--host: str = "127.0.0.1"`
  - `--port: int = 8000`
  - `--reload: bool = False`
  - 내부에서 `uvicorn.run("lotto.web.app:app", host=host, port=port, reload=reload)` 호출
- M5.2 `tests/test_cli_web.py`(또는 기존 `test_cli.py`에 추가) — Typer `CliRunner`로 서브커맨드 등록 여부, `--help` 출력에 `web` 명령 포함 여부 검증. 실제 서버 기동은 mock으로 검증.
- M5.3 `README.md` 업데이트(웹 대시보드 사용법 섹션 추가)

완료 조건:
- `python main.py --help`에 `web` 명령이 표시됨
- `python main.py web --help`에 옵션 3개가 한국어 도움말로 표시됨
- `python main.py web --port 8080`으로 실제 기동 확인(수동 수락 테스트)

### Milestone 6 — Polish, Coverage, Documentation (Priority: Low → Required for completion)

**목표**: 테스트 커버리지 ≥ 85%, 디자인 검토, 회귀 방지.

작업:
- M6.1 `pytest --cov=lotto.web --cov-report=term-missing tests/test_web_*.py` 실행, 미커버 코드 보완
- M6.2 기존 SPEC-LOTTO-001 테스트 전체 회귀 실행: `pytest tests/test_{models,collector,analyzer,recommender,simulator,cli,integration}.py` 모두 통과
- M6.3 디자인 검토: 색상 팔레트 hex 코드가 `design-direction.md`의 토큰과 일치하는지 확인(특히 빨강/금색 미사용)
- M6.4 P95 응답 시간 측정(`pytest-benchmark` 또는 단순 timer 픽스처)
- M6.5 면책 문구가 5개 페이지 모두에 존재하는지 검증하는 통합 테스트
- M6.6 `CHANGELOG.md`에 SPEC-WEB-001 항목 추가

완료 조건:
- 신규 `lotto/web/` 모듈 커버리지 ≥ 85%
- 전체 테스트 카운트: 기존 77개 + 신규 30~40개(예상) = 107~117개, 모두 PASS
- 기존 CLI 4개 명령(`collect/analyze/recommend/simulate`) 동작 회귀 없음(AC-024, AC-025)

---

## File Creation Order and Dependencies (파일 생성 순서)

| 순서 | 파일 | 마일스톤 | 의존 파일 |
|------|------|----------|-----------|
| 1 | `requirements.txt` (수정) | M1 | 없음 |
| 2 | `pyproject.toml` (수정) | M1 | 없음 |
| 3 | `lotto/web/__init__.py` | M1 | 없음 |
| 4 | `lotto/web/app.py` | M1 | 1,2 |
| 5 | `lotto/web/routes/__init__.py` | M1 | 3 |
| 6 | `lotto/web/routes/pages.py` (빈 라우터) | M1 | 5 |
| 7 | `lotto/web/routes/api.py` (빈 라우터) | M1 | 5 |
| 8 | `tests/test_web_app.py` | M1 | 4 |
| 9 | `lotto/web/data.py` | M2 | 기존 `lotto/{collector,analyzer,recommender,simulator,models}.py` |
| 10 | `tests/fixtures/web_mini_stats.json` | M2 | 없음 |
| 11 | `tests/test_web_data.py` | M2 | 9, 10 |
| 12 | `lotto/web/templates/base.html` | M3 | 없음 |
| 13 | `lotto/web/templates/index.html` | M3 | 12 |
| 14 | `lotto/web/templates/collect.html` | M3 | 12 |
| 15 | `lotto/web/templates/analyze.html` | M3 | 12 |
| 16 | `lotto/web/templates/recommend.html` | M3 | 12 |
| 17 | `lotto/web/templates/simulate.html` | M3 | 12 |
| 18 | `lotto/web/routes/pages.py` (구현) | M3 | 9, 13–17 |
| 19 | `tests/test_web_pages.py` | M3 | 18 |
| 20 | `lotto/web/routes/api.py` (구현) | M4 | 9 |
| 21 | `tests/test_web_api.py` | M4 | 20 |
| 22 | `main.py` 또는 `lotto/cli.py` (수정) | M5 | 4 |
| 23 | `tests/test_cli_web.py` | M5 | 22 |
| 24 | `README.md` (수정) | M5 | 22 |
| 25 | `CHANGELOG.md` (수정) | M6 | 모든 마일스톤 완료 |
| 26 | `lotto/web/static/.gitkeep` | M3 | 없음 (StaticFiles 마운트용 빈 디렉토리) |

**총 신규 파일**: 약 20개 (코드 11개 + 템플릿 6개 + 테스트 5개 + 픽스처 1개 + 정적 자원 1개)
**수정 파일**: 3개 (`requirements.txt`, `pyproject.toml`, `main.py`/`lotto/cli.py`, `README.md`, `CHANGELOG.md`)

---

## TDD Approach (테스트 우선 개발)

각 마일스톤에서 RED → GREEN → REFACTOR 사이클을 적용한다.

### Test Pyramid

| 레이어 | 도구 | 대상 | 예상 테스트 수 |
|--------|------|------|---------------|
| Unit | pytest | `data.py`의 percentile/color/get_* 함수 | 12~15개 |
| Integration (route) | `httpx.AsyncClient` 또는 `TestClient` | 5 페이지 + 7 API(`/health` 포함) | 18~22개 |
| Template smoke | `TestClient` + HTML 문자열 매칭 | 핵심 마커(면책, 탭, 그라데이션 배지) | 5~8개 |
| CLI | Typer `CliRunner` + mock | `web` 서브커맨드 등록 | 2~3개 |
| **합계 (신규)** | | | **37~48개** |

### Coverage Target

- `lotto/web/` 모듈 커버리지: **≥ 85%** (REQ-WEB-TEST-03)
- 전체 프로젝트 커버리지: 기존 85.25%를 유지하거나 상향
- 기존 `lotto/{collector,analyzer,recommender,simulator,models}.py` 변경 없음 → 회귀 위험 0(AC-024)

### Test Fixtures

- 기존 `tests/fixtures/mini_draws.csv`(3회차) 재사용
- 신규 `tests/fixtures/web_mini_stats.json` — 45개 번호 빈도 + 페어 데이터 포함(percentile 함수 검증용)
- `conftest.py`에 `tmp_path` 기반 `data/` 디렉토리 임시 픽스처 추가(데이터 누락 시나리오 검증용)

---

## Estimated Counts (정량 목표)

| 항목 | 목표 |
|------|------|
| 신규 Python 모듈 | 6개 (`__init__.py × 2`, `app.py`, `data.py`, `pages.py`, `api.py`) |
| 신규 Jinja2 템플릿 | 6개 (`base.html` + 5 페이지) |
| 신규 테스트 파일 | 5개 (`test_web_app.py`, `test_web_data.py`, `test_web_pages.py`, `test_web_api.py`, `test_cli_web.py`) |
| 신규 테스트 케이스 | 37~48개 |
| 기존 코드 수정 | 0줄 (`lotto/{collector,analyzer,recommender,simulator,models}.py`) |
| CLI 명령 추가 | 1개 (`web`) |
| 코드 라인 추가(Python, 추정) | 약 600~800줄 |
| 코드 라인 추가(HTML/Jinja2, 추정) | 약 400~600줄 |

---

## Risks and Mitigations (계획 단계 리스크)

| 리스크 | 영향 | 완화 방안 |
|--------|------|----------|
| **R1. 비동기 안전성 위반** — `async def` 안에서 동기 `requests.get` 또는 `pandas.read_csv` 호출이 이벤트 루프 차단 | 동시 요청 처리 불가 | 모든 블로킹 호출은 `asyncio.to_thread()` 또는 `BackgroundTasks` 강제. 리뷰 체크리스트에 명시. M4 통합 테스트에서 `asyncio.run` 동시 호출로 검증 |
| **R2. 파일 I/O 경쟁** — `POST /api/collect` 백그라운드 실행 중 `GET /api/draws` 호출 시 CSV 부분 쓰기 상태 노출 | 잘못된 데이터 일시 표시 | 기존 `collect_new`가 atomic write(임시 파일 → rename)인지 확인. 미흡 시 `data.py`에서 mtime 락 또는 fsync 확인 추가. 본 SPEC 범위에서는 best-effort, 후속 SPEC 후보 |
| **R3. Chart.js CDN 장애** | 차트 렌더링 실패 | README에 인터넷 연결 필수임을 명시. 콘솔 에러 메시지를 사용자에게 보이지 않게 try/catch 처리(차트 영역에 "차트를 불러올 수 없습니다" fallback) |
| **R4. 그라데이션 색상 보간 정확성** | 시그니처 시각 요소 일관성 저하 | `interpolate_color` 함수의 경계값(0.0, 0.25, 0.5, 0.75, 1.0)에 대한 단위 테스트 작성. tie-break 규칙(동률 시 번호 오름차순)을 문서화하고 테스트 |
| **R5. 기존 모듈 시그니처 가정 어긋남** — 예: `LottoRecommender.recommend(count=N)`의 실제 시그니처가 다름 | 데이터 레이어 깨짐 | M2 첫 작업에서 기존 `lotto/{collector,analyzer,recommender,simulator}.py`의 공개 API를 grep으로 재확인하고 어댑터 함수에 명시 |
| **R6. Tailwind CDN 버전 변경으로 인한 스타일 깨짐** | UI 회귀 | Tailwind CDN URL을 버전 핀 가능한 형태로 사용 가능한지 검토. 어렵다면 README에 "Tailwind v3 기준" 명시 |
| **R7. 데이터 파일 부재 상태에서 첫 실행** | 빈 페이지로 사용자가 혼란 | REQ-WEB-SERVER-04와 AC-010에 의해 안내 메시지 노출 명시. 각 페이지마다 "데이터를 먼저 수집하세요. CLI: `python main.py collect`" 표시 |
| **R8. P95 응답 시간 초과(>500ms)** — 1,200회차 데이터 매 요청 파싱 시 | NFR-PERF 위반 | M2에서 `get_stats` 결과를 mtime 기반 메모리 캐시(`@lru_cache` 또는 수동) 적용. M6에서 측정 후 필요 시에만 캐시 도입 |
| **R9. 면책 문구 누락** | 사용자 오인 유도 | base.html 푸터에 단일 출처(single source of truth)로 배치, M6 통합 테스트에서 5개 페이지 모두 검증 |
| **R10. 사용자가 외부 노출(`--host 0.0.0.0`)로 실행 시 정보 노출** | 보안 표면 확대 | 기본값 `127.0.0.1` 강제, README에 외부 노출 시 위험 명시. 본 SPEC 범위에서는 인증 미도입(NFR-SEC) |

---

## Definition of Done (계획 단계 완료 정의)

본 plan.md는 다음 조건이 충족될 때 "구현 준비 완료"로 간주된다:

- [ ] 사용자가 spec.md, plan.md, acceptance.md를 검토하여 명시적으로 "Proceed" 승인
- [ ] 6개 마일스톤의 의존 관계가 명확하고, 동일 마일스톤 내 병렬 가능 작업이 식별됨
- [ ] 모든 REQ-* 요구사항이 최소 1개 마일스톤에 매핑됨(추적성)
- [ ] 모든 AC-* 인수 기준이 최소 1개 테스트 케이스로 검증 가능함이 확인됨(acceptance.md 참조)
- [ ] 10개 리스크에 대한 완화 방안이 마일스톤별 작업에 반영됨
- [ ] 기존 SPEC-LOTTO-001 코드가 수정되지 않는다는 제약(AC-024)이 모든 마일스톤에 보존됨

---

## Next Steps

1. 본 plan.md와 acceptance.md를 사용자가 검토
2. 승인 후 `/clear` 실행으로 컨텍스트 초기화
3. `/moai run SPEC-WEB-001`으로 구현 단계 시작
4. M1 → M2 → M3 → M4 → M5 → M6 순서로 진행, 각 마일스톤 완료 시 progress.md 업데이트

---

Version: 1.0.0
Status: Plan ready for review
