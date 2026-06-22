# SPEC-LOTTO-104 구현 계획

## 구현 전략

TDD(Test-Driven Development) 방식으로 구현한다. RED → GREEN → REFACTOR 사이클을 따른다.
손계산이 가능한 소규모 `DrawResult` 픽스처(acceptance.md 기준 5회차)를 사용하여 last_seen_ago·avg/max/min interval·appearance_count·overdue·recent를 결정적으로 검증한다.

예상 테스트 수: 약 25개 (`tests/test_recency_analysis.py`).

---

## 구현 순서

### Phase 1: 테스트 작성 (RED)

`tests/test_recency_analysis.py`에 다음 테스트를 먼저 작성한다 (모두 실패 상태).

**핵심 함수 `get_recency_analysis` 단위 테스트:**

1. `test_numbers_all_45_items` — `numbers`가 1~45 모든 항목 포함, 번호 오름차순 (REQ-REC-U02)
2. `test_number_item_keys` — 각 항목에 6개 필수 키 존재 (REQ-REC-U02)
3. `test_last_seen_ago_hand_counted` — 번호 1=1, 번호 7=2 (REQ-REC-U03)
4. `test_last_seen_ago_zero_when_in_latest` — 최근 회차 출현 번호 = 0 (번호 2) (REQ-REC-U03)
5. `test_last_seen_ago_none_when_never` — 미출현 번호 = None (번호 30) (REQ-REC-U03)
6. `test_avg_interval_uses_consecutive_gaps` — 번호 1 avg_interval=1.5 (mean([1,2])) (REQ-REC-U04)
7. `test_avg_interval_two_decimals` — round(mean(gaps), 2) (REQ-REC-U04)
8. `test_max_min_interval` — 번호 1 max=2, min=1 (REQ-REC-U05)
9. `test_single_appearance_interval_none` — 1회 출현(번호 6) → avg/max/min=None, count=1, last_seen_ago=4 (REQ-REC-S02)
10. `test_appearance_count_hand_counted` — 번호 1·2=3, 번호 7=2 (REQ-REC-U06)
11. `test_appearance_count_main_only` — 보너스 출현은 count 제외 (REQ-REC-N02)
12. `test_overdue_descending` — last_seen_ago 내림차순 상위 top_n (REQ-REC-U07)
13. `test_overdue_none_first` — 미출현(None) 최상단 (REQ-REC-U07)
14. `test_overdue_tie_smaller_number_first` — 동률 시 작은 번호 우선 (REQ-REC-U07)
15. `test_overdue_size_equals_top_n` — top_n=3 → overdue 길이 3 (REQ-REC-U07)
16. `test_recent_is_latest_draw_numbers` — recent == 최근 회차 본번호 오름차순 (REQ-REC-U08)
17. `test_result_keys_present` — 반환 dict 필수 키 모두 존재 (REQ-REC-U01)
18. `test_deterministic` — 동일 입력 → 동일 결과 (REQ-REC-U09)
19. `test_disclaimer_present` — disclaimer 키 포함 (REQ-REC-N03)

**경계/빈 데이터 테스트:**

20. `test_empty_draws_returns_none_filled` — `draws=[]` → total 0, 45개 None/0, 빈 overdue/recent (REQ-REC-S01)
21. `test_none_draws_returns_none_filled` — `draws=None` → 동일

**API 라우트 테스트 (`GET /api/stats/recency`):**

22. `test_recency_api_default_top_n_10` — top_n 미지정 시 기본 10 (REQ-REC-E02)
23. `test_recency_api_returns_required_fields` — 응답에 필수 필드 포함, HTTP 200 (REQ-REC-E01)
24. `test_recency_api_top_n_boundaries` — top_n=0/46 → 422, top_n=1/45 → 200 (REQ-REC-N01)

**웹 페이지 테스트 (`GET /stats/recency`):**

25. `test_recency_page_renders` — HTTP 200, HTML, 번호별 테이블 포함 (REQ-REC-E03)
26. `test_recency_nav_tab_exists` — `base.html` 내비게이션에 "주기 분석" 탭 존재(`/stats/recency`, tab=`recency`)

---

### Phase 2: 구현 (GREEN)

최소 코드로 모든 테스트를 통과시킨다.

**우선순위 High:**

1. `lotto/web/data.py` — `get_recency_analysis(draws, top_n=10) -> dict[str, Any]` 구현
   - 빈/None 데이터 가드 (45개 None/0 항목, 빈 overdue/recent)
   - 회차 오름차순 정렬 (`sorted(draws, key=lambda d: d.drwNo)`), `last_idx = total_draws - 1`
   - 단일 패스로 번호별 출현 인덱스 리스트 수집 (`draw.numbers()` 기준, 보너스 제외)
   - 번호별 last_seen_ago / gaps → avg(round 2)/max/min / appearance_count 산출
   - 1회 출현·미출현 시 None 처리(0 아님)
   - overdue 정렬 (None을 math.inf로 취급, `(-val, number)` 키, 상위 top_n)
   - recent = 최근 회차 `numbers()` (빈 데이터면 [])
   - disclaimer 포함 (도박사의 오류 경계 문구)
   - Python 3.9 호환 타입 힌트, `match`/`case` 및 `zip(strict=True)` 미사용

