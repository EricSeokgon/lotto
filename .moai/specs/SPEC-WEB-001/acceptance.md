---
id: SPEC-WEB-001
version: "1.0.0"
status: planned
created: "2026-05-20"
updated: "2026-05-20"
author: ircp
---

# SPEC-WEB-001: 인수 기준 (Acceptance Criteria)

본 문서는 SPEC-WEB-001(로또 통계 웹 대시보드)의 구현 완료를 판정하는 구체적이고 검증 가능한 인수 기준이다. 각 AC는 spec.md의 REQ-* 요구사항과 추적되며, Given-When-Then 형식으로 시나리오를 기술한다.

상세 요구사항은 `spec.md`, 구현 계획은 `plan.md`를 참조한다.

---

## How to Verify (검증 방법)

각 AC는 다음 검증 방식 중 하나를 명시한다:
- **Auto**: pytest 자동화 테스트로 검증
- **Manual**: 브라우저 또는 터미널 수동 확인
- **Visual**: 디자인 검토(시각적 일치성)

---

## Section 1: Server Lifecycle (서버 기동)

### AC-001: `python main.py web` CLI 명령 동작

**관련 REQ**: REQ-WEB-SERVER-01, REQ-WEB-SERVER-02

- [ ] `python main.py --help`을 실행하면 출력에 `web` 서브커맨드가 표시된다 (Auto)
- [ ] `python main.py web --help`을 실행하면 `--host`, `--port`, `--reload` 옵션이 한국어 도움말과 함께 표시된다 (Manual)
- [ ] `python main.py web`을 실행하면 `127.0.0.1:8000`에서 uvicorn이 기동된다 (Manual)
- [ ] `python main.py web --port 8080`을 실행하면 포트 8080에서 기동된다 (Manual)
- [ ] `python main.py web --reload`을 실행하면 `reload=True`로 uvicorn이 호출된다(mock 검증) (Auto)

**Given-When-Then**:
- GIVEN: 사용자가 프로젝트 루트에 위치
- WHEN: `python main.py web` 명령을 실행
- THEN: uvicorn 로그에 `Uvicorn running on http://127.0.0.1:8000`가 표시되고, 브라우저에서 해당 URL에 접속하면 index 페이지가 렌더링된다

### AC-002: `/health` 헬스 체크 엔드포인트

**관련 REQ**: REQ-WEB-SERVER-05

- [ ] `GET /health`이 HTTP 200을 반환한다 (Auto)
- [ ] 응답 JSON에 `status: "ok"` 필드가 포함된다 (Auto)
- [ ] 응답 JSON에 `data_csv_exists: <bool>`, `stats_json_exists: <bool>` 필드가 포함된다 (Auto)
- [ ] `data/draws.csv`가 존재할 때 `data_csv_exists: true`로 반환된다 (Auto)
- [ ] `data/draws.csv`가 없을 때 `data_csv_exists: false`로 반환된다(서버 크래시 없음) (Auto)

### AC-003: 데이터 누락 상태에서 서버 안정성

**관련 REQ**: REQ-WEB-SERVER-04

- [ ] `data/draws.csv`가 없는 상태에서 서버가 정상 기동된다 (Auto: fixture로 빈 data/ 디렉토리)
- [ ] `data/draws.csv`가 없을 때 5개 페이지(`/`, `/collect`, `/analyze`, `/recommend`, `/simulate`) 접근 시 HTTP 200과 함께 안내 메시지가 표시된다 (Auto: HTML 문자열 검증)
- [ ] 안내 메시지에 `"데이터를 먼저 수집하세요. CLI: python main.py collect"` 문자열이 포함된다 (Auto)
- [ ] 데이터 누락 상태에서 어떤 라우트도 예외(500)를 발생시키지 않는다 (Auto)

---

## Section 2: Page Routes (페이지 라우트)

### AC-004: 5개 페이지 라우트가 모두 HTTP 200 반환

**관련 REQ**: REQ-WEB-PAGE-01 ~ REQ-WEB-PAGE-05

