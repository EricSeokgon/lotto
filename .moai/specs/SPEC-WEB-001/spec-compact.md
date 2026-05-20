# SPEC-WEB-001: Compact Spec (Run 단계용 압축본)

본 문서는 `/moai run SPEC-WEB-001` 실행 시 컨텍스트 효율을 위해 사용되는 압축 SPEC이다. 정상 동작에 필요한 핵심 요구사항, 인수 기준, 파일 목록, 제외 범위만 추출한다. 상세 배경/근거는 `spec.md`, `plan.md`, `acceptance.md`를 참조한다.

---

## 1. Mission (한 줄 요약)

기존 Python 로또 CLI(SPEC-LOTTO-001)의 데이터 파일(`data/draws.csv`, `data/stats.json`)을 FastAPI + Jinja2 + Chart.js로 시각화하는 **읽기 전용 4-탭 웹 대시보드**. 신규 비즈니스 로직 0줄, 기존 `lotto/{collector,analyzer,recommender,simulator,models}.py` diff = 0.

---

## 2. Tech Stack (확정)

- Python 3.11+, FastAPI ≥ 0.115, uvicorn ≥ 0.29, Jinja2 ≥ 3.1, aiofiles ≥ 23.2
- Tailwind CSS via CDN, Chart.js v4 via CDN, Noto Sans KR via Google Fonts CDN
- Node.js/npm 미사용, 빌드 도구 없음, 데이터베이스 없음, 인증 없음

---

## 3. Files to Create (신규)

| 경로 | 목적 |
|------|------|
| `lotto/web/__init__.py` | 패키지 마커 |
| `lotto/web/app.py` | FastAPI 인스턴스, lifespan, Jinja2 설정, 라우터 등록 |
| `lotto/web/data.py` | 기존 모듈 호출 래퍼 + percentile/color 헬퍼 |
| `lotto/web/routes/__init__.py` | 라우터 패키지 마커 |
| `lotto/web/routes/pages.py` | 5개 HTML 페이지 라우트 (`async def`) |
| `lotto/web/routes/api.py` | 6개 JSON API 라우트 + `/health` (`async def`) |
| `lotto/web/templates/base.html` | 공통 레이아웃 + CDN + Tailwind config + Chart defaults |
| `lotto/web/templates/index.html` | 대시보드 홈 |
| `lotto/web/templates/collect.html` | 수집 상태 페이지 |
| `lotto/web/templates/analyze.html` | **시그니처 그라데이션 배지 + 빈도 막대 차트 + 페어 + 히트맵** |
| `lotto/web/templates/recommend.html` | N개 추천 카드 |
| `lotto/web/templates/simulate.html` | 도넛 차트 + 등급 테이블 + 면책 카드 |
| `lotto/web/static/.gitkeep` | StaticFiles 마운트용 빈 디렉토리 |
| `tests/test_web_app.py` | 앱 기동/health 검증 |
| `tests/test_web_data.py` | data.py 단위 테스트 |
| `tests/test_web_pages.py` | 5개 페이지 통합 테스트 |
| `tests/test_web_api.py` | 7개 API 통합 테스트 |
| `tests/test_cli_web.py` | `web` 서브커맨드 등록 검증 |
| `tests/fixtures/web_mini_stats.json` | percentile 테스트 픽스처 |

## Files to Modify

| 경로 | 변경 |
|------|------|
| `requirements.txt` | `fastapi`, `uvicorn`, `jinja2`, `aiofiles` 추가 |
| `pyproject.toml` | 의존성 섹션 동기화 |
| `main.py` 또는 `lotto/cli.py` | `web` 서브커맨드 추가 (host/port/reload 옵션) |
| `README.md` | 웹 대시보드 사용법 섹션 |
| `CHANGELOG.md` | SPEC-WEB-001 항목 |

## Files to NOT Modify (HARD)

- `lotto/collector.py` `lotto/analyzer.py` `lotto/recommender.py` `lotto/simulator.py` `lotto/models.py`
- 기존 `tests/test_{models,collector,analyzer,recommender,simulator,cli,integration}.py`

---

## 4. REQ-* 요구사항 (EARS 압축)

### REQ-WEB-SERVER
- **01 (Event)**: `python main.py web` → uvicorn 기동, 기본 `127.0.0.1:8000`
- **02 (Optional)**: `--host`, `--port`, `--reload` 옵션 전달
- **03 (Ubiquitous)**: `lotto/web/app.py:app` ASGI 모듈, lifespan에서 데이터 파일 검증
- **04 (Unwanted)**: 데이터 없어도 크래시 금지, 안내 메시지 fallback
- **05 (Event)**: `GET /health` → 200 + `{status, data_csv_exists, stats_json_exists}`