2. `lotto/web/routes/api.py` — `GET /api/stats/recency` 엔드포인트 추가
   - `top_n: int = Query(default=10, ge=1, le=45)` (위반 시 자동 HTTP 422)
   - `get_draws()` → `get_recency_analysis(draws, top_n)` → JSON 반환
   - 테스트 patch 호환: 라우트 내부에서 `from lotto.web import data as wd` 동적 호출

3. `lotto/web/routes/pages.py` — `GET /stats/recency` 라우트 추가
   - `top_n: int = Query(default=10, ge=1, le=45)`
   - `active_tab="recency"`, 분석 결과·top_n을 템플릿 컨텍스트로 전달
   - `_render(request, "recency_analysis.html", {...})`

**우선순위 Medium:**

4. `lotto/web/templates/recency_analysis.html` — 신규 템플릿
   - 번호별 테이블 (번호 | last_seen_ago | avg_interval | appearance_count)
   - overdue 강조 (`last_seen_ago > avg_interval * 1.5`인 행)
   - recent 번호 배지 그룹 (최근 회차 출현 번호)
   - top_n 선택기 (5/10/20 프리셋)
   - 면책 고지 표시
   - 선택: max_interval/min_interval 컬럼 (REQ-REC-O01)

5. `lotto/web/templates/base.html` — 내비게이션 수정
   - `desktop_nav_items`에 `('/stats/recency', 'recency', '주기 분석')` 추가
   - `active_tab == 'recency'` 헤딩 분기 추가
   - 기존 `('/numbers/cycle', 'cycle', '당첨 주기')` 탭은 유지(별개 기능)

---

### Phase 3: 리팩토링 (REFACTOR)

- gaps 계산·overdue 정렬 로직 헬퍼 분리 (가독성 향상, 필요 시)
- None-우선 정렬 키를 작은 순수 함수(`_overdue_key`)로 추출
- 코드 중복 제거
- mypy 타입 검사 통과 확인 (`mypy.ini`에 `tests/test_recency_analysis.py` override 등록)
- ruff 린트 통과 확인 (`# noqa` 최소화)
- 테스트 커버리지 확인

---

## 마일스톤

| 우선순위 | 작업 | 산출물 |
|----------|------|--------|
| High | RED: ~25개 테스트 작성 | `tests/test_recency_analysis.py` |
| High | GREEN: `get_recency_analysis` 구현 | `lotto/web/data.py` |
| High | GREEN: API 엔드포인트 | `lotto/web/routes/api.py` |
| Medium | GREEN: 페이지 라우트 + 템플릿 | `pages.py`, `recency_analysis.html` |
| Medium | GREEN: 내비게이션 탭 | `base.html` |
| Low | REFACTOR: 헬퍼 분리·품질 게이트 | 전체 |

---

## 기술적 접근

- 핵심 분석은 `lotto/web/data.py`의 순수 함수(`get_recency_analysis`)에 집중하여 단위 테스트 용이성 확보.
- API/페이지 라우트는 얇은 어댑터로 유지 (`get_draws()` → 분석 함수 → 직렬화/렌더링).
- 출현 인덱스 수집은 O(회차 × 6) 단일 패스, gap/통계는 번호별 O(출현수)로 계산.
- `numbers`/`overdue`를 **리스트(of dict)** 로 반환하여 JSON int/str 키 모호성을 원천 차단(SPEC-103의 dict-키 직렬화 위험 회피).
- 결정적 결과를 위해 난수/시간 의존 배제, 정렬 동률은 항상 (`-val`, `number`)로 안정화.
- SPEC-047 `cycle_analysis`는 호출·수정하지 않고 완전히 독립된 함수를 신설(지표 정의가 다름).

---

## 위험 요소 및 완화

| 위험 | 영향 | 완화 |
|------|------|------|
| `get_draws()` 정렬 순서 미보장 | last_seen_ago·간격 계산 오류 | `sorted(draws, key=lambda d: d.drwNo)`로 명시 정렬 |
| SPEC-047과 혼동·병합 시도 | 잘못된 지표(total/count)로 구현 | spec.md 배경·exclusions에 차이 명시, 독립 함수 신설 |
| 미출현/1회 출현 None 처리 누락 | 0과 혼동되어 통계 왜곡 | None 분기 명시(avg/max/min), 테스트로 강제 |
| overdue None 정렬 오류 | 미출현 번호 누락/오정렬 | `math.inf` 키로 None 최우선, 동률 작은 번호 우선 |
| `numbers()`를 property로 오용 | `AttributeError`/잘못된 집계 | 항상 `draw.numbers()` 메서드 호출 |
| 외부 명세 `draw_no` vs 실제 `drwNo` | AttributeError | 실제 필드 `drwNo` 사용 확인 |
| 전체 mypy 게이트 사전 부채 차단 | 커밋 실패 | `GIT_BIN` 우회 패턴 적용 (기존 관례) |
| Python 3.9 비호환 문법 | 런타임/CI 오류 | `if/elif/else`, `Optional[T]`, `# noqa: B905` 사용 |

---

## 품질 게이트

- `pytest tests/test_recency_analysis.py` — 전체 통과
- `mypy lotto/web/data.py lotto/web/routes/api.py lotto/web/routes/pages.py` — 타입 오류 0건
- ruff 린트 통과
- Python 3.9 호환성 확인
- 면책 고지 API·UI 포함 확인
- 기존 경로·탭 키 충돌 없음, SPEC-047 미수정 확인