- [ ] `GET /`이 HTTP 200을 반환한다 (Auto)
- [ ] `GET /collect`이 HTTP 200을 반환한다 (Auto)
- [ ] `GET /analyze`이 HTTP 200을 반환한다 (Auto)
- [ ] `GET /recommend`이 HTTP 200을 반환한다 (Auto)
- [ ] `GET /simulate`이 HTTP 200을 반환한다 (Auto)
- [ ] 5개 페이지의 응답 `Content-Type`이 `text/html; charset=utf-8`이다 (Auto)

**Given-When-Then**:
- GIVEN: `data/draws.csv`와 `data/stats.json`이 유효한 데이터로 존재
- WHEN: 5개 페이지 라우트에 GET 요청
- THEN: 모두 HTTP 200과 HTML 응답을 반환

### AC-005: 인덱스 페이지 콘텐츠

**관련 REQ**: REQ-WEB-PAGE-01

- [ ] `GET /` 응답에 마지막 회차 번호(예: `제1145회`)가 표시된다 (Auto: 정규식 매칭)
- [ ] 응답에 총 회차 수가 숫자로 표시된다 (Auto)
- [ ] 응답에 가장 최근 당첨 번호 6개 + 보너스 1개가 표시된다 (Auto)
- [ ] 응답에 4개 탭으로의 진입 링크가 존재한다 (Auto)

### AC-006: 수집 페이지 콘텐츠

**관련 REQ**: REQ-WEB-PAGE-02

- [ ] `GET /collect` 응답에 현재 수집된 회차 범위(`1~N`)가 표시된다 (Auto)
- [ ] 응답에 `data/draws.csv` 파일 크기(KB)가 표시된다 (Auto)
- [ ] 응답에 마지막 수집 일시가 `YYYY-MM-DD HH:MM` 형식으로 표시된다 (Auto)
- [ ] 응답에 수동 갱신 안내(`python main.py collect` 또는 "갱신" 버튼)가 존재한다 (Visual/Auto)

### AC-007: 분석 페이지 콘텐츠 (시그니처 요소 포함)

**관련 REQ**: REQ-WEB-PAGE-03, REQ-WEB-BADGE-01~03, REQ-WEB-CHART-01~02

- [ ] `GET /analyze` 응답에 1~45번 빈도 그라데이션 배지가 45개 모두 렌더링된다 (Auto: HTML에 45개 배지 DOM 노드 카운트)
- [ ] 45개 배지가 6열 × 8행 격자(마지막 행 5칸)로 배치된다 (Visual)
- [ ] Chart.js `<canvas>` 요소가 빈도 막대 차트로 존재한다 (Auto)
- [ ] 상위 20개 동반 출현 페어 테이블이 렌더링된다 (Auto)
- [ ] 최근 N회차 히트맵 테이블이 렌더링된다 (Auto)

### AC-008: 추천 페이지 콘텐츠

**관련 REQ**: REQ-WEB-PAGE-04

- [ ] `GET /recommend`(기본 count=5) 응답에 정확히 5개의 추천 카드가 렌더링된다 (Auto)
- [ ] `GET /recommend?count=10` 응답에 10개의 추천 카드가 렌더링된다 (Auto)
- [ ] 각 카드에 6개의 번호 배지가 포함된다 (Auto)
- [ ] 번호 배지는 두 자리 형식(`01`~`45`)으로 표시된다 (Auto)
- [ ] 각 카드에 전략 라벨(예: `고빈도`, `균형`, `최근편향`)이 표시된다 (Auto)
- [ ] 각 카드에 신뢰도 점수가 표시된다 (Auto)

### AC-009: 시뮬레이션 페이지 콘텐츠

**관련 REQ**: REQ-WEB-PAGE-05, REQ-WEB-CHART-03