### REQ-WEB-PAGE
- **01~05 (Event)**: `GET /`, `/collect`, `/analyze`, `/recommend?count=N`, `/simulate?rounds=K` → Jinja2 렌더링
- **06 (Ubiquitous)**: 모든 페이지가 `base.html` 상속, CDN(Tailwind/Chart.js/Noto Sans KR) 포함
- **07 (Ubiquitous)**: 면책 문구 푸터 영구 표시(amber `#D97706`)
- **08 (Ubiquitous)**: 헤더 우측에 마지막 수집 일자 `YYYY-MM-DD`

### REQ-WEB-API
- **01~06 (Event)**: `GET /api/draws`, `/api/stats`, `/api/recommendations?count`, `/api/simulation?rounds`, `POST /api/collect`, `POST /api/analyze`
- **07 (Unwanted)**: count/rounds 범위 초과 → HTTP 422
- **08 (Unwanted)**: 데이터 누락 → HTTP 503 `{error: "data_unavailable", message: "데이터가 없습니다..."}`
- POST 엔드포인트는 `BackgroundTasks`로 블로킹 호출 격리

### REQ-WEB-DATA
- **01**: `data.py`에 `get_draws/get_stats/get_recommendations/get_simulation/get_data_status/compute_frequency_percentiles/interpolate_color` 정의
- **02**: 신규 비즈니스 로직 0줄, 기존 `lotto/` 모듈만 호출
- **03**: mtime 기반 캐싱 옵셔널(현 데이터 규모에서는 미적용)

### REQ-WEB-ASYNC
- **01 (Ubiquitous)**: 모든 GET 라우트 `async def`
- **02 (Unwanted)**: `requests.get` 등 블로킹 호출은 `BackgroundTasks` 또는 `asyncio.to_thread()` 필수
- **03**: 현 규모 파일 I/O는 동기 호출 허용

### REQ-WEB-BADGE (시그니처)
- **01**: `compute_frequency_percentiles(stats) → dict[int, float]` 단조 증가, tie-break = 번호 오름차순
- **02**: `templates/analyze.html`에서 6×8 격자, `#E2E8F0`(0.0) → `#3B82F6`(1.0) 선형 보간, Python/Jinja에서 색상 계산
- **03**: 번호 2자리(`01`~`45`), percentile ≥ 0.5일 때 텍스트 흰색

### REQ-WEB-CHART
- **01**: 빈도 차트 = `bar` + `indexAxis: 'y'`, 데이터는 인라인 JSON 주입(별도 fetch 없음)
- **02**: 상위 10개 `#3B82F6`, 나머지 `#CBD5E0`, `animation: false`
- **03**: 도넛 차트 색상 = `#0D9488, #3B82F6, #4A5568, #718096, #A0AEC0, #CBD5E0` (빨강/금색 절대 금지)
- **04**: Chart.js 전역 defaults — Noto Sans KR, size 12, color `#718096`, legend off, animation off

### REQ-WEB-STYLE
- **01**: Tailwind CDN 단일 (`https://cdn.tailwindcss.com`), 빌드 파일 0개
- **02**: `tailwind.config` 인라인 9개 토큰(surface/ink/muted/slate-blue/data-blue/data-muted/teal/amber/border)
- **03**: max-width 1200px, padding 24px, 데스크탑 전용(반응형 미적용)
- **04 (Unwanted)**: 빨강/금색 도입 PR 거부

### REQ-WEB-NAV
- **01**: 4개 탭(`데이터 수집`, `빈도 분석`, `추천 번호`, `시뮬레이션`) → `/collect`, `/analyze`, `/recommend`, `/simulate`
- **02 (State)**: 활성 탭 `slate-blue` + 2px 하단 보더, 비활성 `muted`

### REQ-WEB-TEST
- **01**: `httpx.AsyncClient` 또는 `TestClient` 사용
- **02**: 페이지/API/검증/percentile/색상 보간 모두 테스트
- **03**: `lotto/web/` 커버리지 ≥ 85%
- **04**: 핵심 마커(배지/면책/탭) HTML 존재 검증

---

## 5. Acceptance Snapshot (인수 기준 요약)

핵심 43개 AC 중 검증 우선순위:

