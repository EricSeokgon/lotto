---
id: SPEC-LOTTO-038
version: 0.1.0
status: Planned
created: 2026-06-01
updated: 2026-06-01
author: ircp
priority: medium
---

# SPEC-LOTTO-038: 로또 통계 대규모 대시보드

## HISTORY

- 2026-06-01 (v0.1.0): 최초 작성 — 전체 회차 데이터를 시각적으로 요약하는 메인 통계 대시보드 (`/stats`). 신규 API `GET /api/stats/overview` + 신규 페이지 `/stats` + 신규 데이터 집계 함수 `dashboard_overview()`. (author: ircp)

---

## 1. Environment (환경)

- **언어/런타임**: Python 3.11 (현 코드베이스는 Python 3.9 호환 마커 유지 — `# noqa: UP017`, `# noqa: UP045` 등 기존 패턴을 깨지 않음)
- **웹 프레임워크**: FastAPI + Jinja2 템플릿
- **데이터 소스**: CSV/JSON 파일 (`lotto/data/draws.csv`, `lotto/data/stats.json`)
- **데이터 접근 레이어**: `lotto/web/data.py` (읽기 전용 래퍼, 60초 TTL 메모리 캐시)
- **테스트**: pytest, `PYTHONPATH=/home/sklee/moai/lotto`, 현재 939 tests / 96%+ coverage
- **도메인 모델**: `lotto.models.DrawResult` — `drwNo`, `date`, `prize1Amount`, `prize1Winners`, `numbers()` 보유
- **기존 통계 진입점** (재사용 대상):
  - `get_prize_stats()` — 총/평균/최대/최소 1등 당첨금 + recent
  - `pattern_analysis()` — odd_even, range_dist, total_draws
  - `get_draws()` — 전체 회차 로드

## 2. Assumptions (가정)

- ASM-001: 모든 회차 데이터는 `get_draws()`로 단일 로드되며, 대시보드 집계는 이 단일 결과를 인자로 전달받아 중복 CSV 파싱을 피한다 (기존 `pattern_analysis(draws)` 패턴 준수).
- ASM-002: 일부 회차는 `prize1Amount`가 `None`일 수 있다 (당첨금 정보 미수집). 당첨금 관련 집계는 `prize1Amount is not None`인 회차만 포함한다.
- ASM-003: 번호대 구간은 기존 `pattern_analysis`와 동일하게 `1-9 / 10-19 / 20-29 / 30-39 / 40-45` 5구간을 사용한다 (요청서의 "1-9, 10-19, ..." 표기와 일치).
- ASM-004: 홀짝 분포는 "전체 회차에 출현한 전체 당첨번호(본번호 6개 × 회차수)"의 홀/짝 누적 개수로 정의한다 (회차별 홀수 개수 히스토그램이 아님 — 요청서의 "홀짝 분포"를 전역 누적으로 해석).
- ASM-005: 연도는 `DrawResult.date.year`로 산출한다.
- ASM-006: 데이터가 전혀 없을 때(`get_draws()` is None 또는 빈 리스트)에도 페이지/API는 정상 동작하며, 0/빈 리스트/None으로 구성된 일관된 빈 구조를 반환한다 (기존 `weekly-report`, `prize-stats` 정책 준수).
- ASM-007: `GET /api/stats/overview`는 외부 의존성을 추가하지 않으며 표준 라이브러리만 사용한다 (Chart.js 등 클라이언트 시각화 라이브러리는 이미 다른 페이지에서 CDN으로 로드 중).

## 3. Requirements (요구사항 — EARS)

### 3.1 데이터 집계 (dashboard_overview)

- **REQ-DASH-001** (Ubiquitous): The system SHALL provide a single aggregation function `dashboard_overview(draws=None)` in `lotto/web/data.py` that returns 전체 회차 요약 통계를 단일 dict로 반환한다.

- **REQ-DASH-002** (Event-Driven): WHEN `dashboard_overview()`가 `draws` 인자 없이 호출되면 THEN the system SHALL `get_draws()`로 전체 회차를 자동 로드한다.

- **REQ-DASH-003** (Ubiquitous): The system SHALL include `total_draws` (총 회차수) in the overview result.

- **REQ-DASH-004** (Ubiquitous): The system SHALL include `total_prize1_sum` (당첨금 정보가 있는 회차의 1등 당첨금 합계, 정수) in the overview result.

- **REQ-DASH-005** (Ubiquitous): The system SHALL include `number_frequency` — 번호 1~45 각각의 본번호 출현 횟수를 담은 구조 (예: `[{"number": n, "count": c}, ...]` 또는 `{number: count}`) — in the overview result, 1부터 45까지 모든 번호 키가 존재해야 한다.

