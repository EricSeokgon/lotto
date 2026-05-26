---
id: SPEC-LOTTO-009
version: "1.0.0"
status: implemented
created: "2026-05-21"
updated: "2026-05-21"
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-009: 데이터 게이트웨이 캐싱 및 최근 수집 정보 표시

## HISTORY

| 버전 | 일자 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| 1.0.0 | 2026-05-21 | ircp | 초기 SPEC 작성 — `lotto/web/data.py`에 TTL 60초 모듈 레벨 캐시 도입 및 인덱스 페이지에 마지막 수집 날짜(last_date) 표시. |

---

## Overview (개요)

### What (무엇을 만드는가)

본 SPEC은 두 가지 개선을 정의한다.

1. **데이터 게이트웨이 캐싱** — `lotto/web/data.py`의 핵심 읽기 함수(`get_draws`, `get_stats`)에 TTL 60초 모듈 레벨 캐시를 도입한다. 동일 요청이 60초 이내 반복되면 CSV/JSON을 재파싱하지 않고 메모리에 보관된 결과를 반환한다. 데이터 수집/분석/크롤링 작업이 완료되면 `invalidate_cache()`를 통해 캐시를 즉시 무효화한다.

2. **인덱스 페이지 최근 수집 정보** — `lotto/web/templates/base.html`이 이미 지원하는 `last_date` 컨텍스트 변수를 `pages.index()` 라우트가 채워서 전달한다. `data/last_sync.json`의 `synced_at` 필드를 우선 사용하고, 없으면 `draws.csv`의 최신 회차 `date`로 대체한다.

### Why (왜 만드는가)

- **성능**: `LottoCollector.load_existing()`은 1,000회차 이상의 CSV 전체를 매 요청마다 파싱한다. 동시 다발 요청(예: 사용자가 빠르게 탭을 전환) 시 디스크 I/O와 파싱 비용이 누적된다. 60초 TTL 캐시는 짧은 윈도우 내 중복 작업을 제거하면서도 데이터 신선도를 유지한다.
- **사용자 경험**: 현재 인덱스 페이지는 데이터 존재 여부만 표시하며 "데이터가 얼마나 최신인가"라는 핵심 정보를 노출하지 않는다. `base.html`은 이미 `last_date` 슬롯을 갖고 있으나, `pages.index()`가 값을 채우지 않아 항상 비어 있다.
- **단순성**: 외부 캐시 라이브러리(redis, memcached)를 도입하지 않고 Python 표준 라이브러리(`time` 모듈)와 모듈 레벨 전역 변수만 사용한다. 단일 ASGI 워커 환경에 충분하다.

### Scope (적용 범위)

**포함**:
- `lotto/web/data.py` — `get_draws()`, `get_stats()` 캐싱 도입 및 `invalidate_cache()`, `get_last_sync_date()` 함수 추가.
- `lotto/web/routes/api.py` — 백그라운드 워커(`_collect_worker`, `_scrape_worker`, `_run_analyze*`) 완료 시점에 `invalidate_cache()` 호출.
- `lotto/web/routes/pages.py` — `index()` 라우트가 `last_date` 컨텍스트를 템플릿에 전달.
- 신규 테스트 `tests/test_data_cache.py`, `tests/test_pages_last_date.py`.

**제외**:
- `get_recommendations()`, `get_simulation()`, `get_strategy_comparison()` 등 파생 함수의 캐싱 (이들은 내부적으로 `get_draws`/`get_stats`를 호출하므로 간접 캐시 효과가 발생).
- 멀티 프로세스/워커 환경 캐시 동기화.
- 외부 캐시 라이브러리.

---

## Requirements (요구사항 — EARS Format)

### Functional Requirements

#### REQ-CACHE-001: get_draws TTL 캐시 (Event-driven)
WHEN `get_draws()`가 호출되면, 시스템은 마지막 디스크 로드 시각으로부터 60초 이내인 경우 메모리 캐시된 결과를 반환해야 하며, CSV를 재파싱하지 않아야 한다.

#### REQ-CACHE-002: get_stats TTL 캐시 (Event-driven)
WHEN `get_stats()`가 호출되면, 시스템은 마지막 디스크 로드 시각으로부터 60초 이내인 경우 메모리 캐시된 결과를 반환해야 하며, JSON을 재파싱하지 않아야 한다.

#### REQ-CACHE-003: 캐시 무효화 함수 (Ubiquitous)
시스템은 `lotto.web.data.invalidate_cache()` 함수를 노출해야 한다. 이 함수는 `get_draws`/`get_stats`의 캐시 엔트리를 모두 제거하며, `POST /collect`, `POST /analyze`, `POST /scrape`의 백그라운드 작업 완료 후 호출되어야 한다.

#### REQ-CACHE-004: 캐시 적중 동등성 (Ubiquitous)
캐시 적중 여부와 무관하게 `get_draws()` 및 `get_stats()`의 반환 객체는 디스크에서 재로드한 결과와 의미론적으로 동일해야 한다.

#### REQ-LAST-001: 인덱스 페이지 최근 수집 날짜 표시 (Ubiquitous)
인덱스 페이지(`GET /`)는 템플릿 컨텍스트에 `last_date` 키를 포함시켜 헤더에 "최근 수집: YYYY-MM-DD" 형식으로 표시해야 한다.

#### REQ-LAST-002: last_date 소스 우선순위 (State-driven)
`get_last_sync_date()`는 다음 순서로 값을 결정해야 한다:
1. `data/last_sync.json`이 존재하고 `synced_at` 필드가 있으면 그 값의 앞 10자(YYYY-MM-DD)를 반환.
2. 그렇지 않으면 `get_draws()` 결과 중 최신 회차의 `date` 필드 문자열을 반환.
3. 두 소스 모두 없으면 `None`을 반환하고, 템플릿은 헤더 영역을 숨겨야 한다(이미 `{% if last_date %}` 가드 적용됨).

### Non-Functional Requirements

#### NFR-001: 표준 라이브러리만 사용
캐시 구현은 Python 표준 라이브러리(`time`, `typing` 모듈)만 사용해야 한다. 외부 패키지(redis, memcached, cachetools 등)를 도입하지 않는다.

#### NFR-002: Python 3.9 호환
모든 신규 코드는 Python 3.9에서 실행 가능해야 한다. `zip(strict=True)`, `match`/`case`, `X|Y` 런타임 union 등 Python 3.10+ 문법을 사용하지 않는다.

#### NFR-003: 기존 API 시그니처 보존
`get_draws()`와 `get_stats()`의 외부 시그니처(파라미터, 반환 타입)는 변경하지 않는다. 모든 379개 기존 테스트가 계속 통과해야 한다.

#### NFR-004: 커버리지 유지
프로젝트 전체 테스트 커버리지는 95% 이상을 유지해야 한다.

---

## SPEC Traceability

- 영향 받는 SPEC: SPEC-WEB-001 (웹 대시보드), SPEC-LOTTO-007 (last_sync.json 메타데이터 생성)
- 신규 게이트웨이 진입점: `lotto.web.data.invalidate_cache`, `lotto.web.data.get_last_sync_date`

---

Version: 1.0.0
Status: draft
Last Updated: 2026-05-21
