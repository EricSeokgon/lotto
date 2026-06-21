# SPEC-LOTTO-103 구현 계획

## 구현 전략

TDD(Test-Driven Development) 방식으로 구현한다. RED → GREEN → REFACTOR 사이클을 따른다.
손계산이 가능한 소규모 `DrawResult` 픽스처를 사용하여 빈도·비율·동시출현·최근추세를 결정적으로 검증한다.

예상 테스트 수: 약 30개 (`tests/test_bonus_analysis.py`).

---

## 구현 순서

### Phase 1: 테스트 작성 (RED)

`tests/test_bonus_analysis.py`에 다음 테스트를 먼저 작성한다 (모두 실패 상태).

**핵심 함수 `get_bonus_analysis` 단위 테스트:**

1. `test_bonus_frequency_all_45_keys` — `bonus_frequency`가 1~45 모든 키 포함, 미출현 번호는 0 (REQ-BON-U02)
2. `test_bonus_frequency_hand_counted` — 손계산 픽스처로 각 번호 빈도 정확 집계
3. `test_bonus_percentage_two_decimals` — `bonus_percentage = round(count/total*100, 2)` (REQ-BON-U03)
4. `test_bonus_percentage_all_45_keys` — 비율도 1~45 전체 키 포함
5. `test_top_bonus_top_10` — `top_bonus`가 빈도 내림차순 상위 10개 (REQ-BON-U04)
6. `test_top_bonus_tie_smaller_number_first` — 동률 시 작은 번호 우선
7. `test_top_bonus_item_keys` — 각 항목에 `number`, `count`, `percentage` 포함
8. `test_recent_bonus_window` — `recent_bonus`가 최근 N회차로 한정 (REQ-BON-U05)
9. `test_recent_bonus_recent_count` — `recent_count = min(recent_n, total_draws)`
10. `test_cooccurrence_top_5` — 각 보너스 번호별 동시출현 상위 5개 (REQ-BON-U06)
11. `test_cooccurrence_descending_tie_break` — 동시출현 내림차순, 동률 시 작은 번호 우선
12. `test_cooccurrence_uses_main_numbers_only` — 본번호(`numbers()`)만 집계, 보너스 제외 (REQ-BON-N02)
13. `test_result_keys_present` — 반환 dict에 필수 키 모두 존재 (REQ-BON-U01)
14. `test_deterministic` — 동일 입력 → 동일 결과 (REQ-BON-U08)
15. `test_hot_cold_normal_classification` — 평균(100/45) 기준 hot/cold/normal 판정 (REQ-BON-S03)
16. `test_disclaimer_present` — `disclaimer` 키 포함 (REQ-BON-N03)

**경계/빈 데이터 테스트:**

17. `test_empty_draws_returns_zeroed` — `draws=[]` → total 0, 전부 0/0.0, 빈 top/cooccurrence (REQ-BON-S01)
18. `test_none_draws_returns_zeroed` — `draws=None` → 동일하게 0 채움
19. `test_recent_n_larger_than_total` — `recent_n > total_draws` → 전체 사용, 에러 없음 (REQ-BON-S02)
20. `test_main_and_bonus_distributions_separate` — 본번호/보너스 빈도 분리 검증 (REQ-BON-N02)

**API 라우트 테스트 (`GET /api/stats/bonus`):**

21. `test_bonus_api_default_recent_n_50` — `recent_n` 미지정 시 기본 50 (REQ-BON-E02)
22. `test_bonus_api_returns_required_fields` — 응답에 필수 필드 포함, HTTP 200 (REQ-BON-E01)
23. `test_bonus_api_recent_n_query` — `?recent_n=100` 반영
24. `test_bonus_api_recent_n_too_small` — `recent_n=0` → HTTP 422 (REQ-BON-N01)
25. `test_bonus_api_recent_n_too_large` — `recent_n=501` → HTTP 422
26. `test_bonus_api_recent_n_boundaries` — `recent_n=1`, `recent_n=500` → HTTP 200

**웹 페이지 테스트 (`GET /stats/bonus`):**

27. `test_bonus_page_renders` — HTTP 200, HTML 응답, 번호별 테이블 포함 (REQ-BON-E03)
28. `test_bonus_page_recent_n_reflected` — `?recent_n=200` 시 최근 컬럼 반영 (REQ-BON-E04)
29. `test_bonus_page_server_rendered` — 핵심 테이블이 서버 렌더링(JS 비의존) (REQ-BON-N06)
30. `test_bonus_nav_tab_exists` — `base.html` 내비게이션에 "보너스 분석" 탭 존재

---

### Phase 2: 구현 (GREEN)

최소 코드로 모든 테스트를 통과시킨다.

**우선순위 High:**

