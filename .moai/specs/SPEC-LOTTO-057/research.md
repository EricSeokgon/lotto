---
id: SPEC-LOTTO-057
version: 0.1.0
status: Planned
created: 2026-06-09
updated: 2026-06-09
author: ircp
---

# SPEC-LOTTO-057 연구 노트 (Arithmetic Complexity Analysis)

## 코드베이스 분석 (기존 패턴 확인)

분석 기능은 일관된 패턴을 따른다. SPEC-LOTTO-057도 동일 패턴으로 구현하며,
가장 가까운 선행 사례는 SPEC-LOTTO-056(간격 분석, get_gap_stats)이다.

### 데이터 계층 — `lotto/web/data.py`

- 분석 함수 명명: `get_<topic>_stats(...)` — 본 SPEC은 `get_ac_stats(draws)`
  - 참고: `get_last_digit_stats`, `get_gap_stats`(SPEC-056), `sum_range_analysis`
- 모듈 레벨 캐시 패턴 (data.py:67~92 확인):
  - `_gap_cache: dict[str, Any] = {}` (data.py:92) — SPEC-056이 도입한
    str-키 캐시. 본 SPEC의 `_ac_cache: dict[str, Any] = {}`는 동일 형태이며
    `str(len(draws))`를 키로 사용 (REQ-AC-016).
  - 그 외 `_last_digit_cache`, `_cooccurrence_cache`, `_rolling_cache`,
    `_backtest_cache` 존재 — 캐시 타입은 기능마다 상이.
- `invalidate_cache()` (data.py:95~112)에서 모든 캐시 무효화:
  - `global` 선언에 `# noqa: PLW0603 — 의도된 모듈 캐시 상태` 주석 관행
  - `_gap_cache.clear()`가 line 112에 등록된 것과 동일하게, 신규
    `_ac_cache.clear()` 라인을 invalidate_cache() 본문에 추가해야 함
  - 주의: `_gap_cache`/`_ac_cache`처럼 `.clear()`로 비우는 캐시는 global 재할당이
    아니므로 global 선언 목록에 넣을 필요 없음 (line 105 참고 — clear 대상은 미포함)

### API 계층 — `lotto/web/routes/api.py`

- 기존 라우트 prefix: `/stats/...`
  - `@router.get("/stats/sum-range")`, `@router.get("/stats/last-digit")`,
    `@router.get("/stats/gap")` (SPEC-056)
- 본 SPEC: `@router.get("/stats/ac")` → 항상 200, 데이터 부재도 정상 응답
- 반환은 `get_ac_stats(...)` 결과 dict를 그대로 JSON 직렬화

### 페이지 계층 — `lotto/web/routes/pages.py`

- 기존 페이지 라우트: `@router.get("/stats/last-digit")`,
  `@router.get("/stats/gap")` (SPEC-056)
- 반환 타입 `TemplateResponse`, async 핸들러 시그니처 `(request: Request)`
- 본 SPEC: `@router.get("/stats/ac")` → `ac.html` 렌더링

### 템플릿 — `lotto/web/templates/`

- 기존: `last_digit.html`, `gap.html`(SPEC-056), `sum_range.html`, `stats.html`
- 본 SPEC: `ac.html` 신규 — 요약 카드(평균 AC / 고AC 비율 / 저AC 비율) +
  AC값 분포 표(AC 값 0..10, 회차 수, 비율)
- 서버 렌더링 전용 (JavaScript 미사용)

### 테스트 — `tests/test_ac_analysis.py`

- 신규 테스트 파일 생성
- `mypy.ini` override 목록에 `test_ac_analysis` 등록 필수
  - 기존에 `test_gap_analysis`, `test_last_digit`, `test_sum_range` 등이
    동일 방식으로 등록되어 있음 (저장소 사전 mypy 부채 회피 목적)
- 데이터/API/페이지 계층별 테스트 분리 권장 (gap/sum-range SPEC 구조 참고)

## 알고리즘 검증 (픽스처 수계산)

