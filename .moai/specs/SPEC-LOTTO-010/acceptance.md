# SPEC-LOTTO-010 인수 기준

## AC-UI-001: /docs 링크가 모든 페이지의 네비게이션에 표시된다

**Given** 웹 서버가 실행 중이고 데이터 상태와 무관하게 어떤 페이지든 접근 가능할 때
**When** 사용자가 `/`, `/collect`, `/analyze`, `/recommend`, `/simulate`,
`/history` 중 어느 페이지든 GET 요청을 보내면
**Then** 응답 HTML에 `href="/docs"` 속성을 가진 `<a>` 태그가 포함되어야 한다.

**검증 방법**: pytest `test_base_nav_has_docs_link`

---

## AC-UI-002: /collect 페이지에 페이지네이션 컨트롤이 렌더링된다

**Given** `/collect` 페이지가 200으로 응답할 때
**When** 응답 HTML을 검사하면
**Then** 다음 요소가 모두 포함되어야 한다:
- `id="draws-tbody"` (페이지네이션 대상 tbody)
- `id="btn-prev"` (이전 버튼)
- `id="btn-next"` (다음 버튼)
- `id="page-info"` (페이지 정보 표시 영역)

**검증 방법**: pytest `test_collect_has_pagination_controls`

---

## AC-UI-003: 클라이언트 JS가 /api/draws?limit=10 패턴을 사용한다

**Given** `/collect` 페이지가 200으로 응답할 때
**When** 응답 HTML 내의 `<script>` 블록을 검사하면
**Then** 다음 패턴 중 하나 이상이 포함되어야 한다:
- 문자열 `/api/draws?limit=` (URL 빌드 시 사용)
- 변수 `PAGE_SIZE` 또는 상수 `10` (페이지당 회차 수)

**검증 방법**: pytest `test_collect_uses_api_draws_for_pagination`

---

## AC-UI-004: 정적 draws[-5:] 루프가 제거된다

**Given** `/collect` 페이지가 렌더링된 후
**When** 응답 HTML을 검사하면
**Then** 응답에는 `<tbody id="draws-tbody"></tbody>`(또는 공백 포함 빈
tbody) 가 존재해야 하며, 서버 사이드 Jinja2 `{% for %}` 루프에서 생성된
회차 행은 포함되지 않아야 한다 (모킹된 draws 데이터의 회차 번호가 초기
HTML에 직접 나타나지 않음).

**검증 방법**: pytest `test_collect_tbody_is_empty_for_js_population`

---

## AC-UI-005: 기존 399개 회귀 테스트 통과

**Given** SPEC-LOTTO-010 변경 적용 후
**When** `python3.9 -m pytest tests/` 명령을 실행하면
**Then** 모든 기존 테스트(399개) + 신규 테스트(4개) = 총 403개 이상이
통과해야 한다.

**검증 방법**: pytest 전체 실행 결과
