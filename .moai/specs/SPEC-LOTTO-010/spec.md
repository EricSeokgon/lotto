---
id: SPEC-LOTTO-010
version: "1.0.0"
status: completed
created: "2026-05-21"
updated: "2026-05-21"
author: ircp
priority: medium
issue_number: 0
---

# SPEC-LOTTO-010: 웹 UI 페이지네이션 컨트롤 및 문서 링크

## HISTORY

| 버전 | 일자 | 작성자 | 변경 내용 |
|------|------|--------|-----------|
| 1.0.0 | 2026-05-21 | ircp | 초기 SPEC 작성 — collect 페이지에 클라이언트 사이드 페이지네이션 컨트롤을 추가하고, 기본 레이아웃 네비게이션에 API 문서(/docs) 링크를 노출한다. |

---

## Overview (개요)

### What (무엇을 만드는가)

SPEC-LOTTO-006에서 `/api/draws` 엔드포인트에 `limit`, `offset`, `from_round`,
`to_round` 페이지네이션 파라미터를 추가했지만, 웹 UI(`/collect` 페이지)는
여전히 서버 사이드 렌더링으로 마지막 5회차만 하드코딩하여 노출하고 있다.
본 SPEC은 `/collect` 페이지의 최근 추첨 결과 테이블을 **JavaScript fetch
기반 페이지네이션 UI**로 교체하고, 모든 페이지의 상단 네비게이션에 FastAPI
자동 생성 OpenAPI 문서(`/docs`) 링크를 추가한다.

### Why (왜 만드는가)

- 사용자가 5회차 이전의 회차 데이터를 보려면 CLI 또는 직접 API 호출이
  필요했으나, 웹 UI 만으로도 전체 데이터 탐색이 가능해야 한다.
- SPEC-LOTTO-006에서 추가된 페이지네이션 API가 실제 UI에서 활용되지 않으면
  기능이 사장된다.
- API 문서(`/docs`)는 FastAPI가 자동 생성하지만, UI 진입점이 없어 일반
  사용자가 API 표면을 발견하기 어렵다.
- 서버 사이드 5회차 하드코딩(`draws[-5:]`)을 제거하면 전체 회차 데이터를
  템플릿으로 직렬화하는 비용을 줄이지는 않더라도, 미래에 데이터 직렬화를
  제거할 여지를 만든다(이 SPEC에서는 호환성을 위해 직렬화 자체는 유지).

### Scope (적용 범위)

포함:
- `lotto/web/templates/base.html`: 네비게이션에 API 문서(`/docs`) 링크 추가
- `lotto/web/templates/collect.html`: 정적 5회차 테이블을 클라이언트 JS
  페이지네이션 테이블로 교체 (페이지당 10회, 이전/다음 버튼, 현재 페이지
  번호 및 총 회차 수 표시)
- `tests/test_web_pages.py`: 위 동작을 검증하는 회귀 테스트 추가

제외:
- `lotto/web/routes/pages.py`: 변경하지 않음 (`draws` 컨텍스트는 요약
  카드(`{% if draws %}`, `draws | length` 등)에서 계속 사용되므로 유지)
- URL 쿼리 파라미터 동기화 (브라우저 뒤로 가기 등)는 본 SPEC에서 제외
- `/api/draws` 엔드포인트 변경 — SPEC-LOTTO-006의 인터페이스 그대로 사용

---

## Glossary (용어 정의)

| 용어 | 정의 |
|------|------|
| 페이지네이션 | 데이터를 한정된 페이지 단위로 분할 표시하고, 이전/다음
                 버튼으로 페이지를 이동하는 UI 패턴 |
| /docs | FastAPI가 자동 생성하는 Swagger UI 기반 OpenAPI 문서 페이지 |
| PAGE_SIZE | 한 페이지에 표시할 회차 수 — 본 SPEC에서는 10으로 고정 |
| 클라이언트 사이드 페이지네이션 | 서버는 페이지네이션 API만 제공하고,
                              브라우저 JavaScript가 페이지 상태를 관리하는
                              패턴 |