- [ ] `GET /simulate`(기본 rounds=10) 응답에 Chart.js `<canvas>` 도넛 차트가 존재한다 (Auto)
- [ ] 등급별(1등/2등/3등/4등/5등/낙첨) 카운트 테이블이 렌더링된다 (Auto)
- [ ] 도넛 차트 바로 아래에 면책 문구 카드가 amber 배경으로 표시된다 (Visual + Auto)
- [ ] `GET /simulate?rounds=20` 응답에 20회차 시뮬레이션 결과가 반영된다 (Auto)

---

## Section 3: JSON API Routes (API 라우트)

### AC-010: `/api/draws` 엔드포인트

**관련 REQ**: REQ-WEB-API-01

- [ ] `GET /api/draws`가 HTTP 200과 JSON 배열을 반환한다 (Auto)
- [ ] 응답 배열의 길이가 `data/draws.csv`의 행 수와 일치한다 (Auto)
- [ ] 각 항목이 `drwNo`, `date`, `numbers`, `bonus` 필드를 포함한다 (Auto)
- [ ] `numbers` 필드는 6개 정수의 배열이며 각 값이 `[1, 45]` 범위 내에 있다 (Auto)

### AC-011: `/api/stats` 엔드포인트

**관련 REQ**: REQ-WEB-API-02

- [ ] `GET /api/stats`가 HTTP 200과 JSON 객체를 반환한다 (Auto)
- [ ] 응답에 `frequency`, `recent_pattern`, `consecutive_pattern`, `pair_analysis` 키가 모두 존재한다 (Auto)
- [ ] `frequency`는 45개 번호 각각의 빈도를 포함한다 (Auto)

### AC-012: `/api/recommendations` 엔드포인트와 검증

**관련 REQ**: REQ-WEB-API-03, REQ-WEB-API-07

- [ ] `GET /api/recommendations`(기본 count=5)이 HTTP 200과 5개 항목 배열을 반환한다 (Auto)
- [ ] `GET /api/recommendations?count=10`이 정확히 10개 항목을 반환한다 (Auto)
- [ ] `GET /api/recommendations?count=20`이 정확히 20개 항목을 반환한다 (Auto)
- [ ] 각 항목이 `numbers`(6개 정수), `strategy`(문자열), `confidence`(float) 필드를 포함한다 (Auto)
- [ ] `GET /api/recommendations?count=0`이 HTTP 422를 반환한다 (Auto)
- [ ] `GET /api/recommendations?count=21`이 HTTP 422를 반환한다 (Auto)
- [ ] `GET /api/recommendations?count=abc`이 HTTP 422를 반환한다 (Auto)

### AC-013: `/api/simulation` 엔드포인트와 검증

**관련 REQ**: REQ-WEB-API-04, REQ-WEB-API-07

- [ ] `GET /api/simulation`(기본 rounds=10)이 HTTP 200과 `SimulationResult` JSON을 반환한다 (Auto)
- [ ] `GET /api/simulation?rounds=50`이 50회차 결과를 반환한다 (Auto)
- [ ] `GET /api/simulation?rounds=0`이 HTTP 422를 반환한다 (Auto)
- [ ] `GET /api/simulation?rounds=101`이 HTTP 422를 반환한다 (Auto)

### AC-014: `POST /api/collect` 백그라운드 트리거

**관련 REQ**: REQ-WEB-API-05

- [ ] `POST /api/collect`가 즉시 HTTP 200과 `{"status": "started"}`를 반환한다 (Auto: 응답 시간 < 100ms)
- [ ] 응답 반환 후 백그라운드에서 `LottoCollector.collect_new`가 호출된다(monkeypatch로 mock 검증) (Auto)
- [ ] 백그라운드 태스크 실패 시 다음 `GET /health` 응답에는 영향을 미치지 않는다 (Auto)

### AC-015: `POST /api/analyze` 백그라운드 트리거

**관련 REQ**: REQ-WEB-API-06

- [ ] `POST /api/analyze`가 즉시 HTTP 200과 `{"status": "started"}`를 반환한다 (Auto)
- [ ] 백그라운드에서 `LottoAnalyzer.analyze`가 호출된다(mock 검증) (Auto)

