---
id: SPEC-LOTTO-058
version: 0.1.0
status: Planned
created: 2026-06-09
updated: 2026-06-09
author: ircp
---

# SPEC-LOTTO-058 연구 노트 (Prime/Composite Number Distribution Analysis)

## 코드베이스 분석 (기존 패턴 확인)

분석 기능은 일관된 패턴을 따른다. SPEC-LOTTO-058도 동일 패턴으로 구현하며,
가장 가까운 선행 사례는 SPEC-LOTTO-056(간격 분석, get_gap_stats)과
SPEC-LOTTO-057(AC 분석, get_ac_stats)이다.

### 데이터 계층 — `lotto/web/data.py`

- 분석 함수 명명: `get_<topic>_stats(...)` — 본 SPEC은 `get_prime_stats(draws)`
  - 참고: `get_last_digit_stats`, `get_gap_stats`(SPEC-056),
    `get_ac_stats`(SPEC-057), `sum_range_analysis`
- 모듈 레벨 캐시 패턴 (data.py:92~98 확인):
  - `_gap_cache: dict[str, Any] = {}` (data.py:93), `_ac_cache: dict[str, Any]
    = {}` (data.py:98) — str-키 캐시. 본 SPEC의 `_prime_cache: dict[str, Any]
    = {}`는 동일 형태이며 `str(len(draws))`를 키로 사용 (REQ-PR-016).
  - 그 외 `_last_digit_cache`, `_cooccurrence_cache`, `_rolling_cache`,
    `_backtest_cache` 존재 — 캐시 타입은 기능마다 상이.
- `invalidate_cache()` (data.py:101~120)에서 모든 캐시 무효화:
  - `_gap_cache.clear()`(line 119), `_ac_cache.clear()`(line 120)가 등록된 것과
    동일하게, 신규 `_prime_cache.clear()` 라인을 invalidate_cache() 본문에
    추가해야 함.
  - 주의: `.clear()`로 비우는 dict 캐시는 global 재할당이 아니므로 line 112의
    global 선언 목록에 넣을 필요 없음 (`_gap_cache`/`_ac_cache`와 동일).

### API 계층 — `lotto/web/routes/api.py`

- 기존 라우트 prefix: `/stats/...`
  - `@router.get("/stats/sum-range")`, `@router.get("/stats/last-digit")`,
    `@router.get("/stats/gap")`(SPEC-056), `@router.get("/stats/ac")`(SPEC-057)
- 본 SPEC: `@router.get("/stats/prime")` → 항상 200, 데이터 부재도 정상 응답
- 반환은 `get_prime_stats(...)` 결과 dict를 그대로 JSON 직렬화

### 페이지 계층 — `lotto/web/routes/pages.py`

- 기존 페이지 라우트: `@router.get("/stats/last-digit")`,
  `@router.get("/stats/gap")`(SPEC-056), `@router.get("/stats/ac")`(SPEC-057)
- 반환 타입 `TemplateResponse`, async 핸들러 시그니처 `(request: Request)`
- 본 SPEC: `@router.get("/stats/prime")` → `prime.html` 렌더링

### 템플릿 — `lotto/web/templates/`

- 기존: `last_digit.html`, `gap.html`(SPEC-056), `ac.html`(SPEC-057),
  `sum_range.html`, `stats.html`
- 본 SPEC: `prime.html` 신규 — 요약 카드(평균 소수 개수 / 평균 합성수 개수 /
  1 등장 비율) + 소수 개수 분포 표(0..6, 회차 수, 비율) + 합성수 개수 분포 표
  (0..6, 회차 수, 비율)
- 서버 렌더링 전용 (JavaScript 미사용)

### 테스트 — `tests/test_prime_analysis.py`

- 신규 테스트 파일 생성
- `mypy.ini` override 목록에 `test_prime_analysis` 등록 필수
  - 기존에 `test_gap_analysis`, `test_ac_analysis`, `test_last_digit`,
    `test_sum_range` 등이 동일 방식으로 등록되어 있음 (저장소 사전 mypy 부채
    회피 목적)
- 데이터/API/페이지 계층별 테스트 분리 권장 (gap/ac SPEC 구조 참고)

## 소수/합성수 분류표 (1~45)

본번호는 1~45 범위에 한정되므로, 일반 소수 판정 알고리즘 대신 사전 정의된
상수 집합(frozenset)으로 분류하는 것이 단순·결정적·빠르다.

- 소수(14개): {2,3,5,7,11,13,17,19,23,29,31,37,41,43}
- 1: neither (one)
- 합성수(30개): 나머지 1 초과 정수 = {1..45} - {1} - 소수집합
  = {4,6,8,9,10,12,14,15,16,18,20,21,22,24,25,26,27,28,30,32,
     33,34,35,36,38,39,40,42,44,45}