- **REQ-DASH-006** (Ubiquitous): The system SHALL include `highest_prize1_draw` (최고 1등 당첨금 회차: `{drwNo, date, prize1Amount}`) and `lowest_prize1_draw` (최저 1등 당첨금 회차) in the overview result.

- **REQ-DASH-007** (State-Driven): IF 당첨금 정보가 있는 회차가 하나도 없으면 THEN the system SHALL `total_prize1_sum`을 0으로, `highest_prize1_draw` / `lowest_prize1_draw`를 `None`으로 반환한다.

- **REQ-DASH-008** (Ubiquitous): The system SHALL include `odd_even` — 전체 당첨번호의 홀수/짝수 누적 개수 (`{"odd": int, "even": int}`) — in the overview result.

- **REQ-DASH-009** (Ubiquitous): The system SHALL include `range_distribution` — `1-9 / 10-19 / 20-29 / 30-39 / 40-45` 5구간별 번호 누적 개수 — in the overview result, 5개 구간 키가 항상 존재해야 한다.

- **REQ-DASH-010** (Ubiquitous): The system SHALL include `yearly_avg_prize` — 연도별 평균 1등 당첨금 추이 (`[{"year": "YYYY", "avg_prize1": int, "draws": int}, ...]`, 연도 오름차순) — in the overview result, 당첨금 정보가 있는 회차만 평균 계산에 포함한다.

- **REQ-DASH-011** (State-Driven): IF `draws`가 비어 있거나 `None`이면 THEN the system SHALL `total_draws=0`, `total_prize1_sum=0`, 1~45 키가 모두 0인 `number_frequency`, `{"odd":0,"even":0}` 홀짝, 5구간 모두 0인 `range_distribution`, 빈 `yearly_avg_prize` 리스트, `None` 최고/최저 회차를 포함한 일관된 빈 구조를 반환한다.

### 3.2 API 엔드포인트

- **REQ-DASH-API-001** (Event-Driven): WHEN 클라이언트가 `GET /api/stats/overview`를 호출하면 THEN the system SHALL `dashboard_overview()` 결과를 HTTP 200 JSON으로 반환한다.

- **REQ-DASH-API-002** (State-Driven): IF 회차 데이터가 없으면 THEN the system SHALL HTTP 200으로 빈 구조(REQ-DASH-011)를 반환한다 (503 아님 — `weekly-report` / `prize-stats` 정책과 동일).

- **REQ-DASH-API-003** (Unwanted): The system SHALL NOT 외부 네트워크 호출이나 파일 쓰기를 `GET /api/stats/overview` 처리 중 수행한다 (읽기 전용 집계 엔드포인트).

### 3.3 웹 페이지

- **REQ-DASH-PAGE-001** (Event-Driven): WHEN 사용자가 `/stats` 페이지를 요청하면 THEN the system SHALL `stats.html` 템플릿을 `active_tab="stats"` 컨텍스트와 함께 렌더링한다.

- **REQ-DASH-PAGE-002** (Ubiquitous): The `/stats` 페이지 SHALL 7개 통계 요소(총 회차수, 총 1등 당첨금 합계, 번호별 출현 횟수 차트, 최고/최저 1등 당첨금 회차, 홀짝 분포, 번호대 분포, 연도별 평균 당첨금 추이)를 모두 표시한다.

- **REQ-DASH-PAGE-003** (State-Driven): IF 회차 데이터가 없으면 THEN the `/stats` 페이지 SHALL 빈 상태 안내 메시지를 표시하고 서버 오류 없이 렌더링한다.

- **REQ-DASH-PAGE-004** (Ubiquitous): The system SHALL `/stats` 항목을 전역 네비게이션(`base.html`의 desktop_nav_items / nav_items)에 추가하여 다른 페이지에서 진입 가능하게 한다.

### 3.4 비기능 요구사항

- **REQ-DASH-NFR-001** (Ubiquitous): The system SHALL 신규 외부 의존성(pip 패키지) 없이 구현된다.

- **REQ-DASH-NFR-002** (Ubiquitous): The system SHALL 기존 939개 테스트를 회귀 없이 모두 통과하며, 신규 테스트는 최소 12개 이상 추가하여 신규 코드의 커버리지 85% 이상을 달성한다.

- **REQ-DASH-NFR-003** (Ubiquitous): The system SHALL `dashboard_overview()`를 전체 회차 데이터에 대해 단일 순회(O(N) — N=회차수)로 집계하여, 동일 데이터에 대한 중복 CSV 파싱을 발생시키지 않는다.

