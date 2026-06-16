---
id: SPEC-LOTTO-056
version: 0.1.0
status: Planned
created: 2026-06-09
updated: 2026-06-09
author: ircp
priority: medium
---

# SPEC-LOTTO-056 연구 노트 (Number Gap Pattern Analysis)

## 코드베이스 분석 (기존 패턴 확인)

분석 기능은 일관된 패턴을 따른다. SPEC-LOTTO-056도 동일 패턴으로 구현한다.

### 데이터 계층 — `lotto/web/data.py`

- 분석 함수 명명: `get_<topic>_stats(...)` 또는 `<topic>_analysis(...)`
  - 참고: `get_last_digit_stats` (data.py:3217), `sum_range_analysis` (data.py:2655),
    `evaluate_sum` (data.py:2749)
- 모듈 레벨 캐시 패턴 (data.py:67~87):
  - 예: `_last_digit_cache: dict[int, dict[str, Any]] | None = None`,
    `_cooccurrence_cache`, `_rolling_cache`, `_backtest_cache`
  - 본 SPEC: `_gap_cache: dict[str, GapStats]` (REQ-GAP-014)
- `invalidate_cache()` (data.py:90)에서 모든 캐시를 무효화:
  - `global` 선언에 `# noqa: PLW0603 — 의도된 모듈 캐시 상태` 주석 관행
  - 신규 캐시는 `invalidate_cache()` 본문에 초기화 라인 추가 필요
- `draws` 파라미터는 `list[DrawResult] | None = _UNSET` 센티넬 패턴 사용
  (sum_range_analysis 참고) — None 명시 시 get_draws 미호출, 기본값은 자동 로드

### API 계층 — `lotto/web/routes/api.py`

- 기존 라우트 prefix: `/stats/...`
  - `@router.get("/stats/sum-range")` (api.py:605)
  - `@router.get("/stats/last-digit")` (api.py:650)
  - `@router.get("/stats/sum-range/evaluate")` (api.py:664)
- 본 SPEC: `@router.get("/stats/gap")` → 항상 200, 데이터 부재도 정상 응답

### 페이지 계층 — `lotto/web/routes/pages.py`

- 기존 페이지 라우트:
  - `@router.get("/stats/last-digit")` (pages.py:682)
  - `@router.get("/stats/sum-range")` (pages.py:724)
- 반환 타입 `TemplateResponse`, async 핸들러 시그니처 `(request: Request)`
- 본 SPEC: `@router.get("/stats/gap")` → `gap.html` 렌더링

### 템플릿 — `lotto/web/templates/`

- 기존: `last_digit.html`, `sum_range.html`, `stats_range.html`, `stats.html`
- 본 SPEC: `gap.html` 신규 — 요약 카드 + 분포 표 + 최빈 간격 표 + 위치별 표
- 서버 렌더링 전용 (JavaScript 미사용)

### 테스트 — `tests/test_gap_analysis.py`

- 신규 테스트 파일 생성
- `mypy.ini` (line 31) override 목록에 `test_gap_analysis` 등록 필수
  - 기존에 `test_sum_range, test_api_sum_range, test_sum_range_page,
    test_last_digit` 등이 동일 방식으로 등록되어 있음
- 데이터/API/페이지 계층별 테스트 분리 권장 (sum-range SPEC 구조 참고)

## 알고리즘 검증 (픽스처 수계산)

본번호만 사용, 보너스 제외. 회차당 정렬 후 5개 간격.

| 회차 | 본번호 | 간격(gaps) | min | max |
|------|--------|-----------|-----|-----|
| D1 | [1,2,3,4,5,6] | [1,1,1,1,1] | 1 | 1 |
| D2 | [3,12,21,33,40,45] | [9,9,12,7,5] | 5 | 12 |
| D3 | [5,10,15,20,25,30] | [5,5,5,5,5] | 5 | 5 |
| D4 | [1,9,17,25,33,41] | [8,8,8,8,8] | 8 | 8 |

- 전체 간격 20개, 합계 111 → avg_gap = 5.55
- 크기 분포: small(1-5)=11, medium(6-10)=8, large(11+)=1 (합 20 ✓)
- 최빈 간격: gap5×6, gap1×5, gap8×5, gap9×2, gap7×1, gap12×1 (distinct 6개)
- avg_min_gap = (1+5+5+8)/4 = 4.75
- avg_max_gap = (1+12+5+8)/4 = 6.5
- position 1→2 평균 = (1+9+5+8)/4 = 5.75

이 수치는 acceptance.md의 AC-02~AC-09에 그대로 반영됨.

## Python 3.9 호환 주의사항 (auto-memory 반영)

- `match/case` 금지, `zip(strict=...)` 금지 — 인접 쌍 산출 시
  `zip(sorted_nums, sorted_nums[1:])` 사용하되 필요 시 `# noqa: B905`
- mypy 게이트: 신규 테스트는 mypy.ini override에 등록(저장소 사전 부채로
  전체 mypy 차단되므로 게이트 우회 패턴 참고)

## 위험 요소 및 완화

- 위험: 6개 미만 본번호 회차에서 IndexError → REQ-GAP-013으로 skip 처리
- 위험: 빈 데이터 division-by-zero → REQ-GAP-011 빈 구조 조기 반환
- 위험: 기존 코어 모듈 침범 → REQ-GAP-012로 data.py/web 레이어에 국한

## 미해결 질문 (구현 시 결정)

- `GapStats` 타입을 TypedDict로 둘지 dict[str, Any]로 둘지 — 기존 last_digit은
  `dict[str, Any]` 사용. 일관성 위해 `dict[str, Any]` 권장하되 캐시 타입
  `dict[str, GapStats]`의 `GapStats`는 `dict[str, Any]` 별칭으로 정의 가능.