1. **AC-001~003**: `python main.py web` 기동, `/health` 200, 데이터 없어도 크래시 없음
2. **AC-004~009**: 5개 페이지 200, 컨텐츠 마커 존재(회차/탭/면책/시그니처 배지)
3. **AC-010~016**: 6 API 정상 + 검증(422) + 데이터 누락(503)
4. **AC-017~020**: 시그니처 배지 — percentile 단조성, `interpolate_color` 경계값, 6×8 격자, 텍스트 대비
5. **AC-021~023**: Chart.js 인라인 데이터, 상위 10/나머지 색상 구분, defaults 설정
6. **AC-024~028**: Tailwind CDN, 디자인 토큰 9개, max-width 1200, 빨강/금색 0개, 4개 탭 활성 표시
7. **AC-029~030**: 면책 문구 5페이지 표시, 헤더 일자 표시
8. **AC-031~033**: 모든 GET `async def`, 블로킹 호출 격리, 동시 요청 처리
9. **AC-034~039**: P95 < 500ms, 커버리지 ≥ 85%, 기존 5개 파일 diff = 0, ruff/mypy/black 통과

상세는 `acceptance.md` 참조.

---

## 6. Data Models (재사용)

기존 `lotto/models.py`의 Pydantic v2 모델 그대로 사용:
- `DrawResult { drwNo, date, numbers: list[int], bonus }`
- `Statistics { frequency, recent_pattern, consecutive_pattern, pair_analysis }`
- `Recommendation { numbers: list[int], strategy: str, confidence: float }`
- `SimulationResult { rounds, hit_distribution, rank_counts, hit_rate }`

신규 모델은 `lotto/web/data.py`에 `DataStatus { csv_exists, json_exists, csv_mtime, json_mtime }` 하나만 정의.

---

## 7. API Contract (요약)

| Method | Path | Query | Response |
|--------|------|-------|----------|
| GET | `/health` | — | `{status, data_csv_exists, stats_json_exists}` |
| GET | `/` | — | HTML (index.html) |
| GET | `/collect` | — | HTML (collect.html) |
| GET | `/analyze` | — | HTML (analyze.html) |
| GET | `/recommend` | `count: 1-20` (default 5) | HTML (recommend.html) |
| GET | `/simulate` | `rounds: 1-100` (default 10) | HTML (simulate.html) |
| GET | `/api/draws` | — | `list[DrawResult]` JSON |
| GET | `/api/stats` | — | `Statistics` JSON |
| GET | `/api/recommendations` | `count: 1-20` (default 5) | `list[Recommendation]` JSON |
| GET | `/api/simulation` | `rounds: 1-100` (default 10) | `SimulationResult` JSON |
| POST | `/api/collect` | — | `{status: "started"}` (BackgroundTasks) |
| POST | `/api/analyze` | — | `{status: "started"}` (BackgroundTasks) |

검증 실패 → 422, 데이터 누락 → 503.

---

## 8. Design Tokens (확정 hex)

| 토큰 | hex | 용도 |
|------|------|------|
| surface | `#F8F9FA` | 페이지 배경 |
| ink | `#1A202C` | 제목/본문 |
| muted | `#718096` | 보조 텍스트, 비활성 탭 |
| slate-blue | `#4A5568` | 활성 탭, 번호 배지 배경 |
| data-blue | `#3B82F6` | 차트 주 계열, 그라데이션 high |
| data-muted | `#CBD5E0` | 차트 보조 계열 |
| teal | `#0D9488` | 1등 등급 |
| amber | `#D97706` | 면책 문구 |
| border | `#E2E8F0` | 카드 테두리, 그라데이션 low |

---

## 9. Disclaimer (영구 표시)

```
이 통계는 과거 데이터 기반이며 미래 당첨을 보장하지 않습니다. 로또는 확률 게임입니다.
```

색상: amber (`#D97706`), 위치: 모든 페이지 푸터.

---

## 10. Exclusions (절대 금지)

- DB, 인증, WebSocket/SSE, 모바일 반응형, Node.js/npm, 신규 알고리즘, i18n, 다크모드
- 빨강/금색 계열 색상
- 차트 라이브러리 추가(Chart.js만)
- 사용자 환경설정 저장
- 외부 알림(이메일/SMS)
- 로또 구매/결제 연동

---

## 11. Test Targets (정량)

- 신규 테스트 파일 5개
- 신규 테스트 케이스 37~48개
- `lotto/web/` 커버리지 ≥ 85%
- 기존 77개 테스트 회귀 0건
- P95 페이지 응답 < 500ms

---

## 12. Implementation Order (6 마일스톤)

1. **M1 Foundation**: 의존성 추가, 빈 FastAPI 골격
2. **M2 Data Layer**: `data.py` + percentile/color 헬퍼 + 단위 테스트
3. **M3 Pages**: 5개 템플릿 + `pages.py` + 페이지 통합 테스트
4. **M4 API**: `api.py` + 7개 API 통합 테스트 + BackgroundTasks
5. **M5 CLI**: `web` 서브커맨드 + README
6. **M6 Polish**: 커버리지 확보, 회귀 검증, CHANGELOG

상세는 `plan.md` 참조.

---

Version: 1.0.0
Status: Ready for Run phase