### AC-016: 데이터 누락 시 API 503 응답

**관련 REQ**: REQ-WEB-API-08

- [ ] `data/draws.csv`가 없는 상태에서 `GET /api/draws`가 HTTP 503을 반환한다 (Auto)
- [ ] `data/stats.json`이 없는 상태에서 `GET /api/stats`가 HTTP 503을 반환한다 (Auto)
- [ ] `data/stats.json`이 없는 상태에서 `GET /api/recommendations`가 HTTP 503을 반환한다 (Auto)
- [ ] 503 응답 JSON에 `error: "data_unavailable"`, `message: "데이터가 없습니다. ..."` 필드가 포함된다 (Auto)

---

## Section 4: Signature Frequency Badge (시그니처 빈도 배지)

### AC-017: `compute_frequency_percentiles` 함수 정확성

**관련 REQ**: REQ-WEB-BADGE-01

- [ ] `compute_frequency_percentiles(stats)`가 정확히 45개 키(번호 1~45)를 가진 dict를 반환한다 (Auto)
- [ ] 모든 값이 `[0.0, 1.0]` 범위 내에 있다 (Auto)
- [ ] 최저 빈도 번호의 percentile이 `0.0`이다 (Auto)
- [ ] 최고 빈도 번호의 percentile이 `1.0`이다 (Auto)
- [ ] 빈도가 증가할수록 percentile이 단조 증가(non-decreasing)한다 (Auto: 정렬 후 검증)
- [ ] 동률 빈도의 tie-break는 번호 오름차순(결정성 보장) (Auto)

### AC-018: `interpolate_color` 함수 정확성

**관련 REQ**: REQ-WEB-BADGE-02

- [ ] `interpolate_color(0.0)`이 `"#E2E8F0"`을 반환한다 (Auto)
- [ ] `interpolate_color(1.0)`이 `"#3B82F6"`을 반환한다 (Auto)
- [ ] `interpolate_color(0.5)`이 두 색의 정확한 중간값을 반환한다(R, G, B 각 채널 평균) (Auto)
- [ ] 반환값이 `^#[0-9A-Fa-f]{6}$` 정규식과 일치한다 (Auto)
- [ ] 입력이 `[0.0, 1.0]` 밖이면 ValueError를 발생시킨다 (Auto)

### AC-019: 그라데이션 배지 격자 렌더링

**관련 REQ**: REQ-WEB-BADGE-02

- [ ] `GET /analyze` HTML 응답에서 45개의 배지 DOM 요소가 카운트된다 (Auto: BeautifulSoup 또는 정규식)
- [ ] 각 배지에 인라인 `style="background-color: #XXXXXX"` 속성이 존재한다 (Auto)
- [ ] 배지가 CSS Grid 6열 레이아웃으로 배치된다 (Visual + Auto: `grid-cols-6` Tailwind 클래스 존재)

### AC-020: 배지 텍스트 대비

**관련 REQ**: REQ-WEB-BADGE-03

- [ ] 모든 배지에 번호가 2자리(`01`~`45`)로 표시된다 (Auto)
- [ ] percentile ≥ 0.5인 배지의 텍스트 색상은 흰색(`#FFFFFF` 또는 `text-white`)이다 (Auto)
- [ ] percentile < 0.5인 배지의 텍스트 색상은 잉크 색(`#1A202C` 또는 `text-ink`)이다 (Auto)

---

## Section 5: Chart.js Integration (차트 통합)

### AC-021: 빈도 막대 차트 설정

**관련 REQ**: REQ-WEB-CHART-01, REQ-WEB-CHART-02

