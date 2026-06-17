---
id: SPEC-LOTTO-060
version: 0.1.0
status: Planned
created: 2026-06-10
updated: 2026-06-10
author: ircp
---

# SPEC-LOTTO-060 연구 노트 (Odd/Even Ratio Analysis)

## 코드베이스 분석 (기존 패턴 확인)

분석 기능은 일관된 패턴을 따른다. SPEC-LOTTO-060도 동일 패턴으로 구현하며,
가장 가까운 선행 사례는 SPEC-LOTTO-058(소수/합성수, get_prime_stats)과
SPEC-LOTTO-059(십의 자리 구간, get_decade_stats)이다.

### 데이터 계층 — `lotto/web/data.py`

- 분석 함수 명명: `get_<topic>_stats(...)` — 본 SPEC은 `get_odd_even_stats(draws)`
  - 참고: `get_last_digit_stats`, `get_gap_stats`(SPEC-056),
    `get_ac_stats`(SPEC-057), `get_prime_stats`(SPEC-058),
    `get_decade_stats`(SPEC-059)
- 모듈 레벨 캐시 패턴 (data.py 확인):
  - `_gap_cache`(line 93), `_ac_cache`(line 98), `_prime_cache`(line 103),
    `_decade_cache`(line 108) — 모두 `dict[str, Any] = {}` str-키 캐시.
    본 SPEC의 `_odd_even_cache: dict[str, Any] = {}`도 동일 형태이며
    `str(len(draws))`를 키로 사용 (REQ-OE-016).
  - `_decade_cache` 다음 줄에 `_odd_even_cache`를 추가하는 것이 가장 자연스럽다.
- `invalidate_cache()` (data.py:111~134)에서 모든 캐시 무효화:
  - line 131~134에 `_gap_cache.clear()`, `_ac_cache.clear()`,
    `_prime_cache.clear()`, `_decade_cache.clear()`가 순차 등록되어 있다.
    신규 `_odd_even_cache.clear()` 라인을 invalidate_cache() 본문 끝(line 134
    다음)에 추가해야 함.
  - 주의: `.clear()`로 비우는 dict 캐시는 global 재할당이 아니므로
    invalidate_cache() 상단의 global 선언 목록(line 112 부근)에 넣을 필요 없음
    (`_decade_cache`/`_prime_cache`와 동일).

### API 계층 — `lotto/web/routes/api.py`

- 기존 라우트 prefix: `/stats/...`
  - `@router.get("/stats/prime")`(line 689), `@router.get("/stats/decade")`
    (line 702)
- 본 SPEC: `@router.get("/stats/odd-even")` → 항상 200, 데이터 부재도 정상 응답
- 반환은 `get_odd_even_stats(...)` 결과 dict를 그대로 JSON 직렬화

### 페이지 계층 — `lotto/web/routes/pages.py`

- 기존 페이지 라우트: `@router.get("/stats/prime")`(line 737),
  `@router.get("/stats/decade")`(line 754)
- 반환 타입 `TemplateResponse`, async 핸들러 시그니처 `(request: Request)`
- 본 SPEC: `@router.get("/stats/odd-even")` → `odd_even.html` 렌더링

### 템플릿 — `lotto/web/templates/`

- 기존: `prime.html`(SPEC-058), `decade.html`(SPEC-059), `gap.html`,
  `ac.html`, `last_digit.html`, `sum_range.html`, `stats.html`
- 본 SPEC: `odd_even.html` 신규 — 요약 카드(평균 홀수 개수 / 평균 짝수 개수 /
  균형 회차 비율) + 홀수 개수 분포 표(0..6, 회차 수, 비율) + 균형(3:3) 회차
  강조 표시
- 서버 렌더링 전용 (JavaScript 미사용)

### 네비게이션 — `lotto/web/templates/base.html`

- 네비게이션 항목은 **두 곳**에 정의되어 있다:
  - desktop_nav_items (line 74)
  - nav_items (line 125, 모바일/기본)
- 두 리스트 모두 `('/stats/decade', 'decade', '구간 분포')` 다음에
  `('/stats/odd-even', 'odd_even', '홀짝 분석')` 튜플을 추가해야 함
  (REQ-OE-010 / 비기능 요구사항). 한 곳만 수정하면 한쪽 레이아웃에서 링크가
  누락된다.

### 테스트 — `tests/test_odd_even_analysis.py`

- 신규 테스트 파일 생성 (최소 20개)
- `mypy.ini` override 목록에 `test_odd_even_analysis` 등록 필수
  - 기존에 `test_prime_analysis`, `test_decade_analysis`, `test_gap_analysis`,
    `test_ac_analysis` 등이 동일 방식으로 등록되어 있음 (저장소 사전 mypy 부채
    회피 목적)
- 데이터/API/페이지 계층별 테스트 분리 권장 (prime/decade SPEC 구조 참고)

## 홀짝 분류표 (1~45)

본번호는 1~45 범위에 한정되므로 단순 패리티 판정(`n % 2`)으로 충분하다.

- 홀수(23개): {1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33,35,37,39,41,43,45}
- 짝수(22개): {2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,44}

검증: 23(홀) + 22(짝) = 45 ✓

소수/합성수와 달리 사전 정의 집합 불필요 — `n % 2 == 1`로 홀수 판정이 결정적이고
빠르다. 단, even_count는 독립 분류 대신 `6 - odd_count`로 유도하여 합 불변식
(odd + even == 6)을 보장한다 (REQ-OE-012).

## 알고리즘 검증 (픽스처 수계산)

본번호만 사용, 보너스 제외. 회차당 6개 번호를 홀/짝으로 분류한다.