검증: 14(소수) + 30(합성수) + 1(숫자 1) = 45 ✓

## 알고리즘 검증 (픽스처 수계산)

본번호만 사용, 보너스 제외. 회차당 6개 번호를 prime/composite/one으로 분류한다.

| 회차 | 본번호 | prime | comp | one | 합 |
|------|--------|-------|------|-----|----|
| D1 | [2,3,5,7,11,13] | 6 | 0 | 0 | 6 |
| D2 | [1,4,6,8,9,10]  | 0 | 5 | 1 | 6 |
| D3 | [1,2,4,6,8,9]   | 1 | 4 | 1 | 6 |
| D4 | [4,6,8,9,10,12] | 0 | 6 | 0 | 6 |

prime_count 모음: [6, 0, 1, 0]
composite_count 모음: [0, 5, 4, 6]
one_count 모음: [0, 1, 1, 0]

- avg_prime = (6+0+1+0)/4 = 1.75
- avg_composite = (0+5+4+6)/4 = 3.75
- prime_distribution = {0:2, 1:1, 6:1}, 나머지 0..6 키는 0 (합 4 ✓)
- prime_distribution_pct = {0:50.0, 1:25.0, 6:25.0}, 나머지 0.0
- most_common_prime_count = 0 (2회로 최다)
- composite_distribution = {0:1, 4:1, 5:1, 6:1}, 나머지 0..6 키는 0 (합 4 ✓)
- one_appeared_count = 2 (D2, D3), one_appeared_pct = 50.0

이 수치는 acceptance.md의 PR-05~PR-14에 그대로 반영됨. prime_count 경계값
0(D2/D4)과 6(D1), composite_count 경계값 0(D1)과 6(D4)을 모두 포함하여
분포 범위 양 끝단을 검증한다.

## 구현 알고리즘 권장 (Python 3.9)

```
from typing import Any, Iterable

_PRIMES_1_45 = frozenset(
    {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43}
)


def _classify_draw(main_numbers: Iterable[int]) -> tuple[int, int, int]:
    prime = composite = one = 0
    for n in main_numbers:
        if n == 1:
            one += 1
        elif n in _PRIMES_1_45:
            prime += 1
        else:
            composite += 1
    return prime, composite, one
```

- frozenset 멤버십 조회는 O(1), 결정적, 부작용 없음.
- 1을 먼저 분기하므로 one은 0 또는 1 (본번호 중복 없음 가정, REQ-PR-012).
- `zip(strict=...)` 불필요 → B905 경고 회피.
- `match/case` 미사용 → if/elif 분기로 Python 3.9 호환.

분포 딕셔너리는 0..6 키를 0으로 초기화한 뒤 카운트를 누적한다:

```
prime_dist = {k: 0 for k in range(7)}
# 회차 루프에서 prime_dist[prime_count] += 1
```

## Python 3.9 호환 주의사항 (auto-memory 반영)

- `match/case` 금지 — 분기는 if/elif 사용.
- `zip(strict=...)` 금지 — 본 SPEC은 사용처 없음.
- mypy 게이트: 신규 테스트는 mypy.ini override에 등록(저장소 사전 부채로
  전체 mypy 차단되므로 게이트 우회 패턴 참고).

## 위험 요소 및 완화

- 위험: 6개 미만 본번호 회차에서 합(prime+comp+one) != 6 → REQ-PR-015로 skip 처리.
- 위험: 빈 데이터 division-by-zero(avg_prime, avg_composite, *_pct) →
  REQ-PR-013 빈 구조 조기 반환.
- 위험: 분포 키 누락(0..6 일부만 채움) → 0으로 초기화한 7개 키 딕셔너리를
  먼저 만든 뒤 카운트 누적하여 REQ-PR-004/005/007 보장.
- 위험: 숫자 1을 합성수로 오분류 → 1을 명시적으로 우선 분기하여 neither(one)로
  처리, REQ-PR-002로 보장.
- 위험: 기존 코어 모듈 침범 → REQ-PR-014로 data.py/web 레이어에 국한.

## 미해결 질문 (구현 시 결정)

- `prime_distribution`/`composite_distribution` 키 타입: int(0..6)로 명시.
  JSON 직렬화 시 키가 문자열로 변환될 수 있으므로(JSON object key는 string),
  API 테스트에서는 문자열/정수 키 허용 여부를 명확히 할 것. 데이터 계층
  (get_prime_stats)은 int 키 dict를 반환하고, API 계층의 직렬화 변환은 FastAPI
  기본 동작에 위임 (gap/ac SPEC과 동일 처리).
- 반환 타입 표기: 기존 last_digit/gap/ac와 일관되게 `dict[str, Any]` 사용 권장.
- 소수 집합 표현: 매 호출 재생성을 피하기 위해 모듈 레벨 frozenset 상수로 1회
  정의 (위 _PRIMES_1_45 참고).