- [ ] `/analyze` HTML에 `new Chart(...)` 호출이 존재한다 (Auto: JS 문자열 매칭)
- [ ] 차트 타입이 `bar`이고 `indexAxis: 'y'`로 설정된다 (Auto)
- [ ] 데이터가 `<script>` 안에 인라인 JSON으로 주입된다(별도 fetch 호출 없음) (Auto: `fetch(` 호출 부재 검증)
- [ ] 상위 10개 막대 색상이 `#3B82F6`이다 (Auto: JS 문자열에서 색상 매칭)
- [ ] 나머지 35개 막대 색상이 `#CBD5E0`이다 (Auto)
- [ ] `animation: false`로 설정된다 (Auto)

### AC-022: 도넛 차트 설정

**관련 REQ**: REQ-WEB-CHART-03

- [ ] `/simulate` HTML에 Chart.js `doughnut` 타입 차트가 존재한다 (Auto)
- [ ] 색상 팔레트가 `#0D9488, #3B82F6, #4A5568, #718096, #A0AEC0, #CBD5E0`만 사용한다 (Auto: 색상 화이트리스트 검증)
- [ ] 빨강(`#FF*`, `red-*`) 또는 금색(`#FFD700`, `yellow-400+`) 색상이 절대 사용되지 않는다 (Auto: 블랙리스트 검증)

### AC-023: Chart.js 전역 기본값

**관련 REQ**: REQ-WEB-CHART-04

- [ ] `base.html`에 `Chart.defaults.font.family = "'Noto Sans KR', system-ui"` 설정이 존재한다 (Auto)
- [ ] `Chart.defaults.animation = false` 설정이 존재한다 (Auto)
- [ ] `Chart.defaults.plugins.legend.display = false` 설정이 존재한다 (Auto)

---

## Section 6: Styling and Layout (스타일 및 레이아웃)

### AC-024: Tailwind CSS CDN 통합

**관련 REQ**: REQ-WEB-STYLE-01, REQ-WEB-PAGE-06

- [ ] `base.html` `<head>`에 `<script src="https://cdn.tailwindcss.com"></script>`가 포함된다 (Auto)
- [ ] `package.json`, `tailwind.config.js`, `postcss.config.js` 등 빌드 설정 파일이 존재하지 않는다 (Auto: `os.path.exists` 검증)
- [ ] `static/css/` 디렉토리에 빌드된 CSS 파일이 존재하지 않는다 (Auto)

### AC-025: 디자인 토큰 정의

**관련 REQ**: REQ-WEB-STYLE-02

- [ ] `base.html`에 `tailwind.config = {...}` 인라인 설정이 존재한다 (Auto)
- [ ] 설정에 9개 디자인 토큰(`surface, ink, muted, slate-blue, data-blue, data-muted, teal, amber, border`)이 정의된다 (Auto)
- [ ] 각 토큰의 hex 값이 design-direction.md와 일치한다 (Auto: hex 문자열 매칭)

### AC-026: 페이지 폭과 패딩

**관련 REQ**: REQ-WEB-STYLE-03

- [ ] 메인 컨테이너 클래스에 `max-w-[1200px]` 또는 동등한 클래스가 적용된다 (Auto)
- [ ] 좌우 padding이 `24px`(Tailwind `px-6` 또는 `px-[24px]`)이다 (Auto)
- [ ] 모바일 우선 클래스(`sm:`, `md:` 등)가 적극적으로 사용되지 않음(데스크탑 전용) (Visual)

### AC-027: 금지 색상 부재

**관련 REQ**: REQ-WEB-STYLE-04

- [ ] 모든 템플릿과 인라인 스타일에 `#FF0000`, `#FFD700`, `red-`, `yellow-400`, `yellow-500`, `yellow-600` 등 금지 색상이 0회 등장한다 (Auto: 정규식 grep)

### AC-028: 4개 탭 네비게이션

**관련 REQ**: REQ-WEB-NAV-01, REQ-WEB-NAV-02

- [ ] `base.html`에 4개 탭(`데이터 수집`, `빈도 분석`, `추천 번호`, `시뮬레이션`)이 nav로 존재한다 (Auto)
- [ ] 4개 탭이 각각 `/collect`, `/analyze`, `/recommend`, `/simulate`로 링크된다 (Auto)
- [ ] 현재 페이지에 해당하는 탭이 `text-slate-blue` 색상과 2px 하단 보더로 활성 표시된다 (Auto: 각 페이지별 검증)
- [ ] 비활성 탭은 `text-muted` 색상으로 표시된다 (Auto)