1. `lotto/web/data.py` — `get_bonus_analysis(draws, recent_n=50) -> dict[str, Any]` 구현
   - 빈/None 데이터 가드 (1~45 키 0 채움)
   - `bonus_frequency` 집계 (`{n: 0 for n in range(1, 46)}` 초기화 후 `draw.bonus` 카운트)
   - `bonus_percentage` 계산 (`round(..., 2)`)
   - `top_bonus` 정렬 (`key=lambda kv: (-count, number)`, 상위 10)
   - `recent_bonus` 슬라이싱 (`sorted(draws, key=lambda d: d.draw_no)[-recent_n:]`)
   - `cooccurrence` (`collections.Counter`, 보너스별 본번호 상위 5)
   - hot/cold/normal 상태 판정 (방식 A: 전체 비율 vs 평균 100/45)
   - `disclaimer` 포함
   - Python 3.9 호환 타입 힌트, `match`/`case` 및 `zip(strict=True)` 미사용

2. `lotto/web/routes/api.py` — `GET /api/stats/bonus` 엔드포인트 추가
   - `recent_n: int = Query(default=50, ge=1, le=500)` (위반 시 자동 HTTP 422)
   - `get_draws()` → `get_bonus_analysis(draws, recent_n)` → JSON 반환

3. `lotto/web/routes/pages.py` — `GET /stats/bonus` 라우트 추가
   - `active_tab="bonus"`, 분석 결과를 템플릿 컨텍스트로 전달

**우선순위 Medium:**

4. `lotto/web/templates/bonus_analysis.html` — 신규 템플릿
   - 보너스 빈도 막대 표현 (top10 강조)
   - `recent_n` 선택기 (50/100/200 프리셋)
   - 번호별 테이블 (번호 | 총 횟수 | 비율 | 최근 횟수 | 상태)
   - 면책 고지 표시

5. `lotto/web/templates/base.html` — 내비게이션 수정
   - `desktop_nav_items`에 `('/stats/bonus', 'bonus', '보너스 분석')` 추가
   - `active_tab == 'bonus'` 헤딩 분기 추가

---

### Phase 3: 리팩토링 (REFACTOR)

- 동시출현/정렬 로직 헬퍼 분리 (가독성 향상, 필요 시)
- hot/cold/normal 판정을 작은 순수 함수로 추출
- 코드 중복 제거
- mypy 타입 검사 통과 확인 (`mypy.ini`에 `tests/test_bonus_analysis.py` override 등록)
- ruff 린트 통과 확인 (`# noqa` 최소화)
- 테스트 커버리지 확인

---

## 마일스톤

| 우선순위 | 작업 | 산출물 |
|----------|------|--------|
| High | RED: 30개 테스트 작성 | `tests/test_bonus_analysis.py` |
| High | GREEN: `get_bonus_analysis` 구현 | `lotto/web/data.py` |
| High | GREEN: API 엔드포인트 | `lotto/web/routes/api.py` |
| Medium | GREEN: 페이지 라우트 + 템플릿 | `pages.py`, `bonus_analysis.html` |
| Medium | GREEN: 내비게이션 탭 | `base.html` |
| Low | REFACTOR: 헬퍼 분리·품질 게이트 | 전체 |

---

## 기술적 접근

- 핵심 분석은 `lotto/web/data.py`의 순수 함수(`get_bonus_analysis`)에 집중하여 단위 테스트 용이성 확보.
- API/페이지 라우트는 얇은 어댑터로 유지 (`get_draws()` → 분석 함수 → 직렬화/렌더링).
- 동시출현은 `collections.Counter`로 O(회차 × 6) 집계, 정렬은 보너스 번호당 1회.
- 결정적 결과를 위해 난수/시간 의존 배제, 정렬 동률은 항상 (`-count`, `number`)로 안정화.

---

## 위험 요소 및 완화

| 위험 | 영향 | 완화 |
|------|------|------|
| `get_draws()` 정렬 순서 미보장 | 최근 추세 슬라이싱 오류 | `sorted(draws, key=lambda d: d.draw_no)[-recent_n:]`로 명시 정렬 |
| JSON dict 키 int/str 직렬화 불일치 | 테스트 단언 실패 | 기존 통계 SPEC 직렬화 관례에 맞춰 한쪽으로 일관 검증 |
| `numbers()`를 property로 오용 | `AttributeError`/잘못된 집계 | 항상 `draw.numbers()` 메서드 호출 |
| 전체 mypy 게이트 사전 부채 차단 | 커밋 실패 | `GIT_BIN` 우회 패턴 적용 (기존 관례) |
| Python 3.9 비호환 문법 | 런타임/CI 오류 | `if/elif/else`, `Optional[T]`, `# noqa: B905` 사용 |

---

## 품질 게이트

- `pytest tests/test_bonus_analysis.py` — 전체 통과
- `mypy lotto/web/data.py lotto/web/routes/api.py lotto/web/routes/pages.py` — 타입 오류 0건
- ruff 린트 통과
- Python 3.9 호환성 확인
- 면책 고지 API·UI 포함 확인