## 4. Specifications (사양)

### 4.1 `dashboard_overview()` 반환 구조 (예시)

```
{
  "total_draws": 1100,
  "total_prize1_sum": 25000000000,
  "number_frequency": [{"number": 1, "count": 152}, ... {"number": 45, "count": 161}],
  "highest_prize1_draw": {"drwNo": 19, "date": "2003-04-12", "prize1Amount": 40722959400},
  "lowest_prize1_draw": {"drwNo": 880, "date": "2019-08-31", "prize1Amount": 1392951225},
  "odd_even": {"odd": 3312, "even": 3288},
  "range_distribution": {"1-9": 1320, "10-19": 1480, "20-29": 1455, "30-39": 1390, "40-45": 955},
  "yearly_avg_prize": [{"year": "2002", "avg_prize1": 13000000000, "draws": 18}, ...]
}
```

### 4.2 위치 및 명명

- 집계 함수: `lotto/web/data.py` 내 `dashboard_overview(draws: list[DrawResult] | None = _UNSET) -> dict[str, Any]` (기존 `_UNSET` 센티넬 패턴 준수)
- API: `lotto/web/routes/api.py` 내 `@router.get("/stats/overview")` (router prefix `/api` → 최종 경로 `/api/stats/overview`)
- 페이지: `lotto/web/routes/pages.py` 내 `@router.get("/stats")`
- 템플릿: `lotto/web/templates/stats.html` (`base.html` 상속)
- 네비게이션: `lotto/web/templates/base.html`에 `('/stats', 'stats', '통계 대시보드')` 항목 추가

### 4.3 데이터 정의 정밀화

- `number_frequency`: 본번호(`DrawResult.numbers()`, 보너스 제외) 기준 누적. 1~45 전 키 존재.
- `odd_even`: 모든 회차의 모든 본번호에 대한 홀/짝 누적 개수 (ASM-004).
- `range_distribution`: `pattern_analysis`의 `range_dist`와 동일 구간/동일 의미. (구현 시 `pattern_analysis` 결과 재사용 가능)
- `yearly_avg_prize`: 연도별로 `prize1Amount is not None`인 회차의 평균(정수, 내림). `draws`는 해당 연도의 당첨금 보유 회차 수.

## 5. Exclusions (What NOT to Build)

- **EXC-001**: 보너스 번호(`bonus`)는 `number_frequency` / `odd_even` / `range_distribution` 집계에서 제외한다 (본번호 6개만 대상). 보너스 통계는 본 SPEC 범위 밖.
- **EXC-002**: 사용자 입력 기반 필터링(연도 범위 선택, 번호 범위 선택 등 인터랙티브 쿼리)은 본 SPEC 범위가 아니다 — 전체 회차 고정 요약만 제공한다.
- **EXC-003**: 대시보드 데이터의 CSV/PDF 내보내기는 본 SPEC 범위 밖이다 (기존 `/api/report/pdf`, `/api/export/*` 활용).
- **EXC-004**: 추천/시뮬레이션/예측 기능은 추가하지 않는다 — 본 SPEC은 순수 기술 통계 시각화에 한정한다.
- **EXC-005**: 새로운 데이터 파일 생성 또는 기존 데이터 파일 쓰기는 하지 않는다 (읽기 전용 집계).
- **EXC-006**: 기존 `/`, `/analyze`, `/numbers` 등 기존 페이지의 통계 표시 로직은 변경하지 않는다 (신규 `/stats` 페이지만 추가).
- **EXC-007**: 실시간 갱신/WebSocket/자동 새로고침은 범위 밖이다 — 페이지 로드 시점의 정적 스냅샷만 렌더링한다.
- **EXC-008**: 다국어(i18n) 지원은 추가하지 않는다 — 기존 한국어 UI 관례를 따른다.

## 6. Traceability

| 요구사항 | 구현 대상 | 검증 (acceptance.md) |
|---------|----------|---------------------|
| REQ-DASH-001~011 | `lotto/web/data.py::dashboard_overview` | AC-1 ~ AC-6 |
| REQ-DASH-API-001~003 | `lotto/web/routes/api.py::/stats/overview` | AC-7 ~ AC-9 |
| REQ-DASH-PAGE-001~004 | `pages.py::/stats`, `stats.html`, `base.html` | AC-10 ~ AC-12 |
| REQ-DASH-NFR-001~003 | 전체 | AC-13 (회귀/커버리지) |