---

## Section 7: Disclaimer and Header (면책 및 헤더)

### AC-029: 면책 문구 영구 표시

**관련 REQ**: REQ-WEB-PAGE-07

- [ ] 5개 페이지 모두의 푸터에 다음 문구가 정확히 표시된다: "이 통계는 과거 데이터 기반이며 미래 당첨을 보장하지 않습니다. 로또는 확률 게임입니다." (Auto)
- [ ] 면책 문구의 색상이 amber(`text-amber` 또는 `#D97706`)이다 (Auto)

### AC-030: 마지막 수집 일자 헤더 표시

**관련 REQ**: REQ-WEB-PAGE-08

- [ ] 5개 페이지 모두의 헤더 우측에 마지막 수집 일자가 `YYYY-MM-DD` 형식으로 표시된다 (Auto)
- [ ] 표시되는 날짜가 `data/draws.csv`의 파일 mtime을 기준으로 한다 (Auto)
- [ ] 파일이 없을 때는 "데이터 없음" 또는 동등한 안내가 표시된다 (Auto)

---

## Section 8: Async Safety (비동기 안전성)

### AC-031: 모든 GET 라우트가 `async def`로 정의됨

**관련 REQ**: REQ-WEB-ASYNC-01

- [ ] `lotto/web/routes/pages.py`의 모든 핸들러가 `async def`로 정의된다 (Auto: AST 검사 또는 정규식)
- [ ] `lotto/web/routes/api.py`의 모든 GET 핸들러와 `/health`가 `async def`로 정의된다 (Auto)

### AC-032: 블로킹 호출 격리

**관련 REQ**: REQ-WEB-ASYNC-02

- [ ] `async def` 핸들러 본문 안에서 `requests.get`, `requests.post` 직접 호출이 0건이다 (Auto: grep)
- [ ] `LottoCollector().collect_new()` 호출이 `BackgroundTasks.add_task` 또는 `asyncio.to_thread`로 래핑된다 (Auto)
- [ ] 비동기 안전성 위반 시 코드 리뷰에서 거부됨(체크리스트 항목으로 명시) (Manual)

### AC-033: 동시 요청 처리

**관련 REQ**: REQ-WEB-ASYNC-01

- [ ] `httpx.AsyncClient`로 5개 페이지 라우트를 동시에 호출했을 때 모두 1초 이내에 200을 반환한다 (Auto: `asyncio.gather`)
- [ ] 동시 요청이 직렬화되지 않음(타임라인 검증: 총 시간 < 5 × 단일 요청 시간) (Auto)

---

## Section 9: Performance and Quality (성능 및 품질)

### AC-034: 페이지 응답 시간

**관련 REQ**: NFR-PERF

- [ ] 5개 페이지 라우트의 P95 응답 시간이 500ms 미만(로컬 측정, 100회 반복) (Auto: timer fixture)
- [ ] `/analyze` 페이지(가장 무거운 페이지) 응답 시간이 1초 미만 (Auto)

### AC-035: 페이로드 크기

**관련 REQ**: NFR-PERF

- [ ] `GET /api/draws` 응답 크기가 1MB 미만 (Auto: `Content-Length` 검증)
- [ ] HTML 페이지 응답 크기가 500KB 미만(인라인 차트 데이터 포함) (Auto)

### AC-036: 테스트 커버리지

**관련 REQ**: REQ-WEB-TEST-03

- [ ] `pytest --cov=lotto.web tests/test_web_*.py` 결과 커버리지가 85% 이상 (Auto)
- [ ] 미커버 라인이 명시적으로 합리적인 이유와 함께 `# pragma: no cover` 처리됨 (Manual review)

### AC-037: 기존 코드 회귀 없음