| 회차 | 본번호 | odd | even | 균형(3:3)? |
|------|--------|-----|------|-----------|
| D1 | [1,3,5,7,9,11] | 6 | 0 | 아니오 |
| D2 | [2,4,6,8,10,12] | 0 | 6 | 아니오 |
| D3 | [1,2,3,4,5,6]   | 3 | 3 | 예 |
| D4 | [1,3,5,2,4,7]   | 4 | 2 | 아니오 |

odd_count 모음: [6, 0, 3, 4]
even_count 모음: [0, 6, 3, 2]

- avg_odd = (6+0+3+4)/4 = 3.25
- avg_even = (0+6+3+2)/4 = 2.75
- odd_distribution = {0:1, 3:1, 4:1, 6:1}, 나머지 0..6 키(1,2,5)는 0 (합 4 ✓)
- even_distribution = {0:1, 2:1, 3:1, 6:1}, 나머지 0..6 키(1,4,5)는 0 (합 4 ✓)
- odd_distribution_pct = {0:25.0, 3:25.0, 4:25.0, 6:25.0}, 나머지 0.0
- even_distribution_pct = {0:25.0, 2:25.0, 3:25.0, 6:25.0}, 나머지 0.0
- most_common_odd_count = 0 (0,3,4,6이 각 1회 동률 → 가장 작은 값 0)
- most_common_even_count = 0 (0,2,3,6이 각 1회 동률 → 가장 작은 값 0)
- balanced_count = 1 (D3만 3:3), balanced_pct = 25.0

이 수치는 acceptance.md의 OE-04~OE-15에 그대로 반영됨. odd_count 경계값
0(D2)과 6(D1)을 모두 포함하여 분포 범위 양 끝단을 검증하며, 균형 회차(D3)와
비균형 회차(D1/D2/D4)를 함께 커버한다. 동률 최빈값 처리(가장 작은 값 우선)도
픽스처가 동률 상황을 만들어 명시적으로 검증한다.

## 구현 알고리즘 권장 (Python 3.9)

```
from typing import Any, Iterable


def _count_odd(main_numbers: Iterable[int]) -> int:
    return sum(1 for n in main_numbers if n % 2 == 1)
```

- `n % 2 == 1` 판정은 O(1), 결정적, 부작용 없음.
- even_count = 6 - odd_count로 유도 (REQ-OE-012).
- `zip(strict=...)` 불필요 → B905 경고 회피.
- `match/case` 미사용 → Python 3.9 호환.

분포 딕셔너리는 0..6 키를 0으로 초기화한 뒤 카운트를 누적한다:

```
odd_dist = {k: 0 for k in range(7)}
even_dist = {k: 0 for k in range(7)}
# 회차 루프에서 odd_dist[odd_count] += 1; even_dist[even_count] += 1
```

최빈값(동률 시 작은 값 우선)은 키 오름차순으로 순회하며 max를 갱신:

```
most_common_odd = max(range(7), key=lambda k: (odd_dist[k], -k))
# 또는 키 0..6 오름차순 순회로 첫 최댓값 채택 — 동률 시 작은 값 우선 보장
```

주의: `max(..., key=lambda k: odd_dist[k])`는 동률 시 첫 항목(가장 작은 키)을
반환하므로 range(7) 오름차순 순회와 결합하면 REQ-OE-007의 "작은 값 우선"을
충족한다.

## Python 3.9 호환 주의사항 (auto-memory 반영)

- `match/case` 금지 — 분기는 if/else 사용.
- `zip(strict=...)` 금지 — 본 SPEC은 사용처 없음.
- mypy 게이트: 신규 테스트는 mypy.ini override에 등록(저장소 사전 부채로
  전체 mypy 차단되므로 게이트 우회 패턴 참고).

## 위험 요소 및 완화

- 위험: 6개 미만 본번호 회차에서 합(odd+even) != 6 → REQ-OE-015로 skip 처리.
- 위험: 빈 데이터 division-by-zero(avg_odd, avg_even, *_pct, balanced_pct) →
  REQ-OE-013 빈 구조 조기 반환.
- 위험: 분포 키 누락(0..6 일부만 채움) → 0으로 초기화한 7개 키 딕셔너리를
  먼저 만든 뒤 카운트 누적하여 REQ-OE-004/005/006 보장.
- 위험: 동률 최빈값을 큰 값으로 잘못 채택 → range(7) 오름차순 순회로
  REQ-OE-007의 "작은 값 우선" 보장.
- 위험: base.html 네비게이션 한 곳만 수정 → 두 리스트(desktop_nav_items,
  nav_items) 모두 갱신 필요.
- 위험: 기존 코어 모듈 침범 → REQ-OE-014로 data.py/web 레이어에 국한.

## 미해결 질문 (구현 시 결정)

- `odd_distribution`/`even_distribution` 키 타입: int(0..6)로 명시.
  JSON 직렬화 시 키가 문자열로 변환될 수 있으므로(JSON object key는 string),
  API 테스트에서는 문자열/정수 키 허용 여부를 명확히 할 것. 데이터 계층
  (get_odd_even_stats)은 int 키 dict를 반환하고, API 계층의 직렬화 변환은
  FastAPI 기본 동작에 위임 (prime/decade SPEC과 동일 처리).
- 반환 타입 표기: 기존 prime/decade와 일관되게 `dict[str, Any]` 사용 권장.
- 균형 정의: "홀==짝"은 6개 본번호 기준 정확히 3:3을 의미. odd_count == 3 으로
  판정하면 충분(even_count == 3과 동치).