---

## Requirements (EARS 형식 요구사항)

### REQ-UI-001 (Event-driven)

**WHEN** 사용자가 `/collect` 페이지를 방문하면,
**THEN** 시스템은 최근 5회 고정 표시 대신 페이지당 10회를 기본으로 표시하고,
이전/다음 버튼을 통해 회차 데이터를 탐색할 수 있도록 한다.

### REQ-UI-002 (Ubiquitous)

`/collect` 페이지의 페이지네이션 컨트롤은 JavaScript `fetch` API를 사용하여
`/api/draws?limit=10&offset=N` 엔드포인트를 호출해야 한다.

### REQ-UI-003 (Ubiquitous)

`/collect` 페이지는 현재 페이지 번호와 총 회차 수를 사용자에게 표시해야
한다.

### REQ-UI-004 (Ubiquitous)

기본 레이아웃(`base.html`)의 네비게이션은 API 문서 페이지(`/docs`) 링크를
포함해야 하며, 이 링크는 모든 페이지에 노출된다.

### NFR-UI-001 (Optional)

페이지네이션 상태(현재 페이지 번호)는 URL 쿼리 파라미터로 유지하지 않아도
무방하다. 클라이언트 JavaScript 메모리 상태로 충분하다.

### NFR-UI-002 (Ubiquitous)

본 SPEC의 변경은 SPEC-LOTTO-006(`/api/draws` 페이지네이션 API)의 동작과
호환되어야 하며, 기존 399개 테스트가 모두 통과해야 한다.

---

## Acceptance Criteria

상세 인수 기준은 `acceptance.md` 참조.

---

## Technical Approach (구현 접근)

1. **base.html**: 네비게이션 `<div class="flex space-x-1 ...">` 내부에
   기존 링크와 동일한 스타일(`px-4 py-2 text-sm font-medium border-b-2 ...`)
   을 사용하여 `/docs` 링크를 추가한다. `active_tab == 'docs'` 분기는
   필요하지 않다 (외부 페이지로 이동).

2. **collect.html**:
   - 라인 160~189의 "최근 추첨 결과" 테이블 섹션을 유지하되, 내부
     `{% for draw in draws[-5:] | reverse %}` Jinja2 루프를 제거하고
     `<tbody id="draws-tbody">`를 빈 채로 둔다.
   - 테이블 아래에 `<div>` 페이지네이션 컨트롤(이전/다음 버튼, 페이지 정보)
     을 추가한다.
   - `{% block scripts %}` 내에 `loadDraws`, `renderTable`,
     `updatePagination`, `changePage` 함수를 추가하고,
     `DOMContentLoaded` 시점에 `loadDraws(0)`을 호출한다.
   - 기존의 `draws | length`, `draws | min(attribute='drwNo')`,
     `draws | max(attribute='drwNo')` 요약 카드와 `{% if draws %}`
     빈 상태 분기는 그대로 유지한다.

3. **pages.py**: 변경하지 않는다 (`draws` 컨텍스트는 요약 카드와 빈 상태
   분기에서 사용 중).

4. **테스트**: `tests/test_web_pages.py`에 다음 테스트를 추가한다:
   - `test_base_nav_has_docs_link`: 모든 페이지에 `/docs` 링크 노출
   - `test_collect_has_pagination_controls`: 페이지네이션 컨트롤 존재
   - `test_collect_uses_api_draws_for_pagination`: fetch URL 패턴 검증
   - `test_collect_shows_page_info_placeholder`: 페이지 정보 영역 존재

---

## Test Plan (테스트 계획)

- pytest로 4개 신규 테스트 추가 (총 403개)
- 기존 399개 회귀 테스트 통과 확인
- 커버리지 96.25% 이상 유지