**관련 REQ**: AC-024 (메타)

- [ ] `git diff` 출력에서 `lotto/collector.py`, `lotto/analyzer.py`, `lotto/recommender.py`, `lotto/simulator.py`, `lotto/models.py` 5개 파일의 변경이 0줄 (Auto)
- [ ] 기존 SPEC-LOTTO-001 테스트 전체(77개)가 모두 PASS (Auto)
- [ ] 기존 CLI 4개 명령(`collect`, `analyze`, `recommend`, `simulate`)이 정상 동작 (Auto: subprocess)

### AC-038: 의존성 추가 확인

**관련 REQ**: 기술 제약

- [ ] `requirements.txt`에 `fastapi>=0.115`이 추가됨 (Auto)
- [ ] `requirements.txt`에 `uvicorn>=0.29`이 추가됨 (Auto)
- [ ] `requirements.txt`에 `jinja2>=3.1`이 추가됨 (Auto)
- [ ] `requirements.txt`에 `aiofiles>=23.2`이 추가됨 (Auto)
- [ ] `pyproject.toml`의 의존성 섹션이 `requirements.txt`와 동기화됨 (Auto)

### AC-039: 코드 품질 게이트

**관련 REQ**: 프로젝트 표준(`ruff`, `mypy`, `black`)

- [ ] `ruff check lotto/web/`이 0개 warning을 보고함 (Auto)
- [ ] `mypy lotto/web/`이 0개 error를 보고함 (Auto)
- [ ] `black --check lotto/web/`이 모든 파일에 대해 통과 (Auto)

---

## Section 10: Documentation (문서)

### AC-040: README 업데이트

**관련 REQ**: 구현 계획 M5.3

- [ ] `README.md`에 "웹 대시보드" 섹션이 추가됨 (Manual)
- [ ] 섹션에 `python main.py web` 실행 방법과 브라우저 접속 안내가 포함됨 (Manual)
- [ ] 인터넷 연결 필수 사항(Tailwind/Chart.js/Noto Sans KR CDN)이 명시됨 (Manual)

### AC-041: CHANGELOG 항목 추가

**관련 REQ**: 구현 계획 M6.6

- [ ] `CHANGELOG.md`에 SPEC-WEB-001 항목이 추가됨 (Manual)
- [ ] 추가 내용에 신규 기능(웹 대시보드, 4개 탭, 시그니처 그라데이션 배지)이 요약됨 (Manual)

---

## Section 11: Visual Design Verification (시각 검토)

다음 항목은 자동화하기 어려우며 디자인 검토에서 수동 확인한다.

### AC-042: 디자인 일관성 (Visual)

- [ ] 5개 페이지의 전체 톤이 Bloomberg/네이버 증권 풍의 차분한 데이터 분석 도구 미감 (Visual)
- [ ] 시그니처 그라데이션 배지가 한눈에 빈도 분포를 전달함(상위/하위 번호 구분 명확) (Visual)
- [ ] 모든 차트가 절제된 색상(Data Blue + Data Muted)으로 데이터 계층을 표현함 (Visual)
- [ ] 면책 문구가 눈에 거슬리지 않으나 명확히 보임(opacity 적절) (Visual)
- [ ] 헤더-탭-콘텐츠-푸터의 시각 위계가 명확함 (Visual)

### AC-043: 한국어 가독성 (Visual)

- [ ] 모든 한국어 텍스트가 Noto Sans KR로 렌더링됨(폰트 fallback 없이) (Visual)
- [ ] 번호 배지(01~45)가 줄바꿈 없이 한 줄에 표시됨(`white-space: nowrap`) (Visual)
- [ ] 차트 레이블이 잘리지 않고 모두 표시됨 (Visual)

---

## Definition of Done (전체 완료 정의)

본 SPEC-WEB-001은 다음 조건을 **모두** 충족할 때 완료된다:

