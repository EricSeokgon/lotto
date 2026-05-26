# 변경 이력

모든 주목할 만한 변경 사항은 이 파일에 기록됩니다.

형식: [Keep a Changelog](https://keepachangelog.com/) 가이드를 따릅니다.

---

## [1.3.0] - 2026-05-26

추천 전략 앙상블 고도화 및 웹 UI 개선 (SPEC-LOTTO-009·013)

### 추가

#### 갭분석 (Gap Analysis) — analyze 페이지 (SPEC-LOTTO-013)
- 번호별 미출현 회차 수(갭) 시각화 — 오랫동안 안 나온 번호를 한눈에 확인
- `gap_rounds` 컨텍스트 변수: `consecutive_pattern.current_streak` 음수값 활용
- analyze 페이지 배지에 갭 정보 툴팁 표시

#### 데이터 게이트웨이 캐싱 (SPEC-LOTTO-009)
- `get_draws()` / `get_stats()` TTL 60초 모듈 레벨 캐시 도입
- `invalidate_cache()` — collect/analyze/scrape 완료 후 자동 호출
- `get_last_sync_date()` — last_sync.json 우선, draws.csv 최신 회차 폴백
- 인덱스 페이지 헤더에 "최근 수집: YYYY-MM-DD" 표시

### 개선

#### 복합 앙상블 추천 전략 고도화 (SPEC-LOTTO-013)
- 8가지 단일 전략을 복합 앙상블 모델로 통합
- 갭분석 기반 "핫콜드혼합" 전략 정확도 개선

#### 웹 UI 개선
- 수집현황: 최신순 정렬 + 처음/마지막 페이징 버튼 추가
- 추첨결과 테이블: 서버사이드 초기 렌더링으로 최신 회차 우선 표시
- 시뮬레이션: 5등 적중률 계산 정확도 개선
- 모바일 반응형 메뉴 (햄버거 메뉴)

#### 테스트 커버리지 향상 (SPEC-LOTTO-011 완료)
- 460개 테스트, 커버리지 98.51% → **99.85%** (statement miss 0건)
- 갭분석·앙상블 전략 테스트 22개 추가 (SPEC-LOTTO-013)
- TYPE_CHECKING 블록·방어용 폴백 코드에 `# pragma: no cover` 적용

---

## [1.2.0] - 2026-05-21

코드 품질 강화 및 운영 모니터링 지원 (SPEC-LOTTO-011~012)

### 추가

#### REQ-HLT: 헬스체크 엔드포인트 (SPEC-LOTTO-012)
- `GET /api/health` 엔드포인트 추가 (항상 HTTP 200)
- 응답 필드: `status`, `uptime_seconds`, `data` (csv_exists, csv_rows, stats_exists, last_sync), `version`
- `status: "ok"` — csv + stats 파일 모두 존재 시
- `status: "degraded"` — 데이터 파일 없을 때
- Pydantic 응답 모델: `HealthResponse`, `HealthDataResponse`
- Prometheus / UptimeRobot / k8s liveness probe 호환

### 개선

#### 테스트 커버리지 향상 (SPEC-LOTTO-011)
- 429개 테스트, 커버리지 96.26% → 98.51%
- 추천기 폴백 경로(홀짝균형, 번호대균형, 핫콜드혼합) 테스트 추가
- 웹 API 커버리지 미비 경로(CSV 삭제, analyze 분기 등) 추가
- 헬스체크 테스트 10개 추가 (REQ-HLT-001~005 검증)

#### mypy 타입 안정화
- mypy 에러 50건 → 0건 (`lotto/` 15개 소스 파일 전체)
- `web/data.py`: 반환 타입 구체화 (`list[DrawResult]`, `Statistics | None` 등)
- `web/routes/pages.py`: `TemplateResponse` 임포트 경로 수정, `dict[str, Any]` 적용
- `config.py`: `typing.Tuple` → `tuple` (UP035/UP006)
- `scraper.py`: `list[tuple[str, str | None]]` 구체화
- `pdf_report.py`: TYPE_CHECKING 임포트 경로 lotto.models로 통일

#### 린트 정리
- ruff SIM105: `try/except/pass` → `contextlib.suppress(OSError)` (collector.py)
- ruff TC003: `Path` → TYPE_CHECKING 블록으로 이동 (collector.py)
- ruff SIM117: 중첩 `with` → 괄호식 단일 `with` (test 파일 3개)
- ruff E501: 긴 줄 분리 (test_pdf_report.py)

---

## [1.1.0] - 2026-05-20

웹 대시보드 추가 (SPEC-WEB-001 구현 완료)

### 추가

#### REQ-WEB: 읽기 전용 웹 대시보드
- FastAPI 기반 5탭 웹 대시보드 (`lotto/web/`)
- 대시보드, 수집 현황, 빈도 분석, 추천 번호, 시뮬레이션 탭
- 번호별 빈도 백분위수 기반 컬러 배지 (저빈도 #E2E8F0 ~ 고빈도 #3B82F6)
- Chart.js v4 차트: 빈도 분석(가로 막대), 시뮬레이션(도넛)
- Tailwind CSS CDN, Noto Sans KR CDN 활용 (빌드 스텝 없음)
- REST API 엔드포인트: GET /api/draws, /api/stats, /api/recommendations, /api/simulation
- POST /api/collect, /api/analyze (비동기 백그라운드 실행)
- `python main.py web` CLI 서브커맨드 추가
- 65개 신규 테스트 추가, lotto.web 커버리지 ≥ 90%

---

## [1.0.0] - 2026-05-20

로또 번호 추천 CLI 도구의 초기 안정 버전 (SPEC-LOTTO-001 구현 완료)

### 추가

#### REQ-COLLECT: 당첨 번호 수집 모듈
- 동행복권 API에서 6/45 로또 당첨 번호 자동 수집
- `data/draws.csv` 형식으로 로컬 저장
- 증분 수집 (신규 회차만) 및 전체 재수집 (`--full`) 옵션
- API 장애 시 지수 백오프 재시도 (1s, 2s, 4s 최대 3회)
- 연속 5회 이상 수집 실패 시 자동 중단으로 데이터 무결성 보호
- 200ms 레이트 제한으로 서버 부하 경감

#### REQ-ANALYZE: 통계 분석 모듈
- 수집된 데이터에서 4가지 통계 지표 계산
  - **출현 빈도 (frequency)**: 각 번호(1~45)의 누적 출현 횟수 및 확률
  - **최근 패턴 (recent_pattern)**: 최근 N회차 내 각 번호의 출현 빈도 및 마지막 출현 회차
  - **연속 패턴 (consecutive_pattern)**: 최대 연속 출현 기간 및 최대 부재 기간
  - **동반 출현 (pair_analysis)**: 자주 함께 나오는 번호 쌍 TOP 20
- `data/stats.json` 형식으로 JSON 저장
- `--recent-window N` 옵션으로 분석 기간 커스터마이징 (기본값: 20회차)
- 데이터 부재 시 명확한 에러 메시지 및 상태 코드 반환

#### REQ-RECOMMEND: 번호 추천 모듈
- 통계 데이터 기반의 가중치식 점수 추천
- 스코어링 공식: `score(n) = w_freq × freq_norm(n) + w_recent × recent_norm(n) + w_pair × pair_norm(n) - w_consec × consec_penalty(n)`
- 5가지 전략 레이블 자동 할당
  - `고빈도`: 출현 빈도 편향
  - `저빈도`: 저빈도 번호 편향
  - `균형`: 모든 지표의 균형
  - `최근편향`: 최근 패턴 편향
  - `동반패턴`: 동반 출현 편향
- `--count N` 옵션으로 추천 세트 수 지정 (1~20, 기본값: 5)
- `--weights w_freq,w_recent,w_pair,w_consec` 옵션으로 가중치 커스터마이징
- 기본 가중치: 0.4, 0.3, 0.2, 0.1
- 추천 세트 번호는 항상 오름차순 정렬
- 동일 실행 내 중복 없음 보장

#### REQ-SIMULATE: 시뮬레이션/백테스팅 모듈
- 과거 회차 데이터를 사용한 인과 안전(look-ahead safe) 백테스팅
- 각 회차마다 독립적인 추천 생성 후 실제 당첨 번호와 비교
- 매칭 등급 자동 계산 (1등~5등, 낙첨)
- 집계 메트릭스 생성: 평가 회차, 등급별 횟수, 적중률(5등 이상)
- `--rounds N` 옵션으로 백테스팅 회차 수 지정 (기본값: 10, 최대: 수집된 전체 회차)
- `--output FILE` 옵션으로 상세 결과를 JSON 파일로 저장
- Rich 라이브러리로 진행 상황 표시

#### REQ-CLI: CLI 인터페이스 모듈
- typer 기반 단일 진입점 (`main.py`)
- 4개 서브커맨드: `collect`, `analyze`, `recommend`, `simulate`
- 한국어 헬프 텍스트 및 사용자 친화적 에러 메시지
- Rich 라이브러리로 테이블 및 칼러 출력
- 진행 상황 표시 (progress bar)
- 상태 코드 정의
  - 0: 성공
  - 1: 입력/데이터 검증 오류
  - 2: 외부 서비스 장애

### 개발

#### 테스트 및 품질
- 77개 단위 테스트 (PyTest)
- 라인 커버리지 85.25%
- ruff 린팅 0 오류
- mypy --strict 타입 검사 0 오류
- TDD 방법론 (RED-GREEN-REFACTOR)

#### 코드 구조
- `lotto/models.py`: Pydantic 데이터 모델 및 타입 정의
- `lotto/collector.py`: 수집 모듈 및 CSV 직렬화
- `lotto/analyzer.py`: 통계 분석 엔진 및 JSON 저장
- `lotto/recommender.py`: 가중치식 추천 알고리즘
- `lotto/simulator.py`: 백테스팅 및 매칭 등급 계산
- `main.py`: typer CLI 엔트리 포인트

#### 호환성
- Python 3.9+ (실제 런타임: 3.9.25)
- 외부 데이터베이스 불필요 (로컬 CSV/JSON만 사용)
- 크로스 플랫폼 (Windows, macOS, Linux)

#### 의존성
- typer 0.9+
- rich 13+
- pydantic 2.0+
- pytest 7.0+ (개발용)
- ruff, mypy (품질 검사용)

### 비기능 요구사항 충족

| 항목 | 요구사항 | 상태 |
|------|---------|------|
| 성능 (analyze) | 5초 이내 (1,200회차) | ✅ |
| 성능 (recommend) | 2초 이내 (5세트) | ✅ |
| 안정성 | API 장애 시 3회 재시도 | ✅ |
| 호환성 | Python 3.11, 3.12 | ✅ |
| 코드 품질 | ruff 0 오류, mypy --strict 0 오류 | ✅ |
| 테스트 | 85% 이상 커버리지 | ✅ 85.25% |
| 보안 | 입력값 범위 검증 | ✅ |

### 배제 범위

명시적으로 v1.0.0에서는 제공하지 않는 기능:
- 당첨 보장 — 본 시스템은 통계 기반이며 어떤 형태로도 당첨을 보장하지 않음
- 자동 구매 연동 — 추천 번호의 실제 구매는 사용자가 직접 수행
- GUI 또는 웹 인터페이스 — 순수 CLI 도구만 제공
- 실시간 스트리밍 — 사용자 명시 수집만 지원
- 외부 데이터베이스 — 로컬 CSV/JSON 파일만 사용
- 머신러닝 기반 추천 — v2.0.0 이후 별도 SPEC에서 다룸
- 다국어 지원 — 한국어만 제공

### 문서

- README.md: 설치, 사용 가이드, 명령어 상세
- 이 CHANGELOG
- SPEC-LOTTO-001 완료

### 면책 사항

⚠️ **본 프로그램은 통계 분석을 기반으로 하며 당첨을 보장하지 않습니다.**
- 로또는 완전 무작위 추첨 게임
- 역사적 패턴은 미래 결과를 예측하지 못함
- 사용자의 손실에 대해 책임지지 않음

---

## [미정] - 향후 계획

### 향후 버전에서 예상되는 기능

- API 입력 검증 강화 (Pydantic 경계 조건)
- Rate limiting (collect/scrape 엔드포인트)
- 웹 UI 개선 (히트맵, 트렌드 차트)
- Docker/배포 설정
- SPEC-LOTTO-002: 머신러닝 기반 추천 (신경망)
- 자동 구매 시스템 (PG 연동)
- 다국어 지원

---

## 버전 관리

- **Semantic Versioning** 준수
- **1.0.0** = 첫 안정 릴리스 (모든 SPEC-LOTTO-001 요구사항 구현)
