# SPEC-LOTTO-038 구현 계획

## 개요

전체 회차 데이터를 시각적으로 요약하는 메인 통계 대시보드(`/stats`)를 추가한다.
신규 데이터 집계 함수 1개, API 엔드포인트 1개, 웹 페이지 1개, 템플릿 1개, 네비게이션 1개 항목으로 구성된다.

기존 코드베이스의 검증된 패턴을 그대로 따른다:
- `_UNSET` 센티넬 + `draws` 선택 인자 (중복 CSV 파싱 회피) — `pattern_analysis`, `weekly_report`와 동일
- 데이터 부재 시 200 + 빈 구조 반환 — `weekly-report`, `prize-stats`와 동일
- 페이지 라우트의 `_render(request, template, ctx)` + `active_tab` 패턴
- 테스트에서 `lotto.web.data` 함수를 patch하는 호환성 (동적 import 또는 모듈 심볼 직접 사용)

## 기술적 접근

### 재사용 vs 신규

| 데이터 요소 | 출처 |
|------------|------|
| 총 회차수 | 신규 집계 (`len(draws)`) |
| 총 1등 당첨금 합계 | 신규 집계 (`sum(prize1Amount)`) — `get_prize_stats`는 합계를 노출하지 않으므로 신규 |
| 번호별 출현 횟수 (1~45) | 신규 집계 — 기존 함수 미제공 |
| 최고/최저 1등 당첨금 회차 | 신규 집계 (`max/min by prize1Amount`) — 기존은 금액만, 회차 식별 미제공 |
| 홀짝 분포 (전역 누적) | 신규 집계 — `pattern_analysis`는 회차별 홀수 개수 히스토그램이라 의미가 다름 (ASM-004) |
| 번호대 분포 | `pattern_analysis(draws)["range_dist"]` 재사용 가능 |
| 연도별 평균 당첨금 추이 | 신규 집계 — 기존 함수 미제공 |

→ 단일 함수 `dashboard_overview(draws)`에서 전체 회차를 1회 순회(O(N))하며 모든 지표를 집계한다 (REQ-DASH-NFR-003).
   `range_distribution`은 동일 순회 내에서 직접 계산하거나 `pattern_analysis` 결과를 차용한다.

### 빈 데이터 처리

`draws`가 `None`/빈 리스트면 모든 키가 존재하는 일관된 빈 구조를 반환한다 (REQ-DASH-011).
1~45 번호 키와 5개 구간 키, `{"odd":0,"even":0}`는 항상 초기화한다.

### Python 3.9 호환 유의

기존 코드는 `# noqa: UP017`(datetime.timezone.utc), `# noqa: UP045`(Optional) 등 3.9 호환 마커를 유지한다.
신규 코드도 동일 관례를 따르며 `zip(strict=...)` 등 3.10+ 전용 API는 사용하지 않는다 (메모리: feedback_python39).

## 마일스톤 (우선순위 기반, 시간 추정 없음)

### Priority High — M1: 데이터 집계 함수

- `lotto/web/data.py`에 `dashboard_overview(draws=_UNSET) -> dict[str, Any]` 추가
- 전체 회차 단일 순회로 7개 지표 집계
- 빈 데이터 일관 구조 반환
- `# @MX:NOTE` / `# @MX:SPEC: SPEC-LOTTO-038` 태그 부착 (기존 함수 관례)
- 대응: REQ-DASH-001 ~ REQ-DASH-011

### Priority High — M2: API 엔드포인트

- `lotto/web/routes/api.py`에 `@router.get("/stats/overview")` 추가
- `dashboard_overview()` 결과를 dict로 반환 (데이터 부재 시 200 + 빈 구조)
- 대응: REQ-DASH-API-001 ~ REQ-DASH-API-003

### Priority Medium — M3: 웹 페이지 + 템플릿

- `lotto/web/routes/pages.py`에 `@router.get("/stats")` 추가, `active_tab="stats"`
- `lotto/web/templates/stats.html` 작성 (`base.html` 상속)
  - 요약 카드: 총 회차수, 총 1등 당첨금 합계
  - 최고/최저 1등 당첨금 회차 카드 (회차 링크 → `/draw/{drwNo}` 재사용)
  - 번호별 출현 횟수 차트 (기존 페이지의 Chart.js CDN 패턴 차용)
  - 홀짝 분포 / 번호대 분포 시각화
  - 연도별 평균 당첨금 추이 라인 차트
  - 빈 데이터 안내 메시지
- 대응: REQ-DASH-PAGE-001 ~ REQ-DASH-PAGE-003

### Priority Medium — M4: 네비게이션 통합

- `lotto/web/templates/base.html`의 `desktop_nav_items`, `nav_items`, 모바일 라벨 분기에 `통계 대시보드` 항목 추가
- 대응: REQ-DASH-PAGE-004

### Priority High — M5: 테스트 (최소 12개)

- `tests/test_dashboard_overview.py` (집계 단위 테스트)
- `tests/test_api_stats_overview.py` (API 통합 테스트)
- `tests/test_stats_page.py` (페이지 렌더링 테스트)
- 대응: REQ-DASH-NFR-002

## 파일 변경 요약

| 파일 | 변경 유형 |
|------|----------|
| `lotto/web/data.py` | 함수 추가 (`dashboard_overview`) |
| `lotto/web/routes/api.py` | 라우트 추가 (`/stats/overview`) |
| `lotto/web/routes/pages.py` | 라우트 추가 (`/stats`) |
| `lotto/web/templates/stats.html` | 신규 파일 |
| `lotto/web/templates/base.html` | 네비게이션 항목 추가 |
| `tests/test_dashboard_overview.py` | 신규 파일 |
| `tests/test_api_stats_overview.py` | 신규 파일 |
| `tests/test_stats_page.py` | 신규 파일 |

(소스 4파일 + 템플릿 1신규/1수정 → 3+파일 변경: file-by-file 단위로 분해 진행)

## 리스크 및 완화

- **R1: 홀짝 분포 정의 모호성** — 요청서 "홀짝 분포"가 (a) 회차별 홀수 개수 히스토그램인지 (b) 전역 홀/짝 누적인지 모호.
  → ASM-004에서 (b) 전역 누적으로 명시 고정. 검토 시 다른 정의를 원하면 REQ-DASH-008 수정.
- **R2: 당첨금 None 회차 혼입** — 초기 회차/미수집 회차는 `prize1Amount` 없음.
  → 모든 당첨금 집계는 `prize1Amount is not None` 필터링 (ASM-002, REQ-DASH-007).
- **R3: 대용량 회차 시 성능** — 1000+ 회차.
  → 단일 O(N) 순회 보장 (REQ-DASH-NFR-003). 기존 60초 TTL 캐시(`get_draws`)가 반복 호출을 흡수.
- **R4: 테스트의 monkeypatch 호환성** — 기존 테스트는 `lotto.web.data`/`pages` 심볼을 patch.
  → 신규 라우트는 기존 패턴(동적 import 또는 모듈 심볼 사용)을 그대로 따른다.

## 전문가 컨설팅 권고

- 백엔드 집계 로직(`dashboard_overview`): 기존 `pattern_analysis` / `get_prize_stats` 패턴이 명확하여 별도 컨설팅 불필요.
- 프론트엔드 차트 구성(`stats.html`): 기존 `analyze.html` / `simulate.html`의 Chart.js 패턴 재사용 권장 — 구현 단계에서 expert-frontend 참조 가능 (선택).