본번호만 사용, 보너스 제외. 회차당 정렬 후 C(6,2)=15개 쌍 차이 → unique 개수 U
→ AC = U - 5.

| 회차 | 본번호 | unique diffs | U | AC |
|------|--------|--------------|---|----|
| D1 | [1,2,3,4,5,6] | {1,2,3,4,5} | 5 | 0 |
| D2 | [2,6,13,16,32,38] | 15개 모두 상이 | 15 | 10 |
| D3 | [1,2,3,4,5,10] | {1,2,3,4,5,6,7,8,9} | 9 | 4 |
| D4 | [3,12,21,33,40,45] | 13개 | 13 | 8 |

AC 모음: [0, 10, 4, 8]
- avg_ac = (0+10+4+8)/4 = 5.5
- ac_distribution = {0:1, 4:1, 8:1, 10:1}, 나머지 0..10 키는 0 (합 4 ✓)
- ac_distribution_pct = {0:25.0, 4:25.0, 8:25.0, 10:25.0}, 나머지 0.0
- most_common_ac = 0 (모두 1회 동률 → 더 작은 AC 우선)
- high_ac_count(AC>=7) = 2 (10, 8), high_ac_pct = 50.0
- low_ac_count(AC<=3) = 1 (0만; 4는 제외), low_ac_pct = 25.0

이 수치는 acceptance.md의 AC-02~AC-13에 그대로 반영됨. 경계값 0(D1)과 10(D2)을
모두 포함하여 AC 범위 양 끝단을 검증한다.

### D2 = [2,6,13,16,32,38] 전개 (AC=10 확인)

15개 차이: 4,11,14,30,36 / 7,10,26,32 / 3,19,25 / 16,22 / 6
정렬 unique = {3,4,6,7,10,11,14,16,19,22,25,26,30,32,36} → U=15 → AC=10.

## 구현 알고리즘 권장 (Python 3.9)

```
from itertools import combinations
def _draw_ac(main_numbers):  # main_numbers: 본번호 6개
    s = sorted(main_numbers)
    diffs = {s[j] - s[i] for i, j in combinations(range(len(s)), 2)}
    return len(diffs) - 5
```

- `itertools.combinations`는 i<j 쌍을 보장하여 REQ-AC-012(15개 쌍) 충족.
- set 컴프리헨션으로 unique 차이 산출 — 결정적, 부작용 없음.
- `zip(strict=...)` 불필요 (combinations 사용) → B905 경고 회피.

## Python 3.9 호환 주의사항 (auto-memory 반영)

- `match/case` 금지 — 분기는 if/elif 사용.
- `zip(strict=...)` 금지 — 본 SPEC은 combinations 기반이라 해당 없음.
- mypy 게이트: 신규 테스트는 mypy.ini override에 등록(저장소 사전 부채로
  전체 mypy 차단되므로 게이트 우회 패턴 참고).

## 위험 요소 및 완화

- 위험: 6개 미만 본번호 회차에서 combinations 결과 왜곡 → REQ-AC-015로 skip 처리.
- 위험: 빈 데이터 division-by-zero(avg_ac, *_pct) → REQ-AC-013 빈 구조 조기 반환.
- 위험: ac_distribution 키 누락(0..10 일부만 채움) → 0으로 초기화한 11개 키 딕셔너리를
  먼저 만든 뒤 카운트 누적하여 REQ-AC-004/005 보장.
- 위험: 기존 코어 모듈 침범 → REQ-AC-014로 data.py/web 레이어에 국한.

## 미해결 질문 (구현 시 결정)

- `ac_distribution` 키 타입: int(0..10)로 명시. JSON 직렬화 시 키가 문자열로
  변환될 수 있으므로(JSON object key는 string), API 테스트에서는 문자열/정수 키
  허용 여부를 명확히 할 것. 데이터 계층(get_ac_stats)은 int 키 dict를 반환하고,
  API 계층의 직렬화 변환은 FastAPI 기본 동작에 위임 (gap SPEC과 동일 처리).
- 반환 타입 표기: 기존 last_digit/gap과 일관되게 `dict[str, Any]` 사용 권장.