- [ ] 43개 AC 항목 중 Auto 카테고리 100%, Manual/Visual 카테고리는 사용자 승인 완료
- [ ] `pytest tests/ --cov=lotto -v` 실행 시 전체 테스트(기존 77 + 신규 ~40 = ~117) PASS
- [ ] `lotto/web/` 모듈 커버리지 ≥ 85%
- [ ] 기존 SPEC-LOTTO-001 회귀 0건(5개 핵심 파일 diff = 0)
- [ ] `ruff`, `mypy`, `black` 품질 게이트 통과
- [ ] `python main.py web` 명령으로 실제 브라우저 접속 후 5개 페이지가 시각적으로 정상 렌더링됨(Manual)
- [ ] 사용자가 본 acceptance.md의 모든 항목을 확인 후 "완료 승인"

---

## Traceability Matrix (요구사항-인수기준 추적)

| REQ | AC |
|-----|-----|
| REQ-WEB-SERVER-01 | AC-001 |
| REQ-WEB-SERVER-02 | AC-001 |
| REQ-WEB-SERVER-03 | AC-001 |
| REQ-WEB-SERVER-04 | AC-003 |
| REQ-WEB-SERVER-05 | AC-002 |
| REQ-WEB-PAGE-01 | AC-004, AC-005 |
| REQ-WEB-PAGE-02 | AC-004, AC-006 |
| REQ-WEB-PAGE-03 | AC-004, AC-007 |
| REQ-WEB-PAGE-04 | AC-004, AC-008 |
| REQ-WEB-PAGE-05 | AC-004, AC-009 |
| REQ-WEB-PAGE-06 | AC-024 |
| REQ-WEB-PAGE-07 | AC-029 |
| REQ-WEB-PAGE-08 | AC-030 |
| REQ-WEB-API-01 | AC-010 |
| REQ-WEB-API-02 | AC-011 |
| REQ-WEB-API-03 | AC-012 |
| REQ-WEB-API-04 | AC-013 |
| REQ-WEB-API-05 | AC-014 |
| REQ-WEB-API-06 | AC-015 |
| REQ-WEB-API-07 | AC-012, AC-013 |
| REQ-WEB-API-08 | AC-016 |
| REQ-WEB-DATA-01 | AC-010 ~ AC-013 (간접) |
| REQ-WEB-DATA-02 | AC-037 |
| REQ-WEB-DATA-03 | AC-034 (성능 측면) |
| REQ-WEB-ASYNC-01 | AC-031, AC-033 |
| REQ-WEB-ASYNC-02 | AC-032 |
| REQ-WEB-ASYNC-03 | AC-034 (성능 측면) |
| REQ-WEB-BADGE-01 | AC-017 |
| REQ-WEB-BADGE-02 | AC-018, AC-019 |
| REQ-WEB-BADGE-03 | AC-020 |
| REQ-WEB-CHART-01 | AC-021 |
| REQ-WEB-CHART-02 | AC-021 |
| REQ-WEB-CHART-03 | AC-022 |
| REQ-WEB-CHART-04 | AC-023 |
| REQ-WEB-STYLE-01 | AC-024 |
| REQ-WEB-STYLE-02 | AC-025 |
| REQ-WEB-STYLE-03 | AC-026 |
| REQ-WEB-STYLE-04 | AC-027 |
| REQ-WEB-NAV-01 | AC-028 |
| REQ-WEB-NAV-02 | AC-028 |
| REQ-WEB-TEST-01 | AC-004 ~ AC-016 (간접) |
| REQ-WEB-TEST-02 | AC-010 ~ AC-020 (간접) |
| REQ-WEB-TEST-03 | AC-036 |
| REQ-WEB-TEST-04 | AC-007, AC-019, AC-029 |
| NFR-PERF | AC-034, AC-035 |
| NFR-COMPAT | AC-001 (Manual) |
| NFR-SEC | AC-024 (정적 자원 한정), AC-001 (host 기본값) |
| NFR-MAINT | AC-037 (기존 코드 회귀 없음) |

---

Version: 1.0.0
Status: Acceptance criteria ready for review
